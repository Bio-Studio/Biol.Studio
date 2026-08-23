# BiolStudio

快速编写 BiuBiuBiu 项目的工具箱。当前为 **Python 功能层原型**（v0.1.0）。

## 现状：三层层级

| 层 | 语言 | 状态 | 职责 |
|---|---|---|---|
| 功能层 | Python | ✅ 原型完成 | 项目脚手架、词法/结构检查、示例库、bio 驱动 |
| 通讯层 | Go | ⏳ 下一步 | 本地服务、任务执行、事件推送（见 `biolstudio/comm.py` 协议草案） |
| 渲染层 | Go | ⏳ 下一步 | 项目树、高亮编辑器、输出面板、示例画廊（见 `biolstudio/render.py` 契约） |

详细路线见 [PLAN.md](PLAN.md)。

## 安装 / 运行

```bash
# 直接跑（无需安装）
cd BiolStudio
python3 -m biolstudio.cli doctor

# 或安装为命令（需要 uv / pip）
uv pip install -e .
biolstudio doctor
```

依赖：**纯 Python 标准库**（≥3.10）。运行/构建需要 `bbb` 二进制（旧 C 版 `bio` 亦可）（自动查找：
`BBB_BIN` 环境变量 → `~/Projects/bio/bin/bio` → PATH 中的 `bbb`/`bio`）。

## 用法

```bash
# 从模板创建项目（hello / project / requests / classes / threads）
biolstudio new myapp -t project

# 静态检查（词法 + 结构，不需要 bio）
biolstudio check myapp

# 运行 / 编译
biolstudio run myapp
biolstudio build myapp

# 示例画廊（来自 bio 仓库 examples/，BIO_REPO 可改路径）
biolstudio demo list
biolstudio demo 2          # 运行 02-requests.bio

# 其他
biolstudio templates       # 列出模板
biolstudio tokens x.bio    # 调试：Token 流
biolstudio doctor          # 环境自检
```

## 目录结构

```
biolstudio/
  cli.py       # argparse 入口（new/check/run/build/demo/tokens/doctor）
  lexer.py     # BiuBiuBiu 词法器（纯 Python，Token 流，供检查/高亮）
  checker.py   # 结构检查：配平、program/Main 契约、need 配对（单文件+全项目）
  templates.py # 模板系统（templates/ 目录，BIOLSTUDIO_TEMPLATES 可加自定义）
  project.py   # 项目模型 + package.toml 最小 TOML 解析
  runner.py    # bbb 二进制驱动（run/build，dry-run 预览）
  gallery.py   # 示例库（读 bio 仓库 examples/（BIO_REPO 可改路径））
  comm.py      # 通讯层占位（协议草案 v0.1，Go 层对齐用）
  render.py    # 渲染层占位（视图契约，Go 层实现用）
templates/     # 内置模板（hello/project/requests/classes/threads）
tests/         # unittest，`python3 -m unittest discover -s tests`
```

## 已知限制

- `biolstudio build` 依赖 bbb 的编译模式；当前 `~/Projects/bio` 已迁移到 MPS
  语言工作台、C 源码已删除，预编译 `bin/bio` 的编译模式会报
  `src/arena.c 没有那个文件或目录`——这是 bio 仓库状态所致，待 Rust 实现
  的编译后端就位后恢复（见 bio 仓库 `RUST-PLAN.md`）。
- 检查器是 Token 流级的结构检查，不是完整语义分析（完整解析器在
  Rust 重写计划里）。
