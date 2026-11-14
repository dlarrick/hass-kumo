"""HomeAssistant sensor component for Kumo Station Device."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from pykumo import PyKumoBase

from . import KumoConfigEntry
from .coordinator import KumoDataUpdateCoordinator
from .entity import CoordinatedKumoEntity
from .last_hvac_mode import (
    get_last_hvac_mode_value,
    register_last_hvac_mode_listener,
    set_last_hvac_mode_value,
)
from .temperature import c_to_f

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KumoSensorEntityDescription(SensorEntityDescription):
    """Describe a Kumo sensor entity."""

    value_fn: Callable[[PyKumoBase], Any]
    is_temperature: bool = False


INDOOR_SENSORS: tuple[KumoSensorEntityDescription, ...] = (
    KumoSensorEntityDescription(
        key="current-humidity",
        translation_key="current_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get_current_humidity(),
    ),
    KumoSensorEntityDescription(
        key="current-temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
        is_temperature=True,
        value_fn=lambda d: d.get_current_temperature(),
    ),
    KumoSensorEntityDescription(
        key="sensor-battery",
        translation_key="sensor_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get_sensor_battery(),
    ),
    KumoSensorEntityDescription(
        key="sensor-signal-strength",
        translation_key="sensor_signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get_sensor_rssi(),
    ),
    KumoSensorEntityDescription(
        key="signal-strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get_wifi_rssi(),
    ),
)

STATION_SENSORS: tuple[KumoSensorEntityDescription, ...] = (
    KumoSensorEntityDescription(
        key="outdoor-temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        is_temperature=True,
        value_fn=lambda d: d.get_outdoor_temperature(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KumoConfigEntry, async_add_entities
):
    """Set up the Kumo sensors."""
    account = entry.runtime_data.settings.get_account()
    coordinators = entry.runtime_data.coordinators

    entities: list[SensorEntity] = []
    all_serials = await hass.async_add_executor_job(account.get_all_units)
    for serial in all_serials:
        coordinator = coordinators[serial]
        for description in INDOOR_SENSORS:
            entities.append(KumoSensor(coordinator, description))
        entities.append(KumoLastHvacModeSensor(coordinator))
        _LOGGER.debug(
            "Adding indoor unit sensors for %s",
            coordinator.get_device().get_name(),
        )

    kumo_station_serials = await hass.async_add_executor_job(account.get_kumo_stations)
    for serial in kumo_station_serials:
        coordinator = coordinators[serial]
        for description in STATION_SENSORS:
            entities.append(KumoSensor(coordinator, description))
        _LOGGER.debug(
            "Adding kumo station sensors for %s",
            coordinator.get_device().get_name(),
        )

    if entities:
        async_add_entities(entities)


class KumoSensor(CoordinatedKumoEntity, SensorEntity):
    """Representation of a Kumo sensor."""

    entity_description: KumoSensorEntityDescription

    def __init__(
        self,
        coordinator: KumoDataUpdateCoordinator,
        description: KumoSensorEntityDescription,
    ) -> None:
        """Initialize the Kumo sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._identifier}-{description.key}"

    @property
    def _use_fahrenheit(self) -> bool:
        """Return True if the user's HA config is set to Fahrenheit."""
        return self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement for this sensor."""
        if self.entity_description.is_temperature:
            if self._use_fahrenheit:
                return UnitOfTemperature.FAHRENHEIT
            return UnitOfTemperature.CELSIUS
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self):
        """Return the sensor value."""
        value = self.entity_description.value_fn(self._pykumo)
        if self.entity_description.is_temperature and self._use_fahrenheit:
            return c_to_f(value)
        return value


class KumoLastHvacModeSensor(CoordinatedKumoEntity, SensorEntity, RestoreEntity):
    """Representation of a Kumo's last active HVAC mode."""

    _attr_translation_key = "last_hvac_mode"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: KumoDataUpdateCoordinator):
        """Initialize the last HVAC mode sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._identifier}-last-hvac-mode"
        self._last_mode = None
        self._unsub_last_hvac_mode = None

    @property
    def native_value(self):
        """Return the last active HVAC mode."""
        self._last_mode = self._last_mode or get_last_hvac_mode_value(
            self.hass, self._identifier
        )
        return self._last_mode

    async def async_added_to_hass(self):
        """Restore last state and listen for updates."""
        await super().async_added_to_hass()
        self._unsub_last_hvac_mode = register_last_hvac_mode_listener(
            self.hass, self._identifier, self._handle_last_hvac_mode_update
        )
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            set_last_hvac_mode_value(self.hass, self._identifier, last_state.state)
            self._last_mode = last_state.state

    async def async_will_remove_from_hass(self):
        """Unregister listeners."""
        await super().async_will_remove_from_hass()
        if self._unsub_last_hvac_mode:
            self._unsub_last_hvac_mode()
            self._unsub_last_hvac_mode = None

    def _handle_last_hvac_mode_update(self, value):
        self._last_mode = value
        self.async_write_ha_state()
