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
                             QTextBrowser, QCheckBox, QMenu, QToolTip,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView)

from . import lexer, checker, templates, gallery
from .project import load_project, parse_toml
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
        # 每个功能内置快捷键（空 = 不绑定）
        "sc_terminal": "F12",        # 终端面板（切换）
        "sc_diagnostics": "Ctrl+Shift+D",  # 诊断面板（切换）
        "sc_inline": "",             # 嵌入式错误显示（切换）
        "sc_live": "",               # 实时错误检查（切换）
        "sc_highlight": "",          # 语法高亮（切换）
        "sc_zoom_reset": "Ctrl+0",   # 重置编辑器字体大小
        "terminal_shell": "auto",  # 终端 shell：auto/bash/zsh/fish/sh/pwsh/cmd/自定义
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

    def get(self, k, default=None):
        return self.values.get(k, self.DEFAULTS.get(k, default))

    def __setitem__(self, k, v):
        self.values[k] = bool(v)


class FeaturesDialog(QDialog):
    """功能管理（一级界面）：功能列表，点击进入二级设置。"""

    FEATURES = [
        # (key, 名称, 描述, 快捷键键, 二级专属选项)
        ("inline_errors", "嵌入式错误显示",
         "在编辑器内以波浪线 + 行号标记 + 悬停提示显示检查结果",
         "sc_inline", [("live_errors", "实时错误检查",
                        "编辑时自动检查当前文件，错误即时显示（输入停顿后刷新）")]),
        ("terminal_panel", "终端面板",
         "底部输出面板：运行/构建结果显示；快捷键可唤起",
         "sc_terminal", []),
        ("diagnostics_panel", "诊断面板",
         "底部诊断列表（错误/警告，点击跳转）",
         "sc_diagnostics", []),
        ("syntax_highlight", "语法高亮",
         "编辑器关键字/字符串/数字/注释着色",
         "sc_highlight", []),
        ("ctrl_wheel_zoom", "Ctrl+滚轮缩放",
         "按住 Ctrl 滚动滚轮调整编辑器字体大小",
         "sc_zoom_reset", []),
    ]

    def __init__(self, settings: Settings, parent=None, on_applied=None):
        super().__init__(parent)
        self.settings = settings
        self.on_applied = on_applied or (lambda: None)
        self.setWindowTitle("功能管理")
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("内置功能列表（双击进入功能内部设置；插件管理为独立选项，后续版本提供）："))
        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self._open_feature)
        lay.addWidget(self.listw)
        btn = QDialogButtonBox()
        btn.addButton("返回（撤销不保存）", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(self.reject)
        btn.addButton("Apply（应用）", QDialogButtonBox.ButtonRole.ApplyRole).clicked.connect(self._apply_now)
        lay.addWidget(btn)
        self._refresh()

    def _refresh(self):
        self.listw.clear()
        for key, name, desc, sc_key, _opts in self.FEATURES:
            state = "已启用" if bool(self.settings[key]) else "已禁用"
            sc = self.settings[sc_key] or "未绑定"
            it = QListWidgetItem(f"{name}    [{state}]    快捷键: {sc}")
            it.setToolTip(desc)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.listw.addItem(it)

    def _apply_now(self):
        self.on_applied()
        self.statusBar().showMessage("设置已应用", 2000) if hasattr(self, 'statusBar') else None

    def _open_feature(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        dlg = FeatureDialog(self.settings, key, self, on_applied=self.on_applied)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh()


class FeatureDialog(QDialog):
    """功能内部设置（二级界面）：开关 + 快捷键 + 专属选项。
    OK = 保存并关闭；Apply = 保存并应用（不关闭）；Cancel/返回 = 撤销修改不保存。"""

    def __init__(self, settings: Settings, key: str, parent=None, on_applied=None):
        super().__init__(parent)
        self.settings = settings
        self.key = key
        self.on_applied = on_applied or (lambda: None)
        info = next(f for f in FeaturesDialog.FEATURES if f[0] == key)
        _key, name, desc, sc_key, opts = info
        self.sc_key = sc_key
        self.setWindowTitle(f"功能设置 — {name}")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(desc))
        lay.addSpacing(8)
        # 启用开关
        self.enable_cb = QCheckBox("启用该功能")
        self.enable_cb.setChecked(bool(settings[key]))
        lay.addWidget(self.enable_cb)
        # 快捷键
        lay.addWidget(QLabel("内置快捷键（点击输入框后按下组合键；清空 = 不绑定）："))
        from PyQt6.QtWidgets import QKeySequenceEdit
        self.sc_edit = QKeySequenceEdit(QKeySequence(settings[sc_key]), self)
        lay.addWidget(self.sc_edit)
        # 专属选项
        self.opt_boxes = {}
        for opt_key, opt_name, opt_desc in opts:
            lay.addWidget(QLabel(opt_desc))
            cb = QCheckBox(opt_name)
            cb.setChecked(bool(settings[opt_key]))
            self.opt_boxes[opt_key] = cb
            lay.addWidget(cb)
        # 终端专属：shell 选择（终端面板功能）
        self.shell_cb = None
        if key == "terminal_panel":
            lay.addWidget(QLabel("终端 shell（支持多系统多 shell）："))
            from PyQt6.QtWidgets import QComboBox as _QComboBox
            self.shell_cb = _QComboBox()
            shells = ["auto（自动检测）", "bash", "zsh", "fish", "sh", "pwsh", "powershell", "cmd", "自定义…"]
            cur = settings.get("terminal_shell", "auto")
            self.shell_cb.addItems(shells)
            idx = next((i for i, s in enumerate(shells) if s.startswith(cur)), 0)
            self.shell_cb.setCurrentIndex(idx)
            self.shell_cb.currentIndexChanged.connect(self._shell_changed)
            lay.addWidget(self.shell_cb)
            self.shell_edit = QLineEdit(settings.get("terminal_shell", "auto"))
            self.shell_edit.setPlaceholderText("shell 命令，如: /bin/bash 或 bash --norc")
            self.shell_edit.setVisible(False)
            lay.addWidget(self.shell_edit)
        # 按钮：OK / Apply / Cancel
        btn = QDialogButtonBox()
        btn.addButton("取消（撤销）", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(self.reject)
        btn.addButton("Apply", QDialogButtonBox.ButtonRole.ApplyRole).clicked.connect(self._apply_and_keep)
        btn.addButton("OK（保存并关闭）", QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(self._apply)
        lay.addWidget(btn)

    def _shell_changed(self, idx):
        if self.shell_cb and self.shell_cb.currentText() == "自定义…":
            self.shell_edit.setVisible(True)
        else:
            self.shell_edit.setVisible(False)

    def _collect(self):
        self.settings[self.key] = self.enable_cb.isChecked()
        seq = self.sc_edit.keySequence().toString()
        self.settings[self.sc_key] = seq
        for k, cb in self.opt_boxes.items():
            self.settings[k] = cb.isChecked()
        if self.shell_cb is not None:
            sel = self.shell_cb.currentText()
            if sel == "自定义…":
                sel = self.shell_edit.text().strip() or "auto"
            elif sel.startswith("auto"):
                sel = "auto"
            self.settings["terminal_shell"] = sel
        self.settings.save()

    def _apply(self):
        self._collect()
        self.on_applied()
        self.accept()

    def _apply_and_keep(self):
        self._collect()
        self.on_applied()


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


class TerminalPanel(QWidget):
    """交互式终端面板：支持多 shell（auto/bash/zsh/fish/sh/pwsh/powershell/cmd/自定义）。
    上：只读输出区；下：输入行。也承接 bbb 运行/构建输出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._shell = "auto"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        # 工具栏行：shell 选择 + 启动/停止 + 清空
        bar = QHBoxLayout()
        bar.addWidget(QLabel("shell:"))
        self.shell_combo = QComboBox()
        self.shell_combo.addItems(
            ["auto（自动）", "bash", "zsh", "fish", "sh", "pwsh", "powershell", "cmd", "自定义…"])
        self.shell_combo.currentIndexChanged.connect(self._shell_combo_changed)
        bar.addWidget(self.shell_combo)
        self.shell_edit = QLineEdit()
        self.shell_edit.setPlaceholderText("shell 命令，如 /bin/bash")
        self.shell_edit.setMaximumWidth(180)
        self.shell_edit.setVisible(False)
        bar.addWidget(self.shell_edit)
        self.btn_start = QPushButton("启动终端")
        self.btn_start.clicked.connect(self.start_shell)
        bar.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self.stop_shell)
        self.btn_stop.setEnabled(False)
        bar.addWidget(self.btn_stop)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear)
        bar.addWidget(self.btn_clear)
        bar.addStretch(1)
        lay.addLayout(bar)
        # 输出区（只读）
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        font = QFont("JetBrains Mono, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.view.setFont(font)
        lay.addWidget(self.view, 1)
        # 输入行
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入命令，回车执行（shell 会话中）")
        self.input.returnPressed.connect(self._send_input)
        lay.addWidget(self.input)

    def shell_command(self) -> list[str]:
        sel = self.shell_combo.currentText()
        if sel == "自定义…":
            cmd = self.shell_edit.text().strip()
            return cmd.split() if cmd else ["bash"]
        if sel.startswith("auto"):
            import shutil
            for c in ("bash", "zsh", "fish", "pwsh", "powershell"):
                if shutil.which(c):
                    return [c, "-i"] if c not in ("powershell",) else [c]
            return ["sh", "-i"]
        if sel == "cmd":
            return ["cmd.exe"]
        if sel == "powershell":
            return ["powershell"]
        if sel == "pwsh":
            return ["pwsh", "-i"]
        return [sel, "-i"]

    def _shell_combo_changed(self, idx):
        self.shell_edit.setVisible(self.shell_combo.currentText() == "自定义…")

    def start_shell(self):
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
            return
        cmd = self.shell_command()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_out)
        self._proc.finished.connect(lambda code, _st: self._on_finished(code))
        self._proc.start(cmd[0], cmd[1:])
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.view.appendPlainText(f"$ {' '.join(cmd)}   (已启动，输入命令回车执行)\n")

    def stop_shell(self):
        if self._proc:
            self._proc.terminate()
            if not self._proc.waitForFinished(1500):
                self._proc.kill()

    def _on_finished(self, code):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.view.appendPlainText(f"\n[终端进程结束，退出码 {code}]\n")

    def _read_out(self):
        if self._proc:
            data = self._proc.readAllStandardOutput().data().decode(errors="replace")
            self.view.appendPlainText(data)

    def _send_input(self):
        text = self.input.text()
        self.input.clear()
        if not text:
            return
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.write((text + "\n").encode())
        else:
            self.view.appendPlainText(f"> {text}\n（终端未启动：{text} 无法执行）\n")

    def clear(self):
        self.view.clear()

    def append_output(self, text: str):
        self.view.appendPlainText(text)


# ───────────────────────── 项目设置（package.toml GUI 面板） ─────────────────────────

class ProjectSettingsDialog(QDialog):
    """项目设置面板：name/version/repo + [dependencies] 逐行编辑，与 package.toml 一一对应。
    保存（Ctrl+S / 保存按钮）写回文件；返回 = 撤销修改不保存。"""

    def __init__(self, root: str, parent=None):
        super().__init__(parent)
        self.root = root
        self.path = os.path.join(root, "package.toml")
        self.setWindowTitle("项目设置 — package.toml")
        self.resize(520, 480)
        try:
            self.meta = parse_toml(open(self.path, encoding="utf-8").read())
        except (OSError, Exception):
            self.meta = {}
        self._dirty = False
        lay = QVBoxLayout(self)
        # 基本信息（每行对应真实文本字段）
        form = QVBoxLayout()
        form.addWidget(QLabel("name（项目名）："))
        self.name_ed = QLineEdit(str(self.meta.get("name", "")))
        form.addWidget(self.name_ed)
        form.addWidget(QLabel("version（版本）："))
        self.ver_ed = QLineEdit(str(self.meta.get("version", "")))
        form.addWidget(self.ver_ed)
        form.addWidget(QLabel("repo（仓库 URL，可选）："))
        self.repo_ed = QLineEdit(str(self.meta.get("repo", "")))
        form.addWidget(self.repo_ed)
        lay.addLayout(form)
        # 依赖表
        lay.addWidget(QLabel("dependencies（依赖；+ 号添加 repo，- 号删除）："))
        self.deps_table = QTableWidget(0, 3)
        self.deps_table.setHorizontalHeaderLabels(["名称", "version", "repo"])
        self.deps_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.deps_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.deps_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.deps_table, 1)
        # 依赖操作按钮
        dep_btn = QHBoxLayout()
        btn_add = QPushButton("+ 添加依赖")
        btn_add.clicked.connect(self._add_dep)
        btn_del = QPushButton("- 删除选中")
        btn_del.clicked.connect(self._del_dep)
        dep_btn.addWidget(btn_add)
        dep_btn.addWidget(btn_del)
        dep_btn.addStretch(1)
        lay.addLayout(dep_btn)
        # 底部按钮：保存 / 返回
        btn = QDialogButtonBox()
        btn.addButton("返回（撤销不保存）", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(self.reject)
        btn.addButton("保存 (Ctrl+S)", QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(self.save)
        lay.addWidget(btn)
        self._load_deps()

    def _load_deps(self):
        deps = self.meta.get("dependencies", {})
        if not isinstance(deps, dict):
            deps = {}
        self.deps_table.setRowCount(len(deps))
        for i, (name, spec) in enumerate(deps.items()):
            ver = spec.get("version", "") if isinstance(spec, dict) else str(spec)
            repo = spec.get("repo", "") if isinstance(spec, dict) else ""
            self.deps_table.setItem(i, 0, QTableWidgetItem(name))
            self.deps_table.setItem(i, 1, QTableWidgetItem(ver))
            self.deps_table.setItem(i, 2, QTableWidgetItem(repo))

    def _add_dep(self):
        r = self.deps_table.rowCount()
        self.deps_table.insertRow(r)
        self.deps_table.setItem(r, 0, QTableWidgetItem("libname"))
        self.deps_table.setItem(r, 1, QTableWidgetItem("1.0.0"))
        self.deps_table.setItem(r, 2, QTableWidgetItem(""))

    def _del_dep(self):
        rows = sorted({i.row() for i in self.deps_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.deps_table.removeRow(r)

    def collect(self) -> dict:
        meta = {
            "name": self.name_ed.text().strip(),
            "version": self.ver_ed.text().strip(),
        }
        repo = self.repo_ed.text().strip()
        if repo:
            meta["repo"] = repo
        deps = {}
        for r in range(self.deps_table.rowCount()):
            name = self.deps_table.item(r, 0).text().strip() if self.deps_table.item(r, 0) else ""
            if not name:
                continue
            ver = self.deps_table.item(r, 1).text().strip() if self.deps_table.item(r, 1) else ""
            repo2 = self.deps_table.item(r, 2).text().strip() if self.deps_table.item(r, 2) else ""
            spec = {}
            if ver:
                spec["version"] = ver
            if repo2:
                spec["repo"] = repo2
            deps[name] = spec if spec else "1.0.0"
        if deps:
            meta["dependencies"] = deps
        return meta

    def save(self):
        from .project import dump_toml
        meta = self.collect()
        try:
            os.makedirs(self.root, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(dump_toml(meta))
        except OSError as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return
        self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_S and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.save()
            return
        super().keyPressEvent(e)


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
        act_proj = QAction("项目设置…", self)
        act_proj.setShortcut(QKeySequence("Ctrl+Alt+P"))
        act_proj.triggered.connect(self._dialog_project_settings)
        self._actions = dict(new=act_new, open=act_open, check=act_check,
                             run=act_run, build=act_build, save=act_save,
                             settings=act_settings)

        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        for a in (act_new, act_open, act_save, act_check, act_run, act_build):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(act_proj)
        self.addToolBar(tb)

        menubar = self.menuBar()
        m_proj = menubar.addMenu("项目")
        m_proj.addAction(act_proj)
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

        # 底部：诊断 + 终端（交互式多 shell）
        bottom = QSplitter(Qt.Orientation.Vertical)
        self.diag = QListWidget()
        self.diag.itemClicked.connect(self._diag_jump)
        self.out = TerminalPanel()
        self.diag_label = QLabel("诊断")
        self.out_label = QLabel("终端")
        bottom.addWidget(self.diag_label)
        bottom.addWidget(self.diag)
        bottom.addWidget(self.out_label)
        bottom.addWidget(self.out)
        bottom.setSizes([140, 220])
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
        # 终端 shell 同步
        shell = s["terminal_shell"]
        for i in range(self.out.shell_combo.count()):
            item = self.out.shell_combo.itemText(i)
            if item.startswith(shell) or (shell == "auto" and item.startswith("auto")):
                self.out.shell_combo.setCurrentIndex(i)
                break
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
        # 功能快捷键（重建：每个功能内置快捷键）
        self._rebind_shortcuts()

    def _rebind_shortcuts(self):
        # 清理旧的
        for sc in getattr(self, "_shortcuts", []):
            try:
                sc.activated.disconnect()
                sc.setEnabled(False)
            except Exception:
                pass
        self._shortcuts = []
        from PyQt6.QtGui import QShortcut, QKeySequence
        bindings = [
            ("sc_terminal", self.toggle_terminal),
            ("sc_diagnostics", self.toggle_diagnostics),
            ("sc_inline", self.toggle_inline),
            ("sc_live", self.toggle_live),
            ("sc_highlight", self.toggle_highlight),
            ("sc_zoom_reset", self.reset_zoom),
        ]
        for sc_key, handler in bindings:
            seq = self.settings[sc_key]
            if not seq:
                continue
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(handler)
            self._shortcuts.append(sc)

    # ---- 功能快捷键动作（每个功能：切换开关并即时应用） ----

    def toggle_terminal(self):
        self.settings["terminal_panel"] = not bool(self.settings["terminal_panel"])
        self.settings.save()
        show = bool(self.settings["terminal_panel"])
        self.out.setVisible(show)
        self.out_label.setVisible(show)
        self.statusBar().showMessage("终端面板已打开" if show else "终端面板已关闭", 2000)

    def toggle_diagnostics(self):
        self.settings["diagnostics_panel"] = not bool(self.settings["diagnostics_panel"])
        self.settings.save()
        show = bool(self.settings["diagnostics_panel"])
        self.diag.setVisible(show)
        self.diag_label.setVisible(show)
        self.statusBar().showMessage("诊断面板已打开" if show else "诊断面板已关闭", 2000)

    def toggle_inline(self):
        self.settings["inline_errors"] = not bool(self.settings["inline_errors"])
        self.settings.save()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                w.set_inline_enabled(bool(self.settings["inline_errors"]))
        self.statusBar().showMessage(
            "嵌入式错误显示已启用" if self.settings["inline_errors"] else "嵌入式错误显示已禁用", 2000)

    def toggle_live(self):
        self.settings["live_errors"] = not bool(self.settings["live_errors"])
        self.settings.save()
        self.statusBar().showMessage(
            "实时错误检查已启用" if self.settings["live_errors"] else "实时错误检查已禁用", 2000)

    def toggle_highlight(self):
        self.settings["syntax_highlight"] = not bool(self.settings["syntax_highlight"])
        self.settings.save()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                if bool(self.settings["syntax_highlight"]):
                    if w._hl.document() is None:
                        w._hl.setDocument(w.document())
                    w._hl.rehighlight()
                else:
                    w._hl.setDocument(None)
        self.statusBar().showMessage(
            "语法高亮已启用" if self.settings["syntax_highlight"] else "语法高亮已禁用", 2000)

    def reset_zoom(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                w._font_size = 11
                f = w.font()
                f.setPointSize(11)
                w.setFont(f)
                w.setTabStopDistance(4 * QFontMetrics(f).horizontalAdvance(' '))
        self.statusBar().showMessage("编辑器字体大小已重置", 2000)

    def _dialog_settings(self):
        dlg = FeaturesDialog(self.settings, self, on_applied=self.apply_settings)
        dlg.exec()
        # 关闭后总是应用（二级 OK/Apply 已保存的设置立即生效）
        self.apply_settings()
        self.statusBar().showMessage("设置已保存", 3000)

    # ---- 模板 / 画廊 ----

    def _load_templates(self):
        self.tpl_list.clear()
        for t in templates.list_templates():
            self.tpl_list.addItem(t.name)

    def _refresh_tree(self):
        if self.project_root:
            self._open_project(self.project_root)

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
            if os.path.basename(path) == "package.toml" and self.project_root:
                self._dialog_project_settings()
                return
            self._open_file(path)

    def _dialog_project_settings(self):
        if not self.project_root:
            QMessageBox.information(self, "项目设置", "请先打开/新建项目")
            return
        dlg = ProjectSettingsDialog(self.project_root, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("项目设置已保存（package.toml 已更新）", 3000)
            self._refresh_tree()

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
        self.out.append_output(text)

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
