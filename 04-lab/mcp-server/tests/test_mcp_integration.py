from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


FIXTURE_SERVER = Path(__file__).with_name("mcp_fixture_server.py")


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest_asyncio.fixture
async def mcp_server_url():
    port = unused_port()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(FIXTURE_SERVER),
        str(port),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(50):
            try:
                async with streamable_http_client(url) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                break
            except Exception:
                await asyncio.sleep(0.1)
        else:
            pytest.fail("fixture MCP server did not become ready")
        yield url
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_streamable_http_discovery_and_calls(mcp_server_url):
    async with streamable_http_client(mcp_server_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            assert {tool.name for tool in result.tools} == {
                "get_current_weather",
                "get_forecast",
                "health_check",
            }

            health = await session.call_tool("health_check", arguments={})
            current = await session.call_tool(
                "get_current_weather", arguments={"city": "Hanoi"}
            )
            forecast = await session.call_tool(
                "get_forecast", arguments={"city": "Danang", "days": 2}
            )

            assert health.content[0].text == "fixture healthy"
            assert "Hanoi" in current.content[0].text
            assert "Danang" in forecast.content[0].text
