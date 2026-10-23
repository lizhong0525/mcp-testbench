"""Test-case execution engine.

Only tools explicitly named in the loaded suite are ever called. Nothing
is probed or executed automatically beyond the initialize handshake and
tools/list.
"""

import time

from .client import McpError, McpTimeout, RpcError

# Outcomes for a single call.
OUTCOME_SUCCESS = "success"   # result without isError
OUTCOME_ERROR = "error"       # RPC error or result with isError: true
OUTCOME_TIMEOUT = "timeout"   # no response within timeout_ms

# Case verdicts.
STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"  # harness-level failure (connection lost, etc.)


def run_suite(suite, client_factory):
    """Run every case in the suite.

    client_factory is a zero-argument callable returning a connected
    StdioMcpClient. A new client is created lazily after a timeout,
    because a timed-out stream can no longer be trusted.
    """
    state = {"client": None}

    def get_client():
        if state["client"] is None:
            state["client"] = client_factory()
        return state["client"]

    def drop_client():
        if state["client"] is not None:
            state["client"].close()
            state["client"] = None

    results = []
    for case in suite["tests"]:
        try:
            results.append(_run_case(case, suite["defaults"], get_client,
                                     drop_client))
        except McpError as exc:
            drop_client()
            results.append({
                "name": case["name"],
                "tool": case["tool"],
                "status": STATUS_ERROR,
                "detail": f"harness error: {exc}",
                "duration_ms": 0.0,
                "repeats": 0,
                "checks": [],
            })
    drop_client()

    return {
        "suite": suite["name"],
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == STATUS_PASS),
        "failed": sum(1 for r in results if r["status"] == STATUS_FAIL),
        "errored": sum(1 for r in results if r["status"] == STATUS_ERROR),
        "results": results,
    }


def _run_case(case, defaults, get_client, drop_client):
    expect = case.get("expect", "success")
    repeat = case.get("repeat", 1)
    timeout_ms = case.get("timeout_ms", defaults["timeout_ms"])
    max_output = case.get("max_output_bytes")
    if max_output is None:
        max_output = defaults.get("max_output_bytes")

    outcomes = []
    notes = []
    check_failures = []
    started = time.monotonic()
    for _ in range(repeat):
        client = get_client()
        outcome, note, output_bytes = _call_once(
            client, case["tool"], case.get("arguments", {}), timeout_ms)
        outcomes.append(outcome)
        if note:
            notes.append(note)
        if outcome == OUTCOME_SUCCESS and max_output is not None \
                and output_bytes > max_output:
            check_failures.append(
                f"output is {output_bytes} bytes, exceeds "
                f"max_output_bytes={max_output}")
        if outcome == OUTCOME_TIMEOUT:
            # Stream may desync after a timeout; force a fresh connection
            # for any later case, and stop repeating this one.
            drop_client()
            break

    duration_ms = round((time.monotonic() - started) * 1000.0, 1)

    failures = []
    if not outcomes or any(o != expect for o in outcomes):
        failures.append(
            f"expected {expect!r} x{repeat}, got "
            + (", ".join(outcomes) if outcomes else "<no call completed>"))
    problems = failures + check_failures
    return {
        "name": case["name"],
        "tool": case["tool"],
        "status": STATUS_PASS if not problems else STATUS_FAIL,
        "detail": "; ".join(problems) if problems else (notes[-1] if notes else ""),
        "duration_ms": duration_ms,
        "repeats": len(outcomes),
        "checks": check_failures,
    }


def _call_once(client, tool, arguments, timeout_ms):
    """Single tool call -> (outcome, note, output_bytes)."""
    timeout_s = timeout_ms / 1000.0
    try:
        result = client.call_tool(tool, arguments, timeout=timeout_s)
    except McpTimeout:
        return OUTCOME_TIMEOUT, f"no response within {timeout_ms}ms", 0
    except RpcError as exc:
        return OUTCOME_ERROR, f"RPC error {exc.code}: {exc.message}", 0
    output_bytes = _result_size(result)
    if result.get("isError"):
        return OUTCOME_ERROR, f"tool returned isError: {_result_text(result)}", \
            output_bytes
    return OUTCOME_SUCCESS, "", output_bytes


def _result_text(result):
    parts = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    return "".join(parts)


def _result_size(result):
    return len(_result_text(result).encode("utf-8"))
