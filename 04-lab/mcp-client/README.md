# Weather Agent - Google ADK with MCP Server

AI agent built with **Google Agent Development Kit (ADK)** that uses tools from a local **MCP server** via Streamable HTTP transport.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│   User Browser  │ ───> │  ADK Web UI      │ ───> │  Weather Agent      │
│   localhost:8000│      │  (Google ADK)    │      │  (Agent with MCP)   │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
                                                             │
                                                             │ Streamable HTTP
                                                             ▼
                                                   ┌─────────────────────┐
                                                   │  MCP Server         │
                                                   │  localhost:8085/mcp │
                                                   │  FastMCP + Tools    │
                                                   └─────────────────────┘
                                                             │
                                                             ▼
                                                   ┌─────────────────────┐
                                                   │  WeatherAPI.com     │
                                                   └─────────────────────┘
```

## Features

- **Remote MCP Tools**: Connects to MCP server via Streamable HTTP
- **3 Weather Tools**:
  - `get_current_weather(city)` - Real-time weather conditions
  - `get_forecast(city, days)` - Weather forecast up to 3 days
  - `health_check()` - Server health verification
- **Web Interface**: UI via ADK web
- **Streaming Responses**: Real-time AI responses

## Quick Start

### 1. Start the MCP Server

```bash
cd ../mcp-server
cp .env.example .env
# Set WEATHERAPI_KEY in .env
uv run python weather.py
```

### 2. Setup Environment

```bash
cd mcp-client

# Create .env from .env.example
cp .env.example .env
# Set GOOGLE_API_KEY and MCP_SERVER_URL in .env
```

### 3. Install Dependencies

```bash
uv sync --dev
```

Verify MCP initialize, discovery, and tool calls before starting ADK:

```bash
uv run python verify_setup.py
```

### 4. Run the Agent

```bash
uv run adk web
```

Optional ADK smoke test (requires `GOOGLE_API_KEY` and a running MCP server):

```bash
uv run python adk_smoke.py
```

### 5. Use the Agent

1. Open browser: http://localhost:8000
2. Select `weather_agent` from dropdown
3. Ask questions like:
   - "What's the weather in Brisbane?"
   - "Give me a 3-day forecast for Tokyo"
   - "How's the weather in New York?"

## Project Structure

```
mcp-client/
├── weather_agent/
│   ├── agent.py           # Main agent with MCP connection
│   └── __init__.py
├── pyproject.toml
├── .env                   # Environment variables (create this)
└── README.md
```

## Configuration

### Agent Configuration

In `weather_agent/agent.py`:

```python
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

connection_params = StreamableHTTPConnectionParams(
    url=MCP_SERVER_URL,
    timeout=30.0,
)

root_agent = Agent(
    name="weather_agent",
    model="gemini-3.6-flash",
    tools=[weather_tools],
)
```

The tool schemas are discovered from the MCP server at runtime; they are not
duplicated in the client.

## Troubleshooting

### Agent won't connect to MCP server

1. **404 errors**: MCP server is not running or wrong port
   - Ensure the MCP server is running on port 8085
   - Check `MCP_SERVER_URL` in `.env`

2. **405 errors**: Port conflict with another application
   - Check what's running on the port: `lsof -i :8085`
   - Change port in both server and client if needed

3. **Timeout errors**: Server not started
   - Start the MCP server first, then the ADK client

### MCP unavailable

The agent does not use a fallback weather implementation. Fix the connection
and restart ADK web; the agent instruction requires it to report that live data
could not be retrieved instead of inventing weather.

## Environment Variables

Create `.env` file:
```bash
GOOGLE_API_KEY=your_gemini_api_key
MCP_SERVER_URL=http://localhost:8085/mcp
```

## Resources

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [WeatherAPI](https://www.weatherapi.com/)
