import os
import sys
import unittest

from mcp_testbench.client import StdioMcpClient
from mcp_testbench.runner import run_suite

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_SERVER = os.path.join(PROJECT_ROOT, "examples", "fake_server.py")
SERVER_CMD = f"{sys.executable} {FAKE_SERVER}"


def make_suite(tests, defaults=None):
    return {
        "name": "test suite",
        "defaults": {"timeout_ms": 5000,
                     "max_output_bytes": (defaults or {}).get(
                         "max_output_bytes")},
        "tests": tests,
    }


class RunSuiteTest(unittest.TestCase):
    def run_cases(self, tests, defaults=None):
        return run_suite(make_suite(tests, defaults),
                         lambda: StdioMcpClient(SERVER_CMD))

    def test_success_case(self):
        report = self.run_cases([
            {"name": "echo ok", "tool": "echo",
             "arguments": {"text": "hi"}, "expect": "success"},
        ])
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["results"][0]["status"], "pass")

    def test_error_expectation_on_missing_field(self):
        report = self.run_cases([
            {"name": "missing field", "tool": "echo",
             "arguments": {}, "expect": "error"},
        ])
        self.assertEqual(report["passed"], 1)

    def test_failed_expectation(self):
        report = self.run_cases([
            {"name": "expect success but errors", "tool": "echo",
             "arguments": {}, "expect": "success"},
        ])
        self.assertEqual(report["failed"], 1)
        self.assertIn("expected 'success'",
                      report["results"][0]["detail"])

    def test_timeout_expectation_and_recovery(self):
        # The slow tool outlives the timeout; the next case must still
        # work because the harness reconnects after a timeout.
        report = self.run_cases([
            {"name": "slow times out", "tool": "slow",
             "arguments": {"delay_ms": 800}, "timeout_ms": 150,
             "expect": "timeout"},
            {"name": "echo still works", "tool": "echo",
             "arguments": {"text": "after"}, "expect": "success"},
        ])
        self.assertEqual(report["passed"], 2, report["results"])

    def test_oversized_output_fails_check(self):
        report = self.run_cases([
            {"name": "too big", "tool": "big_output",
             "arguments": {"size": 5000}, "max_output_bytes": 1000,
             "expect": "success"},
        ])
        result = report["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("exceeds" in c for c in result["checks"]))

    def test_repeated_calls(self):
        report = self.run_cases([
            {"name": "counter x3", "tool": "counter",
             "arguments": {}, "repeat": 3, "expect": "success"},
        ])
        result = report["results"][0]
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["repeats"], 3)

    def test_unknown_tool_yields_error_outcome(self):
        report = self.run_cases([
            {"name": "unknown", "tool": "nope",
             "arguments": {}, "expect": "error"},
        ])
        self.assertEqual(report["passed"], 1)

    def test_harness_error_when_server_unlaunchable(self):
        report = run_suite(
            make_suite([{"name": "c", "tool": "echo", "arguments": {}}]),
            lambda: StdioMcpClient("definitely-not-a-real-command-xyz"))
        self.assertEqual(report["errored"], 1)
        self.assertIn("harness error", report["results"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
