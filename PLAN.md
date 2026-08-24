# BiolStudio 路线图

目标：**让用户快速写一个 BiuBiuBiu 项目**——从零开始到能跑，一分钟以内。

## 阶段一：Python 功能层（业务逻辑层）✅ 完成

纯 Python 标准库，无外部依赖。已验证端到端：
- `new` 脚手架（5 个模板）、`check` 静态检查、`run`/`build` 驱动 bio、
  `demo` 示例画廊、`tokens` 调试、`doctor` 自检
- 16 个单元测试全绿
- 扩展：CLI 支持 `--json` 输出（check/new/demo list/templates），
  `python3 -m biolstudio` 入口

设计要点（为后两层预留，已兑现）：
- 词法器独立（`lexer.py`）：渲染层高亮直接复用 Token 流
- `comm.py` 协议草案 v0.1：方法名与 CLI 子命令一一对应，Go 层按此对齐
- 功能层全部为纯函数/无状态 CLI，方便被服务层包装

## 阶段二：Go 通讯层 ✅ 完成（go/server）

- JSON-RPC 2.0 服务进程：stdio（默认，编辑器内嵌）/ TCP（-tcp）
- 方法：`ping` / `project.new` / `project.check` / `project.run` /
  `project.build` / `demo.list` / `demo.run` / `templates` / `shutdown`
- 业务逻辑复用 `internal/biolang`（Go 封装：run/build 直接调 bbb CLI，
  new/check/demo/templates 调 Python 功能层的 --json 输出）
- 测试：internal（scaffold/check/run/demos/templates）+ server（RPC 协议）

## 阶段三：Go 渲染层 ✅ 完成（go/gui）

- Fyne GUI（纯 Go，无 node 依赖）
- 视图：项目文件树、多标签编辑器、语法高亮预览（示例画廊）、
  输出面板、模板新建向导、工具栏（打开/新建/运行/构建/检查）
- 语法高亮 `go/gui/highlight`：正则分词（关键字/字符串/数字/注释/类型流名）

## 远期

- 编辑器内嵌通讯层（stdio 协议已就绪，等待编辑器宿主）
- 接入 Rust 版 bio 的完整检查器（`~/Projects/bio/rust/`）：
  `check` 换用 Rust lexer/parser（更快、更准）
- BiuBiuBiu 包仓库浏览（复用 `need` 依赖解析）
- GUI 编辑器升级：可编辑 + 实时高亮（Fyne 无现成控件，需自绘或换 Wails）
