# Biol.Studio

A toolbox for writing **BiuBiuBiu** projects quickly. Three layers:

| Layer | Language | Status | Responsibility |
|---|---|---|---|
| Functional (business) | Python | ✅ done | project scaffolding, lexer/checker, `bbb` CLI driver (`biolstudio/`) |
| Communication | Go | ✅ done | JSON-RPC 2.0 service (stdio / TCP), tasks, protocol v0.1 (`go/server/`) |
| Rendering | Go | ✅ done | Fyne GUI: project tree, multi-tab editor, output panel (`go/gui/`) |

Roadmap details: [PLAN.md](PLAN.md).

## Layers

### Python functional layer (business logic)

Pure standard library (≥3.10). Every capability is a stateless CLI command,
callable directly or wrapped by the Go layers:

```bash
biolstudio new myapp -t project     # scaffold (supports --json)
biolstudio check myapp --json       # static check as JSON diagnostics
biolstudio run myapp                # run via bbb
biolstudio build myapp              # build via bbb
biolstudio templates --json         # templates as JSON
```

### Go communication layer

JSON-RPC 2.0 over **stdio** (default, embeddable in editors) or **TCP**
(`-tcp 127.0.0.1:port`). Methods match the CLI subcommands one-to-one
(protocol v0.1, see `biolstudio/comm.py`):

```bash
cd go && make server
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
  '{"jsonrpc":"2.0","id":2,"method":"project.new","params":{"name":"myapp","template":"hello","base":"/tmp"}}' \
  '{"jsonrpc":"2.0","id":3,"method":"project.run","params":{"root":"/tmp/myapp"}}' \
  '{"jsonrpc":"2.0","id":4,"method":"shutdown"}' \
  | ./server/biolstudio-server
```

Methods: `ping` · `project.new` · `project.check` · `project.run` ·
`project.build` · `templates` · `shutdown`.

### Go rendering layer

Fyne GUI (`go/gui`):

```bash
cd go && make gui && ./gui/biolstudio-gui
```

- Project tree (src/ + utils/ + package.toml), multi-tab editor
- Run / build / check actions with live output panel
- Template-based project wizard

## Install / Run

```bash
# Python layer (run directly, no install)
python3 -m biolstudio doctor

# Or install as a command (uv / pip)
uv pip install -e .
biolstudio doctor
```

Dependencies: **pure Python standard library** (≥3.10) for the functional
layer; **Go ≥ 1.26 + Fyne** for the Go layers. Running/building needs the
`bbb` binary (auto-detected: `BBB_BIN` env → PATH `bbb` → `bio`).

## Usage

```bash
# Scaffold a project from a template (hello / project / requests / classes / threads)
biolstudio new myapp -t project

# Static check (lexer + structure, no bbb needed)
biolstudio check myapp

# Run / build
biolstudio run myapp
biolstudio build myapp

# Other
biolstudio templates       # list templates
biolstudio tokens x.bio    # debug: token stream
biolstudio doctor          # environment check
```

## Layout

```
biolstudio/
  cli.py       # argparse entry (new/check/run/build/tokens/doctor)
  lexer.py     # BiuBiuBiu lexer (pure Python, token stream for check/highlight)
  checker.py   # structural check: balance, program/Main contract, need matching
  templates.py # template system (templates/ dir, BIOLSTUDIO_TEMPLATES to add)
  project.py   # project model + minimal TOML parser for package.toml
  runner.py    # bbb binary driver (run/build, dry-run preview)
  comm.py      # communication-layer placeholder (protocol draft v0.1)
  render.py    # rendering-layer placeholder (view contract)
templates/     # built-in templates (hello/project/requests/classes/threads)
tests/         # unittest — `python3 -m unittest discover -s tests`
```

## Known limits

- `biolstudio build` relies on bbb's compile mode; the legacy `bin/bio` build
  mode is broken (its `src/` was removed during the MPS migration). The Rust
  LLVM backend (`bbb llvm`) restores compile capability.
- The checker is token-stream level structural checking, not full semantic
  analysis (the complete parser lives in the Rust implementation).

## License

[MIT](LICENSE)
