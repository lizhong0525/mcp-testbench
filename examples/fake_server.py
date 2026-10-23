#!/usr/bin/env python3
"""Fake reference MCP server (stdio, newline-delimited JSON-RPC 2.0).

Exists so the MCP TestBench suite runs fully offline. It implements the
initialize handshake, tools/list and tools/call with a small set of
tools designed to exercise every test category:

  echo        returns the given text
  add         returns the sum of two numbers
  slow        sleeps for delay_ms before answering (timeout testing)
  big_output  returns a large text payload (oversized-output testing)
  counter     stateful; increments on every call (repeated-call testing)

Arguments are validated against each tool's inputSchema; violations
produce a JSON-RPC -32602 (invalid params) error, mirroring real MCP
SDK behavior.
"""

import json
import sys
import time

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "echo",
        "description": "Return the given text unchanged.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "add",
        "description": "Return the sum of two numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "slow",
        "description": "Sleep for delay_ms milliseconds, then answer.",
        "inputSchema": {
            "type": "object",
            "properties": {"delay_ms": {"type": "integer"}},
            "required": ["delay_ms"],
        },
    },
    {
        "name": "big_output",
        "description": "Return a text payload of 'size' characters.",
        "inputSchema": {
            "type": "object",
            "properties": {"size": {"type": "integer"}},
            "required": ["size"],
        },
    },
    {
        "name": "counter",
        "description": "Increment an internal counter and return it.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
}


class InvalidParams(Exception):
    pass


def validate_arguments(tool, arguments):
    schema = tool["inputSchema"]
    if not isinstance(arguments, dict):
        raise InvalidParams("arguments must be an object")
    for field in schema.get("required", []):
        if field not in arguments:
            raise InvalidParams(f"missing required field: {field!r}")
    for field, value in arguments.items():
        prop = schema.get("properties", {}).get(field)
        if prop is None:
            continue  # additionalProperties are tolerated
        check = _TYPE_CHECKS.get(prop.get("type"))
        if check is not None and not check(value):
            raise InvalidParams(
                f"field {field!r} must be of type {prop['type']}")


def text_result(text, is_error=False):
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


STATE = {"counter": 0}


def call_tool(name, arguments):
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if tool is None:
        raise InvalidParams(f"unknown tool: {name!r}")
    validate_arguments(tool, arguments)
    if name == "echo":
        return text_result(arguments["text"])
    if name == "add":
        return text_result(str(arguments["a"] + arguments["b"]))
    if name == "slow":
        time.sleep(arguments["delay_ms"] / 1000.0)
        return text_result("done")
    if name == "big_output":
        return text_result("x" * arguments["size"])
    if name == "counter":
        STATE["counter"] += 1
        return text_result(str(STATE["counter"]))
    raise InvalidParams(f"unknown tool: {name!r}")  # unreachable


def handle(request):
    method = request.get("method")
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake-mcp-server", "version": "0.1.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = request.get("params") or {}
        return call_tool(params.get("name"), params.get("arguments", {}))
    if method == "ping":
        return {}
    raise InvalidParams(f"unsupported method: {method!r}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in request:
            continue  # notification, e.g. notifications/initialized
        try:
            result = handle(request)
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "result": result}
        except InvalidParams as exc:
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "error": {"code": -32602, "message": str(exc)}}
        except Exception as exc:  # noqa: BLE001 - report as internal error
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "error": {"code": -32603, "message": str(exc)}}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
