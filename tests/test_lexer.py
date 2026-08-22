import unittest

from biolstudio.lexer import LexError, tokenize


class TestLexer(unittest.TestCase):
    def test_hello(self):
        src = 'program main;\nMain { void exec() { CIO::println("hi"); } }'
        toks = tokenize(src)
        kw = [t.value for t in toks if t.kind == "keyword"]
        # program / Main / void 三个关键字
        self.assertEqual(kw, ["program", "Main", "void"])
        self.assertIn("Main", kw)

    def test_string_escape(self):
        toks = tokenize(r'CIO::println("a\"b");')
        s = [t for t in toks if t.kind == "string"]
        self.assertEqual(s[0].value, 'a\\"b')

    def test_char_literal(self):
        toks = tokenize("char c = 'x';")
        c = [t for t in toks if t.kind == "char"]
        self.assertEqual(c[0].value, "x")

    def test_numbers(self):
        toks = tokenize("1 3.14 .5 1e3")
        vals = [(t.kind, t.value) for t in toks if t.kind in ("int", "float")]
        self.assertEqual(vals, [("int", "1"), ("float", "3.14"), ("float", ".5"), ("float", "1e3")])

    def test_ops(self):
        toks = tokenize("a::b == c && d <= e;")
        ops = [t.value for t in toks if t.kind == "op"]
        self.assertEqual(ops, ["::", "==", "&&", "<=", ";"])

    def test_unclosed_string(self):
        with self.assertRaises(LexError):
            tokenize('CIO::println("oops);')

    def test_unclosed_block_comment(self):
        with self.assertRaises(LexError):
            tokenize("/* never closed")

    def test_bad_char(self):
        with self.assertRaises(LexError):
            tokenize("let $x = 1;")

    def test_line_col(self):
        try:
            tokenize('a = 1;\nb = "x;\n')
            self.fail("should raise")
        except LexError as e:
            self.assertEqual(e.line, 2)


if __name__ == "__main__":
    unittest.main()
