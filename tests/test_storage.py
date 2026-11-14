"""Tests for Kumo cache storage migration and safety backup."""

import json
import os

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.kumo.const import KUMO_CONFIG_CACHE, KUMO_CONFIG_CACHE_BACKUP
from custom_components.kumo.storage import (
    STORAGE_KEY,
    STORAGE_VERSION,
    async_load_kumo_cache,
    async_save_kumo_cache,
)


async def test_storage_migration_creates_backup_and_never_writes_legacy(
    hass: HomeAssistant, tmp_path
):
    """Test one-time migration from kumo_cache.json to Store with .bak safety copy."""
    hass.config.config_dir = str(tmp_path)
    legacy_path = tmp_path / KUMO_CONFIG_CACHE
    backup_path = tmp_path / KUMO_CONFIG_CACHE_BACKUP

    legacy_data = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "S1": {
                            "address": "192.168.1.50",
                            "password": "secret-b64-password",
                            "cryptoSerial": "deadbeef",
                        }
                    }
                }
            ]
        },
    ]
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    # First load migrates to Store and creates .bak once
    loaded = await async_load_kumo_cache(hass)
    assert loaded == legacy_data
    assert legacy_path.exists()
    assert backup_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == legacy_data

    # Subsequent saves only update Store, never kumo_cache.json or .bak
    updated_data = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "S1": {
                            "address": "192.168.1.99",
                            "password": "secret-b64-password",
                            "cryptoSerial": "deadbeef",
                        }
                    }
                }
            ]
        },
    ]
    await async_save_kumo_cache(hass, updated_data)

    assert json.loads(legacy_path.read_text(encoding="utf-8")) == legacy_data
    assert json.loads(backup_path.read_text(encoding="utf-8")) == legacy_data
    assert await async_load_kumo_cache(hass) == updated_data


async def test_storage_falls_back_to_backup_if_store_and_legacy_missing(
    hass: HomeAssistant, tmp_path
):
    """Test loading falls back to kumo_cache.json.bak if Store and kumo_cache.json are absent."""
    hass.config.config_dir = str(tmp_path)
    backup_path = tmp_path / KUMO_CONFIG_CACHE_BACKUP
    backup_data = [
        {},
        {},
        {"children": [{"zoneTable": {"S1": {"address": "1.2.3.4"}}}]},
    ]
    backup_path.write_text(json.dumps(backup_data), encoding="utf-8")

    loaded = await async_load_kumo_cache(hass)
    assert loaded == backup_data
    assert not os.path.exists(tmp_path / KUMO_CONFIG_CACHE)

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    assert await store.async_load() == backup_data


async def test_storage_does_not_overwrite_existing_backup(
    hass: HomeAssistant, tmp_path
):
    """Test migration preserves an existing kumo_cache.json.bak without overwriting."""
    hass.config.config_dir = str(tmp_path)
    legacy_path = tmp_path / KUMO_CONFIG_CACHE
    backup_path = tmp_path / KUMO_CONFIG_CACHE_BACKUP

    legacy_data = [
        {},
        {},
        {"children": [{"zoneTable": {"S1": {"address": "1.1.1.1"}}}]},
    ]
    existing_backup = [
        {},
        {},
        {"children": [{"zoneTable": {"S1": {"address": "9.9.9.9"}}}]},
    ]
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")
    backup_path.write_text(json.dumps(existing_backup), encoding="utf-8")

    loaded = await async_load_kumo_cache(hass)
    assert loaded == legacy_data
    assert json.loads(backup_path.read_text(encoding="utf-8")) == existing_backup


async def test_storage_falls_back_to_backup_when_legacy_is_corrupt(
    hass: HomeAssistant, tmp_path
):
    """Test fallback to .bak when Store is missing and kumo_cache.json is corrupt."""
    hass.config.config_dir = str(tmp_path)
    legacy_path = tmp_path / KUMO_CONFIG_CACHE
    backup_path = tmp_path / KUMO_CONFIG_CACHE_BACKUP

    legacy_path.write_text("{not valid json", encoding="utf-8")
    backup_data = [
        {},
        {},
        {"children": [{"zoneTable": {"S1": {"address": "2.2.2.2"}}}]},
    ]
    backup_path.write_text(json.dumps(backup_data), encoding="utf-8")

    loaded = await async_load_kumo_cache(hass)
    assert loaded == backup_data
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    assert await store.async_load() == backup_data


async def test_storage_returns_none_when_all_caches_missing(
    hass: HomeAssistant, tmp_path
):
    """Test async_load_kumo_cache returns None when Store, legacy, and .bak are absent."""
    hass.config.config_dir = str(tmp_path)
    assert await async_load_kumo_cache(hass) is None


async def test_storage_prefers_store_over_legacy(hass: HomeAssistant, tmp_path):
    """Test Store takes precedence over kumo_cache.json and does not create .bak."""
    hass.config.config_dir = str(tmp_path)
    legacy_path = tmp_path / KUMO_CONFIG_CACHE
    backup_path = tmp_path / KUMO_CONFIG_CACHE_BACKUP

    store_data = [{}, {}, {"children": [{"zoneTable": {"S1": {"address": "3.3.3.3"}}}]}]
    legacy_data = [
        {},
        {},
        {"children": [{"zoneTable": {"S1": {"address": "4.4.4.4"}}}]},
    ]
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")
    await async_save_kumo_cache(hass, store_data)

    loaded = await async_load_kumo_cache(hass)
    assert loaded == store_data
    assert not backup_path.exists()
