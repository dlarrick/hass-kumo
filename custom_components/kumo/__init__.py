"""Support for Mitsubishi KumoCloud devices."""

import asyncio
import binascii
from dataclasses import dataclass
from datetime import timedelta
import json
import logging

import homeassistant.helpers.config_validation as cv
import pykumo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CONNECT_TIMEOUT,
    CONF_RESPONSE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DHCP_DISCOVERED_KEY,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KumoDataUpdateCoordinator
from .storage import async_load_kumo_cache, async_save_kumo_cache

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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


@dataclass
class KumoRuntimeData:
    """Runtime data for a Kumo config entry."""

    settings: KumoCloudSettings
    coordinators: dict[str, KumoDataUpdateCoordinator]


type KumoConfigEntry = ConfigEntry[KumoRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: KumoConfigEntry):
    """Setup Kumo Entry"""
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    # Load cached config if available (migrating from legacy kumo_cache.json once)
    cached_dict = await async_load_kumo_cache(hass)

    # Initialize account and try setup (always prefer local cache on startup)
    account = pykumo.KumoCloudAccount(username, password, kumo_dict=cached_dict)
    candidate_ips = hass.data.get(DHCP_DISCOVERED_KEY, {})

    # Never run DHCP discovery inline.
    # Upstream probes every candidate IP x every unreachable unit with a 3 s
    # timeout during setup, so a few dead adapters stretch setup to minutes and
    # HA cancels it, taking ALL units down. Setup now uses cached addresses only;
    # discovery for unreachable units runs in the background after setup.
    try:
        setup_success = await hass.async_add_executor_job(account.try_setup, {}, True)
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady(
            f"Kumo setup failed due to network error: {err}"
        ) from err
    except (json.JSONDecodeError, binascii.Error, ValueError) as err:
        raise ConfigEntryNotReady(
            f"Kumo setup failed due to malformed cached data: {err}"
        ) from err
    except Exception:
        _LOGGER.exception("Unexpected error during Kumo setup")
        raise

    if not setup_success:
        raise ConfigEntryNotReady("Could not load config from KumoCloud")

    # Save updated config for next time
    await async_save_kumo_cache(hass, account.get_raw_json())
    _LOGGER.info("Kumo setup successful")

    settings = KumoCloudSettings(account, entry.data, entry.options)

    # Create a data coordinator for each Kumo device
    coordinators: dict[str, KumoDataUpdateCoordinator] = {}
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
    pykumos = await hass.async_add_executor_job(account.make_pykumos, timeouts, False)
    for device in pykumos.values():
        if device.get_serial() not in coordinators:
            coordinators[device.get_serial()] = KumoDataUpdateCoordinator(
                hass, device, config_entry=entry, update_interval=update_interval
            )
    await asyncio.gather(
        *(coordinator.async_refresh() for coordinator in coordinators.values())
    )

    entry.runtime_data = KumoRuntimeData(settings=settings, coordinators=coordinators)

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
        await async_save_kumo_cache(hass, account.get_raw_json())
        _LOGGER.warning("Kumo unit(s) found at new address %s; reloading", moved)
        hass.config_entries.async_schedule_reload(entry.entry_id)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Background rediscovery encountered error: %s", err)


async def async_unload_entry(hass: HomeAssistant, entry: KumoConfigEntry) -> bool:
    """Unload Entry"""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
