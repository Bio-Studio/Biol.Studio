"""Biol.Studio GUI — 专业的 BBB (BiuBiuBiu) IDE（PyQt6）。

复用功能层：lexer（高亮）、checker（诊断）、project/templates（项目）、
runner（运行/构建）、gallery（示例画廊）。

特性：
- 项目树 / 多标签编辑器（语法高亮 + 行号 + 错误波浪线 + 悬停提示 + 内嵌错误条）
- 检查（Ctrl+Shift+C）：诊断面板点击跳转；编辑器内联显示错误
- 运行（F5）/ 构建（F7）：终端面板流式输出
- 示例画廊双击运行；模板向导新建项目
- 功能管理设置：内嵌错误显示 / 终端面板 / 诊断面板 / 语法高亮 可开关
"""

from __future__ import annotations

import json
import os
import sys

from PyQt6.QtCore import Qt, QProcess, QRect, QSize, QEvent
from PyQt6.QtGui import (QAction, QColor, QFont, QFontMetrics, QPainter,
                         QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                         QTextFormat, QKeySequence)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QTabWidget,
                             QPlainTextEdit, QListWidget, QListWidgetItem,
                             QTextEdit, QVBoxLayout, QHBoxLayout, QLabel,
                             QToolBar, QFileDialog, QDialog, QLineEdit,
                             QComboBox, QDialogButtonBox, QMessageBox,
                             QTextBrowser, QCheckBox, QMenu, QToolTip)

from . import lexer, checker, templates, gallery
from .project import load_project
from .runner import find_bio

APP_NAME = "Biol.Studio — BBB IDE"
APP_VERSION = "1.0.0"

# ───────────────────────── 深色主题 QSS ─────────────────────────

DARK_QSS = """
* { font-size: 13px; }
QMainWindow, QDialog { background: #1e1e1e; color: #d4d4d4; }
QWidget { background: #1e1e1e; color: #d4d4d4; }
QLabel { background: transparent; color: #cccccc; }
QLabel#panelTitle { color: #888888; font-size: 11px; padding: 2px 4px; }
QToolBar { background: #252526; border: none; border-bottom: 1px solid #3c3c3c; spacing: 4px; padding: 3px; }
QToolBar QToolButton { background: transparent; color: #d4d4d4; padding: 5px 10px; border-radius: 4px; }
QToolBar QToolButton:hover { background: #333333; }
QToolBar QToolButton:pressed { background: #094771; }
QTreeWidget, QListWidget, QTextBrowser { background: #252526; border: 1px solid #3c3c3c; color: #d4d4d4; }
QTreeWidget::item, QListWidget::item { padding: 3px 2px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #094771; color: #ffffff; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #2a2d2e; }
QHeaderView::section { background: #2d2d30; color: #cccccc; border: none; padding: 4px; }
QTabWidget::pane { border: 1px solid #3c3c3c; background: #1e1e1e; }
QTabBar::tab { background: #2d2d30; color: #999999; padding: 6px 14px; border: none; border-right: 1px solid #3c3c3c; }
QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-top: 2px solid #007acc; }
QTabBar::tab:hover:!selected { background: #333333; }
QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; border: none; selection-background-color: #094771; }
QLineEdit, QComboBox { background: #3c3c3c; color: #d4d4d4; border: 1px solid #555555; border-radius: 4px; padding: 4px 8px; }
QLineEdit:focus, QComboBox:focus { border-color: #007acc; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #3c3c3c; color: #d4d4d4; selection-background-color: #094771; }
QPushButton { background: #0e639c; color: #ffffff; border: none; border-radius: 4px; padding: 6px 16px; }
QPushButton:hover { background: #1177bb; }
QPushButton:pressed { background: #0a4f7a; }
QDialogButtonBox QPushButton { min-width: 80px; }
QCheckBox { color: #d4d4d4; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { border: 1px solid #666666; background: #252526; border-radius: 3px; }
QCheckBox::indicator:checked { background: #0e639c; border: 1px solid #0e639c; border-radius: 3px; }
QStatusBar { background: #007acc; color: #ffffff; }
QStatusBar QLabel { color: #ffffff; background: transparent; }
QScrollBar:vertical { background: #1e1e1e; width: 12px; }
QScrollBar::handle:vertical { background: #424242; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #555555; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { background: #1e1e1e; height: 12px; }
QScrollBar::handle:horizontal { background: #424242; border-radius: 5px; min-width: 24px; }
QToolTip { background: #252526; color: #f0f0f0; border: 1px solid #007acc; padding: 4px 8px; }
QMenu { background: #252526; color: #d4d4d4; border: 1px solid #3c3c3c; }
QMenu::item:selected { background: #094771; }
QMenuBar { background: #252526; color: #d4d4d4; }
QMenuBar::item:selected { background: #094771; }
QMessageBox { background: #1e1e1e; }
"""


# ───────────────────────── 设置（功能管理） ─────────────────────────

class Settings:
    """功能开关设置，持久化到 ~/.config/biolstudio/settings.json。"""

    DEFAULTS = {
        "inline_errors": True,     # 嵌入式显示错误信息（波浪线/行号标记/内嵌条）
        "live_errors": True,       # 实时错误显示（编辑时自动检查当前文件）
        "terminal_panel": True,    # 终端输出面板
        "diagnostics_panel": True, # 诊断列表面板
        "syntax_highlight": True,  # 语法高亮
        "ctrl_wheel_zoom": True,   # Ctrl+滚轮 切换编辑器字体大小
        "terminal_shortcut": "F12",# 唤起终端面板的快捷键
        # 插件管理是独立选项（预留）
    }

    def __init__(self):
        self.path = os.path.expanduser("~/.config/biolstudio/settings.json")
        self.values = dict(self.DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            for k in self.DEFAULTS:
                if k in data:
                    self.values[k] = bool(data[k])
        except (OSError, json.JSONDecodeError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.values, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def __getitem__(self, k):
        return self.values.get(k, self.DEFAULTS.get(k, True))

    def __setitem__(self, k, v):
        self.values[k] = bool(v)


class SettingsDialog(QDialog):
    """功能管理：启用/禁用 内嵌错误、终端、诊断面板、语法高亮。"""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("功能管理")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("启用 / 禁用内置功能（插件管理为独立选项，后续版本提供）："))
        self.boxes = {}
        for key, label, desc in [
            ("inline_errors", "嵌入式显示错误信息",
             "在编辑器内以波浪线 + 行号标记 + 悬停提示显示检查结果"),
            ("live_errors", "实时错误显示",
             "编辑时自动检查当前文件，错误即时显示（输入停顿后刷新）"),
            ("terminal_panel", "终端面板",
             "底部输出面板：运行/构建结果显示"),
            ("diagnostics_panel", "诊断面板",
             "底部诊断列表（错误/警告，点击跳转）"),
            ("syntax_highlight", "语法高亮",
             "编辑器关键字/字符串/数字/注释着色"),
            ("ctrl_wheel_zoom", "Ctrl+滚轮切换字体大小",
             "按住 Ctrl 滚动滚轮调整编辑器字体大小"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(bool(self.settings[key]))
            cb.setToolTip(desc)
            self.boxes[key] = cb
            lay.addWidget(cb)
            lay.addWidget(QLabel(desc))
        # 终端快捷键配置
        lay.addWidget(QLabel("唤起终端面板的快捷键（点击输入框后按下组合键）："))
        from PyQt6.QtWidgets import QKeySequenceEdit
        self.shortcut_edit = QKeySequenceEdit(
            QKeySequence(self.settings["terminal_shortcut"]), self)
        lay.addWidget(self.shortcut_edit)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(self._apply)
        btn.rejected.connect(self.reject)
        lay.addWidget(btn)

    def _apply(self):
        for k, cb in self.boxes.items():
            self.settings[k] = cb.isChecked()
        seq = self.shortcut_edit.keySequence().toString()
        if seq:
            self.settings["terminal_shortcut"] = seq
        self.settings.save()
        self.accept()


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
        toks = []
        try:
            toks = lexer.tokenize(text)
        except lexer.LexError:
            pass
        for t in toks:
            if t.kind in self.formats:
                self.setFormat(t.col - 1, len(t.value), self.formats[t.kind])
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


# ───────────────────────── 编辑器（行号 + 错误内嵌显示） ─────────────────────────

class CodeEditor(QPlainTextEdit):
    """带行号的代码编辑器。错误内嵌显示：波浪线 + 行号标记 + 悬停提示。"""

    def __init__(self, path=None, parent=None):
        super().__init__(parent)
        self.path = path
        self._hl = BioHighlighter(self.document())
        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width()
        self._diags: list = []          # [(line, col, severity, message)]
        self._inline_enabled = True
        font = QFont("JetBrains Mono, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setTabStopDistance(4 * QFontMetrics(font).horizontalAdvance(' '))
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._zoom_enabled = True
        self._font_size = font.pointSize()

    # ---- 行号区 ----

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

    def paint_line_numbers(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(28, 28, 28))
        # 错误行标记（红点）
        err_lines = {d[0] - 1 for d in self._diags if self._inline_enabled}
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
                if block_number in err_lines:
                    painter.setBrush(QColor(255, 90, 90))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(4, top + self.fontMetrics().height() // 2 - 3, 6, 6)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()

    # ---- 诊断（嵌入式错误显示） ----

    def set_diagnostics(self, diags: list):
        """设置本文件的诊断 [(line, col, severity, message)]，绘制波浪线。"""
        self._diags = diags
        self._refresh_inline()
        self._line_area.update()

    def set_inline_enabled(self, enabled: bool):
        self._inline_enabled = enabled
        self._refresh_inline()
        self._line_area.update()

    def _refresh_inline(self):
        extra = []
        if self._inline_enabled:
            for (line, _col, _sev, _msg) in self._diags:
                block = self.document().findBlockByNumber(line - 1)
                if not block.isValid():
                    continue
                sel = QTextEdit.ExtraSelection()
                sel.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                sel.format.setUnderlineColor(QColor(255, 90, 90))
                sel.cursor = QTextCursor(block)
                sel.cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                                        QTextCursor.MoveMode.KeepAnchor)
                extra.append(sel)
        self.setExtraSelections(extra)

    def wheelEvent(self, e):
        # Ctrl+滚轮切换字体大小（设置可关闭）
        if self._zoom_enabled and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y()
            if delta != 0:
                new_size = max(8, min(26, self._font_size + (1 if delta > 0 else -1)))
                if new_size != self._font_size:
                    self._font_size = new_size
                    f = self.font()
                    f.setPointSize(new_size)
                    self.setFont(f)
                    self.setTabStopDistance(4 * QFontMetrics(f).horizontalAdvance(' '))
                e.accept()
                return
        super().wheelEvent(e)

    def set_zoom_enabled(self, enabled: bool):
        self._zoom_enabled = enabled

    def diagnostics_at_line(self, line: int):
        return [d for d in self._diags if d[0] == line]

    # ---- 悬停提示 ----

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip and self._inline_enabled and self._diags:
            pos = e.pos()
            cursor = self.cursorForPosition(pos)
            line = cursor.blockNumber() + 1
            diags = self.diagnostics_at_line(line)
            if diags:
                msgs = "\n".join(
                    f"{'错误' if s == 'error' else '警告'}: {m}" for _, _, s, m in diags)
                QToolTip.showText(self.viewport().mapToGlobal(pos), msgs, self)
                return True
        return super().event(e)


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


# ───────────────────────── 主窗口 ─────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.project_root = None
        self._proc = None
        self.settings = Settings()
        self._file_diags: dict[str, list] = {}
        self._term_shortcut = None
        self._live_timer = None

        self._build_actions()
        self._build_ui()
        self._load_gallery()
        self._load_templates()
        self.apply_settings()
        self.statusBar().showMessage(f"bbb: {find_bio() or '未找到'}")

    # ---- UI ----

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
        act_settings = QAction("功能管理…", self)
        act_settings.triggered.connect(self._dialog_settings)
        self._actions = dict(new=act_new, open=act_open, check=act_check,
                             run=act_run, build=act_build, save=act_save,
                             settings=act_settings)

        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        for a in (act_new, act_open, act_save, act_check, act_run, act_build):
            tb.addAction(a)
        self.addToolBar(tb)

        menubar = self.menuBar()
        m_settings = menubar.addMenu("设置")
        m_settings.addAction(act_settings)

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
        self.tpl_list.itemDoubleClicked.connect(self._new_from_template)
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

        # 底部：诊断 + 终端
        bottom = QSplitter(Qt.Orientation.Vertical)
        self.diag = QListWidget()
        self.diag.itemClicked.connect(self._diag_jump)
        self.out = QTextBrowser()
        self.out.setOpenExternalLinks(False)
        self.diag_label = QLabel("诊断")
        self.out_label = QLabel("终端")
        bottom.addWidget(self.diag_label)
        bottom.addWidget(self.diag)
        bottom.addWidget(self.out_label)
        bottom.addWidget(self.out)
        bottom.setSizes([140, 200])
        split_main.addWidget(bottom)
        split_main.setStretchFactor(2, 1)

        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

    # ---- 设置应用 ----

    def apply_settings(self):
        s = self.settings
        # 诊断面板显隐
        self.diag.setVisible(bool(s["diagnostics_panel"]))
        self.diag_label.setVisible(bool(s["diagnostics_panel"]))
        # 终端面板显隐（初始状态；快捷键可随时唤起）
        self.out.setVisible(bool(s["terminal_panel"]))
        self.out_label.setVisible(bool(s["terminal_panel"]))
        # 各编辑器内嵌错误开关 / 缩放开关 / 高亮
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                w.set_inline_enabled(bool(s["inline_errors"]))
                w.set_zoom_enabled(bool(s["ctrl_wheel_zoom"]))
                if bool(s["syntax_highlight"]):
                    if w._hl.document() is None:
                        w._hl.setDocument(w.document())
                    w._hl.rehighlight()
                else:
                    w._hl.setDocument(None)
        # 终端快捷键（重建）
        self._rebind_terminal_shortcut()

    def _rebind_terminal_shortcut(self):
        if self._term_shortcut is not None:
            self._term_shortcut.activated.disconnect()
            self._term_shortcut.setEnabled(False)
            self._term_shortcut = None
        seq = self.settings["terminal_shortcut"]
        if not seq:
            return
        from PyQt6.QtGui import QShortcut, QKeySequence
        self._term_shortcut = QShortcut(QKeySequence(seq), self)
        self._term_shortcut.activated.connect(self.toggle_terminal)

    def toggle_terminal(self):
        show = not self.out.isVisible()
        self.out.setVisible(show)
        self.out_label.setVisible(show)
        self.statusBar().showMessage("终端面板已打开" if show else "终端面板已关闭", 2000)

    def _dialog_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.apply_settings()
            self.statusBar().showMessage("设置已保存", 3000)

    # ---- 模板 / 画廊 ----

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
            w = self.tabs.widget(i)
            if getattr(w, "path", None) == path:
                self.tabs.setCurrentIndex(i)
                return
        ed = CodeEditor(path)
        try:
            ed.setPlainText(open(path, encoding="utf-8").read())
        except OSError as e:
            QMessageBox.warning(self, "打开失败", str(e))
            return
        ed.set_inline_enabled(bool(self.settings["inline_errors"]))
        ed.set_zoom_enabled(bool(self.settings["ctrl_wheel_zoom"]))
        ed.set_diagnostics(self._file_diags.get(os.path.abspath(path), []))
        ed.textChanged.connect(lambda: self._schedule_live_check(ed))
        self.tabs.addTab(ed, os.path.basename(path))
        self.tabs.setCurrentWidget(ed)

    def _schedule_live_check(self, ed):
        """实时检查：输入停顿后（500ms）检查当前文件，嵌入式更新错误。"""
        if not bool(self.settings["live_errors"]) or not ed.path:
            return
        if self._live_timer is None:
            from PyQt6.QtCore import QTimer
            self._live_timer = QTimer(self)
            self._live_timer.setSingleShot(True)
            self._live_timer.setInterval(500)
            self._live_timer.timeout.connect(self._do_live_check)
        self._live_timer.start()

    def _do_live_check(self):
        ed = self.tabs.currentWidget()
        if not isinstance(ed, CodeEditor) or not ed.path:
            return
        diags = checker.check_file(ed.path)
        key = os.path.abspath(ed.path)
        self._file_diags[key] = [(d.line, d.col, d.severity, d.message) for d in diags]
        ed.set_diagnostics(self._file_diags[key])
        errs = sum(1 for d in diags if d.severity == "error")
        self.statusBar().showMessage(
            f"实时检查 {os.path.basename(ed.path)}：{errs} 错误 / {len(diags) - errs} 警告", 3000)

    def save_current(self):
        ed = self.tabs.currentWidget()
        if isinstance(ed, CodeEditor) and ed.path:
            try:
                open(ed.path, "w", encoding="utf-8").write(ed.toPlainText())
                ed.document().setModified(False)
                self.statusBar().showMessage(f"已保存 {ed.path}", 3000)
            except OSError as e:
                QMessageBox.warning(self, "保存失败", str(e))

    def save_all(self):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if isinstance(ed, CodeEditor) and ed.path and ed.document().isModified():
                open(ed.path, "w", encoding="utf-8").write(ed.toPlainText())
                ed.document().setModified(False)

    # ---- 检查（嵌入式错误 + 诊断面板） ----

    def run_check(self):
        self.diag.clear()
        if not self.project_root:
            QMessageBox.information(self, "检查", "请先打开/新建项目")
            return
        self.save_all()
        diags = checker.check_project(self.project_root)
        # 按文件分组 → 编辑器内嵌
        self._file_diags = {}
        for d in diags:
            key = os.path.abspath(d.file)
            self._file_diags.setdefault(key, []).append(
                (d.line, d.col, d.severity, d.message))
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.path:
                w.set_diagnostics(self._file_diags.get(os.path.abspath(w.path), []))
        # 诊断列表
        for d in diags:
            icon = "✗" if d.severity == "error" else "!"
            rel = d.file.replace(self.project_root + os.sep, "")
            it = QListWidgetItem(f"{icon} {rel}:{d.line}:{d.col}  {d.message}")
            it.setData(Qt.ItemDataRole.UserRole, d)
            self.diag.addItem(it)
        errs = sum(1 for d in diags if d.severity == "error")
        self.statusBar().showMessage(f"检查完成：{errs} 错误 / {len(diags) - errs} 警告", 5000)
        self._append_out(f"检查完成：{errs} 错误 / {len(diags) - errs} 警告\n")

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

    # ---- 运行 / 构建 ----

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
        if text.endswith("\n"):
            self.out.append(text)
        else:
            self.out.append(text)

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

    def _new_from_template(self, item):
        name = item.text()
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
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
