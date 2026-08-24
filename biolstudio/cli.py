"""biolstudio 命令行入口（argparse，纯标准库）。

子命令：
  new <name>           从模板创建 BiuBiuBiu 项目
  templates            列出可用模板
  check <file|dir>     词法 + 结构检查（不依赖 bio）
  run <file|dir>       用 bio 解释运行
  build <file|dir>     用 bio 编译（-o 指定输出）
  tokens <file>        调试：打印 Token 流
  demo [编号|名字]      运行 bio 仓库示例（demo list 列出）
  doctor               环境自检
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from . import gallery, runner, templates as tmpl
from .checker import check_file, check_project
from .lexer import LexError, tokenize, tokens_to_text
from .project import load_project, resolve_target

EXIT_OK = 0
EXIT_DIAG = 1
EXIT_ERR = 2


def _need_bio() -> str:
    bio = runner.find_bio()
    if not bio:
        print("error: cannot find the bbb/bio binary.", file=sys.stderr)
        print("  set BIO_BIN, or install bbb/bio on PATH.", file=sys.stderr)
        sys.exit(EXIT_ERR)
    return bio


def cmd_new(args: argparse.Namespace) -> int:
    t = tmpl.find_template(args.template)
    if not t:
        print(f"error: template {args.template!r} does not exist. available:", file=sys.stderr)
        for x in tmpl.list_templates():
            print(f"  {x.name:<10} {x.description}", file=sys.stderr)
        return EXIT_ERR
    dest = args.dir or os.getcwd()
    try:
        created = tmpl.scaffold(args.name, t, dest)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERR
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({"name": args.name, "template": t.name, "files": created}))
        return EXIT_OK
    print(f"created project {args.name} (template {t.name}):")
    for f in created:
        print(f"  {f}")
    print(f"\nnext: cd {os.path.join(dest, args.name)}")
    print("  biolstudio check .   # 静态检查")
    print("  biolstudio run .     # 运行")
    return EXIT_OK


def cmd_templates(args: argparse.Namespace) -> int:
    ts = tmpl.list_templates()
    if not ts:
        print("no templates available (BIOLSTUDIO_TEMPLATES points to an empty dir?)", file=sys.stderr)
        return EXIT_ERR
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps([{"name": t.name, "description": t.description} for t in ts]))
        return EXIT_OK
    print("available templates:")
    for t in ts:
        print(f"  {t.name:<10} {t.description}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    target = os.path.abspath(args.target)
    if os.path.isdir(target):
        diags = check_project(target)
    elif os.path.isfile(target):
        diags = check_file(target)
    else:
        print(f"error: {args.target} does not exist", file=sys.stderr)
        return EXIT_ERR
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps([{
            "file": d.file, "line": d.line, "col": d.col,
            "severity": d.severity, "message": d.message,
        } for d in diags]))
        return EXIT_OK if not [d for d in diags if d.severity == "error"] else EXIT_DIAG
    errors = [d for d in diags if d.severity == "error"]
    warnings = [d for d in diags if d.severity == "warning"]
    for d in diags:
        print(d.render())
    print(f"\n{len(errors)} errors, {len(warnings)} warnings")
    return EXIT_OK if not errors else EXIT_DIAG


def cmd_run(args: argparse.Namespace) -> int:
    bio = _need_bio()
    target = resolve_target(args.target)
    if isinstance(target, str):
        result = runner.run_file(bio, target, dry_run=args.dry_run)
    else:
        result = runner.run_project(bio, target.root, dry_run=args.dry_run)
    return EXIT_OK if result.ok else result.returncode


def cmd_build(args: argparse.Namespace) -> int:
    bio = _need_bio()
    target = resolve_target(args.target)
    if isinstance(target, str):
        result = runner.build_file(bio, target, args.out, dry_run=args.dry_run)
    else:
        result = runner.build_project(bio, target.root, dry_run=args.dry_run)
    return EXIT_OK if result.ok else result.returncode


def cmd_tokens(args: argparse.Namespace) -> int:
    try:
        src = open(args.file, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERR
    try:
        toks = tokenize(src, args.file)
    except LexError as e:
        print(f"lex error: {args.file}:{e.line}:{e.col}: {e.msg}", file=sys.stderr)
        return EXIT_DIAG
    print(tokens_to_text(toks))
    return EXIT_OK


def cmd_demo(args: argparse.Namespace) -> int:
    if args.demo == "list":
        demos = gallery.list_demos()
        if not demos:
            print("找不到示例库（设置 BIO_REPO 指向 bio 仓库）", file=sys.stderr)
            return EXIT_ERR
        if getattr(args, "json", False):
            import json as _json
            print(_json.dumps([{"index": d.index, "title": d.title,
                                "filename": d.filename, "path": d.path} for d in demos]))
            return EXIT_OK
        print("BiuBiuBiu 示例画廊：")
        for d in demos:
            print(f"  {d.index:02d}  {d.filename:<28} {d.title}")
        return EXIT_OK
    if not args.demo:
        print("用法：biolstudio demo <编号|名字>（biolstudio demo list 查看全部）", file=sys.stderr)
        return EXIT_ERR
    d = gallery.find_demo(args.demo)
    if not d:
        print(f"找不到示例 {args.demo!r}", file=sys.stderr)
        return EXIT_ERR
    bio = _need_bio()
    return gallery.run_demo(d, bio)


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    bio = runner.find_bio()
    print(f"bio 二进制:   {bio or '未找到'}")
    if not bio:
        ok = False
    repo = gallery.find_repo()
    print(f"bio 仓库:     {repo or '未找到（demo 不可用）'}")
    tdir = tmpl.template_dir()
    n = len(tmpl.list_templates())
    print(f"模板目录:     {tdir}（{n} 个模板）")
    if n == 0:
        ok = False
    print(f"BiolStudio:   v{__version__}")
    return EXIT_OK if ok else EXIT_ERR


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui import run
    run()
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="biolstudio",
        description="BiolStudio — 快速编写 BiuBiuBiu 项目的工具箱（功能层原型）")
    p.add_argument("--version", action="version", version=f"biolstudio {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("new", help="从模板创建项目")
    sp.add_argument("name", help="项目名")
    sp.add_argument("--template", "-t", default="hello", help="模板名（默认 hello）")
    sp.add_argument("--dir", "-d", default=None, help="创建目录（默认当前目录）")
    sp.add_argument("--json", action="store_true", help="输出 JSON 结果")
    sp.set_defaults(func=cmd_new)

    sp_tpl = sub.add_parser("templates", help="列出可用模板")
    sp_tpl.add_argument("--json", action="store_true", help="输出 JSON 数组")
    sp_tpl.set_defaults(func=cmd_templates)

    sp = sub.add_parser("check", help="词法 + 结构检查（无需 bio）")
    sp.add_argument("target", help=".bio 文件或项目目录")
    sp.add_argument("--json", action="store_true", help="输出 JSON 诊断数组")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("run", help="用 bio 解释运行")
    sp.add_argument("target", help=".bio 文件或项目目录")
    sp.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("build", help="用 bio 编译成原生可执行文件")
    sp.add_argument("target", help=".bio 文件或项目目录")
    sp.add_argument("-o", "--out", default=None, help="输出文件名（单文件模式）")
    sp.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("tokens", help="调试：打印 Token 流")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_tokens)

    sp = sub.add_parser("demo", help="运行 bio 仓库示例（demo list 列出全部）")
    sp.add_argument("demo", nargs="?", default=None,
                    help="list=列出全部；否则为示例编号或文件名")
    sp.add_argument("--json", action="store_true", help="demo list 输出 JSON")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("gui", help="启动 GUI（BBB IDE）")
    sp.set_defaults(func=cmd_gui)

    sub.add_parser("doctor", help="环境自检").set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERR


if __name__ == "__main__":
    sys.exit(main())
