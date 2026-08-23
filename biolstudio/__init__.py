"""BiolStudio — 快速编写 BiuBiuBiu 项目的工具箱（Python 功能层原型）。

分层规划（见 PLAN.md）：
- 功能层（本包，Python）：项目脚手架、词法/结构检查、示例库、bio 驱动
- 通讯层（下一步，Go）：服务/协议，编辑器与工具链的桥接
- 渲染层（下一步，Go）：可视化编辑与预览

本版本只实现功能层，comm.py / render.py 为后续层的接口占位。
"""

__version__ = "1.0.0"
