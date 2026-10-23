import json
import os
import tempfile
import unittest

from mcp_testbench.report import render_text, to_json, write_json

SAMPLE = {
    "suite": "demo",
    "server": {"name": "fake", "version": "0.1.0"},
    "protocol_version": "2024-11-05",
    "schema_issues": ["tool 'x': missing 'inputSchema'"],
    "total": 2,
    "passed": 1,
    "failed": 1,
    "errored": 0,
    "results": [
        {"name": "ok case", "tool": "echo", "status": "pass",
         "detail": "", "duration_ms": 1.0, "repeats": 1, "checks": []},
        {"name": "bad case", "tool": "add", "status": "fail",
         "detail": "expected 'success' x1, got error",
         "duration_ms": 2.0, "repeats": 1, "checks": []},
    ],
}


class ReportTest(unittest.TestCase):
    def test_render_text(self):
        text = render_text(SAMPLE)
        self.assertIn("[PASS] ok case", text)
        self.assertIn("[FAIL] bad case", text)
        self.assertIn("expected 'success'", text)
        self.assertIn("2 cases: 1 passed, 1 failed, 0 errored", text)
        self.assertIn("missing 'inputSchema'", text)

    def test_json_roundtrip(self):
        parsed = json.loads(to_json(SAMPLE))
        self.assertEqual(parsed["suite"], "demo")
        self.assertEqual(len(parsed["results"]), 2)

    def test_write_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        write_json(SAMPLE, path)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["failed"], 1)


if __name__ == "__main__":
    unittest.main()
