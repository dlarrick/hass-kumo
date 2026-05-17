"""Shared storage for last active HVAC mode."""
from __future__ import annotations

from homeassistant.components.climate.const import HVACMode

from .const import DOMAIN

_LAST_HVAC_MODE_KEY = "last_hvac_mode"
_LAST_HVAC_MODE_LISTENERS = "last_hvac_mode_listeners"


def _get_store(hass):
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_LAST_HVAC_MODE_KEY, {})


def _get_listeners(hass):
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_LAST_HVAC_MODE_LISTENERS, {})


def get_last_hvac_mode_value(hass, identifier):
    """Return the cached last HVAC mode string, if any."""
    if not hass or not identifier:
        return None
    return _get_store(hass).get(identifier)


def set_last_hvac_mode_value(hass, identifier, value):
    """Store the cached last HVAC mode string."""
    if not hass or not identifier or not value:
        return
    store = _get_store(hass)
    if store.get(identifier) == value:
        return
    store[identifier] = value
    _notify_listeners(hass, identifier, value)


def get_last_hvac_mode(hass, identifier, hvac_modes):
    """Return the cached last HVAC mode as an HVACMode, if any."""
    value = get_last_hvac_mode_value(hass, identifier)
    if value:
        for mode in hvac_modes:
            if mode != HVACMode.OFF and mode.value == value:
                return mode
    return None


def register_last_hvac_mode_listener(hass, identifier, callback):
    """Register a callback for last HVAC mode updates."""
    if not hass or not identifier:
        return lambda: None
    listeners = _get_listeners(hass)
    callbacks = listeners.setdefault(identifier, set())
    callbacks.add(callback)

    def _unsubscribe():
        callbacks.discard(callback)
        if not callbacks:
            listeners.pop(identifier, None)

    return _unsubscribe


def _notify_listeners(hass, identifier, value):
    callbacks = _get_listeners(hass).get(identifier)
    if not callbacks:
        return

    def _run():
        for callback in list(callbacks):
            callback(value)

    hass.loop.call_soon_threadsafe(_run)
