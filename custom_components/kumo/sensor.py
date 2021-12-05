"""HomeAssistant sensor component for Kumo Station Device."""
import logging

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA

from .const import DOMAIN, KUMO_DATA_COORDINATORS
from .coordinator import KumoDataUpdateCoordinator
from .entity import CoordinatedKumoEntitty

try:
    from homeassistant.components.sensor import SensorEntity
except ImportError:
    from homeassistant.components.sensor import SensorDevice as SensorEntity

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (DEVICE_CLASS_SIGNAL_STRENGTH,
                                 DEVICE_CLASS_TEMPERATURE,
                                 SIGNAL_STRENGTH_DECIBELS, TEMP_CELSIUS)
from homeassistant.helpers.typing import HomeAssistantType

from . import KUMO_DATA

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
CONF_ADDRESS = "address"
CONF_CONFIG = "config"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_CONFIG): cv.string,
    }
)

async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry, async_add_entities):
    """Set up the Kumo thermostats."""
    account = hass.data[DOMAIN][entry.entry_id][KUMO_DATA].get_account()
    coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]

    entities = []
    all_serials = await hass.async_add_executor_job(account.get_all_units)
    for serial in all_serials:
        coordinator = coordinators[serial]
        entities.append(KumoWifiSignal(coordinator))
        _LOGGER.debug("Adding entity: wifi_signal for %s", coordinator.get_device().get_name())

    kumo_station_serials = await hass.async_add_executor_job(account.get_kumo_stations)
    for serial in kumo_station_serials:
        coordinator = coordinators[serial]
        entities.append(KumoStationOutdoorTemperature(coordinator))
        _LOGGER.debug("Adding entity: outdoor_temperature for %s", coordinator.get_device().get_name())

    if entities:
        async_add_entities(entities, True)

class KumoStationOutdoorTemperature(CoordinatedKumoEntitty, SensorEntity):
    """Representation of a Kumo Station Outdoor Temperature Sensor."""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Outdoor Temperature"

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-outdoor-temperature"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def native_value(self):
        """Return the high dual setpoint temperature."""
        return self._pykumo.get_outdoor_temperature()

    @property
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE
        # return SensorDeviceClass.TEMPERATURE # Not yet available

class KumoWifiSignal(CoordinatedKumoEntitty, SensorEntity):
    """Representation of a Kumo's WiFi Signal Strength."""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Signal Strength"

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-signal-strength"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return SIGNAL_STRENGTH_DECIBELS

    @property
    def native_value(self):
        """Return the WiFi signal rssi."""
        return self._pykumo.get_wifi_rssi()

    @property
    def device_class(self):
        return DEVICE_CLASS_SIGNAL_STRENGTH
        # return SensorDeviceClass.SIGNAL_STRENGTH # Not yet available

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False

