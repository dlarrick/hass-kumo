"""HomeAssistant climate component for KumoCloud connected HVAC units."""
import logging
import pprint

import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import KumoDataUpdateCoordinator
from .entity import CoordinatedKumoEntity

try:
    from homeassistant.components.climate import ClimateEntity
except ImportError:
    from homeassistant.components.climate import ClimateDevice as ClimateEntity

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from .const import KUMO_DATA, KUMO_DATA_COORDINATORS

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
CONF_ADDRESS = "address"
CONF_CONFIG = "config"

ATTR_FILTER_DIRTY = "filter_dirty"
ATTR_DEFROST = "defrost"
ATTR_RSSI = "rssi"
ATTR_SENSOR_RSSI = "sensor_rssi"
ATTR_RUNSTATE = "runstate"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_CONFIG): cv.string,
    }
)

KUMO_STATE_AUTO = "auto"
KUMO_STATE_AUTO_COOL = "autoCool"
KUMO_STATE_AUTO_HEAT = "autoHeat"
KUMO_STATE_COOL = "cool"
KUMO_STATE_HEAT = "heat"
KUMO_STATE_DRY = "dry"
KUMO_STATE_VENT = "vent"
KUMO_STATE_OFF = "off"

HA_STATE_TO_KUMO = {
    HVACMode.HEAT_COOL: KUMO_STATE_AUTO,
    HVACMode.COOL: KUMO_STATE_COOL,
    HVACMode.HEAT: KUMO_STATE_HEAT,
    HVACMode.DRY: KUMO_STATE_DRY,
    HVACMode.FAN_ONLY: KUMO_STATE_VENT,
    HVACMode.OFF: KUMO_STATE_OFF,
}
KUMO_STATE_TO_HA = {
    KUMO_STATE_AUTO: HVACMode.HEAT_COOL,
    KUMO_STATE_AUTO_COOL: HVACMode.HEAT_COOL,
    KUMO_STATE_AUTO_HEAT: HVACMode.HEAT_COOL,
    KUMO_STATE_COOL: HVACMode.COOL,
    KUMO_STATE_HEAT: HVACMode.HEAT,
    KUMO_STATE_DRY: HVACMode.DRY,
    KUMO_STATE_VENT: HVACMode.FAN_ONLY,
    KUMO_STATE_OFF: HVACMode.OFF,
}
KUMO_STATE_TO_HA_ACTION = {
    KUMO_STATE_AUTO: HVACAction.IDLE,
    KUMO_STATE_AUTO_COOL: HVACAction.COOLING,
    KUMO_STATE_AUTO_HEAT: HVACAction.HEATING,
    KUMO_STATE_COOL: HVACAction.COOLING,
    KUMO_STATE_HEAT: HVACAction.HEATING,
    KUMO_STATE_DRY: HVACAction.DRYING,
    KUMO_STATE_VENT: HVACAction.FAN,
    KUMO_STATE_OFF: HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Kumo thermostats."""
    account = hass.data[DOMAIN][entry.entry_id][KUMO_DATA].get_account()
    coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]

    entities = []
    indoor_unit_serials = await hass.async_add_executor_job(account.get_indoor_units)
    for serial in indoor_unit_serials:
        coordinator = coordinators[serial]
        entities.append(KumoThermostat(coordinator))
        _LOGGER.debug("Adding entity: %s", coordinator.get_device().get_name())
    if not entities:
        raise ConfigEntryNotReady("Kumo integration found no indoor units")
    async_add_entities(entities, True)


class KumoThermostat(CoordinatedKumoEntity, ClimateEntity):
    """Representation of a Kumo Thermostat device."""

    _update_properties = [
        "current_humidity",
        "hvac_mode",
        "hvac_action",
        "fan_mode",
        "swing_mode",
        "current_temperature",
        "target_temperature",
        "target_temperature_high",
        "target_temperature_low",
        "battery_percent",
        "filter_dirty",
        "defrost",
        "rssi",
        "sensor_rssi",
        "runstate",
    ]

    _enable_turn_on_off_backwards_compatibility = False # can be removed once 2024.12 is no longer supported

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the thermostat."""

        super().__init__(coordinator)
        coordinator.add_update_method(self.update)
        self._name = self._pykumo.get_name()
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
        self._filter_dirty = None
        self._defrost = None
        self._rssi = None
        self._sensor_rssi = None
        self._runstate = None
        self._fan_modes = self._pykumo.get_fan_speeds()
        self._swing_modes = self._pykumo.get_vane_directions()
        self._hvac_modes = [HVACMode.OFF, HVACMode.COOL]
        self._supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE |
            ClimateEntityFeature.TURN_OFF
        )
        if self._pykumo.has_dry_mode():
            self._hvac_modes.append(HVACMode.DRY)
        if self._pykumo.has_heat_mode():
            self._hvac_modes.append(HVACMode.HEAT)
        if self._pykumo.has_vent_mode():
            self._hvac_modes.append(HVACMode.FAN_ONLY)
        if self._pykumo.has_auto_mode():
            self._hvac_modes.append(HVACMode.HEAT_COOL)
            self._supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._pykumo.has_vane_direction():
            self._supported_features |= ClimateEntityFeature.SWING_MODE
        for prop in KumoThermostat._update_properties:
            try:
                setattr(self, f"_{prop}", None)
            except AttributeError as err:
                _LOGGER.debug(
                    "Kumo %s: Initializing attr %s error: %s",
                    self._name,
                    prop,
                    str(err),
                )

    @property
    def unique_id(self):
        """Return unique id"""
        # For backwards compatibility, this ID is considered the primary
        return self._identifier

    async def update(self):
        """Call from HA to trigger a refresh of cached state."""
        for prop in KumoThermostat._update_properties:
            self._update_property(prop)
            if not self.available:
                # Get out early if it's failing
                break

    def _update_property(self, prop):
        """Call to refresh the value of a property -- may block on I/O."""
        try:
            do_update = getattr(self, f"_update_{prop}")
        except AttributeError:
            _LOGGER.debug(
                "Kumo %s: %s property updater not implemented", self._name, prop
            )
            return
        do_update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return UnitOfTemperature.CELSIUS

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
        """Refresh cached hvac action."""
        standby = self._pykumo.get_standby()
        if standby:
            result = HVACAction.IDLE
        else:
            mode = self._pykumo.get_mode()
            try:
                result = KUMO_STATE_TO_HA_ACTION[mode]
            except KeyError:
                result = None
        self._hvac_action = result

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return current fan setting."""
        return self._fan_mode

    def _update_fan_mode(self):
        """Refresh cached fan mode."""
        self._fan_mode = self._pykumo.get_fan_speed()

    @property
    def fan_modes(self):
        """Return the list of available operation modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return current swing setting."""
        return self._swing_mode

    def _update_swing_mode(self):
        """Refresh cached swing mode."""
        self._swing_mode = self._pykumo.get_vane_direction()

    @property
    def swing_modes(self):
        """Return the list of available operation modes."""
        return self._swing_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    def _update_current_temperature(self):
        """Refresh cached current temperature."""
        self._current_temperature = self._pykumo.get_current_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def _update_target_temperature(self):
        """Refresh the cached target temperature."""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVACMode.HEAT:
            temp = self._pykumo.get_heat_setpoint()
        elif idumode == HVACMode.COOL:
            temp = self._pykumo.get_cool_setpoint()
        else:
            temp = None
        self._target_temperature = temp

    @property
    def target_temperature_high(self):
        """Return the high dual setpoint temperature."""
        return self._target_temperature_high

    def _update_target_temperature_high(self):
        """Refresh the cached target cooling setpoint."""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVACMode.HEAT_COOL:
            temp = self._pykumo.get_cool_setpoint()
        else:
            temp = None
        self._target_temperature_high = temp

    @property
    def target_temperature_low(self):
        """Return the low dual setpoint temperature."""
        return self._target_temperature_low

    def _update_target_temperature_low(self):
        """Refresh the cached target heating setpoint."""
        temp = None
        idumode = self.hvac_mode
        if idumode == HVACMode.HEAT_COOL:
            temp = self._pykumo.get_heat_setpoint()
        else:
            temp = None
        self._target_temperature_low = temp

    @property
    def battery_percent(self):
        """Return the battery percentage of the attached sensor (if any)."""
        return self._battery_percent

    def _update_battery_percent(self):
        """Refresh the cached battery percentage."""
        percent = self._pykumo.get_sensor_battery()
        self._battery_percent = percent

    @property
    def filter_dirty(self):
        """Return whether filter is dirty."""
        return self._filter_dirty

    def _update_filter_dirty(self):
        """Refresh the cached filter_dirty attribute."""
        dirty = self._pykumo.get_filter_dirty()
        self._filter_dirty = dirty

    @property
    def rssi(self):
        """Return WiFi RSSI, if any."""
        return self._rssi

    def _update_rssi(self):
        """Refresh the cached rssi attribute."""
        rssi = self._pykumo.get_wifi_rssi()
        self._rssi = rssi

    @property
    def sensor_rssi(self):
        """Return sensor RSSI, if any."""
        return self._sensor_rssi

    def _update_sensor_rssi(self):
        """Refresh the cached sensor_rssi attribute."""
        rssi = self._pykumo.get_sensor_rssi()
        self._sensor_rssi = rssi

    @property
    def runstate(self):
        """Return unit's current runstate."""
        return self._runstate

    def _update_runstate(self):
        """Refresh the cached runstate attribute."""
        runstate = self._pykumo.get_runstate()
        self._runstate = runstate

    @property
    def defrost(self):
        """Return whether in defrost mode."""
        return self._defrost

    def _update_defrost(self):
        """Refresh the cached defrost attribute."""
        defrost = self._pykumo.get_defrost()
        self._defrost = defrost

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self._battery_percent is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery_percent
        if self._filter_dirty is not None:
            attr[ATTR_FILTER_DIRTY] = self._filter_dirty
        if self._defrost is not None:
            attr[ATTR_DEFROST] = self._defrost
        if self._rssi is not None:
            attr[ATTR_RSSI] = self._rssi
        if self._sensor_rssi is not None:
            attr[ATTR_SENSOR_RSSI] = self._sensor_rssi
        if self._runstate is not None:
            attr[ATTR_RUNSTATE] = self._runstate

        return attr

    @property
    def device_info(self):
        """Return device information for this Kumo Thermostat"""
        return {
            "identifiers": {(DOMAIN, self._identifier)},
            "name": self.name,
            "manufacturer": "Mitsubishi",
        }

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug(
            "Kumo %s set temp: %s, current mode %s",
            self._name,
            pprint.pformat(kwargs),
            self._hvac_mode,
        )

        if not self.available:
            _LOGGER.warning("Kumo %s is not available", self._name)
            return

        # Validate arguments
        current_mode = self._hvac_mode
        proposed_mode = kwargs.get(ATTR_HVAC_MODE)
        target_mode = proposed_mode or current_mode

        if target_mode not in [HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.HEAT]:
            _LOGGER.warning(
                "Kumo %s not setting target temperature for mode %s",
                self._name,
                target_mode,
            )
            return

        target = {}
        try:
            if target_mode == HVACMode.HEAT_COOL:
                target["cool"] = kwargs.get(ATTR_TARGET_TEMP_HIGH)
                target["heat"] = kwargs.get(ATTR_TARGET_TEMP_LOW)
                if target["cool"] < target["heat"]:
                    _LOGGER.warning(
                        "Kumo %s heat_cool setpoints are inverted", self._name
                    )
                    target["cool"] = target["heat"]
            elif target_mode == HVACMode.COOL:
                target["cool"] = kwargs.get(ATTR_TEMPERATURE)
            elif target_mode == HVACMode.HEAT:
                target["heat"] = kwargs.get(ATTR_TEMPERATURE)
        except KeyError as ke:
            _LOGGER.warning(
                "Kumo %s set temp: %s required to set temp for %s ",
                self._name,
                ke,
                target_mode,
            )
            return

        if current_mode != target_mode:
            self.set_hvac_mode(target_mode)

        if "cool" in target:
            response = self._pykumo.set_cool_setpoint(target["cool"])
            _LOGGER.debug(
                "Kumo %s set %s temp response: %s", self._name, "cool", str(response)
            )
        if "heat" in target:
            response = self._pykumo.set_heat_setpoint(target["heat"])
            _LOGGER.debug(
                "Kumo %s set %s temp response: %s", self._name, "cool", str(response)
            )

    def set_hvac_mode(self, hvac_mode, caller="set_hvac_mode"):
        """Set new target operation mode."""
        try:
            mode = HA_STATE_TO_KUMO[hvac_mode]
        except KeyError:
            mode = "off"

        if not self.available:
            _LOGGER.warning("Kumo %s is not available", self._name)
            return

        response = self._pykumo.set_mode(mode)
        _LOGGER.debug(
            "Kumo %s set mode %s (via `%s`) response: %s", self._name, hvac_mode, caller, response
        )

    def set_swing_mode(self, swing_mode):
        """Set new vane swing mode."""
        if not self.available:
            _LOGGER.warning("Kumo %s is not available", self._name)
            return

        response = self._pykumo.set_vane_direction(swing_mode)
        _LOGGER.debug("Kumo %s set swing mode response: %s", self._name, response)

    def set_fan_mode(self, fan_mode):
        """Set new fan speed mode."""
        if not self.available:
            _LOGGER.warning("Kumo %s is not available", self._name)
            return

        response = self._pykumo.set_fan_speed(fan_mode)
        _LOGGER.debug("Kumo %s set fan speed response: %s", self._name, response)

    def turn_off(self):
        """Turn the climate off. This implements https://www.home-assistant.io/integrations/climate/#action-climateturn_off."""
        self.set_hvac_mode(HVACMode.OFF, caller="turn_off")
