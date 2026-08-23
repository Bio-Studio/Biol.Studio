import os
import tempfile
import unittest

from biolstudio import checker, templates


class TestProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_scaffold_hello(self):
        t = templates.find_template("hello")
        self.assertIsNotNone(t)
        created = templates.scaffold("demo1", t, self.tmp)
        main = os.path.join(self.tmp, "demo1", "src", "main.bio")
        self.assertTrue(os.path.isfile(main))
        self.assertIn("demo1", open(main, encoding="utf-8").read())
        self.assertIn("demo1/package.toml", created)

    def test_scaffold_project(self):
        t = templates.find_template("project")
        created = templates.scaffold("demo2", t, self.tmp)
        for f in ("src/main.bio", "utils/greeter.bio", "utils/config.bio", "package.toml"):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, "demo2", f)), f)

    def test_check_hello_clean(self):
        t = templates.find_template("hello")
        templates.scaffold("demo3", t, self.tmp)
        diags = checker.check_project(os.path.join(self.tmp, "demo3"))
        errors = [d for d in diags if d.severity == "error"]
        self.assertEqual(errors, [], [d.render() for d in diags])

    def test_check_project_needs(self):
        t = templates.find_template("project")
        templates.scaffold("demo4", t, self.tmp)
        diags = checker.check_project(os.path.join(self.tmp, "demo4"))
        errors = [d for d in diags if d.severity == "error"]
        self.assertEqual(errors, [], [d.render() for d in diags])

    def test_check_missing_main(self):
        t = templates.find_template("hello")
        templates.scaffold("demo5", t, self.tmp)
        main = os.path.join(self.tmp, "demo5", "src", "main.bio")
        open(main, "w", encoding="utf-8").write("program main;\nMain { void run() {} }\n")
        diags = checker.check_file(main)
        msgs = " ".join(d.message for d in diags)
        self.assertIn("exec", msgs)

    def test_check_unbalanced(self):
        t = templates.find_template("hello")
        templates.scaffold("demo6", t, self.tmp)
        main = os.path.join(self.tmp, "demo6", "src", "main.bio")
        open(main, "w", encoding="utf-8").write(
            "program main;\nMain { void exec() { CIO::println(\"x\"); }\n")
        diags = checker.check_file(main)
        msgs = " ".join(d.message for d in diags)
        self.assertIn("unclosed", msgs)

    def test_parse_toml(self):
        from biolstudio.project import parse_toml
        data = parse_toml(
            "# comment\nname = \"foo\"\nversion = \"0.1.0\"\n\n[dependencies]\nlib = { version = \"1.0\" }\n")
        self.assertEqual(data["name"], "foo")
        self.assertEqual(data["dependencies"]["lib"]["version"], "1.0")


if __name__ == "__main__":
    unittest.main()
