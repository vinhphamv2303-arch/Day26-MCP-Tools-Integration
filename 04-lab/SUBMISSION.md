# Lab 04 — MCP Tools Integration

**Sinh viên:** Phạm Văn Vinh  
**MSSV:** 2A202601988  
**Ngày làm bài:** 28 thg 8, 2026

## Architecture

```text
User → Gemini/ADK → MCP Client → Streamable HTTP → MCP Server → WeatherAPI
```

The ADK agent uses `McpToolset` to discover tools from the remote server at
runtime. The client does not duplicate the MCP tool schemas.

## Environment

| Item | Value |
|------|-------|
| Python | 3.12 (`py3.12` conda environment) |
| MCP SDK | 1.28.1 (`uv.lock`) |
| Google ADK | 2.3.0 (`uv.lock`) |
| Transport | Streamable HTTP |
| Local MCP URL | `http://localhost:8085/mcp` |

The Docker image defaults to `PORT=8080`; the bare Python server defaults to
`PORT=8085`. Secrets are supplied through `.env` and are not committed.

## Tool discovery evidence

`verify_setup.py` performs a real MCP initialize and `list_tools()` call. The
expected exact tool set is:

```text
get_current_weather
get_forecast
health_check
```

Run from `04-lab/mcp-client` while the server is running:

```text
uv run python verify_setup.py
```

## Tool call evidence

The verifier calls:

```text
health_check()
get_current_weather(city="Hanoi")
get_forecast(city="Hanoi", days=2)
```

The last two calls are reported as `SKIP` when `WEATHERAPI_KEY` is not
configured. Actual output is saved under `04-lab/reports/` when the
verifier is run; no output is fabricated in this submission.

## ADK agent evidence

Use ADK Web with the MCP server running and `GOOGLE_API_KEY` configured:

```text
uv run adk web
```

For an executable tool-path check, run:

```text
uv run python adk_smoke.py
```

It records the observed function-call names in `04-lab/reports/adk_smoke.log`;
without `GOOGLE_API_KEY` it reports `SKIP`.

Recorded ADK result: `PASS` — current weather emitted
`get_current_weather`, and forecast emitted `get_forecast`.

Required prompts:

```text
Thời tiết hiện tại ở Hà Nội thế nào?
Dự báo thời tiết Đà Nẵng 2 ngày tới.
```

The first prompt should select `get_current_weather`; the second should select
`get_forecast` with `days=2`. If MCP is unavailable, the agent instruction
requires it to report that live data could not be retrieved rather than invent
weather.

## Failure handling

- Missing `WEATHERAPI_KEY` returns a clear configuration error from weather tools.
- WeatherAPI 4xx, 5xx, timeout/network, and malformed responses are classified
  and returned without exposing the API key.
- Empty cities and forecast days outside `1 <= days <= 3` are rejected before
  an upstream request.
- `health_check()` does not depend on WeatherAPI availability or its key.

## Tests

The server test suite includes unit tests with mocked WeatherAPI responses and
a Streamable HTTP fixture integration test. Run:

```text
cd 04-lab/mcp-server
uv run pytest -q
```

Test counts and live results belong in `reports/test_output.log` after an
actual run; this repository does not claim unexecuted tests as PASS.

Recorded result: `14 passed, 1 warning`. The warning came from the installed
`pydantic-settings` dependency. The Docker smoke build succeeded, and the
verifier against `http://localhost:8080/mcp` passed initialize, `list_tools: 3
tools`, `health_check`, `get_current_weather`, and `get_forecast`. Container
logs were checked to ensure the WeatherAPI key was not exposed.

## Known limitations

- Weather results depend on WeatherAPI availability and credentials.
- ADK smoke tests require a valid Gemini key.
- The lab server has no production authentication layer.
- The verifier's live WeatherAPI calls are intentionally skipped when the key
  is absent.
