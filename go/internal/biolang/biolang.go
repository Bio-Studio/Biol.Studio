// Package biolang — Biol.Studio 业务逻辑的 Go 封装。
//
// 设计（对齐 PLAN.md）：
// - run/build：直接调用 bbb CLI（Rust 实现，解释器+编译器），流式透传输出
// - new/check/demo：复用 Python 功能层（biolstudio CLI），进程调用包装
// - 全部无状态，供通讯层（server）和渲染层（gui）复用
package biolang

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// FindBBB 查找 bbb 二进制：BBB_BIN → PATH 中的 bbb → 旧 bio。
func FindBBB() string {
	if v := os.Getenv("BBB_BIN"); v != "" {
		if isExecutable(v) {
			return v
		}
	}
	if v := os.Getenv("BIO_BIN"); v != "" {
		if isExecutable(v) {
			return v
		}
	}
	if v, err := exec.LookPath("bbb"); err == nil {
		return v
	}
	if v, err := exec.LookPath("bio"); err == nil {
		return v
	}
	return ""
}

func isExecutable(p string) bool {
	st, err := os.Stat(p)
	return err == nil && !st.IsDir() && st.Mode()&0o111 != 0
}

// RunResult — 一次运行/构建的结果。
type RunResult struct {
	OK         bool   `json:"ok"`
	ExitCode   int    `json:"exit_code"`
	Output     string `json:"output"`
	BinaryPath string `json:"binary_path,omitempty"`
}

// RunProject 解释运行项目目录（bbb run <dir>）。
func RunProject(root string) RunResult {
	bbb := FindBBB()
	if bbb == "" {
		return RunResult{OK: false, ExitCode: 127, Output: "error: cannot find the bbb/bio binary"}
	}
	return execCapture(bbb, []string{"run", root}, root)
}

// RunFile 解释运行单个 .bio 文件。
func RunFile(path string) RunResult {
	bbb := FindBBB()
	if bbb == "" {
		return RunResult{OK: false, ExitCode: 127, Output: "error: cannot find the bbb/bio binary"}
	}
	dir := filepath.Dir(path)
	return execCapture(bbb, []string{path}, dir)
}

// BuildProject 编译项目（bbb build <dir>）→ standalone 可执行。
func BuildProject(root string) RunResult {
	bbb := FindBBB()
	if bbb == "" {
		return RunResult{OK: false, ExitCode: 127, Output: "error: cannot find the bbb/bio binary"}
	}
	return execCapture(bbb, []string{"build", root}, root)
}

// BuildFile 编译单个文件（bbb shell build <file> [-o out]）。
func BuildFile(path string, out string) RunResult {
	bbb := FindBBB()
	if bbb == "" {
		return RunResult{OK: false, ExitCode: 127, Output: "error: cannot find the bbb/bio binary"}
	}
	args := []string{"shell", "build", path}
	if out != "" {
		args = append(args, "-o", out)
	}
	return execCapture(bbb, args, filepath.Dir(path))
}

// Version 查询 bbb 版本。
func Version() string {
	bbb := FindBBB()
	if bbb == "" {
		return "bbb not found"
	}
	var buf bytes.Buffer
	cmd := exec.Command(bbb, "--version")
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		return strings.TrimSpace(buf.String())
	}
	return strings.TrimSpace(buf.String())
}

func execCapture(bin string, args []string, cwd string) RunResult {
	cmd := exec.Command(bin, args...)
	cmd.Dir = cwd
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	err := cmd.Run()
	code := 0
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			code = ee.ExitCode()
		} else {
			code = 127
		}
	}
	return RunResult{
		OK:       err == nil,
		ExitCode: code,
		Output:   buf.String(),
	}
}

// ---------------- Python 功能层封装（new/check/demo） ----------------

// pythonBin 定位 biolstudio CLI（pip 安装的入口或项目内 python -m）。
func pythonBin() string {
	if v := os.Getenv("BIOLSTUDIO_BIN"); v != "" {
		return v
	}
	if v, err := exec.LookPath("biolstudio"); err == nil {
		return v
	}
	return ""
}

// ScaffoldProject 用模板创建项目（python biolstudio new --json）。
type ScaffoldResult struct {
	Name     string   `json:"name"`
	Template string   `json:"template"`
	Files    []string `json:"files"`
}

func ScaffoldProject(name, template, base string) (ScaffoldResult, error) {
	bin := pythonBin()
	var args []string
	if bin == "" {
		// 回退：python3 -m biolstudio
		bin = "python3"
		args = append(args, "-m", "biolstudio")
	}
	args = append(args, "new", name, "--template", template, "--dir", base, "--json")
	cmd := exec.Command(bin, args...)
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		return ScaffoldResult{}, fmt.Errorf("scaffold failed: %s", strings.TrimSpace(buf.String()))
	}
	var res ScaffoldResult
	if err := json.Unmarshal(buf.Bytes(), &res); err != nil {
		return ScaffoldResult{}, fmt.Errorf("scaffold JSON parse failed: %v (output: %s)", err, buf.String())
	}
	return res, nil
}

// Diagnostic — 检查结果的一条诊断。
type Diagnostic struct {
	File     string `json:"file"`
	Line     int    `json:"line"`
	Col      int    `json:"col"`
	Severity string `json:"severity"`
	Message  string `json:"message"`
}

// CheckProject 检查项目（python biolstudio check，输出 JSON）。
func CheckProject(root string) ([]Diagnostic, error) {
	bin := pythonBin()
	var args []string
	if bin == "" {
		bin = "python3"
		args = append(args, "-m", "biolstudio")
	}
	args = append(args, "check", root, "--json")
	cmd := exec.Command(bin, args...)
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		// check 失败也尝试解析输出
	}
	out := strings.TrimSpace(buf.String())
	// 取 JSON 部分（行末 JSON 数组）
	idx := strings.Index(out, "[")
	if idx < 0 {
		return nil, fmt.Errorf("check output has no JSON: %s", out)
	}
	var diags []Diagnostic
	if err := json.Unmarshal([]byte(out[idx:]), &diags); err != nil {
		return nil, fmt.Errorf("check JSON parse failed: %v (output: %s)", err, out)
	}
	return diags, nil
}

// Demo — 示例画廊条目。
type Demo struct {
	Index    int    `json:"index"`
	Title    string `json:"title"`
	Filename string `json:"filename"`
	Path     string `json:"path"`
}

// ListDemos 列出示例（python biolstudio demo --json）。
func ListDemos() ([]Demo, error) {
	bin := pythonBin()
	var args []string
	if bin == "" {
		bin = "python3"
		args = append(args, "-m", "biolstudio")
	}
	args = append(args, "demo", "list", "--json")
	cmd := exec.Command(bin, args...)
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("demo list failed: %s", strings.TrimSpace(buf.String()))
	}
	var demos []Demo
	if err := json.Unmarshal(buf.Bytes(), &demos); err != nil {
		return nil, fmt.Errorf("demo JSON parse failed: %v", err)
	}
	return demos, nil
}

// ListTemplates 列出可用模板名（templates --json）。
func ListTemplates() ([]string, error) {
	bin := pythonBin()
	var args []string
	if bin == "" {
		bin = "python3"
		args = append(args, "-m", "biolstudio")
	}
	args = append(args, "templates", "--json")
	cmd := exec.Command(bin, args...)
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("templates failed: %s", strings.TrimSpace(buf.String()))
	}
	var list []struct {
		Name        string `json:"name"`
		Description string `json:"description"`
	}
	if err := json.Unmarshal(buf.Bytes(), &list); err != nil {
		return nil, fmt.Errorf("templates JSON parse failed: %v", err)
	}
	names := make([]string, 0, len(list))
	for _, t := range list {
		names = append(names, t.Name)
	}
	return names, nil
}
