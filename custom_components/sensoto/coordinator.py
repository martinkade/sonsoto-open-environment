"""DataUpdateCoordinator for the Sensoto Environment Sensors integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SensotoApiClient,
    SensotoApiError,
    SensotoSensorReading,
    parse_sensor_key,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_SENSORS,
    CONF_SENSORS_METADATA,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MAX_CONCURRENT_REQUESTS = 5


class SensotoDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, SensotoSensorReading]]
):
    """Coordinator to manage fetching sensor data from the Sensoto API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: SensotoApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Sensoto coordinator."""
        self.client = client
        self.config_entry = entry

        scan_interval_minutes = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )

    @property
    def selected_sensor_keys(self) -> list[str]:
        """Return the list of configured sensor keys."""
        return list(
            self.config_entry.options.get(
                CONF_SELECTED_SENSORS,
                self.config_entry.data.get(CONF_SELECTED_SENSORS, []),
            )
        )

    @property
    def sensors_metadata(self) -> dict[str, dict[str, Any]]:
        """Return cached static discovery metadata for configured sensors."""
        meta: dict[str, dict[str, Any]] = {}
        meta.update(self.config_entry.data.get(CONF_SENSORS_METADATA, {}))
        meta.update(self.config_entry.options.get(CONF_SENSORS_METADATA, {}))
        return meta

    async def _async_update_data(self) -> dict[str, SensotoSensorReading]:
        """Fetch latest data for all selected sensors."""
        sensor_keys = self.selected_sensor_keys
        if not sensor_keys:
            return {}

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        results: dict[str, SensotoSensorReading] = {}
        errors: list[str] = []

        async def _fetch_one(sensor_key: str) -> None:
            try:
                network_code, device_code, sensor_code = parse_sensor_key(sensor_key)
            except ValueError as err:
                _LOGGER.warning("Skipping malformed sensor key %s: %s", sensor_key, err)
                return

            async with semaphore:
                try:
                    reading = await self.client.async_get_sensor_reading(
                        network_code=network_code,
                        device_code=device_code,
                        sensor_code=sensor_code,
                    )
                    results[sensor_key] = reading
                except SensotoApiError as err:
                    _LOGGER.debug(
                        "Failed to update Sensoto sensor %s: %s", sensor_key, err
                    )
                    errors.append(f"{sensor_key}: {err}")

        await asyncio.gather(*(_fetch_one(key) for key in sensor_keys))

        if not results and errors:
            raise UpdateFailed(
                f"Failed to fetch data from Sensoto for all {len(sensor_keys)} sensors. "
                f"First error: {errors[0]}"
            )

        # Preserve previous reading if a single sensor temporarily failed
        if self.data:
            for key in sensor_keys:
                if key not in results and key in self.data:
                    results[key] = self.data[key]

        return results
