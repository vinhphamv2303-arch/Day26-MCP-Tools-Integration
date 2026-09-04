from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-mcp-server/1.0"
DEFAULT_PORT = 8085
REQUEST_TIMEOUT = 30.0


class WeatherAPIError(RuntimeError):
    """Base class for expected WeatherAPI failures."""


class WeatherAPIConfigurationError(WeatherAPIError):
    """The server is missing the configuration required for WeatherAPI."""


class WeatherAPIRequestError(WeatherAPIError):
    """WeatherAPI rejected a client request, such as an invalid city."""


class WeatherAPIUpstreamError(WeatherAPIError):
    """WeatherAPI returned a server-side error."""


class WeatherAPINetworkError(WeatherAPIError):
    """The request could not reach WeatherAPI or timed out."""


class WeatherAPIResponseError(WeatherAPIError):
    """WeatherAPI returned a response that could not be understood."""


class WeatherAPIClient:
    """Small, injectable WeatherAPI client used by the MCP tools."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        base_url: str = WEATHERAPI_BASE,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    async def request(
        self,
        endpoint: str,
        params: Mapping[str, str],
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        api_key = self._api_key if self._api_key is not None else os.getenv("WEATHERAPI_KEY")
        if not api_key:
            raise WeatherAPIConfigurationError(
                "WEATHERAPI_KEY is not configured"
            )

        request_params = {**params, "key": api_key}
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        client = http_client or await self._client()

        try:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                params=request_params,
                timeout=self._timeout,
            )
            if 400 <= response.status_code < 500:
                raise WeatherAPIRequestError(
                    f"WeatherAPI rejected the request (HTTP {response.status_code})"
                )
            if response.status_code >= 500:
                raise WeatherAPIUpstreamError(
                    f"WeatherAPI returned an upstream error (HTTP {response.status_code})"
                )
            response.raise_for_status()
        except WeatherAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise WeatherAPINetworkError("WeatherAPI request timed out") from exc
        except httpx.RequestError as exc:
            raise WeatherAPINetworkError("WeatherAPI request failed") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherAPIResponseError(
                "WeatherAPI returned malformed JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise WeatherAPIResponseError("WeatherAPI returned an unexpected payload")

        upstream_error = payload.get("error")
        if isinstance(upstream_error, dict):
            message = upstream_error.get("message", "request rejected")
            raise WeatherAPIRequestError(f"WeatherAPI rejected the request: {message}")

        return payload

    async def aclose(self) -> None:
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


port = int(os.getenv("PORT", DEFAULT_PORT))
mcp = FastMCP("weather", host="0.0.0.0", port=port)
weather_api_client = WeatherAPIClient()


async def make_weather_request(
    endpoint: str,
    params: Mapping[str, str],
    *,
    client: WeatherAPIClient | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Request WeatherAPI data through an injectable client."""
    request_client = client or weather_api_client
    return await request_client.request(endpoint, params, http_client=http_client)


def _validated_city(city: str) -> str:
    if not isinstance(city, str) or not city.strip():
        raise ValueError("city must not be empty")
    return city.strip()


def _tool_error(city: str, error: Exception) -> str:
    if isinstance(error, ValueError):
        return "❌ City must not be empty."
    if isinstance(error, WeatherAPIConfigurationError):
        return "❌ WeatherAPI key is not configured. Set WEATHERAPI_KEY on the server."
    if isinstance(error, WeatherAPIRequestError):
        return f"❌ WeatherAPI rejected the request for {city}. Check the city name and API key."
    if isinstance(error, WeatherAPIUpstreamError):
        return "❌ WeatherAPI is temporarily unavailable. Please try again later."
    if isinstance(error, WeatherAPINetworkError):
        return "❌ Could not reach WeatherAPI. Please try again later."
    if isinstance(error, WeatherAPIResponseError):
        return "❌ WeatherAPI returned an unexpected response."
    logger.exception("Unexpected weather tool failure for city=%r", city)
    return "❌ Unable to fetch weather data due to an unexpected server error."


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city."""
    try:
        city = _validated_city(city)
        data = await make_weather_request(
            "current.json", {"q": city, "aqi": "no"}
        )
        location = data["location"]
        current = data["current"]
        if not isinstance(location, dict) or not isinstance(current, dict):
            raise WeatherAPIResponseError("current weather fields are missing")
        condition = current["condition"]
        if not isinstance(condition, dict):
            raise WeatherAPIResponseError("current condition is missing")
    except (ValueError, KeyError, TypeError, WeatherAPIError) as error:
        if isinstance(error, (KeyError, TypeError)):
            error = WeatherAPIResponseError("current weather fields are missing")
        logger.warning("Current weather request failed for city=%r: %s", city, error)
        return _tool_error(city, error)

    location_name = ", ".join(
        value for value in (
            location.get("name"),
            location.get("region"),
            location.get("country"),
        )
        if value
    )
    return (
        f"Current Weather for {location_name}:\n\n"
        f"Temperature: {current.get('temp_c')}°C ({current.get('temp_f')}°F)\n"
        f"Feels like: {current.get('feelslike_c')}°C ({current.get('feelslike_f')}°F)\n"
        f"Condition: {condition.get('text')}\n"
        f"Humidity: {current.get('humidity')}%\n"
        f"Wind: {current.get('wind_kph')} km/h ({current.get('wind_mph')} mph) {current.get('wind_dir')}\n"
        f"Pressure: {current.get('pressure_mb')} mb\n"
        f"UV Index: {current.get('uv')}\n"
        f"Visibility: {current.get('vis_km')} km\n\n"
        f"Last updated: {current.get('last_updated')}"
    )


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get a 1-to-3-day weather forecast for a city."""
    try:
        city = _validated_city(city)
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3:
            raise ValueError("days must be an integer between 1 and 3")

        data = await make_weather_request(
            "forecast.json",
            {"q": city, "days": str(days), "aqi": "no", "alerts": "no"},
        )
        location = data["location"]
        forecast = data["forecast"]
        forecast_days = forecast["forecastday"]
        if not isinstance(location, dict) or not isinstance(forecast_days, list):
            raise WeatherAPIResponseError("forecast fields are missing")
    except (ValueError, KeyError, TypeError, WeatherAPIError) as error:
        if isinstance(error, (KeyError, TypeError)):
            error = WeatherAPIResponseError("forecast fields are missing")
        logger.warning("Forecast request failed for city=%r: %s", city, error)
        if isinstance(error, ValueError) and "days" in str(error):
            return "❌ days must be an integer between 1 and 3."
        return _tool_error(city, error)

    location_name = ", ".join(
        value for value in (
            location.get("name"),
            location.get("region"),
            location.get("country"),
        )
        if value
    )
    forecasts = [f"Weather Forecast for {location_name}:"]
    try:
        for day in forecast_days:
            day_data = day["day"]
            forecasts.append(
                "\n"
                f"{day['date']}:\n"
                f"High: {day_data['maxtemp_c']}°C ({day_data['maxtemp_f']}°F)\n"
                f"Low: {day_data['mintemp_c']}°C ({day_data['mintemp_f']}°F)\n"
                f"Condition: {day_data['condition']['text']}\n"
                f"Chance of Rain: {day_data['daily_chance_of_rain']}%\n"
                f"Max Wind: {day_data['maxwind_kph']} km/h\n"
                f"UV Index: {day_data['uv']}"
            )
    except (KeyError, TypeError) as error:
        logger.warning("Malformed forecast response for city=%r: %s", city, error)
        return "❌ WeatherAPI returned an unexpected response."

    return "\n---\n".join(forecasts)


@mcp.tool()
async def health_check() -> str:
    """Confirm that the MCP server is running without calling WeatherAPI."""
    return "✅ Weather MCP Server is running."


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx logs full request URLs at INFO, which would expose the API key
    # because WeatherAPI accepts it as a query parameter.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logger.info("MCP server starting on http://0.0.0.0:%s/mcp", port)
    logger.info("Registered tools: get_current_weather, get_forecast, health_check")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
