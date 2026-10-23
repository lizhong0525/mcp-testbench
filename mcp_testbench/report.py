"""Human-readable and JSON report rendering."""

import json

_ICONS = {"pass": "PASS", "fail": "FAIL", "error": "ERR "}


def render_text(report, schema_issues=None):
    lines = []
    lines.append(f"MCP TestBench - suite: {report['suite']}")
    server = report.get("server") or {}
    if server:
        lines.append(
            f"server: {server.get('name', '?')} "
            f"{server.get('version', '?')} "
            f"(protocol {report.get('protocol_version', '?')})")
    issues = schema_issues if schema_issues is not None \
        else report.get("schema_issues") or []
    if issues:
        lines.append(f"schema issues ({len(issues)}):")
        for issue in issues:
            lines.append(f"  - {issue}")
    lines.append("")
    for result in report["results"]:
        icon = _ICONS.get(result["status"], "????")
        line = (f"[{icon}] {result['name']} (tool: {result['tool']}, "
                f"{result['duration_ms']}ms")
        if result.get("repeats", 1) > 1:
            line += f", repeats: {result['repeats']}"
        line += ")"
        lines.append(line)
        if result.get("detail"):
            lines.append(f"       {result['detail']}")
    lines.append("")
    lines.append(
        f"{report['total']} cases: {report['passed']} passed, "
        f"{report['failed']} failed, {report['errored']} errored")
    return "\n".join(lines)


def to_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False)


def write_json(report, path):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(to_json(report))
        handle.write("\n")
