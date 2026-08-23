"""BiuBiuBiu 词法器（纯 Python，功能层核心）。

输入 .bio / .bl 源码，输出 Token 流。服务于：
- `biolstudio check` 的结构检查
- 未来的语法高亮 / 编辑器功能

关键字表以 examples/ 与 DESIGN.md 为准。所有错误带 行:列 定位。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# BiuBiuBiu 关键字（按 DESIGN.md / README / examples 归纳）
KEYWORDS = {
    "program", "Main", "Stream", "Class", "Interface", "implements",
    "const", "thread", "need",
    "res", "ref", "get", "cause", "ALL", "if", "else", "while", "for",
    "break", "continue", "new", "this",
    # 基础类型
    "void", "int", "float", "double", "string", "char", "bool",
    # 字面量
    "true", "false",
}

# 多字符运算符（长优先）
OPS3 = []
OPS2 = ["==", "!=", "<=", ">=", "&&", "||", "::", "++", "--", "->"]
OPS1 = set("+-*/%<>=!&|.:,;(){}[]")


class LexError(Exception):
    def __init__(self, line: int, col: int, msg: str):
        self.line, self.col, self.msg = line, col, msg
        super().__init__(f"{line}:{col}: {msg}")


@dataclass
class Token:
    kind: str          # ident / keyword / int / float / string / char / op / punct / eof
    value: str
    line: int
    col: int
    # 词法附加信息
    is_keyword: bool = field(default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


def _is_ident_start(c: str) -> bool:
    return c.isalpha() or c == "_"


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def tokenize(src: str, filename: str = "<string>") -> list[Token]:
    """把源码切成 Token 流。遇非法字符/未闭合字面量抛 LexError。"""
    tokens: list[Token] = []
    i, n = 0, len(src)
    line = col = 1

    def advance(k: int = 1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and src[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        c = src[i]

        # 空白
        if c in " \t\r\n":
            advance()
            continue

        # 注释 // ... 和 /* ... */
        if src.startswith("//", i):
            while i < n and src[i] != "\n":
                advance()
            continue
        if src.startswith("/*", i):
            start_line, start_col = line, col
            advance(2)
            while i < n and not src.startswith("*/", i):
                advance()
            if i >= n:
                raise LexError(start_line, start_col, "未闭合的块注释 /*")
            advance(2)
            continue

        # 字符串 "..."（支持 \" 转义）
        if c == '"':
            start_line, start_col = line, col
            advance()
            buf = []
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    buf.append(src[i] + src[i + 1])
                    advance(2)
                else:
                    buf.append(src[i])
                    advance()
            if i >= n:
                raise LexError(start_line, start_col, "未闭合的字符串字面量")
            advance()  # 收尾 "
            tokens.append(Token("string", "".join(buf), start_line, start_col))
            continue

        # 字符 'x'（单字符字面量，'\\'' 等转义）
        if c == "'":
            start_line, start_col = line, col
            advance()
            if i >= n:
                raise LexError(start_line, start_col, "未闭合的字符字面量")
            if src[i] == "\\":
                if i + 1 >= n:
                    raise LexError(start_line, start_col, "未闭合的字符字面量")
                ch = src[i] + src[i + 1]
                advance(2)
            else:
                ch = src[i]
                advance()
            if i >= n or src[i] != "'":
                raise LexError(start_line, start_col, "字符字面量必须恰好一个字符")
            advance()
            tokens.append(Token("char", ch, start_line, start_col))
            continue

        # 数字：int / float（支持 3.14、.5、1e3）
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            start_line, start_col = line, col
            m = re.match(r"(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?", src[i:])
            assert m
            text = m.group(0)
            if "." in text or "e" in text.lower():
                tokens.append(Token("float", text, start_line, start_col))
            else:
                tokens.append(Token("int", text, start_line, start_col))
            advance(len(text))
            continue

        # 标识符 / 关键字
        if _is_ident_start(c):
            start_line, start_col = line, col
            j = i
            while j < n and _is_ident_char(src[j]):
                j += 1
            word = src[i:j]
            advance(j - i)
            if word in KEYWORDS:
                tokens.append(Token("keyword", word, start_line, start_col, is_keyword=True))
            else:
                tokens.append(Token("ident", word, start_line, start_col))
            continue

        # 运算符
        for op in OPS2:
            if src.startswith(op, i):
                tokens.append(Token("op", op, line, col))
                advance(len(op))
                break
        else:
            if c in OPS1:
                tokens.append(Token("op", c, line, col))
                advance()
                continue
            raise LexError(line, col, f"无法识别的字符 {c!r}")

    tokens.append(Token("eof", "", line, col))
    return tokens


def tokens_to_text(tokens: list[Token]) -> str:
    """调试用：把 Token 流打成可读文本。"""
    return "\n".join(f"{t.line:>4}:{t.col:<3} {t.kind:<8} {t.value!r}" for t in tokens)
