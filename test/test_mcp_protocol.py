"""MCP SSE 协议辅助逻辑测试。"""
import os
import sys
from types import SimpleNamespace

from starlette.requests import Request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.server import _get_mcp_base_url, _to_mcp_tool_result


def _request(headers):
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/mcp/sse",
        "raw_path": b"/mcp/sse",
        "query_string": b"",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "server": ("127.0.0.1", 3001),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_public_base_url_has_priority():
    cfg = SimpleNamespace(server=SimpleNamespace(public_base_url="https://configured.example.com/"))
    request = _request({"host": "internal:3001", "x-forwarded-proto": "http"})
    assert _get_mcp_base_url(request, cfg) == "https://configured.example.com"


def test_forwarded_https_is_used():
    cfg = SimpleNamespace(server=SimpleNamespace(public_base_url=None))
    request = _request({
        "host": "internal:3001",
        "x-forwarded-proto": "https",
        "x-forwarded-host": "gitmcp.example.com",
    })
    assert _get_mcp_base_url(request, cfg) == "https://gitmcp.example.com"


def test_tool_result_uses_mcp_content_shape():
    result = _to_mcp_tool_result({"repos": [{"id": 1, "name": "demo"}]})
    assert result["content"][0]["type"] == "text"
    assert '"repos"' in result["content"][0]["text"]


if __name__ == "__main__":
    test_public_base_url_has_priority()
    test_forwarded_https_is_used()
    test_tool_result_uses_mcp_content_shape()
    print("MCP 协议测试通过")
