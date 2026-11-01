"""Asynchronous API client for Sensoto Environment Sensors."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_ORG_OPEN, API_SEARCH_URL, DEFAULT_DAYS_WITH_DATA

_LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Accept": "application/json, */*",
    "Origin": "https://sensoto.io",
    "Referer": "https://sensoto.io/",
    "User-Agent": "HomeAssistant-Sensoto/1.0.0",
}


class SensotoApiError(Exception):
    """Base exception for Sensoto API errors."""


class SensotoConnectionError(SensotoApiError):
    """Exception raised when connection to Sensoto fails."""


@dataclass
class GeoBoundingBox:
    """Geographic bounding box for Sensoto sensor search."""

    top_left_lat: float
    top_left_lon: float
    bottom_right_lat: float
    bottom_right_lon: float

    def to_api_dict(self) -> dict[str, dict[str, float]]:
        """Serialize to the geo_bbox payload expected by Sensoto."""
        return {
            "top_left": {
                "lon": round(self.top_left_lon, 6),
                "lat": round(self.top_left_lat, 6),
            },
            "bottom_right": {
                "lon": round(self.bottom_right_lon, 6),
                "lat": round(self.bottom_right_lat, 6),
            },
        }


def bbox_from_center(lat: float, lon: float, radius_km: float) -> GeoBoundingBox:
    """Calculate a bounding box around a center coordinate given a radius in km."""
    lat_delta = radius_km / 111.32
    cos_lat = math.cos(math.radians(lat))
    lon_delta = radius_km / (111.32 * max(cos_lat, 0.01))
    return GeoBoundingBox(
        top_left_lat=min(90.0, lat + lat_delta),
        top_left_lon=max(-180.0, lon - lon_delta),
        bottom_right_lat=max(-90.0, lat - lat_delta),
        bottom_right_lon=min(180.0, lon + lon_delta),
    )


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in kilometers between two coordinates."""
    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def make_sensor_key(network_code: str, device_code: str, sensor_code: str) -> str:
    """Create a canonical unique identifier key for a Sensoto sensor."""
    return f"{network_code}::{device_code}::{sensor_code}"


def parse_sensor_key(sensor_key: str) -> tuple[str, str, str]:
    """Split a canonical sensor key into (network_code, device_code, sensor_code)."""
    parts = sensor_key.split("::", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid sensor key format: {sensor_key}")
    return parts[0], parts[1], parts[2]


@dataclass
class SensotoSensorReading:
    """Latest reading and statistics for a single Sensoto sensor."""

    sensor_key: str
    network_code: str
    device_code: str
    sensor_code: str
    latest_value: float | None
    min_value: float | None
    max_value: float | None
    last_measured_at: datetime | None
    value_count: int | None
    days_with_data: int | None
    uom: str | None
    phenomenon_code: str | None
    aggregation: str | None
    sens_interval: str | None
    sampl_interval: str | None
    source_shortname: str | None
    citation_statement: str | None
    source_link_uri: str | None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string into an aware UTC datetime."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_int(value: Any) -> int | None:
    """Safely convert a value to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class SensotoApiClient:
    """Client for interacting with the public Sensoto REST API v1."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        request_timeout: float = 20.0,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    async def async_search_sensors(
        self,
        bbox: GeoBoundingBox,
        phenomenon_codes: list[str] | None = None,
        max_age_days: int | None = None,
        days_with_data: int = DEFAULT_DAYS_WITH_DATA,
    ) -> list[dict[str, Any]]:
        """Search for available public sensors within a geographic bounding box."""
        filters: dict[str, Any] = {
            "geo_bbox": bbox.to_api_dict(),
            "days_with_data": days_with_data,
        }
        if phenomenon_codes:
            filters["phenomenon_codes"] = phenomenon_codes

        payload: dict[str, Any] = {"filters": filters}

        try:
            async with self._session.post(
                API_SEARCH_URL,
                json=payload,
                headers=DEFAULT_HEADERS,
                timeout=self._timeout,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise SensotoApiError(
                        f"Sensoto search returned HTTP {response.status}: {body[:200]}"
                    )
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SensotoConnectionError(
                f"Error communicating with Sensoto search API: {err}"
            ) from err

        if not isinstance(data, list):
            raise SensotoApiError("Unexpected search response format (expected JSON array)")

        now = datetime.now(timezone.utc)
        cutoff = (
            now - timedelta(days=max_age_days)
            if max_age_days is not None and max_age_days > 0
            else None
        )

        results: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get("organization") != API_ORG_OPEN:
                continue

            network_code = item.get("network_code")
            device_code = item.get("device_code")
            sensor_code = item.get("sensor_code")
            if not (network_code and device_code and sensor_code):
                continue

            if cutoff is not None:
                max_date_str = item.get("max_date_iso") or item.get("max_date")
                max_dt = _parse_iso_datetime(max_date_str)
                if max_dt is not None and max_dt < cutoff:
                    continue

            results.append(item)

        return results

    async def async_get_sensor_reading(
        self,
        network_code: str,
        device_code: str,
        sensor_code: str,
    ) -> SensotoSensorReading:
        """Fetch the latest value and metadata for a specific sensor."""
        url = (
            f"{API_BASE_URL}/organizations/{API_ORG_OPEN}"
            f"/networks/{network_code.lower()}"
            f"/devices/{device_code.lower()}"
            f"/sensors/{sensor_code.lower()}"
        )
        try:
            async with self._session.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=self._timeout,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise SensotoApiError(
                        f"Sensoto sensor GET {url} returned HTTP {response.status}: {body[:200]}"
                    )
                data: dict[str, Any] = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SensotoConnectionError(
                f"Error fetching sensor {network_code}/{device_code}/{sensor_code}: {err}"
            ) from err

        stats = data.get("sensor_stats") or {}
        phenomenon = data.get("phenomenon") or {}
        data_source = data.get("data_source") or {}

        sensor_key = make_sensor_key(network_code, device_code, sensor_code)
        return SensotoSensorReading(
            sensor_key=sensor_key,
            network_code=network_code,
            device_code=device_code,
            sensor_code=sensor_code,
            latest_value=_parse_float(stats.get("latest_value")),
            min_value=_parse_float(stats.get("min_value")),
            max_value=_parse_float(stats.get("max_value")),
            last_measured_at=_parse_iso_datetime(stats.get("max_time")),
            value_count=_parse_int(stats.get("value_count")),
            days_with_data=_parse_int(stats.get("days_with_data")),
            uom=phenomenon.get("uom"),
            phenomenon_code=phenomenon.get("code"),
            aggregation=phenomenon.get("aggregation"),
            sens_interval=data.get("sens_interval"),
            sampl_interval=data.get("sampl_interval"),
            source_shortname=data_source.get("source_shortname"),
            citation_statement=data_source.get("citation_statement"),
            source_link_uri=data_source.get("source_link_uri"),
        )
