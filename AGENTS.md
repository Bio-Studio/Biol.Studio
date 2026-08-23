# BiolStudio — Contributor Guide

## Git Commits（用户明确要求，2026-08-23 焊死）

- **提交信息必须用英文**（English ONLY）。禁止中文提交信息。
- Conventional style: `feat:` / `fix:` / `docs:` / `chore:` / `refactor:` / `i18n:` / `test:`。
- 一个逻辑变更一个提交。
- 违反此规则 = 回退重写提交。

## 开发约定

- Python 功能层：纯标准库（≥3.10），不引第三方依赖。
- 用户界面字符串可用中文（工具面向中文用户）；代码注释中英皆可。
- 提交前跑 `python3 -m unittest discover -s tests` 保证全绿。

## 结构

```
biolstudio/   # 功能层（Python）
templates/    # 项目模板
tests/        # unittest
```

分层路线见 PLAN.md：Python 功能层 → Go 通讯层 → Go 渲染层。
