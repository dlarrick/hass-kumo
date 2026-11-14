"""Tests for Kumo setup resilience, runtime_data, and coordinator updates."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kumo import KumoRuntimeData
from custom_components.kumo.climate import KumoThermostat
from custom_components.kumo.const import DOMAIN
from custom_components.kumo.coordinator import KumoDataUpdateCoordinator


async def test_setup_network_error_triggers_retry(hass: HomeAssistant):
    """Test that ConnectionError during setup raises ConfigEntryNotReady (SETUP_RETRY)."""
    with patch(
        "pykumo.KumoCloudAccount.try_setup",
        side_effect=ConnectionError("cloud unreachable"),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failure_triggers_retry(hass: HomeAssistant):
    """Test that try_setup returning False raises ConfigEntryNotReady (SETUP_RETRY)."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=False):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_runtime_data_and_unload(hass: HomeAssistant):
    """Test that entry.runtime_data is populated on setup and entry unloads cleanly."""
    with (
        patch("pykumo.KumoCloudAccount.try_setup", return_value=True),
        patch(
            "pykumo.KumoCloudAccount.get_raw_json",
            return_value=[{}, {}, {"children": []}],
        ),
        patch("pykumo.KumoCloudAccount.make_pykumos", return_value={}),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert isinstance(entry.runtime_data, KumoRuntimeData)
        assert entry.runtime_data.coordinators == {}

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_climate_handle_coordinator_update(hass: HomeAssistant):
    """Test KumoThermostat refreshes cached state on _handle_coordinator_update."""
    device = MagicMock()
    device.get_serial.return_value = "SERIAL1"
    device.get_name.return_value = "Living Room"
    device.has_profile.return_value = False
    device.get_current_temperature.return_value = 21.5
    device.get_mode.return_value = "heat"
    device.get_heat_setpoint.return_value = 22.0
    device.get_cool_setpoint.return_value = 25.0
    device.get_fan_speed.return_value = "auto"
    device.get_vane_direction.return_value = "auto"
    device.get_current_humidity.return_value = 45
    device.get_sensor_battery.return_value = None
    device.get_filter_dirty.return_value = False
    device.get_defrost.return_value = False
    device.get_wifi_rssi.return_value = -55
    device.get_sensor_rssi.return_value = None
    device.get_runstate.return_value = "normal"

    coordinator = KumoDataUpdateCoordinator(hass, device)
    coordinator._available = True
    entity = KumoThermostat(coordinator)
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.native_current_temperature == 21.5
    assert entity.native_target_temperature == 22.0
    assert entity.current_humidity == 45
    assert entity.runstate == "normal"
    entity.async_write_ha_state.assert_called_once()
