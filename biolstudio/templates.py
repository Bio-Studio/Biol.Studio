"""模板系统（功能层）。

模板 = templates/ 下的一个目录：
  templates/<name>/
    template.json      # {"name": "...", "description": "..."}
    <其余文件照抄，`__NAME__` 会被替换成项目名>

用户可在 BIOLSTUDIO_TEMPLATES 指向的目录放自己的模板。
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass

# 模板目录解析顺序：环境变量 > 包内 templates/（本仓库根）
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_TEMPLATE_DIR = os.path.join(_PKG_ROOT, "templates")


@dataclass
class Template:
    name: str
    description: str
    path: str


def template_dir() -> str:
    return os.environ.get("BIOLSTUDIO_TEMPLATES", _DEFAULT_TEMPLATE_DIR)


def list_templates() -> list[Template]:
    out: list[Template] = []
    root = template_dir()
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        meta = os.path.join(d, "template.json")
        if not os.path.isdir(d) or not os.path.isfile(meta):
            continue
        try:
            with open(meta, encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, json.JSONDecodeError):
            info = {}
        out.append(Template(
            name=info.get("name", name),
            description=info.get("description", ""),
            path=d,
        ))
    return out


def find_template(name: str) -> Template | None:
    for t in list_templates():
        if t.name == name:
            return t
    return None


def scaffold(name: str, template: Template, dest: str) -> list[str]:
    """把模板复制到 dest/<name>，__NAME__ 占位符替换为项目名。返回创建的文件列表。"""
    target = os.path.join(dest, name)
    if os.path.exists(target):
        raise FileExistsError(f"{target} 已存在")
    created: list[str] = []
    os.makedirs(target)
    for dirpath, dirnames, filenames in os.walk(template.path):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn == "template.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), template.path)
            out_path = os.path.join(target, rel)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                content = f.read()
            content = content.replace("__NAME__", name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(os.path.join(name, rel))
    return created
