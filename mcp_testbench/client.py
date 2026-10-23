"""Minimal MCP client over the stdio transport.

MCP stdio framing is newline-delimited JSON-RPC 2.0: each message is a
single JSON object on one line, written to the server's stdin and read
back from its stdout. This client implements just enough of the protocol
for testing: initialize handshake, tools/list and tools/call.

Protocol assumption: the client offers PROTOCOL_VERSION and accepts
whatever protocol version the server returns. Requests/responses are
matched by id; server-to-client notifications are ignored.
"""

import json
import os
import queue
import shlex
import subprocess
import threading

PROTOCOL_VERSION = "2024-11-05"


def split_command(command):
    """Split a server command string into argv.

    On Windows backslashes must survive (paths like C:\\Python\\python.exe),
    so the POSIX quoting rules are disabled and surrounding quotes are
    stripped instead.
    """
    if os.name == "nt":
        return [token.strip("\"'")
                for token in shlex.split(command, posix=False)]
    return shlex.split(command)


class McpError(Exception):
    """Base error for transport and protocol failures."""


class RpcError(McpError):
    """The server returned a JSON-RPC error response."""

    def __init__(self, code, message):
        super().__init__(f"RPC error {code}: {message}")
        self.code = code
        self.message = message


class McpTimeout(McpError):
    """No response was received within the requested timeout.

    After a timeout the message stream may be out of sync (a late
    response could arrive later), so the client must be closed and a
    fresh one started.
    """


class StdioMcpClient:
    """Synchronous client that spawns an MCP server as a subprocess."""

    def __init__(self, command, startup_timeout=10.0):
        if isinstance(command, str):
            argv = split_command(command)
        else:
            argv = list(command)
        if not argv:
            raise McpError("empty server command")
        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise McpError(f"server command not found: {argv[0]!r}") from exc
        self._messages = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._next_id = 0
        self.server_info = {}
        self.protocol_version = None
        self._initialize(startup_timeout)

    def _read_loop(self):
        try:
            for line in self._proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._messages.put(json.loads(line))
                except json.JSONDecodeError:
                    # Non-JSON noise on stdout is not a protocol message.
                    continue
        except (ValueError, OSError):
            pass
        self._messages.put(None)  # EOF sentinel

    def _send(self, payload):
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise McpError(f"server process closed its stdin: {exc}") from exc

    def _request(self, method, params, timeout):
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method,
                    "params": params})
        while True:
            try:
                message = self._messages.get(timeout=timeout)
            except queue.Empty:
                raise McpTimeout(
                    f"no response to {method!r} within {timeout}s")
            if message is None:
                raise McpError("server closed stdout (process exited?)")
            # Skip notifications and responses for other ids.
            if not isinstance(message, dict) or message.get("id") != request_id:
                continue
            if "error" in message and message["error"] is not None:
                err = message["error"]
                raise RpcError(err.get("code", -1),
                               err.get("message", "unknown error"))
            return message.get("result", {})

    def _notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _initialize(self, timeout):
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcp-testbench", "version": "0.1.0"},
        }, timeout)
        self.protocol_version = result.get("protocolVersion", PROTOCOL_VERSION)
        self.server_info = result.get("serverInfo", {})
        self._notify("notifications/initialized")

    def list_tools(self, timeout=10.0):
        result = self._request("tools/list", {}, timeout)
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise McpError("tools/list result has no 'tools' array")
        return tools

    def call_tool(self, name, arguments, timeout=10.0):
        """Call a tool. Returns the raw result dict (content, isError...)."""
        return self._request(
            "tools/call", {"name": name, "arguments": arguments}, timeout)

    def close(self):
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
