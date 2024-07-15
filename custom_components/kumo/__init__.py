"""Support for Mitsubishi KumoCloud devices."""
import logging
from typing import Optional

import homeassistant.helpers.config_validation as cv
import pykumo
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util.json import load_json, save_json

from .coordinator import KumoDataUpdateCoordinator
from .const import (
    CONF_CONNECT_TIMEOUT,
    CONF_PREFER_CACHE,
    CONF_RESPONSE_TIMEOUT,
    DOMAIN,
    KUMO_CONFIG_CACHE,
    KUMO_DATA,
    KUMO_DATA_COORDINATORS,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PREFER_CACHE, default=False): cv.boolean,
                vol.Optional(CONF_CONNECT_TIMEOUT): float,
                vol.Optional(CONF_RESPONSE_TIMEOUT): float,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class KumoCloudSettings:
    """Hold object representing KumoCloud account."""

    def __init__(self, account, domain_config, domain_options):
        """Init KumoCloudAccount object."""
        self._account = account
        self._domain_config = domain_config
        self._domain_options = domain_options
        self._setup_tries = 0

    def get_account(self):
        """Retrieve account."""
        return self._account

    def get_domain_config(self):
        """Retrieve domain config."""
        return self._domain_config

    def get_domain_options(self):
        """Retrieve domain config."""
        return self._domain_options

    def get_raw_json(self):
        """Retrieve raw JSON config from account."""
        return self._account.get_raw_json()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Setup Kumo Entry"""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    prefer_cache = entry.data.get(CONF_PREFER_CACHE)

    account = await async_kumo_setup(hass, prefer_cache, username, password)

    if not account:
        # Attempt setup again, but flip the prefer_cache flag
        account = await async_kumo_setup(hass, not prefer_cache, username, password)

    if account:
        hass.data[DOMAIN][entry.entry_id][KUMO_DATA] = KumoCloudSettings(account, entry.data, entry.options)

        # Create a data coordinator for each Kumo device
        hass.data[DOMAIN][entry.entry_id].setdefault(KUMO_DATA_COORDINATORS, {})
        coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]
        connect_timeout = float(
            entry.options.get(CONF_CONNECT_TIMEOUT, "1.2")
        )
        response_timeout = float(
            entry.options.get(CONF_RESPONSE_TIMEOUT, "8")
        )
        timeouts = (connect_timeout, response_timeout)
        pykumos = await hass.async_add_executor_job(account.make_pykumos, timeouts, True)
        for device in pykumos.values():
            if device.get_serial() not in coordinators:
                coordinators[device.get_serial()] = KumoDataUpdateCoordinator(hass, device)

        for platform in PLATFORMS:
            forward_entry = await hass.config_entries.async_forward_entry_setup(entry, platform)
            await hass.async_create_task(forward_entry)
        return True

    _LOGGER.warning("Could not load config from KumoCloud server or cache")
    return False

async def async_kumo_setup(hass: HomeAssistant, prefer_cache: bool, username: str, password: str) -> Optional[pykumo.KumoCloudAccount]:
    """Attempt to load data from cache or Kumo Cloud"""
    if prefer_cache:
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE)
        ) or {"fetched": False}
        account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
    else:
        account = pykumo.KumoCloudAccount(username, password)

    setup_success = await hass.async_add_executor_job(account.try_setup)

    if setup_success:
        if prefer_cache:
            _LOGGER.info("Loaded config from local cache")
        else:
            await hass.async_add_executor_job(
                save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
            )
            _LOGGER.info("Loaded config from KumoCloud server")

        return account

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Entry"""

    for platform in PLATFORMS:
        all_ok = True
        unload_ok = await hass.config_entries.async_forward_entry_unload(entry, platform)
        if not unload_ok:
            all_ok = False
    return all_ok
