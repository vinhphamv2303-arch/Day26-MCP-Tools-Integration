#!/usr/bin/env python3
"""Verify the MCP protocol and tools exposed by the configured server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {
    "get_current_weather",
    "get_forecast",
    "health_check",
}


def _result_failed(result: Any) -> bool:
    return bool(getattr(result, "isError", False) or getattr(result, "is_error", False))


def _result_text(result: Any) -> str:
    parts: list[str] = []
    for content in getattr(result, "content", []) or []:
        text = getattr(content, "text", None)
        if text:
            parts.append(text)
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        parts.append(json.dumps(structured, ensure_ascii=False, default=str))
    return "\n".join(parts)


async def verify_mcp_server(
    server_url: str,
    *,
    city: str = "Hanoi",
    evidence_dir: Path | None = None,
) -> int:
    """Run a real initialize/list_tools/call_tool verification."""
    lines: list[str] = []
    tools_payload: list[dict[str, Any]] = []
    failure: str | None = None

    try:
        async with streamable_http_client(server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                lines.append("[PASS] MCP connection")

                tools_result = await session.list_tools()
                tools = list(getattr(tools_result, "tools", []) or [])
                tool_names = {tool.name for tool in tools}
                tools_payload = [
                    {
                        "name": tool.name,
                        "description": getattr(tool, "description", None),
                        "inputSchema": getattr(tool, "inputSchema", None)
                        or getattr(tool, "input_schema", None),
                    }
                    for tool in tools
                ]
                if tool_names != EXPECTED_TOOLS or len(tools) != len(EXPECTED_TOOLS):
                    failure = (
                        "list_tools: expected exactly 3 tools "
                        f"{sorted(EXPECTED_TOOLS)}, got {sorted(tool_names)}"
                    )
                else:
                    lines.append("[PASS] list_tools: 3 tools")

                    health_result = await session.call_tool("health_check", arguments={})
                    if _result_failed(health_result):
                        failure = f"health_check: {_result_text(health_result)}"
                    else:
                        lines.append("[PASS] health_check")
                        current_result = await session.call_tool(
                            "get_current_weather", arguments={"city": city}
                        )
                        current_text = _result_text(current_result)
                        if "key is not configured" in current_text.lower():
                            lines.append(
                                "[SKIP] get_current_weather: WEATHERAPI_KEY not configured"
                            )
                            lines.append(
                                "[SKIP] get_forecast: WEATHERAPI_KEY not configured"
                            )
                        elif _result_failed(current_result) or current_text.startswith("❌"):
                            failure = f"get_current_weather: {current_text}"
                        else:
                            lines.append("[PASS] get_current_weather")
                            forecast_result = await session.call_tool(
                                "get_forecast", arguments={"city": city, "days": 2}
                            )
                            forecast_text = _result_text(forecast_result)
                            if _result_failed(forecast_result) or forecast_text.startswith(
                                "❌"
                            ):
                                failure = f"get_forecast: {forecast_text}"
                            else:
                                lines.append("[PASS] get_forecast")
    except Exception as exc:
        lines.append(f"[FAIL] MCP connection: {type(exc).__name__}: {exc}")
        return_code = 1
    else:
        if failure is not None:
            lines.append(f"[FAIL] {failure}")
            return_code = 1
        else:
            return_code = 0

    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "mcp_tools.json").write_text(
            json.dumps(tools_payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "verify_setup.log").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    print("\n".join(lines))
    return return_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports",
        help="Directory for mcp_tools.json and verify_setup.log",
    )
    parser.add_argument(
        "--city",
        default=os.getenv("VERIFY_CITY", "Hanoi"),
        help="Real city used for optional WeatherAPI calls",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    load_dotenv()
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")
    args = parse_args()
    return asyncio.run(
        verify_mcp_server(
            server_url,
            city=args.city,
            evidence_dir=args.evidence_dir,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
