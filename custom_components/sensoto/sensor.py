"""Sensor platform for Sensoto Environment Sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SensotoSensorReading, parse_sensor_key
from .const import DOMAIN, PHENOMENON_CATALOG
from .coordinator import SensotoDataUpdateCoordinator
from .entity import SensotoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensoto sensor entities from a config entry."""
    coordinator: SensotoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors_metadata = coordinator.sensors_metadata

    entities: list[SensorEntity] = []
    for sensor_key in coordinator.selected_sensor_keys:
        meta = sensors_metadata.get(sensor_key)
        if meta is None:
            try:
                net_code, dev_code, sens_code = parse_sensor_key(sensor_key)
            except ValueError:
                continue
            meta = {
                "network_code": net_code,
                "device_code": dev_code,
                "device_name": dev_code,
                "sensor_code": sens_code,
                "sensor_name": sens_code,
            }
        entities.append(
            SensotoSensorEntity(
                coordinator=coordinator,
                sensor_key=sensor_key,
                metadata=meta,
            )
        )
        entities.append(
            SensotoTimestampSensorEntity(
                coordinator=coordinator,
                sensor_key=sensor_key,
                metadata=meta,
            )
        )

    async_add_entities(entities)


def _format_interval_short(iso_interval: str | None) -> str:
    """Format an ISO-8601 duration like PT10M or PT24H into a short readable string."""
    if not iso_interval:
        return ""
    return iso_interval.replace("PT", "").replace("P", "").lower()


def _format_sensor_display_name(
    metadata: dict[str, Any],
    reading: SensotoSensorReading | None,
    language: str = "de",
) -> str:
    """Generate display name for a sensor, including height and interval qualifiers."""
    phenomenon_code = (
        (reading.phenomenon_code if reading else None)
        or metadata.get("phenomenon_code")
        or ""
    )
    sensor_code = metadata.get("sensor_code", "")
    phen_meta = PHENOMENON_CATALOG.get(phenomenon_code)

    if phen_meta:
        base_name = (
            phen_meta.name_de if language.startswith("de") else phen_meta.name_en
        )
    else:
        base_name = metadata.get("sensor_name") or sensor_code

    elevation = metadata.get("elevation")
    sens_interval = (
        reading.sens_interval if reading and reading.sens_interval else None
    ) or metadata.get("sens_interval")
    sensor_name = metadata.get("sensor_name") or ""

    qualifiers: list[str] = []
    if isinstance(elevation, dict) and elevation.get("height") is not None:
        height = elevation.get("height")
        elev_uom = elevation.get("uom") or "cm"
        qualifiers.append(f"{height} {elev_uom}")
    elif (
        sensor_name
        and sensor_name.lower()
        not in {
            phenomenon_code.lower(),
            base_name.lower(),
            sensor_code.lower(),
            "dose_rate",
            "odl",
        }
        and base_name.lower() not in sensor_name.lower()
    ):
        qualifiers.append(sensor_name)

    interval_short = _format_interval_short(sens_interval)
    if interval_short and interval_short not in {"1h"}:
        qualifiers.append(interval_short)

    if qualifiers:
        return f"{base_name} ({', '.join(qualifiers)})"
    return base_name


class SensotoSensorEntity(SensotoEntity, SensorEntity):
    """Representation of a single Sensoto environment sensor value."""

    def __init__(
        self,
        coordinator: SensotoDataUpdateCoordinator,
        sensor_key: str,
        metadata: dict[str, Any],
    ) -> None:
        """Initialize the Sensoto sensor entity."""
        super().__init__(coordinator, sensor_key, metadata)

        network_code = metadata.get("network_code", "")
        device_code = metadata.get("device_code", "")
        sensor_code = metadata.get("sensor_code", "")
        self._attr_unique_id = f"{network_code}_{device_code}_{sensor_code}".lower()

        reading = self.reading
        phenomenon_code = (
            (reading.phenomenon_code if reading else None)
            or metadata.get("phenomenon_code")
            or ""
        )
        uom = (reading.uom if reading and reading.uom else None) or metadata.get("uom")

        lang = getattr(getattr(coordinator.hass, "config", None), "language", "de")
        self._attr_name = _format_sensor_display_name(metadata, reading, lang)
        self._attr_native_unit_of_measurement = uom

        phen_meta = PHENOMENON_CATALOG.get(phenomenon_code)
        if phen_meta is not None:
            self._attr_icon = phen_meta.icon
            self._attr_state_class = phen_meta.state_class
            if (
                phen_meta.device_class is not None
                and phen_meta.valid_device_class_units is not None
                and uom in phen_meta.valid_device_class_units
            ):
                self._attr_device_class = phen_meta.device_class
            elif (
                phen_meta.device_class is not None
                and phen_meta.valid_device_class_units is None
            ):
                self._attr_device_class = phen_meta.device_class
            else:
                self._attr_device_class = None
        else:
            self._attr_icon = "mdi:chart-line"
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_device_class = None

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and sensor has a reading."""
        return super().available and self.reading is not None

    @property
    def native_value(self) -> float | None:
        """Return the latest value reported by the sensor."""
        reading = self.reading
        if reading is None:
            return None
        return reading.latest_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for the sensor."""
        reading = self.reading
        attrs: dict[str, Any] = {
            "network_code": self._metadata.get("network_code"),
            "device_code": self._metadata.get("device_code"),
            "sensor_code": self._metadata.get("sensor_code"),
            "phenomenon_code": self._metadata.get("phenomenon_code"),
        }

        lat = self._metadata.get("latitude")
        lon = self._metadata.get("longitude")
        if lat is not None and lon is not None:
            attrs[ATTR_LATITUDE] = lat
            attrs[ATTR_LONGITUDE] = lon

        elevation = self._metadata.get("elevation")
        if isinstance(elevation, dict) and elevation.get("height") is not None:
            attrs["elevation_height"] = elevation.get("height")
            attrs["elevation_unit"] = elevation.get("uom")

        if reading is not None:
            if reading.last_measured_at is not None:
                iso_time = reading.last_measured_at.isoformat()
                attrs["last_measured_at"] = iso_time
                attrs["timestamp"] = iso_time
                attrs["erfassungszeitpunkt"] = iso_time
            if reading.min_value is not None:
                attrs["historical_min_value"] = reading.min_value
            if reading.max_value is not None:
                attrs["historical_max_value"] = reading.max_value
            if reading.aggregation:
                attrs["aggregation"] = reading.aggregation
            if reading.sens_interval:
                attrs["sensing_interval"] = reading.sens_interval
            if reading.sampl_interval:
                attrs["sampling_interval"] = reading.sampl_interval
            if reading.source_shortname:
                attrs["data_source"] = reading.source_shortname
            if reading.citation_statement:
                attrs[ATTR_ATTRIBUTION] = reading.citation_statement

        return attrs


class SensotoTimestampSensorEntity(SensotoEntity, SensorEntity):
    """Representation of the acquisition timestamp for a Sensoto environment sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: SensotoDataUpdateCoordinator,
        sensor_key: str,
        metadata: dict[str, Any],
    ) -> None:
        """Initialize the Sensoto timestamp sensor entity."""
        super().__init__(coordinator, sensor_key, metadata)

        network_code = metadata.get("network_code", "")
        device_code = metadata.get("device_code", "")
        sensor_code = metadata.get("sensor_code", "")
        self._attr_unique_id = (
            f"{network_code}_{device_code}_{sensor_code}_timestamp".lower()
        )

        lang = getattr(getattr(coordinator.hass, "config", None), "language", "de")
        base_display_name = _format_sensor_display_name(metadata, self.reading, lang)
        suffix = "Erfassungszeitpunkt" if lang.startswith("de") else "Last Measured"
        self._attr_name = f"{base_display_name} {suffix}"
        self._attr_icon = "mdi:clock-outline"

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and sensor has a reading."""
        return super().available and self.reading is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp when the measurement was acquired."""
        reading = self.reading
        if reading is None:
            return None
        return reading.last_measured_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for the timestamp sensor."""
        reading = self.reading
        attrs: dict[str, Any] = {
            "network_code": self._metadata.get("network_code"),
            "device_code": self._metadata.get("device_code"),
            "sensor_code": self._metadata.get("sensor_code"),
            "phenomenon_code": self._metadata.get("phenomenon_code"),
        }

        lat = self._metadata.get("latitude")
        lon = self._metadata.get("longitude")
        if lat is not None and lon is not None:
            attrs[ATTR_LATITUDE] = lat
            attrs[ATTR_LONGITUDE] = lon

        elevation = self._metadata.get("elevation")
        if isinstance(elevation, dict) and elevation.get("height") is not None:
            attrs["elevation_height"] = elevation.get("height")
            attrs["elevation_unit"] = elevation.get("uom")

        if reading is not None:
            if reading.last_measured_at is not None:
                iso_time = reading.last_measured_at.isoformat()
                attrs["last_measured_at"] = iso_time
                attrs["timestamp"] = iso_time
                attrs["erfassungszeitpunkt"] = iso_time
            if reading.latest_value is not None:
                attrs["latest_value"] = reading.latest_value
            if reading.uom:
                attrs["unit_of_measurement"] = reading.uom
            if reading.sens_interval:
                attrs["sensing_interval"] = reading.sens_interval
            if reading.sampl_interval:
                attrs["sampling_interval"] = reading.sampl_interval
            if reading.source_shortname:
                attrs["data_source"] = reading.source_shortname
            if reading.citation_statement:
                attrs[ATTR_ATTRIBUTION] = reading.citation_statement

        return attrs
