package biolang

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindBBB(t *testing.T) {
	b := FindBBB()
	if b == "" {
		t.Fatal("bbb binary not found — needed for run/build tests")
	}
}

func TestScaffoldAndCheck(t *testing.T) {
	base := t.TempDir()
	res, err := ScaffoldProject("gotest", "hello", base)
	if err != nil {
		t.Fatalf("scaffold: %v", err)
	}
	if res.Name != "gotest" || len(res.Files) == 0 {
		t.Fatalf("bad scaffold result: %+v", res)
	}
	root := filepath.Join(base, "gotest")
	if _, err := os.Stat(filepath.Join(root, "src", "main.bio")); err != nil {
		t.Fatalf("main.bio not created: %v", err)
	}
	diags, err := CheckProject(root)
	if err != nil {
		t.Fatalf("check: %v", err)
	}
	for _, d := range diags {
		if d.Severity == "error" {
			t.Fatalf("unexpected error: %s:%d %s", d.File, d.Line, d.Message)
		}
	}
}

func TestRunProject(t *testing.T) {
	base := t.TempDir()
	_, err := ScaffoldProject("runtest", "hello", base)
	if err != nil {
		t.Fatalf("scaffold: %v", err)
	}
	r := RunProject(filepath.Join(base, "runtest"))
	if !r.OK {
		t.Fatalf("run failed (exit %d): %s", r.ExitCode, r.Output)
	}
	if r.Output == "" {
		t.Fatal("run produced no output")
	}
}

func TestListTemplates(t *testing.T) {
	ts, err := ListTemplates()
	if err != nil {
		t.Fatalf("templates: %v", err)
	}
	if len(ts) < 3 {
		t.Fatalf("expected >=3 templates, got %d: %v", len(ts), ts)
	}
}
