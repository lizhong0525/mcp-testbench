import json
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_SERVER = os.path.join(PROJECT_ROOT, "examples", "fake_server.py")
SERVER_CMD = f"{sys.executable} {FAKE_SERVER}"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "mcp_testbench", *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60)


class CliIntegrationTest(unittest.TestCase):
    def test_list(self):
        proc = run_cli("list", "--server", SERVER_CMD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("fake-mcp-server", proc.stdout)
        self.assertIn("echo", proc.stdout)
        self.assertIn("inputSchema", proc.stdout)

    def test_validate(self):
        proc = run_cli("validate", "--server", SERVER_CMD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no schema issues", proc.stdout)

    def test_run_passing_suite(self):
        suite = os.path.join(PROJECT_ROOT, "examples", "tests.yaml")
        proc = run_cli("run", "--server", SERVER_CMD, "--tests", suite)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("8 passed", proc.stdout)
        self.assertIn("0 failed", proc.stdout)

    def test_run_failing_suite_exit_1_and_json_report(self):
        suite = os.path.join(PROJECT_ROOT, "examples", "failing_tests.yaml")
        fd, report_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.addCleanup(os.unlink, report_path)
        proc = run_cli("run", "--server", SERVER_CMD, "--tests", suite,
                       "--json-report", report_path)
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        self.assertIn("3 failed", proc.stdout)
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["failed"], 3)
        self.assertEqual(report["server"]["name"], "fake-mcp-server")
        statuses = {r["name"]: r["status"] for r in report["results"]}
        self.assertTrue(all(s == "fail" for s in statuses.values()))

    def test_bad_server_command_exit_2(self):
        proc = run_cli("list", "--server", "not-a-real-command-xyz")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)

    def test_bad_suite_file_exit_2(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as handle:
            handle.write('{"tests": []}')
        self.addCleanup(os.unlink, path)
        proc = run_cli("run", "--server", SERVER_CMD, "--tests", path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("empty", proc.stderr)


if __name__ == "__main__":
    unittest.main()
