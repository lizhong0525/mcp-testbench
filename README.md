# MCP TestBench

A contract and reliability test harness for MCP (Model Context Protocol) servers — for developers who need to verify that a server actually honors its advertised tool schemas before wiring it into an agent.

## Quickstart

From the repository root (the example paths below are relative to it):

```bash
pip install -r requirements.txt   # PyYAML; the only runtime dependency
python -m mcp_testbench run --server "python examples/fake_server.py" --tests examples/tests.yaml
```

PyYAML is the only third-party runtime dependency (if it is missing, suite files must be JSON — YAML files will not load). The suite above runs fully offline against the included fake server; no API keys, browsers or network access are needed.

The very first run prints a stderr warning that the suite references `nonexistent_tool`, which the fake server does not advertise. That is intentional: the demo suite includes a case proving the server rejects unknown tools.

## Demo walkthrough

The repo ships with a fake reference MCP server (stdio, newline-delimited JSON-RPC 2.0) exposing five tools: `echo`, `add`, `slow`, `big_output`, `counter`.

1. List the tools a server advertises:

   ```bash
   python -m mcp_testbench list --server "python examples/fake_server.py"
   ```

2. Check schema structure (required fields declared, properties typed, no duplicate names, ...):

   ```bash
   python -m mcp_testbench validate --server "python examples/fake_server.py"
   ```

3. Run the passing contract suite — covers valid inputs, invalid types, missing required fields, unknown tools, timeouts, oversized outputs and repeated calls:

   ```bash
   python -m mcp_testbench run --server "python examples/fake_server.py" --tests examples/tests.yaml --json-report report.json
   ```

   Exit code 0, prints a human-readable report and writes `report.json`.

4. See violations detected — `examples/failing_tests.yaml` contains three cases that intentionally fail (unexpected error, timeout, oversized output). Exit code 1:

   ```bash
   python -m mcp_testbench run --server "python examples/fake_server.py" --tests examples/failing_tests.yaml
   ```

## Writing your own suite

Suites are YAML (JSON works too — it is a YAML subset — and is the automatic fallback when PyYAML is not installed):

```yaml
name: my server contract
defaults:
  timeout_ms: 5000        # per-call timeout
  max_output_bytes: 100000  # optional output-size cap for every case
tests:
  - name: search works
    tool: search
    arguments: {query: "hello"}
    expect: success       # success | error | timeout
  - name: search rejects empty args
    tool: search
    arguments: {}
    expect: error
  - name: search is stable
    tool: search
    arguments: {query: "hello"}
    repeat: 10
    expect: success
```

Each case supports `timeout_ms` and `max_output_bytes` overrides. A case passes when every repetition matches `expect` and all checks hold. After a timeout the harness restarts the server connection before continuing, because a late response could desynchronize the stream.

Point `--server` at any MCP stdio server command, e.g. `"node my-server.js"` or `"uv run my_server"`.

## Features

- stdio transport MCP client (initialize handshake, `tools/list`, `tools/call`)
- structural schema validation of advertised tools
- test categories: valid inputs, invalid inputs, missing required fields, timeouts, oversized outputs, repeated calls
- YAML suite files with JSON fallback when PyYAML is unavailable
- human-readable console report plus `--json-report` machine-readable export
- exit codes: 0 = pass, 1 = failures / schema issues, 2 = config or connection error
- fake reference server so everything runs offline

## Safety model

- Only tools explicitly named in the loaded suite are ever called. The harness never probes or executes tools on its own beyond `initialize` and `tools/list`.
- A schema that passes `validate` is merely well formed — **a schema-valid server is not necessarily a safe server**. Always run behavioral tests before trusting one.

## Transport and protocol assumptions

- Transport: **stdio only** (newline-delimited JSON-RPC 2.0, one message per line). HTTP/SSE transports are not supported in v1.
- Protocol: the client offers protocol version `2024-11-05` and accepts whatever version the server returns; only the `tools` capability is exercised.
- On Windows, the `--server` command string is split on whitespace (quote paths containing spaces).

## Testing

```bash
python -m pytest -q      # or: python -m unittest discover -v
```

37 deterministic tests cover schema validation, suite parsing (including the JSON fallback), the runner against the real fake server, report rendering, and full CLI integration. No network access required.

## Known limitations

- stdio transport only; no HTTP/SSE
- no authentication, resources, prompts, or notification handling
- output-size check measures aggregated `text` content only
- after a timeout the server process is restarted, which resets any server-side state

## Roadmap

1. HTTP/SSE transport support
2. Response-content assertions (match output against expected values/patterns)
3. Latency budgets and percentile stats for repeated calls

## License

MIT — see LICENSE.
