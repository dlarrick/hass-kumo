import pytest
from unittest.mock import patch
from homeassistant.core import HomeAssistant
from custom_components.kumo.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
async def kumo_setup(hass):
    """Fixture to set up the kumo integration."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"username": "user", "password": "pass"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.kumo.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_scenario_1_cached_info_fine(hass: HomeAssistant):
    """Cached info is fine. Units reachable."""
    with (
        patch("pykumo.KumoCloudAccount.try_setup", return_value=True),
        patch(
            "pykumo.KumoCloudAccount.get_raw_json",
            return_value=[
                {},
                {},
                {"children": [{"zoneTable": {"S1": {"address": "1.1.1.1"}}}]},
            ],
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_scenario_2_cached_info_unreachable(hass: HomeAssistant):
    """Cached info fine, some unreachable."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=True):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_scenario_3_stale_ip_new_discovery(hass: HomeAssistant):
    """Stale IP in cache, new address in discovery."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=True):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_scenario_4_new_unit_in_discovery(hass: HomeAssistant):
    """New unit in discovery."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=True):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_scenario_5_new_installation_all_discovered(hass: HomeAssistant):
    """New installation, all in discovery."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=True):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_scenario_6_new_installation_missing_discovery(hass: HomeAssistant):
    """New installation, missing discovery."""
    with patch("pykumo.KumoCloudAccount.try_setup", return_value=True):
        entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
