# BiolStudio 路线图

目标：**让用户快速写一个 BiuBiuBiu 项目**——从零开始到能跑，一分钟以内。

## 阶段一：Python 功能层原型（当前，已完成）

纯 Python 标准库，无外部依赖。已验证端到端：
- `new` 脚手架（5 个模板）、`check` 静态检查、`run`/`build` 驱动 bio、
  `demo` 示例画廊、`tokens` 调试、`doctor` 自检
- 16 个单元测试全绿

设计要点（为后两层预留）：
- 词法器独立（`lexer.py`）：渲染层高亮直接复用 Token 流
- `comm.py` 协议草案 v0.1：方法名与 CLI 子命令一一对应，Go 层按此对齐
- 功能层全部为纯函数/无状态 CLI，方便被服务层包装

## 阶段二：Go 通讯层（下一步）

- 本地服务进程（localhost），暴露功能层能力：
  - `project.new` / `project.check` / `project.run` / `project.build` /
    `demo.list` / `demo.run`（方法签名见 `biolstudio/comm.py`）
- 长任务（run/build）异步执行 + 事件推送（输出流、退出码）
- 协议：JSON-RPC over WebSocket（或 stdio，供编辑器内嵌）
- Go 直接复用 bio 的调用逻辑（runner 语义移植），Python 侧不驻留

## 阶段三：Go 渲染层

- 本地 GUI（Fyne / Wails 选型待定）或 Web 前端
- 视图：项目文件树、语法高亮编辑器（Token 流来自功能层）、输出面板、示例画廊
- 编辑体验：模板补全、`need` 高亮、错误定位（诊断带 行:列，直接跳转）

## 远期

- 接入 Rust 版 bio（`~/Projects/bio/rust/`）：`check` 换用 Rust 的
  lexer/parser（更快、更准），通讯层通过进程协议调用
- BiuBiuBiu 包仓库浏览（复用 `need` 依赖解析）
