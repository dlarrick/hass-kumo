"""Persistent cache storage for Kumo."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util.json import load_json

from .const import DOMAIN, KUMO_CONFIG_CACHE, KUMO_CONFIG_CACHE_BACKUP

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.cache"


def _is_valid_cache(data: Any) -> bool:
    """Return True if data looks like a valid pykumo kumo_dict."""
    return isinstance(data, list) and len(data) >= 3


def _copy_if_missing(src: str, dst: str) -> None:
    """Create a one-time safety backup copy if dst does not already exist."""
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)


async def async_load_kumo_cache(hass: HomeAssistant) -> list[Any] | None:
    """Load the Kumo cache from .storage, migrating from kumo_cache.json if needed."""
    store = Store[list[Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()
    if _is_valid_cache(data):
        return data

    # One-time migration from legacy <config>/kumo_cache.json (or .bak fallback).
    legacy_path = hass.config.path(KUMO_CONFIG_CACHE)
    backup_path = hass.config.path(KUMO_CONFIG_CACHE_BACKUP)

    for candidate in (legacy_path, backup_path):
        if not os.path.exists(candidate):
            continue
        try:
            legacy_data = await hass.async_add_executor_job(load_json, candidate)
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to read %s: %s", candidate, err)
            continue
        if _is_valid_cache(legacy_data):
            if candidate == legacy_path:
                try:
                    await hass.async_add_executor_job(
                        _copy_if_missing, legacy_path, backup_path
                    )
                except OSError as err:
                    _LOGGER.warning(
                        "Failed to create safety backup %s: %s", backup_path, err
                    )
            await store.async_save(legacy_data)
            _LOGGER.info(
                "Migrated Kumo cache from %s to .storage/%s",
                candidate,
                STORAGE_KEY,
            )
            return legacy_data

    return None


async def async_save_kumo_cache(hass: HomeAssistant, data: list[Any]) -> None:
    """Persist the Kumo cache to .storage (never modifying legacy files)."""
    store = Store[list[Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_save(data)
