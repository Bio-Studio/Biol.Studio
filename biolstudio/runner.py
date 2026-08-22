"""bio 二进制驱动（功能层）。

查找顺序：BIO_BIN 环境变量 → ~/Projects/bio/bin/bio（本机 bio 仓库预编译产物）
→ PATH 中的 bio。所有执行均流式透传 stdout/stderr，支持 dry_run 预览。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

_CANDIDATES = [
    os.environ.get("BIO_BIN", ""),
    os.path.expanduser("~/Projects/bio/bin/bio"),
]
_CANDIDATES = [c for c in _CANDIDATES if c]


def find_bio() -> str | None:
    for c in _CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which("bio")


@dataclass
class RunResult:
    ok: bool
    returncode: int
    cmd: list[str]


def _run(cmd: list[str], cwd: str | None, dry_run: bool) -> RunResult:
    if dry_run:
        print("$ " + " ".join(cmd))
        return RunResult(True, 0, cmd)
    try:
        proc = subprocess.run(cmd, cwd=cwd)
    except FileNotFoundError:
        print(f"无法执行: {cmd[0]}", file=sys.stderr)
        return RunResult(False, 127, cmd)
    return RunResult(proc.returncode == 0, proc.returncode, cmd)


def run_file(bio: str, path: str, dry_run: bool = False) -> RunResult:
    return _run([bio, path], cwd=os.path.dirname(os.path.abspath(path)) or None, dry_run=dry_run)


def run_project(bio: str, root: str, dry_run: bool = False) -> RunResult:
    return _run([bio, "run", root], cwd=root, dry_run=dry_run)


def build_file(bio: str, path: str, out: str | None, dry_run: bool = False) -> RunResult:
    cmd = [bio, "shell", "build", path]
    if out:
        cmd += ["-o", out]
    return _run(cmd, cwd=os.path.dirname(os.path.abspath(path)) or None, dry_run=dry_run)


def build_project(bio: str, root: str, dry_run: bool = False) -> RunResult:
    return _run([bio, "build", root], cwd=root, dry_run=dry_run)
