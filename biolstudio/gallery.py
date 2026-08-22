"""示例库（功能层）：读 bio 仓库 examples/ 作为教程画廊。

bio 仓库路径：BIO_REPO 环境变量 → ~/Projects/bio → BiolStudio 的兄弟目录 ../bio。
`demo list` 列出全部示例；`demo <编号|文件名>` 直接运行。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

_DEFAULT_REPO = os.path.expanduser("~/Projects/bio")
_SIBLING_REPO = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "bio"))


def find_repo() -> str | None:
    for cand in (os.environ.get("BIO_REPO", ""), _DEFAULT_REPO, _SIBLING_REPO):
        if cand and os.path.isdir(os.path.join(cand, "examples")):
            return cand
    return None


@dataclass
class Demo:
    index: int
    filename: str
    title: str
    path: str

    @property
    def name(self) -> str:
        return os.path.splitext(self.filename)[0]


def list_demos() -> list[Demo]:
    repo = find_repo()
    if not repo:
        return []
    ex_dir = os.path.join(repo, "examples")
    out: list[Demo] = []
    for fn in sorted(os.listdir(ex_dir)):
        m = re.match(r"(\d+)-(.*)\.bio$", fn)
        if not m:
            continue
        num, rest = int(m.group(1)), m.group(2)
        title = rest.replace("-", " ").title()
        out.append(Demo(num, fn, title, os.path.join(ex_dir, fn)))
    out.sort(key=lambda d: d.index)
    return out


def find_demo(arg: str) -> Demo | None:
    demos = list_demos()
    if not demos:
        return None
    if arg.isdigit():
        for d in demos:
            if d.index == int(arg):
                return d
        return None
    for d in demos:
        if arg in (d.name, d.filename):
            return d
    return None


def run_demo(demo: Demo, bio: str) -> int:
    print(f"=== {demo.index:02d} {demo.filename} — {demo.title} ===")
    proc = subprocess.run([bio, demo.path])
    return proc.returncode
