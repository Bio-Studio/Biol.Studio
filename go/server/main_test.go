package main

import (
	"bufio"
	"encoding/json"
	"os/exec"
	"strings"
	"testing"
)

// 启动 server（stdio 模式）并发送请求，返回响应。
func rpcCall(t *testing.T, reqs []string) []map[string]any {
	t.Helper()
	cmd := exec.Command("go", "run", ".")
	var stdin strings.Builder
	for _, r := range reqs {
		stdin.WriteString(r + "\n")
	}
	cmd.Stdin = strings.NewReader(stdin.String())
	out, err := cmd.Output()
	if err != nil {
		// go run 输出可能含编译信息，取 stdout
		t.Fatalf("server run failed: %v (out: %s)", err, out)
	}
	var resps []map[string]any
	sc := bufio.NewScanner(strings.NewReader(string(out)))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || !strings.HasPrefix(line, "{") {
			continue
		}
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err == nil {
			resps = append(resps, m)
		}
	}
	return resps
}

func TestRPCPingAndTemplates(t *testing.T) {
	resps := rpcCall(t, []string{
		`{"jsonrpc":"2.0","id":1,"method":"ping"}`,
		`{"jsonrpc":"2.0","id":2,"method":"templates"}`,
		`{"jsonrpc":"2.0","id":3,"method":"shutdown"}`,
	})
	if len(resps) < 2 {
		t.Fatalf("expected >=2 responses, got %d: %v", len(resps), resps)
	}
	if resps[0]["id"] != float64(1) {
		t.Fatalf("bad id: %v", resps[0]["id"])
	}
	result, ok := resps[0]["result"].(map[string]any)
	if !ok || !strings.Contains(result["pong"].(string), "bbb") {
		t.Fatalf("bad ping result: %v", resps[0]["result"])
	}
	tpls, ok := resps[1]["result"].(map[string]any)
	if !ok {
		t.Fatalf("bad templates result: %v", resps[1]["result"])
	}
	list := tpls["templates"].([]any)
	if len(list) < 3 {
		t.Fatalf("expected >=3 templates, got %d", len(list))
	}
}

func TestRPCProjectLifecycle(t *testing.T) {
	dir := t.TempDir()
	resps := rpcCall(t, []string{
		`{"jsonrpc":"2.0","id":1,"method":"project.new","params":{"name":"rpctest","template":"hello","base":"` + dir + `"}}`,
		`{"jsonrpc":"2.0","id":2,"method":"project.check","params":{"root":"` + dir + `/rpctest"}}`,
		`{"jsonrpc":"2.0","id":3,"method":"project.run","params":{"root":"` + dir + `/rpctest"}}`,
		`{"jsonrpc":"2.0","id":4,"method":"shutdown"}`,
	})
	if len(resps) < 3 {
		t.Fatalf("expected >=3 responses, got %d", len(resps))
	}
	if _, ok := resps[0]["error"]; ok {
		t.Fatalf("new failed: %v", resps[0])
	}
	run, ok := resps[2]["result"].(map[string]any)
	if !ok || run["ok"] != true {
		t.Fatalf("run failed: %v", resps[2])
	}
}
