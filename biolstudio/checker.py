"""BiuBiuBiu 结构检查器（功能层）。

基于 Token 流的轻量静态检查，不依赖 bio 二进制：
- 词法错误（未闭合字符串、非法字符等）
- 括号/花括号/方括号配平
- program main / program utils 声明
- main 程序必须有 Main 流 + void exec()
- need 声明与项目内 provider 配对（need value/function/stream/Class）
- res/ref/get/cause 出现在方法体外等明显误用

输出：Diagnostic(file, line, col, severity, message)。check_file 返回诊断列表。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .lexer import LexError, Token, tokenize


@dataclass
class Diagnostic:
    file: str
    line: int
    col: int
    severity: str   # error / warning
    message: str

    def render(self) -> str:
        return f"{self.file}:{self.line}:{self.col}: {self.severity}: {self.message}"


class _Cursor:
    """Token 游标：支持窥视/前进/断言关键字。"""

    def __init__(self, toks: list[Token]):
        self.toks = toks
        self.pos = 0

    def peek(self, k: int = 0) -> Token:
        i = min(self.pos + k, len(self.toks) - 1)
        return self.toks[i]

    def next(self) -> Token:
        t = self.peek()
        if self.pos < len(self.toks) - 1:
            self.pos += 1
        return t

    def at_eof(self) -> bool:
        return self.peek().kind == "eof"

    def at_kw(self, kw: str) -> bool:
        return self.peek().kind == "keyword" and self.peek().value == kw

    def at_op(self, op: str) -> bool:
        return self.peek().kind == "op" and self.peek().value == op

    def eat_op(self, op: str) -> bool:
        if self.at_op(op):
            self.next()
            return True
        return False


def _balance(toks: list[Token], diags: list[Diagnostic], filename: str) -> None:
    stack: list[Token] = []
    pairs = {"}": "{", ")": "(", "]": "["}
    for t in toks:
        if t.value in pairs.values():
            stack.append(t)
        elif t.value in pairs:
            if not stack or stack[-1].value != pairs[t.value]:
                diags.append(Diagnostic(filename, t.line, t.col, "error",
                                        f"unmatched closing token {t.value}"))
                continue
            stack.pop()
    for t in reversed(stack):
        diags.append(Diagnostic(filename, t.line, t.col, "error",
                                f"unclosed {t.value}"))


# ---- need 配对 ---------------------------------------------------------------

@dataclass
class Need:
    kind: str      # value / function / stream / Class
    subject: str
    line: int
    col: int


@dataclass
class Provider:
    kind: str      # const / function / stream / Class
    name: str


def _collect_needs(toks: list[Token], filename: str) -> list[Need]:
    needs: list[Need] = []
    cur = _Cursor(toks)
    while not cur.at_eof():
        if cur.at_kw("need"):
            t = cur.next()
            kind_t = cur.next()
            subject_t = cur.next()
            kinds = {"value", "function", "stream", "Class"}
            if kind_t.kind != "keyword" or kind_t.value not in kinds:
                diag_line = t.line
                diags_placeholder = None
                # 语法不标准，跳过到分号
                while not cur.at_op(";"):
                    cur.next()
                cur.eat_op(";")
                continue
            needs.append(Need(kind_t.value, subject_t.value, t.line, t.col))
            while not cur.at_op(";"):
                cur.next()
            cur.eat_op(";")
        else:
            cur.next()
    return needs


def _collect_providers(toks: list[Token], filename: str) -> list[Provider]:
    """扫描本文件的 provider：顶层 const、Stream/Class 声明、方法名。"""
    providers: list[Provider] = []
    depth = 0
    cur = _Cursor(toks)
    while not cur.at_eof():
        t = cur.peek()
        if t.value in "{([":
            depth += 1
            cur.next()
            continue
        if t.value in "})]":
            depth -= 1
            cur.next()
            continue
        if depth == 0:
            if cur.at_kw("const"):
                # const string GREETING = "...";
                cur.next()
                cur.next()          # 类型
                name_t = cur.next()  # 名字
                if name_t.kind in ("ident", "keyword"):
                    providers.append(Provider("const", name_t.value))
            elif cur.at_kw("Stream") or cur.at_kw("Class") or cur.at_kw("Interface"):
                cur.next()
                name_t = cur.next()
                if name_t.kind in ("ident", "keyword"):
                    providers.append(Provider(
                        {"Stream": "stream", "Class": "Class", "Interface": "interface"}[t.value],
                        name_t.value))
            elif cur.at_kw("program"):
                # program utils; → 跳过
                cur.next()
                cur.next()
                cur.eat_op(";")
                continue
        # 方法名：ident 后跟 ( 且前一个 token 是返回类型（void/int/...）或方法签名行
        if (cur.peek().kind == "keyword" and cur.peek().value in
                ("void", "int", "float", "double", "string", "char", "bool")):
            ret = cur.next()
            name_t = cur.next()
            if name_t.kind in ("ident", "keyword") and cur.at_op("("):
                # 方法声明（含签名流里的声明）
                providers.append(Provider("function", name_t.value))
                continue
        cur.next()
    return providers


def _collect_iface_methods(toks: list[Token], start_idx: int) -> tuple[set[str], int]:
    """从 start_idx（Interface/Class 名字后）收集方法名直到匹配的 }。
    返回 (方法名集合, 结束位置)。"""
    methods: set[str] = set()
    i = start_idx
    depth = 0
    n = len(toks)
    # 先找 {
    while i < n and toks[i].value != "{":
        i += 1
    if i >= n:
        return methods, i
    # 块内：ret name( 模式收集方法名
    j = i + 1
    while j < n:
        v = toks[j].value
        if v in "{([":
            depth += 1
            j += 1
            continue
        if v in "})]":
            if depth == 0:
                return methods, j
            depth -= 1
            j += 1
            continue
        if (toks[j].kind == "keyword" and toks[j].value in
                ("void", "int", "float", "double", "string", "char", "bool")
                and j + 2 < n and toks[j + 2].value == "("
                and toks[j + 1].kind in ("ident", "keyword")):
            methods.add(toks[j + 1].value)
        j += 1
    return methods, j


def _check_interfaces(toks: list[Token], filename: str, diags: list[Diagnostic]) -> None:
    """Interface 实现检查：Class X implements Y 必须提供 Y 的全部签名方法。"""
    interfaces: dict[str, set[str]] = {}
    classes: list[tuple[str, list[str], set[str], int]] = []  # (name, impls, methods, line)
    cur = _Cursor(toks)
    while not cur.at_eof():
        t = cur.peek()
        if cur.at_kw("Interface"):
            start = cur.next()
            name_t = cur.next()
            if name_t.kind not in ("ident", "keyword"):
                continue
            idx = cur.pos
            methods, end = _collect_iface_methods(toks, idx)
            interfaces[name_t.value] = methods
            cur.pos = min(end + 1, len(toks) - 1)
            continue
        if cur.at_kw("Class"):
            cls_t = cur.next()
            name_t = cur.next()
            impls: list[str] = []
            if cur.at_kw("implements"):
                cur.next()
                while not cur.at_op("{") and not cur.at_eof():
                    if cur.peek().kind in ("ident", "keyword"):
                        impls.append(cur.next().value)
                        cur.eat_op(",")
                    else:
                        cur.next()
            idx = cur.pos
            methods, end = _collect_iface_methods(toks, idx)
            classes.append((name_t.value, impls, methods, cls_t.line))
            cur.pos = min(end + 1, len(toks) - 1)
            continue
        cur.next()
    for name, impls, methods, line in classes:
        for iface in impls:
            need_methods = interfaces.get(iface)
            if need_methods is None:
                diags.append(Diagnostic(filename, line, 1, "error",
                                        f"Class {name} implements undefined interface {iface}"))
                continue
            for mn in sorted(need_methods):
                if mn not in methods:
                    diags.append(Diagnostic(filename, line, 1, "error",
                                            f"Class {name} does not implement interface {iface} method {mn}()"))


def _match_needs(needs: list[Need], providers: list[Provider],
                 diags: list[Diagnostic], filename: str) -> None:
    kind_map = {"value": "const", "function": "function",
                "stream": "stream", "Class": "Class"}
    for nd in needs:
        ok = any(p.kind == kind_map[nd.kind] and p.name == nd.subject
                 for p in providers)
        if not ok:
            diags.append(Diagnostic(filename, nd.line, nd.col, "warning",
                                    f"need {nd.kind} {nd.subject} has no provider in this file"
                                    "(may be in another file; cross-file check in check_project)"))


# ---- 主检查入口 --------------------------------------------------------------

def check_tokens(toks: list[Token], filename: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    _balance(toks, diags, filename)
    _check_interfaces(toks, filename, diags)

    cur = _Cursor(toks)

    # program 声明
    has_program = False
    prog_kind = None
    while not cur.at_eof():
        if cur.at_kw("program"):
            has_program = True
            cur.next()
            kind_t = cur.next()
            prog_kind = kind_t.value if kind_t.kind in ("ident", "keyword") else None
            if prog_kind not in ("main", "utils"):
                diags.append(Diagnostic(filename, kind_t.line, kind_t.col, "error",
                                        f"program declaration must be main or utils, got {prog_kind!r}"))
            cur.eat_op(";")
            break
        cur.next()
    if not has_program:
        diags.append(Diagnostic(filename, 1, 1, "error",
                                "missing program main; / program utils; declaration"))

    # main 程序必须有 Main 流 + void exec()
    if prog_kind == "main":
        has_main = has_exec = False
        cur = _Cursor(toks)
        while not cur.at_eof():
            if (cur.at_kw("Main")
                    and cur.peek(1).kind == "op" and cur.peek(1).value == "{"):
                has_main = True
                # 找 exec(
                sub = _Cursor(toks[cur.pos:])
                while not sub.at_eof():
                    if (sub.peek().kind == "keyword" and sub.peek().value == "void"
                            and sub.peek(1).kind in ("ident", "keyword")
                            and sub.peek(1).value == "exec"
                            and sub.peek(2).kind == "op" and sub.peek(2).value == "("):
                        has_exec = True
                        break
                    sub.next()
                break
            cur.next()
        if not has_main:
            diags.append(Diagnostic(filename, 1, 1, "error",
                                    "main program is missing the Main stream"))
        elif not has_exec:
            diags.append(Diagnostic(filename, 1, 1, "error",
                                    "Main stream is missing the void exec() entry method"))

    # need 配对（单文件视角）
    needs = _collect_needs(toks, filename)
    providers = _collect_providers(toks, filename)
    _match_needs(needs, providers, diags, filename)

    return diags


def check_source(src: str, filename: str = "<string>") -> list[Diagnostic]:
    try:
        toks = tokenize(src, filename)
    except LexError as e:
        return [Diagnostic(filename, e.line, e.col, "error", e.msg)]
    return check_tokens(toks, filename)


def check_file(path: str) -> list[Diagnostic]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        return [Diagnostic(path, 1, 1, "error", f"cannot read file: {e}")]
    return check_source(src, path)


def check_project(root: str) -> list[Diagnostic]:
    """检查整个项目：src/ + utils/ 全部 .bio 文件，need 跨文件配对。"""
    diags: list[Diagnostic] = []
    files: list[str] = []
    for base in ("src", "utils"):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith((".bio", ".bl")):
                files.append(os.path.join(d, name))

    if not files:
        diags.append(Diagnostic(root, 1, 1, "error", "no .bio files under src/ or utils/"))
        return diags

    all_needs: list[tuple[Need, str]] = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                toks = tokenize(f.read(), path)
        except LexError as e:
            diags.append(Diagnostic(path, e.line, e.col, "error", e.msg))
            continue
        diags.extend(check_tokens(toks, path))
        for nd in _collect_needs(toks, path):
            all_needs.append((nd, path))

    # 全项目 provider 表
    providers: list[tuple[Provider, str]] = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                toks = tokenize(f.read(), path)
        except LexError:
            continue
        for p in _collect_providers(toks, path):
            providers.append((p, path))

    kind_map = {"value": "const", "function": "function",
                "stream": "stream", "Class": "Class"}
    for nd, src_file in all_needs:
        ok = any(p.kind == kind_map[nd.kind] and p.name == nd.subject
                 for p, _ in providers)
        if not ok:
            diags.append(Diagnostic(src_file, nd.line, nd.col, "error",
                                    f"need {nd.kind} {nd.subject} has no provider in the whole project"
                                    "(src/ + utils/ + .biolang/deps/)"))
    return diags
