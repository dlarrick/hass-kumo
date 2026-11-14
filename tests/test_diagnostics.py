"""Tests for Kumo diagnostics redaction."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kumo import KumoCloudSettings, KumoRuntimeData
from custom_components.kumo.const import DOMAIN
from custom_components.kumo.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


async def test_config_entry_diagnostics_redaction(hass: HomeAssistant):
    """Test sensitive fields are redacted in config entry diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "secret@example.com", "password": "secret-password"},
    )
    entry.add_to_hass(hass)

    account = MagicMock()
    account.get_raw_json.return_value = [
        {"token": "tok-123", "access": "acc-123", "refresh": "ref-123"},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "SERIAL123": {
                            "label": "Living Room",
                            "address": "192.168.1.50",
                            "mac": "AA:BB:CC:DD:EE:FF",
                            "serial": "SERIAL123",
                            "cryptoSerial": "deadbeef01",
                            "password": "unit-b64-password",
                        }
                    }
                }
            ]
        },
    ]
    entry.runtime_data = KumoRuntimeData(
        settings=KumoCloudSettings(account, entry.data, entry.options),
        coordinators={},
    )

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["config_entry"]["data"]["username"] == "**REDACTED**"
    assert diag["config_entry"]["data"]["password"] == "**REDACTED**"

    raw = diag["kumo_dict"]
    assert raw[0]["token"] == "**REDACTED**"
    assert raw[0]["access"] == "**REDACTED**"
    assert raw[0]["refresh"] == "**REDACTED**"
    unit = raw[2]["children"][0]["zoneTable"]["SERIAL123"]
    assert unit["label"] == "Living Room"
    assert unit["address"] == "**REDACTED**"
    assert unit["mac"] == "**REDACTED**"
    assert unit["serial"] == "**REDACTED**"
    assert unit["cryptoSerial"] == "**REDACTED**"
    assert unit["password"] == "**REDACTED**"


async def test_device_diagnostics_redaction(hass: HomeAssistant):
    """Test sensitive fields are redacted in device diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SERIAL123")},
        name="Living Room",
        manufacturer="Mitsubishi",
    )

    pykumo_device = MagicMock()
    pykumo_device.address = "192.168.1.50"
    pykumo_device.password = "unit-b64-password"
    pykumo_device.crypto_serial = "deadbeef01"
    pykumo_device.serial = "SERIAL123"
    pykumo_device.name = "Living Room"

    coordinator = MagicMock()
    coordinator.get_device.return_value = pykumo_device

    entry.runtime_data = KumoRuntimeData(
        settings=MagicMock(),
        coordinators={"SERIAL123": coordinator},
    )

    diag = await async_get_device_diagnostics(hass, entry, device_entry)

    assert diag["device_info"]["name"] == "Living Room"
    state = diag["pykumo_state"]
    assert state["address"] == "**REDACTED**"
    assert state["password"] == "**REDACTED**"
    assert state["crypto_serial"] == "**REDACTED**"
    assert state["serial"] == "**REDACTED**"
    assert state["name"] == "Living Room"
