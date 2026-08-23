"""Biol.Studio GUI — 专业的 BBB (BiuBiuBiu) IDE（PyQt6）。

复用功能层：lexer（高亮）、checker（诊断）、project/templates（项目）、
runner（运行/构建）、gallery（示例画廊）。

布局：
  ┌────────────────────────────────────────────────────┐
  │ 菜单栏 / 工具栏（新建/打开/检查/运行/构建）          │
  ├──────────┬─────────────────────────────┬───────────┤
  │ 项目树    │  标签页编辑器（语法高亮）    │ 示例画廊   │
  │ (文件/模板)│                             │           │
  ├──────────┴─────────────────────────────┴───────────┤
  │ 诊断面板（错误/警告，点击跳转）                      │
  │ 输出面板（运行/构建输出）                            │
  ├────────────────────────────────────────────────────┤
  │ 状态栏（项目/bbb 路径/行:列）                        │
  └────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import sys
import subprocess

from PyQt6.QtCore import Qt, QProcess, QRect, QSize
from PyQt6.QtGui import (QAction, QColor, QFont, QFontMetrics, QPainter,
                         QSyntaxHighlighter, QTextCharFormat, QIcon, QKeySequence)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QTabWidget,
                             QPlainTextEdit, QListWidget, QListWidgetItem,
                             QTextEdit, QVBoxLayout, QHBoxLayout, QLabel,
                             QToolBar, QFileDialog, QDialog, QLineEdit,
                             QComboBox, QDialogButtonBox, QMessageBox,
                             QStatusBar, QTextBrowser, QMenu)

from . import lexer, checker, templates, gallery
from .project import load_project, parse_toml
from .runner import find_bio

APP_NAME = "Biol.Studio — BBB IDE"
APP_VERSION = "0.2.0"


# ───────────────────────── 语法高亮 ─────────────────────────

class BioHighlighter(QSyntaxHighlighter):
    """用功能层词法器做 token 上色（注释用正则补充——词法器跳过注释）。"""

    def __init__(self, doc):
        super().__init__(doc)
        self.formats = {
            'keyword': self._fmt(QColor(86, 156, 214), bold=True),
            'string': self._fmt(QColor(206, 145, 120)),
            'char': self._fmt(QColor(206, 145, 120)),
            'number': self._fmt(QColor(181, 206, 168)),
            'comment': self._fmt(QColor(106, 153, 85), italic=True),
            'call': self._fmt(QColor(220, 220, 170)),
        }

    @staticmethod
    def _fmt(color, bold=False, italic=False):
        f = QTextCharFormat()
        f.setForeground(color)
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        if italic:
            f.setFontItalic(True)
        return f

    def highlightBlock(self, text):
        # 仅当前行做词法分析（单行 token 的 col 即行内列）
        toks = []
        try:
            toks = lexer.tokenize(text)
        except lexer.LexError:
            pass
        for t in toks:
            if t.kind in self.formats:
                self.setFormat(t.col - 1, len(t.value), self.formats[t.kind])
        # 注释（词法器跳过注释，正则补充）
        i = 0
        while i < len(text):
            if text.startswith('//', i):
                self.setFormat(i, len(text) - i, self.formats['comment'])
                break
            if text.startswith('/*', i):
                end = text.find('*/', i + 2)
                if end == -1:
                    self.setFormat(i, len(text) - i, self.formats['comment'])
                    break
                self.setFormat(i, end + 2 - i, self.formats['comment'])
                i = end + 2
                continue
            i += 1


# ───────────────────────── 编辑器 + 行号 ─────────────────────────

class CodeEditor(QPlainTextEdit):
    """带行号的代码编辑器。"""

    def __init__(self, path=None, parent=None):
        super().__init__(parent)
        self.path = path
        self._hl = BioHighlighter(self.document())
        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_area_width()
        self._highlight_current_line()
        font = QFont("JetBrains Mono, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setTabStopDistance(4 * QFontMetrics(font).horizontalAdvance(' '))

    def line_number_area_width(self):
        digits = max(2, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(),
                                          self.line_number_area_width(), cr.height()))

    def _highlight_current_line(self):
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(30, 30, 30))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    def paint_line_numbers(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(28, 28, 28))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(120, 120, 120))
                painter.drawText(0, top, self._line_area.width() - 6,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight,
                                 str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


# PyQt6 导入别名（简化）
from PyQt6.QtGui import QTextFormat
QTextFormat_Property = QTextFormat.Property.FullWidthSelection


# ───────────────────────── 主窗口 ─────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.project_root = None
        self._proc = None

        self._build_actions()
        self._build_ui()
        self._load_gallery()
        self.statusBar().showMessage(f"bbb: {find_bio() or '未找到'}")
        self._load_templates()

    # ---- UI 构建 ----

    def _build_actions(self):
        act_new = QAction("新建项目…", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self._dialog_new_project)
        act_open = QAction("打开项目…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._dialog_open_project)
        act_check = QAction("检查", self)
        act_check.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_check.triggered.connect(self.run_check)
        act_run = QAction("运行", self)
        act_run.setShortcut(QKeySequence("F5"))
        act_run.triggered.connect(self.run_project)
        act_build = QAction("构建", self)
        act_build.setShortcut(QKeySequence("F7"))
        act_build.triggered.connect(self.build_project)
        act_save = QAction("保存", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.save_current)
        self._actions = dict(new=act_new, open=act_open, check=act_check,
                             run=act_run, build=act_build, save=act_save)

        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        for a in (act_new, act_open, act_save, act_check, act_run, act_build):
            tb.addAction(a)
        self.addToolBar(tb)

    def _build_ui(self):
        split_main = QSplitter(Qt.Orientation.Horizontal)

        # 左：项目树 + 模板
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("项目")
        self.tree.itemDoubleClicked.connect(self._tree_open)
        self.tpl_list = QListWidget()
        self.tpl_list.setMaximumHeight(120)
        self.tpl_list.itemDoubleClicked.connect(lambda it: self._new_from_template(it.text()))
        left_lay.addWidget(QLabel("项目文件"))
        left_lay.addWidget(self.tree)
        left_lay.addWidget(QLabel("模板（双击创建）"))
        left_lay.addWidget(self.tpl_list)
        split_main.addWidget(left)

        # 中：编辑器标签页
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.tabs.removeTab)
        split_main.addWidget(self.tabs)

        # 右：示例画廊
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        self.demo_list = QListWidget()
        self.demo_list.itemDoubleClicked.connect(self._run_demo)
        right_lay.addWidget(QLabel("示例画廊（双击运行）"))
        right_lay.addWidget(self.demo_list)
        right.setMaximumWidth(280)
        split_main.addWidget(right)
        split_main.setSizes([220, 800, 260])
        self.setCentralWidget(split_main)

        # 底部：诊断 + 输出
        bottom = QSplitter(Qt.Orientation.Vertical)
        self.diag = QListWidget()
        self.diag.itemClicked.connect(self._diag_jump)
        self.out = QTextBrowser()
        self.out.setOpenExternalLinks(False)
        bottom.addWidget(self.diag)
        bottom.addWidget(self.out)
        bottom.setSizes([140, 200])
        split_main.addWidget(bottom)
        split_main.setStretchFactor(2, 1)

        # 状态栏
        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

    def _load_templates(self):
        self.tpl_list.clear()
        for t in templates.list_templates():
            self.tpl_list.addItem(t.name)

    def _load_gallery(self):
        self.demo_list.clear()
        for d in gallery.list_demos():
            self.demo_list.addItem(f"{d.index:02d}  {d.title}")

    # ---- 项目操作 ----

    def _dialog_new_project(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("新建 BBB 项目")
        lay = QVBoxLayout(dlg)
        name_ed = QLineEdit("myapp")
        tpl_cb = QComboBox()
        for t in templates.list_templates():
            tpl_cb.addItem(t.name, t.description)
        dir_ed = QLineEdit(os.path.expanduser("~/Projects"))
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(dlg.accept)
        btn.rejected.connect(dlg.reject)
        lay.addWidget(QLabel("项目名"))
        lay.addWidget(name_ed)
        lay.addWidget(QLabel("模板"))
        lay.addWidget(tpl_cb)
        lay.addWidget(QLabel("创建目录"))
        lay.addWidget(dir_ed)
        lay.addWidget(btn)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = name_ed.text().strip()
        tpl = tpl_cb.currentText()
        base = os.path.expanduser(dir_ed.text().strip())
        try:
            created = templates.scaffold(name, templates.find_template(tpl), base)
        except FileExistsError as e:
            QMessageBox.warning(self, "创建失败", str(e))
            return
        self._open_project(os.path.join(base, name))
        self._append_out(f"已创建项目 {name}（模板 {tpl}）\n" + "\n".join(f"  {c}" for c in created) + "\n")

    def _dialog_open_project(self):
        d = QFileDialog.getExistingDirectory(self, "打开 BBB 项目")
        if d:
            self._open_project(d)

    def _open_project(self, root):
        self.project_root = root
        proj = load_project(root)
        self.setWindowTitle(f"{APP_NAME} — {proj.name or root}")
        self.tree.clear()
        root_item = QTreeWidgetItem([proj.name or os.path.basename(root)])
        for base in ("package.toml", "src", "utils"):
            p = os.path.join(root, base)
            if os.path.isfile(p):
                root_item.addChild(QTreeWidgetItem([base]))
            elif os.path.isdir(p):
                dir_item = QTreeWidgetItem([base])
                for fn in sorted(os.listdir(p)):
                    if fn.endswith((".bio", ".bl")):
                        dir_item.addChild(QTreeWidgetItem([fn]))
                root_item.addChild(dir_item)
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self.status_label.setText(f"项目: {proj.name} v{proj.version or '?'}")
        # 打开 main
        if proj.main_file and os.path.isfile(proj.main_file):
            self._open_file(proj.main_file)

    def _tree_open(self, item, _col):
        path = self._tree_path(item)
        if path and os.path.isfile(path):
            self._open_file(path)

    def _tree_path(self, item):
        if not self.project_root:
            return None
        parts = []
        while item is not None:
            parts.append(item.text(0))
            item = item.parent()
        rel = os.path.join(*reversed(parts))
        return os.path.join(self.project_root, rel)

    def _open_file(self, path):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).path == path:
                self.tabs.setCurrentIndex(i)
                return
        ed = CodeEditor(path)
        try:
            ed.setPlainText(open(path, encoding="utf-8").read())
        except OSError as e:
            QMessageBox.warning(self, "打开失败", str(e))
            return
        ed.modificationChanged.connect(self._tab_modified)
        self.tabs.addTab(ed, os.path.basename(path))
        self.tabs.setCurrentWidget(ed)

    def _tab_modified(self, _v):
        i = self.tabs.indexOf(self.sender())
        if i >= 0:
            self.tabs.setTabText(i, os.path.basename(self.tabs.widget(i).path or "") + " •")

    def save_current(self):
        ed = self.tabs.currentWidget()
        if isinstance(ed, CodeEditor) and ed.path:
            try:
                open(ed.path, "w", encoding="utf-8").write(ed.toPlainText())
                ed.document().setModified(False)
                self.statusBar().showMessage(f"已保存 {ed.path}", 3000)
            except OSError as e:
                QMessageBox.warning(self, "保存失败", str(e))

    # ---- 检查 / 运行 / 构建 ----

    def run_check(self):
        self.diag.clear()
        if not self.project_root:
            QMessageBox.information(self, "检查", "请先打开/新建项目")
            return
        self.save_all()
        diags = checker.check_project(self.project_root)
        for d in diags:
            icon = "❌" if d.severity == "error" else "⚠️"
            it = QListWidgetItem(f"{icon} {d.file.replace(self.project_root + os.sep, '')}:{d.line}:{d.col}  {d.message}")
            it.setData(Qt.ItemDataRole.UserRole, d)
            self.diag.addItem(it)
        errs = sum(1 for d in diags if d.severity == "error")
        self.statusBar().showMessage(f"检查完成：{errs} 错误 / {len(diags) - errs} 警告", 5000)

    def _diag_jump(self, item):
        d = item.data(Qt.ItemDataRole.UserRole)
        if d and os.path.isfile(d.file):
            self._open_file(d.file)
            ed = self.tabs.currentWidget()
            if isinstance(ed, CodeEditor):
                cur = ed.textCursor()
                cur.setPosition(ed.document().findBlockByNumber(d.line - 1).position())
                ed.setTextCursor(cur)
                ed.setFocus()

    def save_all(self):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if isinstance(ed, CodeEditor) and ed.path and ed.document().isModified():
                open(ed.path, "w", encoding="utf-8").write(ed.toPlainText())
                ed.document().setModified(False)

    def run_project(self):
        self._launch(["run", self.project_root or "."])

    def build_project(self):
        self._launch(["build", self.project_root or "."])

    def _launch(self, args):
        bio = find_bio()
        if not bio:
            QMessageBox.warning(self, "运行", "找不到 bbb/bio 二进制")
            return
        self.save_all()
        self.out.clear()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(
            lambda: self._append_out(self._proc.readAllStandardOutput().data().decode(errors="replace")))
        self._proc.finished.connect(lambda code, _st: self._append_out(f"\n[退出码 {code}]\n"))
        self._proc.start(bio, args)
        self._append_out(f"$ {bio} {' '.join(args)}\n")

    def _append_out(self, text):
        self.out.append(text if text.endswith("\n") else text)

    # ---- 示例 ----

    def _run_demo(self, item):
        text = item.text()
        idx = text.split()[0]
        d = gallery.find_demo(idx)
        bio = find_bio()
        if not d or not bio:
            return
        self.out.clear()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(
            lambda: self._append_out(self._proc.readAllStandardOutput().data().decode(errors="replace")))
        self._proc.finished.connect(lambda code, _st: self._append_out(f"\n[退出码 {code}]\n"))
        self._proc.start(bio, [d.path])
        self._append_out(f"$ {bio} {d.path}\n")

    def _new_from_template(self, name):
        self._dialog_new_project() if False else None
        # 简化：双击模板 → 直接用当前目录
        base = os.path.dirname(self.project_root) if self.project_root else os.path.expanduser("~/Projects")
        name2 = f"{name}-demo"
        try:
            created = templates.scaffold(name2, templates.find_template(name), base)
        except FileExistsError:
            return
        self._open_project(os.path.join(base, name2))
        self._append_out(f"已创建项目 {name2}（模板 {name}）\n")


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Biol.Studio")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
