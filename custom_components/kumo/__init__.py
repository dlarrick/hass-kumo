"""Support for Mitsubishi KumoCloud devices."""

import asyncio
import logging
import json
import binascii
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import pykumo
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util.json import load_json
from homeassistant.helpers.json import save_json

from .coordinator import KumoDataUpdateCoordinator
from .const import (
    CONF_CONNECT_TIMEOUT,
    CONF_PREFER_CACHE,
    CONF_RESPONSE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DHCP_DISCOVERED_KEY,
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

    # Load cached config if available
    cached_dict = await hass.async_add_executor_job(
        load_json, hass.config.path(KUMO_CONFIG_CACHE)
    )
    if not isinstance(cached_dict, list) or len(cached_dict) < 3:
        cached_dict = None

    # Initialize account and try setup
    account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_dict)
    candidate_ips = hass.data.get(DHCP_DISCOVERED_KEY, {})

    # Never run DHCP discovery inline.
    # Upstream probes every candidate IP x every unreachable unit with a 3 s
    # timeout during setup, so a few dead adapters stretch setup to minutes and
    # HA cancels it, taking ALL units down. Setup now uses cached addresses only;
    # discovery for unreachable units runs in the background after setup.
    try:
        setup_success = await hass.async_add_executor_job(
            account.try_setup, {}, prefer_cache
        )
    except (ConnectionError, OSError) as err:
        _LOGGER.warning("Kumo setup failed due to network error: %s", err)
        return False
    except (json.JSONDecodeError, binascii.Error, ValueError) as err:
        _LOGGER.error("Kumo setup failed due to malformed cached data: %s", err)
        return False
    except Exception:
        _LOGGER.exception("Unexpected error during Kumo setup")
        raise

    if setup_success:
        # Save updated config for next time
        await hass.async_add_executor_job(
            save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
        )
        _LOGGER.info("Kumo setup successful")

        hass.data[DOMAIN][entry.entry_id][KUMO_DATA] = KumoCloudSettings(
            account, entry.data, entry.options
        )

        # Create a data coordinator for each Kumo device
        hass.data[DOMAIN][entry.entry_id].setdefault(KUMO_DATA_COORDINATORS, {})
        coordinators = hass.data[DOMAIN][entry.entry_id][KUMO_DATA_COORDINATORS]
        connect_timeout = float(entry.options.get(CONF_CONNECT_TIMEOUT, "1.2"))
        response_timeout = float(entry.options.get(CONF_RESPONSE_TIMEOUT, "8"))
        timeouts = (connect_timeout, response_timeout)
        scan_interval_secs = float(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        update_interval = timedelta(seconds=scan_interval_secs)
        # Skip pykumo's serial status poll (one dead unit = ~30 s
        # each); poll all units in parallel instead, so a dead adapter only
        # marks its own entity unavailable.
        pykumos = await hass.async_add_executor_job(
            account.make_pykumos, timeouts, False
        )
        for device in pykumos.values():
            if device.get_serial() not in coordinators:
                coordinators[device.get_serial()] = KumoDataUpdateCoordinator(
                    hass, device, config_entry=entry, update_interval=update_interval
                )
        await asyncio.gather(
            *(coordinator.async_refresh() for coordinator in coordinators.values())
        )

        unreachable = _unreachable_units(account)
        if unreachable:
            _LOGGER.warning(
                "Kumo loaded without %d unreachable unit(s): %s",
                len(unreachable),
                ", ".join(
                    account.get_name(s) or u.get("label") or s
                    for s, u in unreachable.items()
                ),
            )
            if candidate_ips:
                entry.async_create_background_task(
                    hass,
                    _async_rediscover(
                        hass, entry, account, unreachable, dict(candidate_ips)
                    ),
                    "kumo_rediscover",
                )

        entry.async_on_unload(entry.add_update_listener(_async_options_updated))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    _LOGGER.warning("Could not load config from KumoCloud")
    return False


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _zone_table(account) -> dict:
    """Return pykumo's cached zone table (serial -> unit dict), or {}."""
    if hasattr(account, "get_zone_table"):
        return account.get_zone_table()
    try:
        return account.get_raw_json()[2]["children"][0]["zoneTable"]
    except (TypeError, KeyError, IndexError):
        return {}


def _unreachable_units(account) -> dict:
    """Units whose cached address did not answer during setup."""
    if hasattr(account, "get_unreachable_units"):
        return account.get_unreachable_units()
    return {
        serial: unit
        for serial, unit in _zone_table(account).items()
        if not unit.get("reachable")
    }


async def _async_rediscover(hass, entry, account, unreachable, candidate_ips):
    """Background: look for unreachable units at other DHCP-seen addresses.

    Reload only if a unit is found at a NEW address; a unit that simply comes
    back at its cached address recovers on its own at the next poll.
    """
    try:
        ips = [ip for ip in candidate_ips.values() if ip]
        if not ips:
            return

        if hasattr(account, "rediscover_unreachable_units"):
            moved = await hass.async_add_executor_job(
                account.rediscover_unreachable_units, ips
            )
        else:
            try:
                from pykumo.py_kumo_discovery import probe_candidate_ips
            except ImportError:
                return
            table = _zone_table(account)
            in_use = {u.get("address") for u in table.values() if u.get("reachable")}
            probe_ips = [ip for ip in ips if ip not in in_use]
            if not probe_ips:
                return
            matched = await hass.async_add_executor_job(
                probe_candidate_ips, unreachable, probe_ips
            )
            moved = {
                serial: ip
                for serial, ip in matched.items()
                if ip != unreachable[serial].get("address")
            }
            for serial, ip in moved.items():
                table[serial]["address"] = ip
                table[serial]["reachable"] = True

        if not moved:
            return
        await hass.async_add_executor_job(
            save_json, hass.config.path(KUMO_CONFIG_CACHE), account.get_raw_json()
        )
        _LOGGER.warning("Kumo unit(s) found at new address %s; reloading", moved)
        hass.config_entries.async_schedule_reload(entry.entry_id)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Background rediscovery encountered error: %s", err)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Entry"""

    all_ok = True
    for platform in PLATFORMS:
        unload_ok = await hass.config_entries.async_forward_entry_unload(
            entry, platform
        )
        if not unload_ok:
            all_ok = False

    if all_ok:
        hass.data[DOMAIN][entry.entry_id].pop(KUMO_DATA_COORDINATORS, None)

    return all_ok
