from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

import weather


def current_payload() -> dict:
    return {
        "location": {"name": "Hanoi", "region": "", "country": "Vietnam"},
        "current": {
            "temp_c": 30,
            "temp_f": 86,
            "feelslike_c": 34,
            "feelslike_f": 93.2,
            "condition": {"text": "Sunny"},
            "humidity": 70,
            "wind_kph": 10,
            "wind_mph": 6.2,
            "wind_dir": "SE",
            "pressure_mb": 1008,
            "uv": 7,
            "vis_km": 10,
            "last_updated": "2026-08-28 12:00",
        },
    }


def forecast_payload(days: int = 3) -> dict:
    return {
        "location": {"name": "Danang", "region": "", "country": "Vietnam"},
        "forecast": {
            "forecastday": [
                {
                    "date": f"2026-08-{28 + index:02d}",
                    "day": {
                        "maxtemp_c": 33,
                        "maxtemp_f": 91.4,
                        "mintemp_c": 26,
                        "mintemp_f": 78.8,
                        "condition": {"text": "Partly cloudy"},
                        "daily_chance_of_rain": 20,
                        "maxwind_kph": 18,
                        "uv": 8,
                    },
                }
                for index in range(days)
            ]
        },
    }


@pytest_asyncio.fixture
async def install_weather_client(monkeypatch):
    clients: list[httpx.AsyncClient] = []

    async def install(handler, *, api_key: str | None = "test-key"):
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(http_client)
        client = weather.WeatherAPIClient(http_client=http_client, api_key=api_key)
        monkeypatch.setattr(weather, "weather_api_client", client)
        return client

    yield install
    for client in clients:
        await client.aclose()


@pytest.fixture(autouse=True)
def weather_key(monkeypatch):
    monkeypatch.setenv("WEATHERAPI_KEY", "test-key")


@pytest.mark.asyncio
async def test_current_weather_success(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/current.json")
        assert request.url.params["q"] == "Hanoi"
        assert request.url.params["key"] == "test-key"
        return httpx.Response(200, json=current_payload())

    await install_weather_client(handler)
    result = await weather.get_current_weather(" Hanoi ")
    assert "Current Weather for Hanoi, Vietnam" in result
    assert "30°C" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [1, 3])
async def test_forecast_success_for_supported_days(days, install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/forecast.json")
        assert request.url.params["days"] == str(days)
        return httpx.Response(200, json=forecast_payload(days))

    await install_weather_client(handler)
    result = await weather.get_forecast("Danang", days)
    assert "Weather Forecast for Danang, Vietnam" in result
    assert result.count("2026-08-") == days


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [0, 4, -1])
async def test_forecast_rejects_invalid_days(days, install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("WeatherAPI must not be called for invalid days")

    await install_weather_client(handler)
    result = await weather.get_forecast("Hanoi", days)
    assert result == "❌ days must be an integer between 1 and 3."


@pytest.mark.asyncio
async def test_empty_city_is_rejected(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("WeatherAPI must not be called for an empty city")

    await install_weather_client(handler)
    assert await weather.get_current_weather("  ") == "❌ City must not be empty."


@pytest.mark.asyncio
async def test_missing_api_key(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("WeatherAPI must not be called without a key")

    await install_weather_client(handler, api_key="")
    result = await weather.get_current_weather("Hanoi")
    assert "key is not configured" in result


@pytest.mark.asyncio
async def test_weatherapi_4xx(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "No matching location found."}})

    await install_weather_client(handler)
    result = await weather.get_current_weather("Not a city")
    assert "rejected the request" in result


@pytest.mark.asyncio
async def test_weatherapi_5xx(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    await install_weather_client(handler)
    result = await weather.get_current_weather("Hanoi")
    assert "temporarily unavailable" in result


@pytest.mark.asyncio
async def test_weatherapi_timeout(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    await install_weather_client(handler)
    result = await weather.get_current_weather("Hanoi")
    assert "Could not reach WeatherAPI" in result


@pytest.mark.asyncio
async def test_malformed_upstream_response(install_weather_client):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    await install_weather_client(handler)
    result = await weather.get_current_weather("Hanoi")
    assert "unexpected response" in result


@pytest.mark.asyncio
async def test_health_check_does_not_require_weatherapi():
    assert await weather.health_check() == "✅ Weather MCP Server is running."
