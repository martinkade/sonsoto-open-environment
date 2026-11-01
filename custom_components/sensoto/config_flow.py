"""Config flow for Sensoto Environment Sensors integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import (
    GeoBoundingBox,
    SensotoApiClient,
    SensotoApiError,
    SensotoConnectionError,
    bbox_from_center,
    haversine_distance_km,
    make_sensor_key,
)
from .const import (
    CATEGORY_AIR_AND_ATMOSPHERE,
    CATEGORY_LIGHT_AND_RADIATION,
    CATEGORY_PHENOMENA,
    CATEGORY_WATER_AND_SOIL,
    CONF_BOTTOM_RIGHT_LAT,
    CONF_BOTTOM_RIGHT_LON,
    CONF_CATEGORIES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_AGE_DAYS,
    CONF_RADIUS_KM,
    CONF_SCAN_INTERVAL,
    CONF_SEARCH_MODE,
    CONF_SELECTED_SENSORS,
    CONF_SENSORS_METADATA,
    CONF_TOP_LEFT_LAT,
    CONF_TOP_LEFT_LON,
    DEFAULT_CATEGORIES,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    PHENOMENON_CATALOG,
    SEARCH_MODE_BBOX,
    SEARCH_MODE_RADIUS,
)

_LOGGER = logging.getLogger(__name__)


def _build_phenomena_list(categories: list[str]) -> list[str]:
    """Flatten selected category keys into a list of phenomenon codes."""
    codes: list[str] = []
    for cat in categories:
        for code in CATEGORY_PHENOMENA.get(cat, []):
            if code not in codes:
                codes.append(code)
    return codes


def _extract_sensor_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """Extract compact serializable metadata for storing in the ConfigEntry."""
    geometry = item.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    lon = float(coords[0]) if len(coords) >= 2 else None
    lat = float(coords[1]) if len(coords) >= 2 else None

    return {
        "network_code": item.get("network_code", ""),
        "device_code": item.get("device_code", ""),
        "device_name": item.get("device_name") or item.get("device_code", ""),
        "sensor_code": item.get("sensor_code", ""),
        "sensor_name": item.get("sensor_name") or item.get("sensor_code", ""),
        "topic_code": item.get("topic_code", ""),
        "phenomenon_code": item.get("phenomenon_code", ""),
        "uom": item.get("uom", ""),
        "sens_interval": item.get("sens_interval", ""),
        "sampl_interval": item.get("sampl_interval", ""),
        "value_aggregation": item.get("value_aggregation", ""),
        "latitude": lat,
        "longitude": lon,
        "elevation": item.get("elevation"),
    }


def _format_sensor_option_label(
    meta: dict[str, Any],
    center_lat: float,
    center_lon: float,
) -> tuple[float, str]:
    """Build a human-readable label and distance for the sensor selector."""
    device_name = meta.get("device_name") or meta.get("device_code")
    network_code = meta.get("network_code")
    sensor_name = meta.get("sensor_name") or meta.get("sensor_code")
    phenomenon_code = meta.get("phenomenon_code", "")
    uom = meta.get("uom") or ""
    interval = (meta.get("sens_interval") or "").replace("PT", "").replace("P", "")

    phen_meta = PHENOMENON_CATALOG.get(phenomenon_code)
    phen_label = phen_meta.name_de if phen_meta else phenomenon_code

    # Avoid redundant labels if sensor_name equals sensor_code or phenomenon
    if sensor_name and sensor_name.lower() not in {
        phenomenon_code.lower(),
        phen_label.lower(),
        "dose_rate",
        "odl",
    }:
        display_sensor = f"{phen_label} ({sensor_name})"
    else:
        display_sensor = phen_label

    lat = meta.get("latitude")
    lon = meta.get("longitude")
    if lat is not None and lon is not None:
        dist_km = haversine_distance_km(center_lat, center_lon, lat, lon)
        dist_str = f"{dist_km:.1f} km"
    else:
        dist_km = 9999.0
        dist_str = "? km"

    unit_part = f" [{uom}, {interval}]" if uom and interval else (f" [{uom}]" if uom else "")
    label = f"{device_name} ({network_code}) – {display_sensor}{unit_part} ({dist_str})"
    return dist_km, label


CATEGORY_OPTIONS: list[SelectOptionDict] = [
    SelectOptionDict(
        value=CATEGORY_LIGHT_AND_RADIATION,
        label="Licht & Strahlung (Globalstrahlung, Sonnenschein, Radioaktivität/ODL, UV)",
    ),
    SelectOptionDict(
        value=CATEGORY_AIR_AND_ATMOSPHERE,
        label="Luft & Atmosphäre (Temperatur, Luftfeuchte, Druck, Wind, Regen, Feinstaub)",
    ),
    SelectOptionDict(
        value=CATEGORY_WATER_AND_SOIL,
        label="Wasser & Boden (Pegelstand, Wassertemperatur, Bodentemperatur, Schneehöhe)",
    ),
]


class SensotoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensoto Environment Sensors."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow state."""
        self._search_config: dict[str, Any] = {}
        self._discovered_sensors: dict[str, dict[str, Any]] = {}
        self._center_lat: float = 0.0
        self._center_lon: float = 0.0

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SensotoOptionsFlowHandler:
        """Return the options flow handler."""
        return SensotoOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Choose search mode (radius around location vs explicit bounding box) and categories."""
        if user_input is not None:
            self._search_config.update(user_input)
            if user_input.get(CONF_SEARCH_MODE) == SEARCH_MODE_BBOX:
                return await self.async_step_bbox()
            return await self.async_step_radius()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Sensoto Umweltsensoren"): TextSelector(),
                vol.Required(
                    CONF_SEARCH_MODE, default=SEARCH_MODE_RADIUS
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=SEARCH_MODE_RADIUS,
                                label="Umkreissuche (Koordinaten & Radius in km)",
                            ),
                            SelectOptionDict(
                                value=SEARCH_MODE_BBOX,
                                label="Bounding Box (Top-Left / Bottom-Right Koordinaten)",
                            ),
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_CATEGORIES, default=DEFAULT_CATEGORIES
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=CATEGORY_OPTIONS,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_MAX_AGE_DAYS, default=DEFAULT_MAX_AGE_DAYS
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=3650,
                        step=1,
                        unit_of_measurement="Tage",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_radius(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2a: Configure center coordinates and radius in km."""
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = float(user_input[CONF_LATITUDE])
            lon = float(user_input[CONF_LONGITUDE])
            radius_km = float(user_input[CONF_RADIUS_KM])
            self._center_lat = lat
            self._center_lon = lon
            self._search_config.update(user_input)

            bbox = bbox_from_center(lat, lon, radius_km)
            errors = await self._async_perform_search(bbox)
            if not errors:
                return await self.async_step_select_sensors()

        default_lat = self.hass.config.latitude or 52.0813
        default_lon = self.hass.config.longitude or 6.9409

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=default_lat): NumberSelector(
                    NumberSelectorConfig(
                        min=-90.0, max=90.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_LONGITUDE, default=default_lon): NumberSelector(
                    NumberSelectorConfig(
                        min=-180.0, max=180.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_RADIUS_KM, default=DEFAULT_RADIUS_KM
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1.0,
                        max=150.0,
                        step=1.0,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="radius", data_schema=schema, errors=errors
        )

    async def async_step_bbox(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2b: Configure explicit geographic bounding box (top_left / bottom_right)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            tl_lat = float(user_input[CONF_TOP_LEFT_LAT])
            tl_lon = float(user_input[CONF_TOP_LEFT_LON])
            br_lat = float(user_input[CONF_BOTTOM_RIGHT_LAT])
            br_lon = float(user_input[CONF_BOTTOM_RIGHT_LON])

            if tl_lat <= br_lat or tl_lon >= br_lon:
                errors["base"] = "invalid_bbox"
            else:
                self._center_lat = (tl_lat + br_lat) / 2.0
                self._center_lon = (tl_lon + br_lon) / 2.0
                self._search_config.update(user_input)

                bbox = GeoBoundingBox(
                    top_left_lat=tl_lat,
                    top_left_lon=tl_lon,
                    bottom_right_lat=br_lat,
                    bottom_right_lon=br_lon,
                )
                errors = await self._async_perform_search(bbox)
                if not errors:
                    return await self.async_step_select_sensors()

        schema = vol.Schema(
            {
                vol.Required(CONF_TOP_LEFT_LAT, default=52.181038): NumberSelector(
                    NumberSelectorConfig(
                        min=-90.0, max=90.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_TOP_LEFT_LON, default=6.782584): NumberSelector(
                    NumberSelectorConfig(
                        min=-180.0, max=180.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_BOTTOM_RIGHT_LAT, default=52.021201): NumberSelector(
                    NumberSelectorConfig(
                        min=-90.0, max=90.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_BOTTOM_RIGHT_LON, default=7.151693): NumberSelector(
                    NumberSelectorConfig(
                        min=-180.0, max=180.0, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="bbox", data_schema=schema, errors=errors)

    async def _async_perform_search(self, bbox: GeoBoundingBox) -> dict[str, str]:
        """Run the Sensoto sensor search and populate self._discovered_sensors."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        client = SensotoApiClient(session)

        categories: list[str] = self._search_config.get(
            CONF_CATEGORIES, DEFAULT_CATEGORIES
        )
        phenomenon_codes = _build_phenomena_list(categories)
        max_age_days = int(
            self._search_config.get(CONF_MAX_AGE_DAYS, DEFAULT_MAX_AGE_DAYS)
        )

        try:
            raw_sensors = await client.async_search_sensors(
                bbox=bbox,
                phenomenon_codes=phenomenon_codes,
                max_age_days=max_age_days if max_age_days > 0 else None,
            )
        except SensotoConnectionError:
            errors["base"] = "cannot_connect"
            return errors
        except SensotoApiError:
            errors["base"] = "api_error"
            return errors

        discovered: dict[str, dict[str, Any]] = {}
        for item in raw_sensors:
            meta = _extract_sensor_metadata(item)
            key = make_sensor_key(
                meta["network_code"], meta["device_code"], meta["sensor_code"]
            )
            discovered[key] = meta

        if not discovered:
            errors["base"] = "no_sensors_found"
            return errors

        self._discovered_sensors = discovered
        return errors

    async def async_step_select_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Let the user pick which discovered sensors to add."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_keys: list[str] = user_input.get(CONF_SELECTED_SENSORS, [])
            if not selected_keys:
                errors["base"] = "no_sensors_selected"
            else:
                selected_metadata = {
                    key: self._discovered_sensors[key]
                    for key in selected_keys
                    if key in self._discovered_sensors
                }
                entry_data = {
                    **self._search_config,
                    CONF_SELECTED_SENSORS: selected_keys,
                    CONF_SENSORS_METADATA: selected_metadata,
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                        )
                    ),
                }
                title = self._search_config.get(CONF_NAME, "Sensoto Umweltsensoren")
                return self.async_create_entry(title=title, data=entry_data)

        # Sort options by distance to center coordinate
        scored_options: list[tuple[float, str, SelectOptionDict]] = []
        for key, meta in self._discovered_sensors.items():
            dist_km, label = _format_sensor_option_label(
                meta, self._center_lat, self._center_lon
            )
            scored_options.append(
                (dist_km, label, SelectOptionDict(value=key, label=label))
            )

        scored_options.sort(key=lambda item: (item[0], item[1]))
        select_options = [item[2] for item in scored_options]

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_SENSORS): SelectSelector(
                    SelectSelectorConfig(
                        options=select_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=1440,
                        step=5,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_sensors",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "sensor_count": str(len(select_options)),
            },
        )


class SensotoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for reconfiguring selected Sensoto sensors and scan interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._discovered_sensors: dict[str, dict[str, Any]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Sensoto options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_keys: list[str] = user_input.get(CONF_SELECTED_SENSORS, [])
            if not selected_keys:
                errors["base"] = "no_sensors_selected"
            else:
                merged_meta: dict[str, dict[str, Any]] = {}
                merged_meta.update(
                    self._config_entry.data.get(CONF_SENSORS_METADATA, {})
                )
                merged_meta.update(
                    self._config_entry.options.get(CONF_SENSORS_METADATA, {})
                )
                merged_meta.update(self._discovered_sensors)

                kept_meta = {
                    key: merged_meta[key]
                    for key in selected_keys
                    if key in merged_meta
                }
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SELECTED_SENSORS: selected_keys,
                        CONF_SENSORS_METADATA: kept_meta,
                        CONF_SCAN_INTERVAL: int(
                            user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                            )
                        ),
                    },
                )

        # Rebuild bounding box from entry data to discover available sensors
        data = self._config_entry.data
        search_mode = data.get(CONF_SEARCH_MODE, SEARCH_MODE_RADIUS)
        if search_mode == SEARCH_MODE_BBOX:
            tl_lat = float(data.get(CONF_TOP_LEFT_LAT, 52.181038))
            tl_lon = float(data.get(CONF_TOP_LEFT_LON, 6.782584))
            br_lat = float(data.get(CONF_BOTTOM_RIGHT_LAT, 52.021201))
            br_lon = float(data.get(CONF_BOTTOM_RIGHT_LON, 7.151693))
            center_lat = (tl_lat + br_lat) / 2.0
            center_lon = (tl_lon + br_lon) / 2.0
            bbox = GeoBoundingBox(
                top_left_lat=tl_lat,
                top_left_lon=tl_lon,
                bottom_right_lat=br_lat,
                bottom_right_lon=br_lon,
            )
        else:
            center_lat = float(
                data.get(CONF_LATITUDE, self.hass.config.latitude or 52.0813)
            )
            center_lon = float(
                data.get(CONF_LONGITUDE, self.hass.config.longitude or 6.9409)
            )
            radius_km = float(data.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM))
            bbox = bbox_from_center(center_lat, center_lon, radius_km)

        categories: list[str] = data.get(CONF_CATEGORIES, DEFAULT_CATEGORIES)
        phenomenon_codes = _build_phenomena_list(categories)
        max_age_days = int(data.get(CONF_MAX_AGE_DAYS, DEFAULT_MAX_AGE_DAYS))

        # Start with already configured sensors so none disappear if temporarily offline
        discovered: dict[str, dict[str, Any]] = {}
        discovered.update(data.get(CONF_SENSORS_METADATA, {}))
        discovered.update(self._config_entry.options.get(CONF_SENSORS_METADATA, {}))

        session = async_get_clientsession(self.hass)
        client = SensotoApiClient(session)
        try:
            raw_sensors = await client.async_search_sensors(
                bbox=bbox,
                phenomenon_codes=phenomenon_codes,
                max_age_days=max_age_days if max_age_days > 0 else None,
            )
            for item in raw_sensors:
                meta = _extract_sensor_metadata(item)
                key = make_sensor_key(
                    meta["network_code"], meta["device_code"], meta["sensor_code"]
                )
                discovered[key] = meta
        except SensotoApiError as err:
            _LOGGER.warning("Search failed during options flow, using cached list: %s", err)

        self._discovered_sensors = discovered

        scored_options: list[tuple[float, str, SelectOptionDict]] = []
        for key, meta in discovered.items():
            dist_km, label = _format_sensor_option_label(meta, center_lat, center_lon)
            scored_options.append(
                (dist_km, label, SelectOptionDict(value=key, label=label))
            )
        scored_options.sort(key=lambda item: (item[0], item[1]))
        select_options = [item[2] for item in scored_options]

        current_selected = self._config_entry.options.get(
            CONF_SELECTED_SENSORS,
            data.get(CONF_SELECTED_SENSORS, []),
        )
        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_SENSORS, default=current_selected
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=select_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=1440,
                        step=5,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
