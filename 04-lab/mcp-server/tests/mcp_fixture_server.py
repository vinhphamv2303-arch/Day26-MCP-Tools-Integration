from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP


def main() -> None:
    port = int(sys.argv[1])
    server = FastMCP("integration-fixture", host="127.0.0.1", port=port)

    @server.tool()
    async def get_current_weather(city: str) -> str:
        return f"fixture current weather for {city}"

    @server.tool()
    async def get_forecast(city: str, days: int = 3) -> str:
        return f"fixture forecast for {city} ({days} days)"

    @server.tool()
    async def health_check() -> str:
        return "fixture healthy"

    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
