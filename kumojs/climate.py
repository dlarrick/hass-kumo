import json
import logging
import urllib
import urllib.parse
from urllib.request import urlopen

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import(ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.components.climate.const import(
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_DRY,
    ATTR_HVAC_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
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
    """Set up the KumoJS thermostat."""

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    add_devices([KumoJSThermostat(name, host)])

class KumoJSThermostat(ClimateDevice):
    """Representation of a KumoJS Thermostat device."""

    def __init__(self, name, host):
        """Initialize the thermostat."""
        self.host = host
        self._name = name
        self._current = {'temperature':  None,
                         'swing_mode': None,
                         'fan_mode': None,
                         'hvac_mode': None}
        self._target_temperature = None
        self._hvac_mode = HVAC_MODE_OFF
        self._hvac_modes = ['auto', 'heat', 'cool', 'dry', 'off']
        self._fan_modes = ['auto', 'quiet', 'low', 'powerful', 'superPowerful']
        self._swing_modes = ['auto', 'horizontal', 'midhorizontal', 'midpoint', 'midvertical',
                             'vertical', 'swing']
        self.data = None
        self.update()

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
    def hvac_mode(self):
        """Return current hvac operation mode."""
        if self.data is not None:
            try:
                self._current['hvac_mode'] = self.data['r']['indoorUnit']['status']['mode']
            except KeyError:
                pass
        else:
            self._current['hvac_mode'] = None
        try:
            result = KUMO_STATE_TO_HA[self._current['hvac_mode']]
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
        if self.data is not None:
            try:
                self._current['fan_mode'] = self.data['r']['indoorUnit']['status']['fanSpeed']
            except KeyError:
                pass
        else:
            self._current['fan_mode'] = None
        return self._current['fan_mode']

    @property
    def fan_modes(self):
        """Returns the list of available operation modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return current swing setting."""
        if self.data is not None:
            try:
                self._current['swing_mode'] = self.data['r']['indoorUnit']['status']['vaneDir']
            except KeyError:
                pass
        else:
            self._current['swing_mode'] = None
        return self._current['swing_mode']

    @property
    def swing_modes(self):
        """Returns the list of available operation modes."""
        return self._swing_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.data is not None:
            try:
                self._current['temperature'] = self.data['r']['indoorUnit']['status']['roomTemp']
            except KeyError:
                pass
        else:
            self._current['temperature'] = None
        return self._current['temperature']

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.data is None:
            self._target_temperature = None
            return None

        try:
            idumode = self.data['r']['indoorUnit']['status']['mode']
            if idumode == 'heat':
                mode = 'spHeat'
            elif idumode == 'cool':
                mode = 'spCool'
            else:
                self._target_temperature = None
                return None

            self._target_temperature = self.data['r']['indoorUnit']['status'][mode]
        except KeyError:
            pass
        return self._target_temperature

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # Set requires temp in F
        temperature_f = (temperature * 1.8) + 32

        try:
            mode_to_set = HA_STATE_TO_KUMO[kwargs.get(ATTR_HVAC_MODE)]
        except KeyError:
            mode_to_set = None

        if mode_to_set is None:
            try:
                idumode = self.data['r']['indoorUnit']['status']['mode']
                if idumode in ('heat', 'cool'):
                    mode = idumode
                else:
                    _LOGGER.warning("KumoJS %s not setting target temperature for current mode %s",
                                    self._name, mode_to_set)
                    return
            except KeyError:
                return
        else:
            if mode_to_set in ('heat', 'cool'):
                mode = mode_to_set
            else:
                _LOGGER.warning("KumoJS %s not setting target temperature for supplied mode %s",
                                self._name, mode_to_set)
                return

        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/' + mode +
            '/temp/' + str(temperature_f), method='PUT')
        _LOGGER.debug("KumoJS %s set temp: %s", self._name, str(temperature_f))
        response = urlopen(req)
        self._target_temperature = temperature
        string = response.read().decode('utf-8')
        _LOGGER.info("KumoJS %s set temp response: %s", self._name, string)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode"""
        try:
            mode = HA_STATE_TO_KUMO[hvac_mode]
        except KeyError:
            mode = "off"

        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/mode/' + mode,
            method='PUT')
        response = urlopen(req)
        self._current['hvac_mode'] = mode
        string = response.read().decode('utf-8')
        _LOGGER.info("KumoJS %s set mode response: %s", self._name, string)

    def set_swing_mode(self, swing_mode):
        """Set new vane swing mode"""
        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/vent/' + swing_mode,
            method='PUT')
        response = urlopen(req)
        self._current['swing_mode'] = swing_mode
        string = response.read().decode('utf-8')
        _LOGGER.info("KumoJS %s set swing mode response: %s", self._name, string)

    def set_fan_mode(self, fan_mode):
        """Set new fan speed mode"""
        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/speed/' + fan_mode,
            method='PUT')
        response = urlopen(req)
        self._current['fan_mode'] = fan_mode
        string = response.read().decode('utf-8')
        _LOGGER.info("KumoJS %s set fan speed response: %s", self._name, string)

    def update(self):
        """Get the latest data."""
        response = urlopen('http://' + self.host + ':8084/v0/room/' +
                           urllib.parse.quote(self.name) + "/status")
        string = response.read().decode('utf-8')
        _LOGGER.debug("KumoJS %s update: %s", self._name, string)
        self.data = json.loads(string)
