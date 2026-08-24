"""渲染层占位（下一步：Go 实现）。

规划（见 PLAN.md）：Go 渲染层负责
- 项目/文件树视图、语法高亮编辑器、运行输出面板
- 基于功能层 + 通讯层的数据，本地 GUI（或 Web 前端）
- Python 原型阶段不实现任何渲染；词法器（lexer.py）已为高亮提供 Token 流

本模块仅作契约声明。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RenderContract:
    """Go 渲染层必须实现的视图。"""
    project_tree: str = "项目文件树（src/ + utils/ + package.toml）"
    editor: str = "语法高亮编辑器（token 流来自功能层 lexer.py）"
    output_panel: str = "运行/构建输出（来自通讯层事件）"
