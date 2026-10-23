"""Command-line interface.

Subcommands:
  list      connect and print the server's tools and schemas
  validate  list tools and run structural schema checks
  run       execute a YAML/JSON test suite against the server

Exit codes: 0 = ok / all tests passed, 1 = schema issues or test
failures, 2 = usage, config or connection error.
"""

import argparse
import json
import sys

from .client import McpError, StdioMcpClient
from .config import ConfigError, load_suite
from .report import render_text, write_json
from .runner import run_suite
from .schema import validate_tools


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mcp-testbench",
        description="Contract and reliability test harness for MCP servers "
                    "(stdio transport).")
    parser.add_argument("--version", action="version",
                        version="%(prog)s 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "validate", "run"):
        p = sub.add_parser(name)
        p.add_argument("--server", required=True,
                       help="command that starts the MCP server, e.g. "
                            "'python examples/fake_server.py'")
    sub.choices["run"].add_argument(
        "--tests", required=True, help="YAML (or JSON) test-suite file")
    sub.choices["run"].add_argument(
        "--json-report", metavar="PATH",
        help="also write the full report as JSON to PATH")

    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            return _cmd_list(args)
        if args.command == "validate":
            return _cmd_validate(args)
        return _cmd_run(args)
    except McpError as exc:
        print(f"error: cannot talk to server: {exc}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _connect(args):
    return StdioMcpClient(args.server)


def _cmd_list(args):
    client = _connect(args)
    try:
        tools = client.list_tools()
    finally:
        client.close()
    print(f"server: {client.server_info.get('name', '?')} "
          f"{client.server_info.get('version', '?')} "
          f"(protocol {client.protocol_version})")
    print(f"{len(tools)} tool(s):")
    for tool in tools:
        name = tool.get("name", "?") if isinstance(tool, dict) else "?"
        description = ""
        if isinstance(tool, dict):
            description = tool.get("description") or ""
        print(f"\n  {name}")
        if description:
            print(f"    {description}")
        schema = tool.get("inputSchema") if isinstance(tool, dict) else None
        print("    inputSchema: "
              + json.dumps(schema, ensure_ascii=False))
    return 0


def _cmd_validate(args):
    client = _connect(args)
    try:
        tools = client.list_tools()
    finally:
        client.close()
    issues = validate_tools(tools)
    print(f"server: {client.server_info.get('name', '?')} "
          f"{client.server_info.get('version', '?')} "
          f"(protocol {client.protocol_version})")
    if not issues:
        print(f"{len(tools)} tool(s): no schema issues found")
        return 0
    print(f"{len(issues)} schema issue(s):")
    for issue in issues:
        print(f"  - {issue}")
    print("note: a schema-valid server is not necessarily a safe server; "
          "run behavioral tests too.")
    return 1


def _cmd_run(args):
    suite = load_suite(args.tests)

    def factory():
        return StdioMcpClient(args.server)

    # Connect once up front to collect server info and validate schemas.
    probe = factory()
    try:
        tools = probe.list_tools()
        server_info = probe.server_info
        protocol_version = probe.protocol_version
    finally:
        probe.close()
    schema_issues = validate_tools(tools)

    known_tools = {t.get("name") for t in tools if isinstance(t, dict)}
    unknown = sorted({c["tool"] for c in suite["tests"]} - known_tools)
    if unknown:
        print(f"warning: suite references tools the server does not "
              f"advertise: {', '.join(unknown)}", file=sys.stderr)

    report = run_suite(suite, factory)
    report["server"] = server_info
    report["protocol_version"] = protocol_version
    report["schema_issues"] = schema_issues

    print(render_text(report))
    if args.json_report:
        write_json(report, args.json_report)
        print(f"\nJSON report written to {args.json_report}")
    return 0 if report["failed"] == 0 and report["errored"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
