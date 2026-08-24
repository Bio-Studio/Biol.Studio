// Command server — Biol.Studio 通讯层。
//
// JSON-RPC 2.0 over stdio（默认，供 GUI/编辑器内嵌），可选 -tcp localhost:port。
// 方法（与 CLI 子命令一一对应，协议 v0.1，见 biolstudio/comm.py）：
//   ping                  → {pong: "bbb <ver>"}
//   project.new           → {files: [...]}
//   project.check         → {diagnostics: [...]}
//   project.run           → {ok, exit_code, output}
//   project.build         → {ok, exit_code, output}
//   templates             → {templates: [...]}
//   shutdown              → 退出服务
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"io"
	"log"
	"net"
	"os"
	"strings"
	"sync"

	"biolstudio/internal/biolang"
)

type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type rpcNotification struct {
	JSONRPC string `json:"jsonrpc"`
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

// params 解析辅助
func strParam(p json.RawMessage, key string) string {
	var m map[string]any
	if err := json.Unmarshal(p, &m); err != nil {
		return ""
	}
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func handle(method string, params json.RawMessage) (any, *rpcError) {
	switch method {
	case "ping":
		return map[string]string{"pong": "bbb " + biolang.Version()}, nil

	case "project.new":
		name := strParam(params, "name")
		tpl := strParam(params, "template")
		base := strParam(params, "base")
		if name == "" {
			return nil, &rpcError{Code: -32602, Message: "name required"}
		}
		if tpl == "" {
			tpl = "hello"
		}
		if base == "" {
			base = "."
		}
		res, err := biolang.ScaffoldProject(name, tpl, base)
		if err != nil {
			return nil, &rpcError{Code: -32000, Message: err.Error()}
		}
		return res, nil

	case "project.check":
		root := strParam(params, "root")
		if root == "" {
			return nil, &rpcError{Code: -32602, Message: "root required"}
		}
		diags, err := biolang.CheckProject(root)
		if err != nil {
			// 检查失败视为空诊断（功能层多数错误是诊断形式）
			return map[string]any{"diagnostics": []biolang.Diagnostic{}, "error": err.Error()}, nil
		}
		return map[string]any{"diagnostics": diags}, nil

	case "project.run":
		root := strParam(params, "root")
		if root == "" {
			return nil, &rpcError{Code: -32602, Message: "root required"}
		}
		r := biolang.RunProject(root)
		return r, nil

	case "project.build":
		root := strParam(params, "root")
		if root == "" {
			return nil, &rpcError{Code: -32602, Message: "root required"}
		}
		r := biolang.BuildProject(root)
		return r, nil

	case "templates":
		ts, err := biolang.ListTemplates()
		if err != nil {
			return nil, &rpcError{Code: -32000, Message: err.Error()}
		}
		return map[string]any{"templates": ts}, nil

	case "shutdown":
		return map[string]string{"bye": "ok"}, nil

	default:
		return nil, &rpcError{Code: -32601, Message: "method not found: " + method}
	}
}

// serve 处理一个连接（stdio 或 TCP）。
func serve(r io.Reader, w io.Writer, shutdown *bool, mu *sync.Mutex) {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	enc := json.NewEncoder(w)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var req rpcRequest
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			_ = enc.Encode(rpcResponse{
				JSONRPC: "2.0",
				ID:      nil,
				Error:   &rpcError{Code: -32700, Message: "parse error"},
			})
			continue
		}
		if req.Method == "" {
			_ = enc.Encode(rpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error:   &rpcError{Code: -32600, Message: "invalid request"},
			})
			continue
		}
		result, rpcErr := handle(req.Method, req.Params)
		// 通知类（无 id）不回复
		if len(req.ID) == 0 || string(req.ID) == "null" {
			if req.Method == "shutdown" {
				mu.Lock()
				*shutdown = true
				mu.Unlock()
				return
			}
			continue
		}
		resp := rpcResponse{JSONRPC: "2.0", ID: req.ID, Result: result}
		if rpcErr != nil {
			resp.Result = nil
			resp.Error = rpcErr
		}
		_ = enc.Encode(resp)
	}
}

func main() {
	tcpAddr := flag.String("tcp", "", "listen address, e.g. 127.0.0.1:47011 (empty = stdio)")
	flag.Parse()

	log.SetPrefix("[biolstudio-server] ")
	log.SetFlags(log.LstdFlags)

	if *tcpAddr != "" {
		ln, err := net.Listen("tcp", *tcpAddr)
		if err != nil {
			log.Fatalf("listen %s: %v", *tcpAddr, err)
		}
		log.Printf("listening on %s", *tcpAddr)
		var shutdown bool
		var mu sync.Mutex
		for {
			conn, err := ln.Accept()
			if err != nil {
				log.Printf("accept: %v", err)
				continue
			}
			go func() {
				defer conn.Close()
				serve(conn, conn, &shutdown, &mu)
			}()
			mu.Lock()
			done := shutdown
			mu.Unlock()
			if done {
				ln.Close()
				return
			}
		}
	}

	// stdio 模式（默认）
	log.Printf("biolstudio server %s ready (stdio)", biolang.Version())
	var shutdown bool
	var mu sync.Mutex
	serve(os.Stdin, os.Stdout, &shutdown, &mu)
}
