"""Loading and structural validation of test-suite definitions.

Suites are written in YAML. If PyYAML is not installed, the loader falls
back to JSON (JSON is a subset of YAML, so a JSON suite file is always
valid). Suite shape:

    name: my suite
    defaults:
      timeout_ms: 5000        # per-call timeout, default 5000
      max_output_bytes: 100000  # output size check cap (optional)
    tests:
      - name: echo works
        tool: echo
        arguments: {text: hello}
        expect: success        # success | error | timeout
        repeat: 1              # optional; every repetition must pass
        timeout_ms: 2000       # optional per-case override
        max_output_bytes: 1000 # optional per-case check
"""

import json

try:
    import yaml
except ImportError:  # pragma: no cover - depends on environment
    yaml = None

VALID_EXPECTATIONS = ("success", "error", "timeout")
DEFAULT_TIMEOUT_MS = 5000


class ConfigError(Exception):
    """The suite file could not be read or has an invalid structure."""


def load_suite(path):
    """Load a suite file and return the validated suite dict."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ConfigError(f"cannot read suite file {path!r}: {exc}") from exc
    data = _parse(text, path)
    return validate_suite(data, source=path)


def _parse(text, path):
    if yaml is not None:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {path!r}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"PyYAML is not installed and {path!r} is not valid JSON: {exc}"
        ) from exc


def validate_suite(data, source="<suite>"):
    if not isinstance(data, dict):
        raise ConfigError(f"{source}: top level must be a mapping")
    tests = data.get("tests")
    if not isinstance(tests, list):
        raise ConfigError(f"{source}: missing 'tests' list")
    if not tests:
        raise ConfigError(f"{source}: 'tests' list is empty")
    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ConfigError(f"{source}: 'defaults' must be a mapping")
    for index, case in enumerate(tests):
        _validate_case(index, case, source)
    max_output = defaults.get("max_output_bytes")
    if max_output is not None:
        _positive_int(max_output, "defaults.max_output_bytes", source)
    return {
        "name": data.get("name") or "unnamed suite",
        "defaults": {
            "timeout_ms": _positive_int(
                defaults.get("timeout_ms", DEFAULT_TIMEOUT_MS),
                "defaults.timeout_ms", source),
            "max_output_bytes": max_output,
        },
        "tests": tests,
    }


def _validate_case(index, case, source):
    label = f"{source}: tests[{index}]"
    if not isinstance(case, dict):
        raise ConfigError(f"{label}: must be a mapping")
    if not isinstance(case.get("name"), str) or not case["name"]:
        raise ConfigError(f"{label}: missing 'name'")
    if not isinstance(case.get("tool"), str) or not case["tool"]:
        raise ConfigError(f"{label}: missing 'tool'")
    arguments = case.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ConfigError(f"{label}: 'arguments' must be a mapping")
    expect = case.get("expect", "success")
    if expect not in VALID_EXPECTATIONS:
        raise ConfigError(
            f"{label}: 'expect' must be one of {VALID_EXPECTATIONS}")
    _positive_int(case.get("repeat", 1), f"tests[{index}].repeat", source)
    if "timeout_ms" in case:
        _positive_int(case["timeout_ms"], f"tests[{index}].timeout_ms", source)
    if "max_output_bytes" in case and case["max_output_bytes"] is not None:
        _positive_int(case["max_output_bytes"],
                      f"tests[{index}].max_output_bytes", source)


def _positive_int(value, field, source):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{source}: {field} must be a positive integer")
    return value
