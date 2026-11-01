"""Base entity for Sensoto Environment Sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SensotoSensorReading
from .const import DOMAIN
from .coordinator import SensotoDataUpdateCoordinator


class SensotoEntity(CoordinatorEntity[SensotoDataUpdateCoordinator]):
    """Base entity representing a Sensoto sensor attached to a measurement station."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensotoDataUpdateCoordinator,
        sensor_key: str,
        metadata: dict[str, Any],
    ) -> None:
        """Initialize the base Sensoto entity."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._metadata = metadata

        network_code = metadata.get("network_code", "unknown")
        device_code = metadata.get("device_code", "unknown")
        device_name = metadata.get("device_name") or device_code

        reading = self.reading
        manufacturer = (
            reading.source_shortname
            if reading and reading.source_shortname
            else f"Sensoto ({network_code})"
        )
        config_url = (
            reading.source_link_uri
            if reading and reading.source_link_uri
            else "https://sensoto.io/"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{network_code}_{device_code}")},
            name=f"{device_name} ({network_code})",
            manufacturer=manufacturer,
            model=f"{network_code} ({device_code})",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
        )

    @property
    def reading(self) -> SensotoSensorReading | None:
        """Return the latest sensor reading from the coordinator."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._sensor_key)
