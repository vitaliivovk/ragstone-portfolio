"""Minimal stdlib HTTP MCP-shaped server (scaffold — not full MCP SDK).

Routes:
  GET  /health
  POST /mcp   — JSON-RPC: initialize | tools/list | tools/call | ping

No Microsoft Graph. Tool handlers return stub payloads after scope checks.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

from mcp_plugins.common.audit import format_mcp_tool_audit
from mcp_plugins.common.policy import (
    ScopeDenied,
    ToolScope,
    V1_DEFAULT_POLICY,
    enforce_scope,
    resolve_tool_scope,
)

ToolHandler = Callable[[Mapping[str, Any], Mapping[str, str]], Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    scope: ToolScope
    input_schema: Mapping[str, Any]
    handler: ToolHandler


def _stub_ok(message: str, **extra: Any) -> Dict[str, Any]:
    return {"stub": True, "message": message, **extra}


def build_default_tools() -> List[ToolSpec]:
    def health_echo(arguments: Mapping[str, Any], _headers: Mapping[str, str]) -> Any:
        return _stub_ok("template health tool", echo=arguments.get("text", ""))

    return [
        ToolSpec(
            name="template_ping",
            description="No-op health tool for MCP wiring smoke tests.",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            handler=health_echo,
        ),
        ToolSpec(
            name="template_forbidden_send",
            description="Example tool marked SEND — always denied in v1.",
            scope=ToolScope.SEND,
            input_schema={"type": "object", "properties": {}},
            handler=lambda _a, _h: _stub_ok("should never run"),
        ),
    ]


class McpHttpServer:
    """Threading HTTP server exposing /health and /mcp."""

    def __init__(
        self,
        *,
        plugin_name: str,
        tools: Sequence[ToolSpec],
        host: str = "127.0.0.1",
        port: int = 8090,
        allowed_scopes=None,
    ) -> None:
        self.plugin_name = plugin_name
        self.host = host
        self.port = port
        self.allowed_scopes = (
            V1_DEFAULT_POLICY if allowed_scopes is None else frozenset(allowed_scopes)
        )
        self._tools: Dict[str, ToolSpec] = {t.name: t for t in tools}
        self._catalog = {t.name: t.scope for t in tools}

    def serve_forever(self) -> None:
        plugin = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:  # quieter than default
                return

            def _read_json(self) -> Any:
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))

            def _write_json(self, code: int, body: Any) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/health":
                    self._write_json(
                        200,
                        {
                            "status": "ok",
                            "plugin": plugin.plugin_name,
                            "tools": sorted(plugin._tools),
                        },
                    )
                    return
                self._write_json(404, {"error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path != "/mcp":
                    self._write_json(404, {"error": "not_found"})
                    return
                try:
                    req = self._read_json()
                except json.JSONDecodeError:
                    self._write_json(
                        400,
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"},
                        },
                    )
                    return
                resp = plugin.handle_rpc(
                    req, headers={k.lower(): v for k, v in self.headers.items()}
                )
                self._write_json(200, resp)

        httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        print(
            f"[mcp-plugins] {self.plugin_name} listening on http://{self.host}:{self.port} "
            f"(GET /health, POST /mcp)",
            flush=True,
        )
        httpd.serve_forever()

    def handle_rpc(self, req: Mapping[str, Any], headers: Mapping[str, str]) -> Dict[str, Any]:
        req_id = req.get("id")
        method = req.get("method") or ""
        params = req.get("params") or {}
        if not isinstance(params, Mapping):
            params = {}

        if method in ("initialize", "notifications/initialized"):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.plugin_name, "version": "0.1.0-stub"},
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            tools_out = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": dict(t.input_schema),
                    "_meta": {"scope": t.scope.value},
                }
                for t in self._tools.values()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_out}}

        if method == "tools/call":
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, Mapping):
                arguments = {}
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": self._call_tool(name, arguments, headers),
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def _call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        user_oid = headers.get("x-user-id") or headers.get("x-librechat-user-openidid") or ""
        tenant_id = headers.get("x-tenant-id") or ""
        conversation_id = headers.get("x-conversation-id") or ""

        try:
            scope = resolve_tool_scope(name, self._catalog)
            enforce_scope(name, scope, self.allowed_scopes)
            spec = self._tools[name]
            payload = spec.handler(arguments, headers)
            status = "stub"
            is_error = False
            text = json.dumps(payload, ensure_ascii=False)
        except ScopeDenied as exc:
            status = "denied"
            is_error = True
            text = json.dumps({"error": "scope_denied", "reason": exc.reason, "tool": name})
            scope = exc.scope
        except Exception as exc:  # noqa: BLE001 — surface as tool error for scaffold
            status = "error"
            is_error = True
            text = json.dumps({"error": type(exc).__name__, "message": str(exc)})
            scope = self._catalog.get(name, ToolScope.READ)

        duration_ms = int((time.perf_counter() - started) * 1000)
        line = format_mcp_tool_audit(
            plugin=self.plugin_name,
            tool=name,
            scope=scope.value if isinstance(scope, ToolScope) else str(scope),
            status=status,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            user_oid=user_oid,
            conversation_id=conversation_id,
            detail={"stub": True} if status == "stub" else {"reason": status},
        )
        print(line, flush=True)

        return {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        }


def main(
    *,
    plugin_name: str = "template",
    tools: Optional[Sequence[ToolSpec]] = None,
    host: str = "127.0.0.1",
    port: int = 8090,
) -> None:
    server = McpHttpServer(
        plugin_name=plugin_name,
        tools=list(tools) if tools is not None else build_default_tools(),
        host=host,
        port=port,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
