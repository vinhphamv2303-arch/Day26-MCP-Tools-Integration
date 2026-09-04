"""Google ADK agent backed by tools discovered from a remote MCP server."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

connection_params = StreamableHTTPConnectionParams(
    url=MCP_SERVER_URL,
    timeout=30.0,
)

# McpToolset lets ADK initialize the MCP session and discover the server's
# tools at runtime. The client intentionally does not duplicate tool schemas.
weather_tools = McpToolset(connection_params=connection_params)

root_agent = Agent(
    name="weather_agent",
    model=os.getenv("ADK_MODEL", "gemini-3.6-flash"),
    instruction=(
        "You are a weather assistant. For current weather questions, use the "
        "discovered get_current_weather tool. For forecast questions, use the "
        "discovered get_forecast tool with the requested city and number of days. "
        "Use health_check only when checking MCP server availability. Never invent "
        "live weather data. If the MCP server or WeatherAPI fails, clearly say that "
        "live weather data could not be retrieved and explain the failure briefly. "
        "For non-weather requests, answer normally without calling weather tools."
    ),
    tools=[weather_tools],
)

logger.info("Weather agent configured with MCP server URL: %s", MCP_SERVER_URL)
