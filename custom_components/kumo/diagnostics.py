"""Diagnostics support for Kumo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, KUMO_DATA, KUMO_DATA_COORDINATORS

TO_REDACT = {
    "username",
    "password",
    "address",
    "mac",
    "serial",
    "cryptoSerial",
    "crypto_serial",
    "token",
    "access",
    "refresh",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    kumo_settings = hass.data[DOMAIN][entry.entry_id][KUMO_DATA]
    account = kumo_settings.get_account()

    # Redact config entry and raw account JSON
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "kumo_dict": async_redact_data(account.get_raw_json(), TO_REDACT),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a specific device."""
    # Find the coordinator for this device
    # hass-kumo stores coordinators by serial number
    serial = next(iter(device.identifiers))[1]
    coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]
    coordinator = coordinators.get(serial)

    if not coordinator:
        return {"error": "Device coordinator not found"}

    pykumo_device = coordinator.get_device()

    return {
        "device_info": {
            "name": device.name,
            "model": device.model,
            "sw_version": device.sw_version,
            "manufacturer": device.manufacturer,
        },
        "pykumo_state": async_redact_data(pykumo_device.__dict__, TO_REDACT),
    }
