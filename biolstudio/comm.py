"""通讯层占位（下一步：Go 实现）。

规划（见 PLAN.md）：Go 通讯层负责
- 本地服务（localhost）暴露功能层能力：项目 CRUD、check/run/build 任务、事件推送
- 编辑器/前端（后续渲染层）通过该服务与功能层对话
- 协议草案：JSON-RPC over WebSocket / stdio，方法名与 CLI 子命令一一对应

Python 原型阶段：本模块只定义接口约定，供 Go 层对齐。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 协议版本，Go 层必须兼容
PROTOCOL_VERSION = "0.1"


@dataclass
class ServiceMethod:
    name: str
    params: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)


# 计划暴露的服务方法（与 cli 子命令一一对应）
SERVICE_METHODS = [
    ServiceMethod("project.new", {"name": "str", "template": "str"}, {"files": "list[str]"}),
    ServiceMethod("project.check", {"root": "str"}, {"diagnostics": "list[dict]"}),
    ServiceMethod("project.run", {"root": "str"}, {"exit_code": "int"}),
    ServiceMethod("project.build", {"root": "str"}, {"exit_code": "int"}),
    ServiceMethod("demo.list", {}, {"demos": "list[dict]"}),
    ServiceMethod("demo.run", {"demo": "str"}, {"exit_code": "int"}),
]
