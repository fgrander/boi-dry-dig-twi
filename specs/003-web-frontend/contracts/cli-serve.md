# Contract: `boidrytwin serve`

**Covers**: FR-020, research R10

```text
boidrytwin serve [--runs DIR] [--scenarios DIR] [--examples DIR] [--port N] [--no-browser]
                 [--log-format json|console] [--log-level LEVEL]
```

| Option | Default | Meaning |
|---|---|---|
| `--runs` | `runs` | run folders; the app folder is `<runs>/.app/` |
| `--scenarios` | `scenarios` | saved and operator scenarios (created if missing) |
| `--examples` | `examples` | read-only example scenarios |
| `--port` | `8765` | port on `127.0.0.1` |
| `--no-browser` | off | do not open the browser |

Behaviour:
- Starts the web server on `127.0.0.1:<port>` and one worker process, applies the restart rules
  to the queue, prints `serving http://127.0.0.1:<port>` on stdout, and opens the browser unless
  `--no-browser`.
- `Ctrl+C` stops the server and the worker. A run in progress is marked `interrupted`.
- Exit codes: 0 after a normal stop; 1 if a folder option is invalid; 3 if the port is busy or the
  server fails to start (message on stderr).
- Requires the optional extra: `uv sync --extra web` (or `pip install boidrytwin[web]`).
  Without it, `serve` exits with code 1 and says which extra to install. The other commands
  work without it.
