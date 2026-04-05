"""HomeAssistant sensor component for Kumo Station Device."""
import logging

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA

from .const import DOMAIN, KUMO_DATA_COORDINATORS
from .coordinator import KumoDataUpdateCoordinator
from .entity import CoordinatedKumoEntity
from .temperature import c_to_f

try:
    from homeassistant.components.sensor import SensorEntity
except ImportError:
    from homeassistant.components.sensor import SensorDevice as SensorEntity

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS, UnitOfTemperature, PERCENTAGE, PRECISION_TENTHS
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant

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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Kumo thermostats."""
    account = hass.data[DOMAIN][entry.entry_id][KUMO_DATA].get_account()
    coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]

    entities = []
    all_serials = await hass.async_add_executor_job(account.get_all_units)
    for serial in all_serials:
        coordinator = coordinators[serial]

        entities.append(KumoCurrentHumidity(coordinator))
        _LOGGER.debug("Adding entity: current_humidity for %s", coordinator.get_device().get_name())
        entities.append(KumoCurrentTemperature(coordinator))
        _LOGGER.debug("Adding entity: current_temperature for %s", coordinator.get_device().get_name())
        entities.append(KumoSensorBattery(coordinator))
        _LOGGER.debug("Adding entity: sensor_battery for %s", coordinator.get_device().get_name())
        entities.append(KumoSensorSignalStrength(coordinator))
        _LOGGER.debug("Adding entity: sensor_signal_strength for %s", coordinator.get_device().get_name())
        entities.append(KumoWifiSignal(coordinator))
        _LOGGER.debug("Adding entity: wifi_signal for %s", coordinator.get_device().get_name())

    kumo_station_serials = await hass.async_add_executor_job(account.get_kumo_stations)
    for serial in kumo_station_serials:
        coordinator = coordinators[serial]
        entities.append(KumoStationOutdoorTemperature(coordinator))
        _LOGGER.debug("Adding entity: outdoor_temperature for %s", coordinator.get_device().get_name())

    if entities:
        async_add_entities(entities, True)

class KumoCurrentHumidity(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo's Unit's Current Humidity"""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Current Humidity"

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-current-humidity"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return PERCENTAGE

    @property
    def native_value(self):
        """Return the current humidity level."""
        return self._pykumo.get_current_humidity()

    @property
    def device_class(self):
        return SensorDeviceClass.HUMIDITY

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False

class KumoCurrentTemperature(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo's Unit's Current Temperature"""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Current Temperature"

    @property
    def _use_fahrenheit(self):
        """Return True if the user's HA config is set to Fahrenheit."""
        return self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-current-temperature"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        if self._use_fahrenheit:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the current temperature."""
        temp = self._pykumo.get_current_temperature()
        if self._use_fahrenheit:
            temp = c_to_f(temp)
        return temp

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable entity by default."""
        return True

class KumoSensorBattery(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo Sensor's Battery Level."""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Sensor Battery"

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-sensor-battery"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return PERCENTAGE

    @property
    def native_value(self):
        """Return the sensor's current battery level."""
        return self._pykumo.get_sensor_battery()

    @property
    def device_class(self):
        return SensorDeviceClass.BATTERY

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False

class KumoSensorSignalStrength(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo Sensor's Signal Strength."""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Sensor Signal Strength"

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-sensor-signal-strength"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return SIGNAL_STRENGTH_DECIBELS

    @property
    def native_value(self):
        """Return the sengor's signal strength in rssi."""
        return self._pykumo.get_sensor_rssi()

    @property
    def device_class(self):
        return SensorDeviceClass.SIGNAL_STRENGTH

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False


class KumoStationOutdoorTemperature(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo Station Outdoor Temperature Sensor."""

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the kumo station."""
        super().__init__(coordinator)
        self._name = self._pykumo.get_name() + " Outdoor Temperature"

    @property
    def _use_fahrenheit(self):
        """Return True if the user's HA config is set to Fahrenheit."""
        return self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    @property
    def unique_id(self):
        """Return unique id"""
        return f"{self._identifier}-outdoor-temperature"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        if self._use_fahrenheit:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the unit's reported outdoor temperature."""
        temp = self._pykumo.get_outdoor_temperature()
        if self._use_fahrenheit:
            temp = c_to_f(temp)
        return temp

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False


class KumoWifiSignal(CoordinatedKumoEntity, SensorEntity):
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
        return SensorDeviceClass.SIGNAL_STRENGTH

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Disable entity by default."""
        return False
