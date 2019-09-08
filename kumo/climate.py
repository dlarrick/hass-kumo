""" HomeAssistant climate component for KumoCloud connected HVAC units
"""
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import(ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.components.climate.const import(
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_DRY,
    ATTR_HVAC_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE)

import pykumo

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
CONF_ADDRESS = 'address'
CONF_CONFIG = 'config'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_CONFIG): cv.string,
})

HA_STATE_TO_KUMO = {
    HVAC_MODE_HEAT_COOL: 'auto',
    HVAC_MODE_COOL: 'cool',
    HVAC_MODE_HEAT: 'heat',
    HVAC_MODE_DRY: 'dry',
    HVAC_MODE_OFF: 'off'
}
KUMO_STATE_TO_HA = {
    'auto': HVAC_MODE_HEAT_COOL,
    'cool': HVAC_MODE_COOL,
    'heat': HVAC_MODE_HEAT,
    'dry': HVAC_MODE_DRY,
    'off': HVAC_MODE_OFF
}

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Kumo thermostat."""

    name = config.get(CONF_NAME)
    address = config.get(CONF_ADDRESS)
    config_js = config.get(CONF_CONFIG)

    add_devices([KumoThermostat(name, address, config_js)])

class KumoThermostat(ClimateDevice):
    """Representation of a Kumo Thermostat device."""

    def __init__(self, name, address, config_js):
        """Initialize the thermostat."""
        self._name = name
        self._target_temperature = None
        self._hvac_modes = ['auto', 'heat', 'cool', 'dry', 'off']
        self._fan_modes = ['auto', 'quiet', 'low', 'powerful', 'superPowerful']
        self._swing_modes = ['auto', 'horizontal', 'midhorizontal', 'midpoint', 'midvertical',
                             'vertical', 'swing']
        self._pykumo = pykumo.PyKumo(name, address, config_js)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_humidity(self):
        """Return the current humidity, if known."""
        humidity = self._pykumo.get_current_humidity()
        return humidity

    @property
    def hvac_mode(self):
        """Return current hvac operation mode."""
        mode = self._pykumo.get_mode()
        try:
            result = KUMO_STATE_TO_HA[mode]
        except KeyError:
            result = HVAC_MODE_OFF
        return result

    @property
    def hvac_modes(self):
        """Returns the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return current fan setting."""
        fan_mode = self._pykumo.get_fan_speed()
        return fan_mode

    @property
    def fan_modes(self):
        """Returns the list of available operation modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return current swing setting."""
        swing_mode = self._pykumo.get_vane_direction()
        return swing_mode

    @property
    def swing_modes(self):
        """Returns the list of available operation modes."""
        return self._swing_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        temp = self._pykumo.get_current_temperature()
        return temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        temp = None
        idumode = self.hvac_mode
        if idumode == 'heat':
            temp = self._pykumo.get_heat_setpoint()
        elif idumode == 'cool':
            temp = self._pykumo.get_cool_setpoint()
        else:
            temp = None
        return temp

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            mode_to_set = HA_STATE_TO_KUMO[kwargs.get(ATTR_HVAC_MODE)]
        except KeyError:
            mode_to_set = None

        if mode_to_set is None:
            mode_to_set = self.hvac_mode

        if mode_to_set not in ('heat', 'cool'):
            _LOGGER.warning("Kumo %s not setting target temperature for mode %s",
                            self._name, mode_to_set)
            return

        if mode_to_set == 'heat':
            response = self._pykumo.set_heat_setpoint(temperature)
        else:
            response = self._pykumo.set_cool_setpoint(temperature)
        _LOGGER.debug("Kumo %s set temp: %s C", self._name, str(temperature))
        _LOGGER.info("Kumo %s set temp response: %s", self._name, response)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode"""
        try:
            mode = HA_STATE_TO_KUMO[hvac_mode]
        except KeyError:
            mode = "off"

        response = self._pykumo.set_mode(mode)
        _LOGGER.info("Kumo %s set mode response: %s", self._name, response)

    def set_swing_mode(self, swing_mode):
        """Set new vane swing mode"""
        response = self._pykumo.set_vane_direction(swing_mode)
        _LOGGER.info("Kumo %s set swing mode response: %s", self._name, response)

    def set_fan_mode(self, fan_mode):
        """Set new fan speed mode"""
        response = self._pykumo.set_fan_speed(fan_mode)
        _LOGGER.info("Kumo %s set fan speed response: %s", self._name, response)
