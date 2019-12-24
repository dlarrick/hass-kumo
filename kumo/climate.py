""" HomeAssistant climate component for KumoCloud connected HVAC units
"""
import logging
import pprint

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import(ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.components.climate.const import(
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, ATTR_HVAC_MODE, CURRENT_HVAC_IDLE,
    CURRENT_HVAC_COOL, CURRENT_HVAC_HEAT, CURRENT_HVAC_DRY, CURRENT_HVAC_OFF,
    SUPPORT_TARGET_TEMPERATURE_RANGE)
from homeassistant.const import (TEMP_CELSIUS)

from . import KUMO_DATA

_LOGGER = logging.getLogger(__name__)
__PLATFORM_IS_SET_UP = False

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
    HVAC_MODE_FAN_ONLY: 'vent',
    HVAC_MODE_OFF: 'off'
}
KUMO_STATE_TO_HA = {
    'auto': HVAC_MODE_HEAT_COOL,
    'autoCool': HVAC_MODE_HEAT_COOL,
    'autoHeat': HVAC_MODE_HEAT_COOL,
    'cool': HVAC_MODE_COOL,
    'heat': HVAC_MODE_HEAT,
    'dry': HVAC_MODE_DRY,
    'vent': HVAC_MODE_FAN_ONLY,
    'off': HVAC_MODE_OFF
}
KUMO_STATE_TO_HA_ACTION = {
    'auto': CURRENT_HVAC_IDLE,
    'autoCool': CURRENT_HVAC_COOL,
    'autoHeat': CURRENT_HVAC_HEAT,
    'cool': CURRENT_HVAC_COOL,
    'heat': CURRENT_HVAC_HEAT,
    'dry': CURRENT_HVAC_DRY,
    'vent': CURRENT_HVAC_IDLE,
    'off': CURRENT_HVAC_OFF
}

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Kumo thermostats."""

    # Run once
    global __PLATFORM_IS_SET_UP
    if __PLATFORM_IS_SET_UP:
        return
    __PLATFORM_IS_SET_UP = True

    data = hass.data[KUMO_DATA]
    devices = []
    units = data.get_account().get_indoor_units()
    for unit in units:
        name = data.get_account().get_name(unit)
        address = data.get_account().get_address(unit)
        credentials = data.get_account().get_credentials(unit)
        devices.append(KumoThermostat(name, address, credentials))
        _LOGGER.debug("Kumo adding entity: %s", name)
    async_add_entities(devices)

class KumoThermostat(ClimateDevice):
    """Representation of a Kumo Thermostat device."""

    _update_properties = ['current_humidity', 'hvac_mode',
                          'hvac_action', 'fan_mode', 'swing_mode',
                          'current_temperature', 'target_temperature',
                          'target_temperature_high', 'target_temperature_low',
                          'battery_percent']

    def __init__(self, name, address, config_js):
        """Initialize the thermostat."""
        import pykumo

        self._name = name
        self._target_temperature = None
        self._target_temperature_low = None
        self._target_temperature_high = None
        self._current_humidity = None
        self._hvac_mode = None
        self._hvac_action = None
        self._fan_mode = None
        self._swing_mode = None
        self._current_temperature = None
        self._battery_percent = None
        self._pykumo = pykumo.PyKumo(name, address, config_js)
        self._fan_modes = self._pykumo.get_fan_speeds()
        self._swing_modes = self._pykumo.get_vane_directions()
        self._hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_COOL]
        self._supported_features = (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE)
        if self._pykumo.has_dry_mode():
            self._hvac_modes.append(HVAC_MODE_DRY)
        if self._pykumo.has_heat_mode():
            self._hvac_modes.append(HVAC_MODE_HEAT)
        if self._pykumo.has_vent_mode():
            self._hvac_modes.append(HVAC_MODE_FAN_ONLY)
        if self._pykumo.has_auto_mode():
            self._hvac_modes.append(HVAC_MODE_HEAT_COOL)
            self._supported_features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self._pykumo.has_vane_direction():
            self._supported_features |= SUPPORT_SWING_MODE
        for prop in KumoThermostat._update_properties:
            try:
                setattr(self, "_%s" % prop, None)
            except AttributeError as err:
                _LOGGER.debug("Kumo %s: Initializing attr %s error: %s",
                              self._name, prop, str(err))

        self._available = True

    def update(self):
        """Called by HA to trigger a refresh of cached state."""
        for prop in KumoThermostat._update_properties:
            self._update_property(prop)

    def _update_property(self, prop):
        """Called to refresh the value of a property -- may block on I/O"""
        try:
            do_update = getattr(self, "_update_%s" % prop)
        except AttributeError:
            _LOGGER.debug("Kumo %s: %s property updater not implemented",
                          self._name, prop)
            return
        do_update()

    @property
    def available(self):
        """Return whether Home Assistant is able to read the state and control
        the underlying device.
        """
        return self._available

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

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
        return self._current_humidity

    def _update_current_humidity(self):
        """Refresh cached current humidity."""
        self._current_humidity = self._pykumo.get_current_humidity()

    @property
    def hvac_mode(self):
        """Return current hvac operation state."""
        return self._hvac_mode

    def _update_hvac_mode(self):
        """Refresh cached hvac mode."""
        mode = self._pykumo.get_mode()
        try:
            result = KUMO_STATE_TO_HA[mode]
        except KeyError:
            result = None
        self._hvac_mode = result

    @property
    def hvac_action(self):
        """Return current hvac operation in action."""
        return self._hvac_action

    def _update_hvac_action(self):
        """Refresh cached hvac action"""
        standby = self._pykumo.get_standby()
        if standby:
            result = CURRENT_HVAC_IDLE
        else:
            mode = self._pykumo.get_mode()
            try:
                result = KUMO_STATE_TO_HA_ACTION[mode]
            except KeyError:
                result = None
        self._hvac_action = result

    @property
    def hvac_modes(self):
        """Returns the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return current fan setting."""
        return self._fan_mode

    def _update_fan_mode(self):
        """Refresh cached fan mode"""
        self._fan_mode = self._pykumo.get_fan_speed()

    @property
    def fan_modes(self):
        """Returns the list of available operation modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return current swing setting."""
        return self._swing_mode

    def _update_swing_mode(self):
        """Refresh cached swing mode"""
        self._swing_mode = self._pykumo.get_vane_direction()

    @property
    def swing_modes(self):
        """Returns the list of available operation modes."""
        return self._swing_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    def _update_current_temperature(self):
        """Refresh cached current temperature"""
        self._current_temperature = self._pykumo.get_current_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def _update_target_temperature(self):
        """Refresh the cached target temperature."""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVAC_MODE_HEAT:
            temp = self._pykumo.get_heat_setpoint()
        elif idumode == HVAC_MODE_COOL:
            temp = self._pykumo.get_cool_setpoint()
        else:
            temp = None
        self._target_temperature = temp

    @property
    def target_temperature_high(self):
        """Return the high dual setpoint temperature."""
        return self._target_temperature_high

    def _update_target_temperature_high(self):
        """Refresh the cached target cooling setpoint"""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVAC_MODE_HEAT_COOL:
            temp = self._pykumo.get_cool_setpoint()
        else:
            temp = None
        self._target_temperature_high = temp

    @property
    def target_temperature_low(self):
        """Return the low dual setpoint temperature."""
        return self._target_temperature_low

    def _update_target_temperature_low(self):
        """Refresh the cached target heating setpoint"""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVAC_MODE_HEAT_COOL:
            temp = self._pykumo.get_heat_setpoint()
        else:
            temp = None
        self._target_temperature_low = temp

    @property
    def battery_percent(self):
        """ Return the battery percentage of the attached sensor (if any) """
        return self._battery_percent

    def _update_battery_percent(self):
        """Refresh the cached battery percentage."""
        percent = self._pykumo.get_sensor_battery()
        self._battery_percent = percent

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug("Kumo %s set temp: %s", self._name,
                      pprint.pformat(kwargs))
        target = {}
        if 'target_temp_high' in kwargs:
            target['cool'] = kwargs['target_temp_high']
        if 'target_temp_low' in kwargs:
            target['heat'] = kwargs['target_temp_low']
        if 'temperature' in kwargs:
            target['setpoint'] = kwargs['temperature']
        if len(target) == 0:
            _LOGGER.debug("Kumo %s set temp: no temp in args", self._name)
            return

        try:
            mode_to_set = HA_STATE_TO_KUMO[kwargs.get(ATTR_HVAC_MODE)]
        except KeyError:
            mode_to_set = None

        if mode_to_set is None:
            mode_to_set = self.hvac_mode

        if mode_to_set not in (HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT):
            _LOGGER.warning("Kumo %s not setting target temperature for mode %s",
                            self._name, mode_to_set)
            return

        if mode_to_set == HVAC_MODE_HEAT:
            response = self._pykumo.set_heat_setpoint(target['setpoint'])
        elif mode_to_set == HVAC_MODE_COOL:
            response = self._pykumo.set_cool_setpoint(target['setpoint'])
        else:
            response = self._pykumo.set_heat_setpoint(target['heat'])
            response += " " + self._pykumo.set_cool_setpoint(['cool'])
        _LOGGER.debug("Kumo %s set temp: %s C", self._name, target)
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
