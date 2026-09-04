#!/usr/bin/env python3
"""Run optional ADK prompts and verify the model emitted MCP tool calls."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

APP_NAME = "weather_agent_smoke"
USER_ID = "lab04"
PROMPTS = (
    ("current weather", "Thời tiết hiện tại ở Hà Nội thế nào?", "get_current_weather"),
    ("forecast", "Dự báo thời tiết Đà Nẵng 2 ngày tới.", "get_forecast"),
)


async def run_prompt(
    runner: Any,
    session_service: Any,
    prompt: str,
    expected_tool: str,
) -> list[str]:
    from google.genai import types

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    tool_calls: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        for part in (event.content.parts if event.content else []):
            if part.function_call and part.function_call.name:
                tool_calls.append(part.function_call.name)
    if expected_tool not in tool_calls:
        raise RuntimeError(
            f"expected MCP tool {expected_tool!r}, observed {tool_calls!r}"
        )
    return tool_calls


async def run_smoke(evidence_path: Path) -> int:
    if not os.getenv("GOOGLE_API_KEY"):
        output = "[SKIP] ADK smoke: GOOGLE_API_KEY not configured\n"
        print(output, end="")
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(output, encoding="utf-8")
        return 0

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from weather_agent import root_agent

    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    lines: list[str] = []
    try:
        for label, prompt, expected_tool in PROMPTS:
            tool_calls = await run_prompt(
                runner, session_service, prompt, expected_tool
            )
            lines.append(f"[PASS] {label}: MCP tool call(s) {tool_calls}")
        return_code = 0
    except Exception as exc:
        lines.append(f"[FAIL] ADK smoke: {type(exc).__name__}: {exc}")
        return_code = 1

    output = "\n".join(lines) + "\n"
    print(output, end="")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(output, encoding="utf-8")
    return return_code


def main() -> int:
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / "adk_smoke.log",
    )
    args = parser.parse_args()
    return asyncio.run(run_smoke(args.evidence))


if __name__ == "__main__":
    raise SystemExit(main())
