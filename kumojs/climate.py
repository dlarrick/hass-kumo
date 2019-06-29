import json
import logging
import urllib
import urllib.parse
from urllib.request import urlopen

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import(ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.const import (STATE_OFF)
from homeassistant.components.climate.const import(
    ATTR_OPERATION_MODE,
    STATE_HEAT, STATE_COOL, STATE_DRY, STATE_AUTO,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
})

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
                         'operation': None}
        self._target_temperature = None
        self._state = None
        self._operation_list = ['auto', 'heat', 'cool', 'dry', 'off']
        self._fan_list = ['auto', 'quiet', 'low', 'powerful', 'superPowerful']
        self._swing_list = ['auto', 'horizontal', 'midhorizontal', 'midpoint', 'midvertical',
                            'vertical', 'swing']
        self.data = None
        self.update()

    @property
    def state(self):
        """Return the current state."""
        if self.data is not None:
            try:
                mode = self.data['r']['indoorUnit']['status']['mode']
                if mode == 'off':
                    self._state = STATE_OFF
                elif mode == 'cool':
                    self._state = STATE_COOL
                elif mode == 'heat':
                    self._state = STATE_HEAT
                elif mode == 'auto':
                    self._state = STATE_AUTO
                elif mode == 'dry':
                    self._state = STATE_DRY
            except KeyError:
                pass
        else:
            self._state = None
        return self._state

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                SUPPORT_FAN_MODE | SUPPORT_SWING_MODE)

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation mode."""
        if self.data is not None:
            try:
                self._current['operation'] = self.data['r']['indoorUnit']['status']['mode']
            except KeyError:
                pass
        else:
            self._current['operation'] = None
        return self._current['operation']

    @property
    def operation_list(self):
        """Returns the list of available operation modes."""
        return self._operation_list

    @property
    def current_fan_mode(self):
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
    def fan_list(self):
        """Returns the list of available operation modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
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
    def swing_list(self):
        """Returns the list of available operation modes."""
        return self._swing_list

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

        mode_to_set = kwargs.get(ATTR_OPERATION_MODE)

        if mode_to_set is None:
            try:
                idumode = self.data['r']['indoorUnit']['status']['mode']
                if idumode == 'heat':
                    mode = 'heat'
                elif idumode == 'cool':
                    mode = 'cool'
                else:
                    _LOGGER.warning("KumoJS %s not setting target temperature for current mode %s",
                                    self._name, mode_to_set)
                    return
            except KeyError:
                return
        else:
            if mode_to_set == 'heat' or mode_to_set == 'cool':
                mode = mode_to_set
            else:
                _LOGGER.warning("KumoJS %s not setting target temperature for supplied mode %s",
                                self._name, mode_to_set)
                return

        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/' + mode +
            '/temp/' + str(temperature_f), method='PUT')
        _LOGGER.info("KumoJS %s set temp: %s", self._name, str(temperature_f))
        response = urlopen(req)
        self._target_temperature = temperature
        string = response.read().decode('utf-8')
        _LOGGER.info("KumoJS %s set temp response: %s", self._name, string)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode"""
        mode = "off"
        if operation_mode == STATE_HEAT:
            mode = "heat"
        elif operation_mode == STATE_COOL:
            mode = "cool"
        elif operation_mode == STATE_DRY:
            mode = "dry"
        elif operation_mode == STATE_AUTO:
            mode = "auto"

        req = urllib.request.Request(
            'http://' + self.host + ':8084/v0/room/' +
            urllib.parse.quote(self.name) + '/mode/' + mode,
            method='PUT')
        response = urlopen(req)
        self._current['operation'] = mode
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
        _LOGGER.info("KumoJS %s update: %s", self._name, string)
        self.data = json.loads(string)
