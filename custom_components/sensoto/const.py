"""Constants for the Sensoto Environment Sensors integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN: Final = "sensoto"

API_BASE_URL: Final = "https://api.sensoto.io/v1"
API_SEARCH_URL: Final = f"{API_BASE_URL}/index/sensors/search"
API_ORG_OPEN: Final = "open"

DEFAULT_SCAN_INTERVAL_MINUTES: Final = 15
DEFAULT_RADIUS_KM: Final = 15.0
DEFAULT_MAX_AGE_DAYS: Final = 7
DEFAULT_DAYS_WITH_DATA: Final = 5

# Configuration keys
CONF_SEARCH_MODE: Final = "search_mode"
SEARCH_MODE_RADIUS: Final = "radius"
SEARCH_MODE_BBOX: Final = "bbox"

CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_RADIUS_KM: Final = "radius_km"

CONF_TOP_LEFT_LAT: Final = "top_left_lat"
CONF_TOP_LEFT_LON: Final = "top_left_lon"
CONF_BOTTOM_RIGHT_LAT: Final = "bottom_right_lat"
CONF_BOTTOM_RIGHT_LON: Final = "bottom_right_lon"

CONF_CATEGORIES: Final = "categories"
CONF_MAX_AGE_DAYS: Final = "max_age_days"
CONF_SELECTED_SENSORS: Final = "selected_sensors"
CONF_SENSORS_METADATA: Final = "sensors_metadata"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Categories
CATEGORY_LIGHT_AND_RADIATION: Final = "light_and_radiation"
CATEGORY_AIR_AND_ATMOSPHERE: Final = "air_and_atmosphere"
CATEGORY_WATER_AND_SOIL: Final = "water_and_soil"

DEFAULT_CATEGORIES: Final[list[str]] = [
    CATEGORY_LIGHT_AND_RADIATION,
    CATEGORY_AIR_AND_ATMOSPHERE,
    CATEGORY_WATER_AND_SOIL,
]

CATEGORY_PHENOMENA: Final[dict[str, list[str]]] = {
    CATEGORY_LIGHT_AND_RADIATION: [
        "solar_zenith_angle",
        "sunshine_duration",
        "global_radiation",
        "global_radiation_short",
        "global_radiation_long",
        "diffuse_sky_radiation",
        "ambient_radioactive_dose_rate",
        "radioactive_count_rate",
        "ultraviolet_radiation",
        "ultraviolet_a",
        "ultraviolet_b",
        "infrared_radiation",
        "photosynthetically_active_radiation",
    ],
    CATEGORY_AIR_AND_ATMOSPHERE: [
        "air_temperature",
        "relative_humidity",
        "atmospheric_pressure",
        "precipitation",
        "wind_speed",
        "wind_direction",
        "cloud_coverage",
        "snowfall",
        "concentration_of_pm10_in_air",
        "concentration_of_pm2_5_in_air",
    ],
    CATEGORY_WATER_AND_SOIL: [
        "water_level",
        "water_temperature",
        "soil_temperature",
        "snow_depth",
    ],
}


@dataclass(frozen=True)
class PhenomenonMetadata:
    """Metadata mapping for a Sensoto phenomenon code."""

    code: str
    name_de: str
    name_en: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    icon: str = "mdi:chart-line"
    valid_device_class_units: set[str] | None = None


PHENOMENON_CATALOG: Final[dict[str, PhenomenonMetadata]] = {
    # Light & Radiation
    "solar_zenith_angle": PhenomenonMetadata(
        code="solar_zenith_angle",
        name_de="Sonnenzenitwinkel",
        name_en="Solar Zenith Angle",
        icon="mdi:angle-acute",
    ),
    "sunshine_duration": PhenomenonMetadata(
        code="sunshine_duration",
        name_de="Sonnenscheindauer",
        name_en="Sunshine Duration",
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:weather-sunny",
        valid_device_class_units={"s", "min", "h", "d"},
    ),
    "global_radiation": PhenomenonMetadata(
        code="global_radiation",
        name_de="Globalstrahlung",
        name_en="Global Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:white-balance-sunny",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "global_radiation_short": PhenomenonMetadata(
        code="global_radiation_short",
        name_de="Kurzwellige Globalstrahlung",
        name_en="Shortwave Global Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:solar-power",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "global_radiation_long": PhenomenonMetadata(
        code="global_radiation_long",
        name_de="Langwellige Strahlung",
        name_en="Longwave Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:solar-power",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "diffuse_sky_radiation": PhenomenonMetadata(
        code="diffuse_sky_radiation",
        name_de="Diffuse Himmelsstrahlung",
        name_en="Diffuse Sky Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:weather-partly-cloudy",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "ambient_radioactive_dose_rate": PhenomenonMetadata(
        code="ambient_radioactive_dose_rate",
        name_de="Ortsdosisleistung (ODL)",
        name_en="Ambient Radioactive Dose Rate",
        icon="mdi:radioactive",
    ),
    "radioactive_count_rate": PhenomenonMetadata(
        code="radioactive_count_rate",
        name_de="Radioaktive Zählrate",
        name_en="Radioactive Count Rate",
        icon="mdi:pulse",
    ),
    "ultraviolet_radiation": PhenomenonMetadata(
        code="ultraviolet_radiation",
        name_de="UV-Strahlung",
        name_en="Ultraviolet Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:sun-wireless",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "ultraviolet_a": PhenomenonMetadata(
        code="ultraviolet_a",
        name_de="UV-A Strahlung",
        name_en="UV-A Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:sun-wireless",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "ultraviolet_b": PhenomenonMetadata(
        code="ultraviolet_b",
        name_de="UV-B Strahlung",
        name_en="UV-B Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:sun-wireless",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "infrared_radiation": PhenomenonMetadata(
        code="infrared_radiation",
        name_de="Infrarotstrahlung",
        name_en="Infrared Radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:heat-wave",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    "photosynthetically_active_radiation": PhenomenonMetadata(
        code="photosynthetically_active_radiation",
        name_de="Photosynthetisch aktive Strahlung (PAR)",
        name_en="Photosynthetically Active Radiation (PAR)",
        device_class=SensorDeviceClass.IRRADIANCE,
        icon="mdi:sprout",
        valid_device_class_units={"W/m²", "W/m2"},
    ),
    # Air & Atmosphere
    "air_temperature": PhenomenonMetadata(
        code="air_temperature",
        name_de="Lufttemperatur",
        name_en="Air Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
        valid_device_class_units={"°C", "°F", "K"},
    ),
    "relative_humidity": PhenomenonMetadata(
        code="relative_humidity",
        name_de="Relative Luftfeuchtigkeit",
        name_en="Relative Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        icon="mdi:water-percent",
        valid_device_class_units={"%"},
    ),
    "atmospheric_pressure": PhenomenonMetadata(
        code="atmospheric_pressure",
        name_de="Luftdruck",
        name_en="Atmospheric Pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        icon="mdi:gauge",
        valid_device_class_units={"hPa", "Pa", "kPa", "mbar", "bar"},
    ),
    "precipitation": PhenomenonMetadata(
        code="precipitation",
        name_de="Niederschlag",
        name_en="Precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        icon="mdi:weather-rainy",
        valid_device_class_units={"mm", "cm", "in"},
    ),
    "wind_speed": PhenomenonMetadata(
        code="wind_speed",
        name_de="Windgeschwindigkeit",
        name_en="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        icon="mdi:weather-windy",
        valid_device_class_units={"m/s", "km/h", "kn", "mph"},
    ),
    "wind_direction": PhenomenonMetadata(
        code="wind_direction",
        name_de="Windrichtung",
        name_en="Wind Direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        icon="mdi:compass-outline",
        valid_device_class_units={"°"},
    ),
    "cloud_coverage": PhenomenonMetadata(
        code="cloud_coverage",
        name_de="Bewölkungsgrad",
        name_en="Cloud Coverage",
        icon="mdi:weather-cloudy",
    ),
    "snowfall": PhenomenonMetadata(
        code="snowfall",
        name_de="Schneefall",
        name_en="Snowfall",
        device_class=SensorDeviceClass.PRECIPITATION,
        icon="mdi:weather-snowy-heavy",
        valid_device_class_units={"mm", "cm", "in"},
    ),
    "concentration_of_pm10_in_air": PhenomenonMetadata(
        code="concentration_of_pm10_in_air",
        name_de="Feinstaub PM10",
        name_en="Particulate Matter PM10",
        device_class=SensorDeviceClass.PM10,
        icon="mdi:blur",
        valid_device_class_units={"µg/m³", "ug/m3"},
    ),
    "concentration_of_pm2_5_in_air": PhenomenonMetadata(
        code="concentration_of_pm2_5_in_air",
        name_de="Feinstaub PM2.5",
        name_en="Particulate Matter PM2.5",
        device_class=SensorDeviceClass.PM25,
        icon="mdi:blur",
        valid_device_class_units={"µg/m³", "ug/m3"},
    ),
    # Water & Soil
    "water_level": PhenomenonMetadata(
        code="water_level",
        name_de="Wasserstand / Pegel",
        name_en="Water Level",
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:waves-arrow-up",
        valid_device_class_units={"cm", "m", "mm"},
    ),
    "water_temperature": PhenomenonMetadata(
        code="water_temperature",
        name_de="Wassertemperatur",
        name_en="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:coolant-temperature",
        valid_device_class_units={"°C", "°F", "K"},
    ),
    "soil_temperature": PhenomenonMetadata(
        code="soil_temperature",
        name_de="Bodentemperatur",
        name_en="Soil Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-lines",
        valid_device_class_units={"°C", "°F", "K"},
    ),
    "snow_depth": PhenomenonMetadata(
        code="snow_depth",
        name_de="Schneehöhe",
        name_en="Snow Depth",
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:snowflake",
        valid_device_class_units={"cm", "m", "mm"},
    ),
}
