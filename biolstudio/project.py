"""项目模型：package.toml 读写 + 目录结构识别（功能层）。

package.toml 是 TOML 子集（注释、[section] 头、key = 标量/内联表），
这里内置一个最小解析器，不引第三方依赖。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


class TomlError(Exception):
    pass


def parse_toml(text: str) -> dict:
    """最小 TOML 子集解析：支持注释、[section]、key = 字符串/数字/bool/内联表。"""
    root: dict = {}
    cur: dict = root
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            m = re.match(r"\[([^\]]+)\]", line)
            if not m:
                raise TomlError(f"无效的 section 头: {line!r}")
            section = root.setdefault(m.group(1).strip(), {})
            cur = section
            continue
        m = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*(.*)$", line)
        if not m:
            raise TomlError(f"无法解析的行: {line!r}")
        key, val = m.group(1).strip(), m.group(2).strip()
        if val.startswith("{") and val.endswith("}"):
            inner: dict = {}
            for part in val[1:-1].split(","):
                if not part.strip():
                    continue
                km = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*(.+)", part.strip())
                if km:
                    inner[km.group(1)] = _parse_scalar(km.group(2))
            cur[key] = inner
        else:
            cur[key] = _parse_scalar(val)
    return root


def _parse_scalar(val: str):
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val in ("true", "false"):
        return val == "true"
    if re.fullmatch(r"[-+]?\d+", val):
        return int(val)
    if re.fullmatch(r"[-+]?\d+\.\d+", val):
        return float(val)
    return val


@dataclass
class BioProject:
    root: str
    name: str = ""
    version: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def is_project(self) -> bool:
        return os.path.isfile(os.path.join(self.root, "package.toml"))

    @property
    def main_file(self) -> str | None:
        p = os.path.join(self.root, "src", "main.bio")
        return p if os.path.isfile(p) else None

    def source_files(self) -> list[str]:
        """src/ + utils/ 下的全部 .bio 文件（排序）。"""
        out: list[str] = []
        for base in ("src", "utils"):
            d = os.path.join(self.root, base)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if name.endswith((".bio", ".bl")):
                    out.append(os.path.join(d, name))
        return out


def load_project(root: str) -> BioProject:
    proj = BioProject(root=os.path.abspath(root))
    toml_path = os.path.join(proj.root, "package.toml")
    if os.path.isfile(toml_path):
        try:
            proj.meta = parse_toml(open(toml_path, encoding="utf-8").read())
        except TomlError:
            proj.meta = {}
        proj.name = proj.meta.get("name", os.path.basename(proj.root))
        proj.version = proj.meta.get("version", "")
    return proj


def resolve_target(arg: str) -> BioProject | str:
    """CLI 参数可能是项目目录或 .bio 文件，统一解析。"""
    p = os.path.abspath(arg)
    if os.path.isdir(p):
        return load_project(p)
    if os.path.isfile(p):
        return p
    raise FileNotFoundError(f"{arg} 不存在")
