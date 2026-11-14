"""Tests for Kumo sensors, SensorEntityDescription, naming, and entity_id preservation."""

from unittest.mock import MagicMock, patch

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kumo.const import DOMAIN
from custom_components.kumo.coordinator import KumoDataUpdateCoordinator
from custom_components.kumo.sensor import INDOOR_SENSORS, KumoSensor


def _make_mock_device(serial: str = "SERIAL1", name: str = "Living Room") -> MagicMock:
    device = MagicMock()
    device.get_serial.return_value = serial
    device.get_name.return_value = name
    device.has_profile.return_value = False
    device.get_current_temperature.return_value = 19.0
    device.get_current_humidity.return_value = 48.0
    device.get_sensor_battery.return_value = 95
    device.get_sensor_rssi.return_value = -62
    device.get_wifi_rssi.return_value = -48
    device.get_outdoor_temperature.return_value = 10.0
    device.get_mode.return_value = "heat"
    device.get_heat_setpoint.return_value = 21.0
    device.get_cool_setpoint.return_value = 25.0
    device.get_fan_speed.return_value = "auto"
    device.get_vane_direction.return_value = "auto"
    device.get_filter_dirty.return_value = False
    device.get_defrost.return_value = False
    device.get_runstate.return_value = "normal"
    return device


async def test_sensor_descriptions_and_fahrenheit_lookup(hass: HomeAssistant):
    """Test SensorEntityDescription values, precision, and Mitsubishi c_to_f lookup."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    device = _make_mock_device()
    coordinator = KumoDataUpdateCoordinator(hass, device)

    temp_desc = next(d for d in INDOOR_SENSORS if d.key == "current-temperature")
    sensor = KumoSensor(coordinator, temp_desc)
    sensor.hass = hass

    assert sensor.has_entity_name is True
    assert sensor.unique_id == "SERIAL1-current-temperature"
    assert sensor.suggested_display_precision == 1
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    # 19.0 C -> 67 F in Mitsubishi's lookup table (pure math would be 66.2 F)
    assert sensor.native_value == 67

    hum_desc = next(d for d in INDOOR_SENSORS if d.key == "current-humidity")
    hum_sensor = KumoSensor(coordinator, hum_desc)
    hum_sensor.hass = hass
    assert hum_sensor.native_value == 48.0
    assert hum_sensor.suggested_display_precision == 1


async def test_existing_entity_ids_preserved_on_upgrade(hass: HomeAssistant):
    """Pre-populated legacy entity_ids must remain unchanged after setup with has_entity_name."""
    entity_registry = er.async_get(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
    entry.add_to_hass(hass)

    # Simulate legacy entity registry entries before Phase 4 upgrade
    legacy_climate = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "SERIAL1",
        config_entry=entry,
        suggested_object_id="custom_legacy_thermostat",
    )
    legacy_temp = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SERIAL1-current-temperature",
        config_entry=entry,
        suggested_object_id="custom_legacy_temp",
    )
    legacy_mode = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SERIAL1-last-hvac-mode",
        config_entry=entry,
        suggested_object_id="custom_legacy_mode",
    )

    device = _make_mock_device()
    account = MagicMock()
    account.get_raw_json.return_value = [
        {},
        {},
        {
            "children": [
                {"zoneTable": {"SERIAL1": {"address": "1.2.3.4", "reachable": True}}}
            ]
        },
    ]
    account.try_setup.return_value = True
    account.make_pykumos.return_value = {"SERIAL1": device}
    account.get_indoor_units.return_value = ["SERIAL1"]
    account.get_all_units.return_value = ["SERIAL1"]
    account.get_kumo_stations.return_value = []
    account.get_unreachable_units.return_value = {}

    with (
        patch("custom_components.kumo.pykumo.KumoCloudAccount", return_value=account),
        patch("custom_components.kumo.async_load_kumo_cache", return_value=None),
        patch("custom_components.kumo.async_save_kumo_cache"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL1")
        == legacy_climate.entity_id
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "SERIAL1-current-temperature"
        )
        == legacy_temp.entity_id
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "SERIAL1-last-hvac-mode")
        == legacy_mode.entity_id
    )
