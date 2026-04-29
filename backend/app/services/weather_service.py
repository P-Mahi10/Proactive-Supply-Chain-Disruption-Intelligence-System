"""
backend/app/services/weather_service.py
========================================
Fetches real weather data from OpenWeatherMap API based on port coordinates.
"""

from typing import Dict, Union
import requests
import os
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)

# OpenWeatherMap API Key from environment
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Port coordinates (latitude, longitude)
PORT_COORDINATES = {
    "Shanghai (Pudong)": (30.1155, 121.6573),
    "Singapore": (1.3521, 103.8198),
    "Busan": (35.0973, 129.0331),
    "Ningbo": (29.8683, 121.5440),
    "Shenzhen": (22.5431, 114.0579),
    "Qingdao": (36.0621, 120.3826),
    "Tianjin": (39.0842, 117.2010),
    "Hong Kong": (22.2817, 114.1863),
    "Rotterdam": (51.9217, 4.2683),
    "Antwerp": (51.3176, 4.4011),
    "Hamburg": (53.5511, 9.9937),
    "Los Angeles": (34.0522, -118.2437),
    "New York": (40.6892, -74.0445),
    "Jebel Ali": (25.0148, 55.1433),
    "Colombo": (6.9271, 79.8612),
    "Tanjung Pelepas": (1.3521, 103.7618),
    "Port Said": (31.2565, 32.2841),
    "Felixstowe": (51.9687, 1.3472),
    "Yokohama": (35.4437, 139.6380),
    "Karachi": (24.8607, 66.9910),
    "JNPT": (18.9676, 72.9194),
    "Mundra": (22.7383, 69.6283),
    "Chennai": (13.1939, 80.2822),
    "Visakhapatnam": (17.6869, 83.2185),
    "Kolkata": (22.5726, 88.3639),
    "Cochin": (9.9312, 76.2673),
    "Pipavav": (21.1206, 71.1947),
}

# Cache for API calls
_weather_cache: Dict[tuple, Dict] = {}


def _fetch_from_openweather(
    latitude: float,
    longitude: float,
    season: str,
) -> Dict[str, Union[float, int]]:
    """
    Fetch weather data from OpenWeatherMap API.
    """
    if not OPENWEATHER_API_KEY:
        logger.error("OPENWEATHER_API_KEY not set in environment")
        raise ValueError("OPENWEATHER_API_KEY environment variable is not set")

    try:
        # Use current weather endpoint for real-time data
        url = "https://api.openweathermap.org/data/2.5/weather"

        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        logger.info(
            "Weather data fetched from OpenWeatherMap for lat=%f, lon=%f",
            latitude,
            longitude,
        )

        # Extract weather information
        weather = data.get("weather", [{}])[0]
        main = data.get("main", {})
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        visibility = data.get("visibility", 10000)

        # Get weather code and description
        weather_code = weather.get("id", 800)  # 800 = clear sky
        description = weather.get("main", "Clear").lower()

        # Extract values
        temperature = main.get("temp", 20)
        humidity = main.get("humidity", 50)
        wind_speed_ms = wind.get("speed", 5)  # m/s
        wind_speed_kmh = wind_speed_ms * 3.6  # Convert m/s to km/h
        cloud_coverage = clouds.get("all", 0)
        visibility_km = visibility / 1000  # Convert meters to km

        # Convert WMO weather code to severity (1-5)
        severity = _weather_code_to_severity(weather_code)

        # Estimate cyclone probability based on weather conditions
        cyclone_prob = _weather_conditions_to_cyclone_prob(weather_code, description, wind_speed_kmh)

        # Wave height estimation based on wind speed
        wave_height = _wind_to_wave_height(wind_speed_kmh)

        # Rainfall estimation based on weather description
        rainfall = _weather_to_rainfall(description, humidity, cloud_coverage)

        # Adjust based on season
        if season == "monsoon":
            rainfall *= 2.5
            cyclone_prob = min(0.99, cyclone_prob * 1.5)
            severity = min(5, severity + 1)
        elif season == "winter":
            wind_speed_kmh *= 1.2
            wave_height *= 1.3
            rainfall *= 1.3
            cyclone_prob *= 1.2
        elif season == "summer":
            rainfall *= 0.6
            cyclone_prob *= 0.7

        result = {
            "weather_forecast_severity": min(5, max(1, int(severity))),
            "cyclone_probability": round(min(0.99, max(0.01, cyclone_prob)), 2),
            "wind_speed_kmh": round(max(0, wind_speed_kmh), 1),
            "wave_height_m": round(max(0.1, wave_height), 2),
            "rainfall_mm": round(max(0, rainfall), 1),
            "visibility_km": round(max(0.5, visibility_km), 1),
        }

        logger.info(
            "Parsed weather: severity=%d, cyclone_prob=%.2f, wind=%.1f km/h",
            result["weather_forecast_severity"],
            result["cyclone_probability"],
            result["wind_speed_kmh"],
        )
        return result

    except requests.exceptions.RequestException as e:
        logger.error("HTTP error fetching from OpenWeatherMap: %s", str(e))
        raise
    except Exception as e:
        logger.error("Error processing OpenWeatherMap data: %s", str(e))
        raise


def _weather_code_to_severity(code: int) -> int:
    """
    Convert OpenWeatherMap weather code to severity level (1-5).
    Reference: https://openweathermap.org/weather-conditions
    """
    # 2xx: Thunderstorm
    if 200 <= code < 300:
        return 5
    # 3xx: Drizzle
    elif 300 <= code < 400:
        return 2
    # 5xx: Rain
    elif 500 <= code < 600:
        if code >= 520:  # Heavy rain
            return 4
        else:  # Light/Moderate rain
            return 3
    # 6xx: Snow
    elif 600 <= code < 700:
        return 3
    # 7xx: Atmosphere (fog, mist, etc.)
    elif 700 <= code < 800:
        return 2
    # 800: Clear sky
    elif code == 800:
        return 1
    # 80x: Clouds
    elif code > 800:
        return 1 if code == 801 else 2
    else:
        return 2


def _weather_conditions_to_cyclone_prob(code: int, description: str, wind_speed_kmh: float) -> float:
    """
    Estimate cyclone probability based on weather code and wind speed.
    """
    base_prob = 0.01

    # Thunderstorm = higher cyclone probability
    if 200 <= code < 300:
        base_prob = 0.25
    # Heavy rain
    elif 520 <= code < 533:
        base_prob = 0.15
    # Moderate rain
    elif 500 <= code < 520:
        base_prob = 0.08
    # Light rain/drizzle
    elif 300 <= code < 500:
        base_prob = 0.03
    # Clear conditions
    elif code == 800:
        base_prob = 0.01

    # Adjust based on wind speed (strong winds indicate potential cyclone)
    if wind_speed_kmh > 60:  # Gale force
        base_prob = min(0.5, base_prob * 2)
    elif wind_speed_kmh > 40:  # Strong wind
        base_prob = min(0.4, base_prob * 1.5)

    return base_prob


def _wind_to_wave_height(wind_speed_kmh: float) -> float:
    """
    Estimate wave height from wind speed using empirical relationships.
    Beaufort scale adaptation
    """
    if wind_speed_kmh < 5:
        return 0.1
    elif wind_speed_kmh < 15:
        return 0.5
    elif wind_speed_kmh < 25:
        return 1.0
    elif wind_speed_kmh < 40:
        return 2.0
    elif wind_speed_kmh < 63:
        return 3.5
    else:
        return 5.0 + (wind_speed_kmh - 63) * 0.1


def _weather_to_rainfall(description: str, humidity: float, cloud_coverage: float) -> float:
    """
    Estimate rainfall based on weather description, humidity, and cloud coverage.
    """
    rainfall = 0.0

    description_lower = description.lower()

    # Direct rainfall from weather description
    if "thunderstorm" in description_lower or "tornado" in description_lower:
        rainfall = 20 + (humidity / 100) * 30
    elif "heavy rain" in description_lower:
        rainfall = 15 + (humidity / 100) * 20
    elif "rain" in description_lower or "shower" in description_lower:
        rainfall = 5 + (humidity / 100) * 10
    elif "drizzle" in description_lower or "light rain" in description_lower:
        rainfall = 1 + (humidity / 100) * 3
    elif "snow" in description_lower:
        rainfall = 3 + (humidity / 100) * 5
    elif "cloud" in description_lower or "overcast" in description_lower:
        # Estimate rainfall based on cloud coverage and humidity
        rainfall = (cloud_coverage / 100) * (humidity / 100) * 5
    else:
        # Clear or mostly clear
        rainfall = (cloud_coverage / 100) * (humidity / 100) * 1

    return rainfall


def fetch_weather_data(
    origin_port: str,
    destination_port: str,
    season: str,
    month: int,
    day_of_week: int,
) -> Dict[str, Union[float, int]]:
    """
    Fetch real weather data for a port route using OpenWeatherMap API.

    Args:
        origin_port: Starting port name
        destination_port: Ending port name
        season: Season (summer, winter, monsoon, spring, autumn)
        month: Month (1-12) - used for seasonal adjustments
        day_of_week: Day of week (0-6, 0=Monday) - used for seasonal adjustments

    Returns:
        Dictionary with weather fields
    """
    logger.info(
        "Fetching weather data: %s -> %s, season=%s, month=%d, dow=%d",
        origin_port,
        destination_port,
        season,
        month,
        day_of_week,
    )

    # Use destination port coordinates (weather at arrival port)
    coords = PORT_COORDINATES.get(destination_port)
    if not coords:
        logger.warning("Port '%s' not found in coordinates, using default", destination_port)
        coords = (0, 0)  # Default to equator

    latitude, longitude = coords

    # Check cache (use a simple cache based on port to avoid hitting API limits)
    cache_key = (latitude, longitude, season)
    if cache_key in _weather_cache:
        logger.info("Returning cached weather data")
        return _weather_cache[cache_key]

    # Fetch from API
    result = _fetch_from_openweather(latitude, longitude, season)

    # Cache the result
    _weather_cache[cache_key] = result

    logger.info("Weather data fetched successfully")
    return result
