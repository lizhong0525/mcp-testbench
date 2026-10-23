import json
import os
import tempfile
import unittest

from mcp_testbench import config
from mcp_testbench.config import ConfigError, load_suite

VALID_SUITE = {
    "name": "demo",
    "defaults": {"timeout_ms": 3000},
    "tests": [
        {"name": "case1", "tool": "echo",
         "arguments": {"text": "hi"}, "expect": "success"},
    ],
}


class LoadSuiteTest(unittest.TestCase):
    def _write(self, text, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_load_yaml(self):
        path = self._write(
            "name: demo\ntests:\n"
            "  - name: c1\n    tool: echo\n"
            "    arguments: {text: hi}\n    expect: success\n", ".yaml")
        suite = load_suite(path)
        self.assertEqual(suite["name"], "demo")
        self.assertEqual(len(suite["tests"]), 1)
        self.assertEqual(suite["defaults"]["timeout_ms"],
                         config.DEFAULT_TIMEOUT_MS)

    def test_load_json(self):
        path = self._write(json.dumps(VALID_SUITE), ".json")
        suite = load_suite(path)
        self.assertEqual(suite["defaults"]["timeout_ms"], 3000)

    def test_json_fallback_when_pyyaml_missing(self):
        saved = config.yaml
        config.yaml = None
        try:
            path = self._write(json.dumps(VALID_SUITE), ".json")
            suite = load_suite(path)
            self.assertEqual(suite["name"], "demo")
            bad = self._write("name: demo\ntests: [unclosed", ".yaml")
            with self.assertRaises(ConfigError):
                load_suite(bad)
        finally:
            config.yaml = saved

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_suite("does/not/exist.yaml")

    def test_malformed_yaml(self):
        path = self._write("tests: [unclosed\n", ".yaml")
        with self.assertRaises(ConfigError):
            load_suite(path)

    def test_missing_tests_key(self):
        path = self._write(json.dumps({"name": "x"}), ".json")
        with self.assertRaisesRegex(ConfigError, "tests"):
            load_suite(path)

    def test_empty_tests_list(self):
        path = self._write(json.dumps({"tests": []}), ".json")
        with self.assertRaisesRegex(ConfigError, "empty"):
            load_suite(path)

    def test_bad_expectation(self):
        suite = {"tests": [{"name": "c", "tool": "t", "expect": "boom"}]}
        path = self._write(json.dumps(suite), ".json")
        with self.assertRaisesRegex(ConfigError, "expect"):
            load_suite(path)

    def test_missing_tool(self):
        suite = {"tests": [{"name": "c"}]}
        path = self._write(json.dumps(suite), ".json")
        with self.assertRaisesRegex(ConfigError, "tool"):
            load_suite(path)

    def test_bad_repeat(self):
        suite = {"tests": [{"name": "c", "tool": "t", "repeat": 0}]}
        path = self._write(json.dumps(suite), ".json")
        with self.assertRaisesRegex(ConfigError, "positive integer"):
            load_suite(path)


if __name__ == "__main__":
    unittest.main()
