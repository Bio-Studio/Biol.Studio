# Biol.Studio Go 层构建
#   make server   — 通讯层（JSON-RPC over stdio / -tcp）
#   make gui      — 渲染层（Fyne GUI）
#   make test     — Go 测试（internal + server）
#   make all      — 全部构建 + 测试

GO ?= go

.PHONY: all server gui test clean

all: server gui test

server:
	$(GO) build -o server/biolstudio-server ./server

gui:
	$(GO) build -o gui/biolstudio-gui ./gui

test:
	$(GO) test ./internal/... ./server/

clean:
	rm -f server/biolstudio-server gui/biolstudio-gui
