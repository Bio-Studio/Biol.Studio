# Biol.Studio

A toolbox for writing **BiuBiuBiu** projects quickly. Current stage: **Python
functional-layer prototype** (v0.1.0).

## Layers

| Layer | Language | Status | Responsibility |
|---|---|---|---|
| Functional | Python | ✅ prototype | project scaffolding, lexer/checker, example gallery, `bbb` CLI driver |
| Communication | Go | ⏳ next | local service, task execution, event push (protocol draft in `biolstudio/comm.py`) |
| Rendering | Go | ⏳ next | project tree, highlighted editor, output panel, demo gallery (contract in `biolstudio/render.py`) |

Roadmap details: [PLAN.md](PLAN.md).

## Install / Run

```bash
# Run directly (no install)
cd Biol.Studio
python3 -m biolstudio.cli doctor

# Or install as a command (uv / pip)
uv pip install -e .
biolstudio doctor
```

Dependencies: **pure Python standard library** (≥3.10). Running/building needs
the `bbb` binary (auto-detected: `BBB_BIN` env → `~/Projects/bio/bin/bio` →
`bbb`/`bio` on PATH).

## Usage

```bash
# Scaffold a project from a template (hello / project / requests / classes / threads)
biolstudio new myapp -t project

# Static check (lexer + structure, no bbb needed)
biolstudio check myapp

# Run / build
biolstudio run myapp
biolstudio build myapp

# Example gallery (from the biu repo examples/, BIO_REPO overrides the path)
biolstudio demo list
biolstudio demo 2          # run 02-requests.bio

# Other
biolstudio templates       # list templates
biolstudio tokens x.bio    # debug: token stream
biolstudio doctor          # environment check
```

## Layout

```
biolstudio/
  cli.py       # argparse entry (new/check/run/build/demo/tokens/doctor)
  lexer.py     # BiuBiuBiu lexer (pure Python, token stream for check/highlight)
  checker.py   # structural check: balance, program/Main contract, need matching
  templates.py # template system (templates/ dir, BIOLSTUDIO_TEMPLATES to add)
  project.py   # project model + minimal TOML parser for package.toml
  runner.py    # bbb binary driver (run/build, dry-run preview)
  gallery.py   # example gallery (reads bio repo examples/)
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
