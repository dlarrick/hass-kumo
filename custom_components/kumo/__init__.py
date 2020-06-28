"""Support for Mitsubishi KumoCloud devices."""
import logging
import pykumo
import asyncio
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util.json import load_json, save_json
from .const import (
    DOMAIN,
    KUMO_DATA,
    KUMO_CONFIG_CACHE,
    CONF_PREFER_CACHE,
    CONF_CONNECT_TIMEOUT,
    CONF_RESPONSE_TIMEOUT,
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


class KumoData:
    """Hold object representing KumoCloud account."""

    def __init__(self, account, domain_config, domain_options):
        """Init KumoCloudAccount object."""
        self._account = account
        self._domain_config = domain_config
        self._domain_options = domain_options

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


def setup_kumo(hass, config):
    """Set up the Kumo indoor units."""
    hass.async_create_task(async_load_platform(hass, "climate", DOMAIN, {}, config))
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(config, "climate"))


async def async_setup(hass, config):
    """Set up the Kumo Cloud devices. Will create climate and sensor components to support devices listed on the provided Kumo Cloud account."""
    if DOMAIN not in config:
        return True
    # pylint: disable=C0415
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    prefer_cache = config[DOMAIN].get(CONF_PREFER_CACHE)
    domain_options = {
        "connect_timeout": config[DOMAIN].get(CONF_CONNECT_TIMEOUT),
        "response_timeout": config[DOMAIN].get(CONF_RESPONSE_TIMEOUT),
    }

    # Read config from either remote KumoCloud server or
    # cached JSON.
    cached_json = {}
    success = False
    if prefer_cache:
        # Try to load from cache
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE)
        ) or {"fetched": False}
        account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
    else:
        # Try to load from server
        account = pykumo.KumoCloudAccount(username, password)
    setup_success = await hass.async_add_executor_job(account.try_setup)
    if setup_success:
        if prefer_cache:
            _LOGGER.info("Loaded config from local cache")
            success = True
        else:
            await hass.async_add_executor_job(
                save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
            )
            _LOGGER.info("Loaded config from KumoCloud server")
            success = True
    else:
        # Fall back
        if prefer_cache:
            # Try to load from server
            account = pykumo.KumoCloudAccount(username, password)
        else:
            # Try to load from cache
            cached_json = await hass.async_add_executor_job(
                load_json, hass.config.path(KUMO_CONFIG_CACHE)
            ) or {"fetched": False}
            account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
        setup_success = await hass.async_add_executor_job(account.try_setup)
        if setup_success:
            if prefer_cache:
                await hass.async_add_executor_job(
                    save_json,
                    hass.config.path(KUMO_CONFIG_CACHE),
                    account.get_raw_json(),
                )
                _LOGGER.info("Loaded config from KumoCloud server as fallback")
                success = True
            else:
                _LOGGER.info("Loaded config from local cache as fallback")
                success = True

    if success:
        hass.data[KUMO_DATA] = KumoData(account, config[DOMAIN], domain_options)
        setup_kumo(hass, config)
        return True

    _LOGGER.warning("Could not load config from KumoCloud server or cache")
    return False


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Setup Entry"""
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    prefer_cache = entry.data.get(CONF_PREFER_CACHE)
    # Read config from either remote KumoCloud server or
    # cached JSON.
    cached_json = {}
    success = False
    if prefer_cache:
        # Try to load from cache
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE)
        ) or {"fetched": False}
        account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
    else:
        # Try to load from server
        account = pykumo.KumoCloudAccount(username, password)
    setup_success = await hass.async_add_executor_job(account.try_setup)
    if setup_success:
        if prefer_cache:
            _LOGGER.info("Loaded config from local cache")
            success = True
        else:
            await hass.async_add_executor_job(
                save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
            )
            _LOGGER.info("Loaded config from KumoCloud server")
            success = True
    else:
        # Fall back
        if prefer_cache:
            # Try to load from server
            account = pykumo.KumoCloudAccount(username, password)
        else:
            # Try to load from cache
            cached_json = await hass.async_add_executor_job(
                load_json, hass.config.path(KUMO_CONFIG_CACHE)
            ) or {"fetched": False}
            account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_json)
        setup_success = await hass.async_add_executor_job(account.try_setup)
        if setup_success:
            if prefer_cache:
                await hass.async_add_executor_job(
                    save_json,
                    hass.config.path(KUMO_CONFIG_CACHE),
                    account.get_raw_json(),
                )
                _LOGGER.info("Loaded config from KumoCloud server as fallback")
                success = True
            else:
                _LOGGER.info("Loaded config from local cache as fallback")
                success = True
    if success:
        data = KumoData(account, entry.data, entry.options)
        hass.data[DOMAIN] = data
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "climate")
        )
        return True
    _LOGGER.warning("Could not load config from KumoCloud server or cache")
    return False


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Entry"""
    hass.data.pop(DOMAIN)
    tasks = []
    tasks.append(hass.config_entries.async_forward_entry_unload(entry, "climate"))
    return all(await asyncio.gather(*tasks))
