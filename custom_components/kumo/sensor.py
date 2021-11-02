"""HomeAssistant sensor component for Kumo Station Device."""
import logging
import pprint
from datetime import timedelta

import pykumo
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady

from .const import DOMAIN

try:
    from homeassistant.components.sensor import SensorEntity
except ImportError:
    from homeassistant.components.sensor import SensorDevice as SensorEntity

import homeassistant.helpers.config_validation as cv

from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, CONF_SCAN_INTERVAL

from . import CONF_CONNECT_TIMEOUT, CONF_RESPONSE_TIMEOUT, KUMO_DATA

_LOGGER = logging.getLogger(__name__)
__PLATFORM_IS_SET_UP = False

CONF_NAME = "name"
CONF_ADDRESS = "address"
CONF_CONFIG = "config"

ATTR_RSSI = "rssi"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_CONFIG): cv.string,
    }
)

MAX_SETUP_TRIES = 10
MAX_AVAILABILITY_TRIES = 3

SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kumo Stations."""
    data = hass.data[DOMAIN]
    data._setup_tries += 1
    if data._setup_tries > MAX_SETUP_TRIES:
        raise HomeAssistantError("Giving up trying to set up Kumo")

    devices = []
    units = await hass.async_add_executor_job(data.get_account().get_kumo_stations)
    for unit in units:
        name = data.get_account().get_name(unit)
        address = data.get_account().get_address(unit)
        credentials = data.get_account().get_credentials(unit)
        connect_timeout = float(
            data.get_domain_options().get(CONF_CONNECT_TIMEOUT, "1.2")
        )
        response_timeout = float(
            data.get_domain_options().get(CONF_RESPONSE_TIMEOUT, "8")
        )
        kumo_api = pykumo.PyKumoStation(
            name, address, credentials, (connect_timeout, response_timeout)
        )
        success = await hass.async_add_executor_job(kumo_api.update_status)
        if not success:
            _LOGGER.warning("Kumo %s could not be set up", name)
            continue
        kumo_station = KumoStationOutdoorTemperature(kumo_api, unit)
        await hass.async_add_executor_job(kumo_station.update)
        devices.append(kumo_station)
        _LOGGER.debug("Kumo adding entity: %s", name)

    if devices:
        async_add_entities(devices, True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Kumo Stations. Run Once"""
    global __PLATFORM_IS_SET_UP
    if __PLATFORM_IS_SET_UP:
        return
    __PLATFORM_IS_SET_UP = True

    data = hass.data[KUMO_DATA]
    data._setup_tries += 1
    if data._setup_tries > MAX_SETUP_TRIES:
        raise HomeAssistantError("Giving up trying to set up Kumo Stations")

    devices = []
    units = data.get_account().get_kumo_stations()
    for unit in units:
        name = data.get_account().get_name(unit)
        address = data.get_account().get_address(unit)
        credentials = data.get_account().get_credentials(unit)
        if data.get_domain_options().get(CONF_CONNECT_TIMEOUT) is None:
            connect_timeout = 1.2
        else:
            connect_timeout = float(
                data.get_domain_options().get(CONF_CONNECT_TIMEOUT, "1.2")
            )
        if data.get_domain_options().get(CONF_RESPONSE_TIMEOUT) is None:
            response_timeout = 8.0
        else:
            response_timeout = float(
                data.get_domain_options().get(CONF_RESPONSE_TIMEOUT, "8")
            )
        kumo_api = pykumo.PyKumoStation(
            name, address, credentials, (connect_timeout, response_timeout)
        )
        success = await hass.async_add_executor_job(kumo_api.update_status)
        if not success:
            _LOGGER.warning("Kumo %s could not be set up", name)
            continue
        kumo_station = KumoStationOutdoorTemperature(kumo_api, unit)
        await hass.async_add_executor_job(kumo_station.update)
        devices.append(kumo_station)
        _LOGGER.debug("Kumo adding entity: %s", name)
    if devices:
        async_add_entities(devices)


class KumoStationOutdoorTemperature(SensorEntity):
    """Representation of a Kumo Station Outdoor Temperature Sensor."""

    def __init__(self, kumo_api, unit):
        """Initialize the kumo station."""

        self._name = kumo_api.get_name() + " Outdoor Temperature"
        self._identifier = unit
        self._outdoor_temperature = None
        self._rssi = None
        self._pykumo = kumo_api
        self._unavailable_count = 0
        self._available = False

    def update(self):
        """Call from HA to trigger a refresh of cached state."""
        success = self._pykumo.update_status()
        self._update_availability(success)
        self._outdoor_temperature = self._pykumo.get_outdoor_temperature()

    def _update_availability(self, success):
        if success:
            self._available = True
            self._unavailable_count = 0
        else:
            self._unavailable_count += 1
            if self._unavailable_count >= MAX_AVAILABILITY_TRIES:
                self._available = False

    @property
    def available(self):
        """Return whether Home Assistant is able to read the state and control the underlying device."""
        return self._available

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def native_value(self):
        """Return the high dual setpoint temperature."""
        return self._outdoor_temperature

    @property
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def unique_id(self):
        """Return unique id"""
        return self._identifier

    @property
    def device_info(self):
        """Return device information for this Kumo Station"""
        return {
            "identifiers": {(DOMAIN, self._identifier)},
            "name": self.name,
            "manufacturer": "Mistubishi",
        }
