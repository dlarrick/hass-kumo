"""Config flow for Kumo integration."""
import logging
import os

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
from homeassistant.util.json import load_json
from homeassistant.helpers.json import save_json
from pykumo import KumoCloudAccount
from requests.exceptions import ConnectionError

from .const import DOMAIN, KUMO_CONFIG_CACHE

DEFAULT_PREFER_CACHE = False
_LOGGER = logging.getLogger(__name__)
EDIT_KEY = "edit_selection"
EDIT_TIMEOUT = "Timeouts"
EDIT_UNITS = "Unit Settings"


class PlaceholderAccount:
    """Placeholder class to make tests pass."""

    def __init__(self, username, password):
        """Initialize."""
        self.username = username
        self.password = password


# ── Zone table helpers ──────────────────────────────────────
# The kumo_dict structure nests units in children[].zoneTable and
# optionally children[].children[].zoneTable. These helpers avoid
# repeating that traversal pattern throughout the code.

def _iter_zone_units(kumo_cache):
    """Yield (serial, raw_unit) for every unit in the zone tables."""
    try:
        for child in kumo_cache[2]["children"]:
            for serial, raw_unit in child["zoneTable"].items():
                yield serial, raw_unit
            for grandchild in child.get("children", []):
                for serial, raw_unit in grandchild["zoneTable"].items():
                    yield serial, raw_unit
    except (KeyError, IndexError, TypeError):
        pass


def _get_unit_label(raw_unit, serial=""):
    """Get a display label for a unit, handling blank labels."""
    label = raw_unit.get("label", "").strip()
    if not label:
        serial = serial or raw_unit.get("serial", "unknown")
        label = f"Unit {serial[-6:]}"
    return label


def _set_unit_address(kumo_cache, label, address):
    """Set the address for the unit matching `label`."""
    for serial, raw_unit in _iter_zone_units(kumo_cache):
        if _get_unit_label(raw_unit, serial) == label:
            raw_unit["address"] = address
            return


def _merge_cache_addresses(kumo_cache, cached_json):
    """Merge IP addresses from cached_json into kumo_cache where missing."""
    # Build lookup of cached addresses
    cached_addresses = {}
    for serial, raw_unit in _iter_zone_units(cached_json):
        addr = raw_unit.get("address")
        if addr and addr not in ("N/A", "empty"):
            cached_addresses[serial] = addr

    if not cached_addresses:
        return False

    merged = False
    for serial, raw_unit in _iter_zone_units(kumo_cache):
        if not raw_unit.get("address") and serial in cached_addresses:
            raw_unit["address"] = cached_addresses[serial]
            merged = True

    return merged


# ── Validation ──────────────────────────────────────────────

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Tries V3 API first, then falls back to V2 API.
    """
    # Try V3 first
    account = KumoCloudAccount(data["username"], data["password"])
    try:
        result = await hass.async_add_executor_job(account.try_setup_v3_only)
    except ConnectionError:
        result = False

    if not result:
        # Fall back to V2
        _LOGGER.info("V3 validation failed; trying V2 API")
        account = KumoCloudAccount(data["username"], data["password"])
        try:
            result = await hass.async_add_executor_job(account.try_setup)
        except ConnectionError:
            raise CannotConnect

    if not result:
        raise InvalidAuth

    return {"title": data["username"]}


# ── Config Flow ─────────────────────────────────────────────

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kumo."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
            vol.Optional("prefer_cache", default=DEFAULT_PREFER_CACHE): bool,
        }
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Set up account (V3-first, V2-fallback)
                account = KumoCloudAccount(
                    user_input["username"], user_input["password"]
                )
                setup_ok = await self.hass.async_add_executor_job(
                    account.try_setup_v3_only
                )
                if not setup_ok:
                    _LOGGER.info("V3 setup failed in config flow; trying V2")
                    account = KumoCloudAccount(
                        user_input["username"], user_input["password"]
                    )
                    setup_ok = await self.hass.async_add_executor_job(
                        account.try_setup
                    )
                if not setup_ok:
                    raise InvalidAuth

                self.kumo_cache = await self.hass.async_add_executor_job(
                    account.get_raw_json
                )
                self.user_account_setup = user_input
                self.title = info["title"]

                # Merge addresses from existing cache if prefer_cache is set
                if user_input.get("prefer_cache"):
                    cache_path = self.hass.config.path(KUMO_CONFIG_CACHE)
                    if os.path.exists(cache_path):
                        cached_json = await self.hass.async_add_executor_job(
                            load_json, cache_path
                        )
                        if cached_json and _merge_cache_addresses(self.kumo_cache, cached_json):
                            _LOGGER.info("Merged IP addresses from existing cache")

                # Build unit list
                self.units = []
                for serial, raw_unit in _iter_zone_units(self.kumo_cache):
                    self.units.append({
                        "label": _get_unit_label(raw_unit, serial),
                        "ip_address": raw_unit.get("address", "empty") or "empty",
                        "mac": raw_unit.get("mac", "unknown"),
                        "serial": serial,
                    })

                ip_addresses = [u["ip_address"] for u in self.units]
                if "empty" in ip_addresses:
                    return await self.async_step_request_ips()
                else:
                    await self.hass.async_add_executor_job(
                        save_json,
                        self.hass.config.path(KUMO_CONFIG_CACHE),
                        self.kumo_cache,
                    )
                    return self.async_create_entry(
                        title=info["title"],
                        data={
                            "username": user_input["username"],
                            "password": user_input["password"],
                            "prefer_cache": user_input["prefer_cache"],
                        },
                    )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_request_ips(self, user_input=None):
        data_schema = {}
        for x in self.units:
            if x["ip_address"] == "empty":
                data_schema[
                    vol.Required(x["label"], default=x["label"] + " " + x["mac"])
                ] = str

        if user_input is not None:
            for label, ip_addr in user_input.items():
                _set_unit_address(self.kumo_cache, label, ip_addr)
            await self.hass.async_add_executor_job(
                save_json, self.hass.config.path(KUMO_CONFIG_CACHE), self.kumo_cache
            )
            return self.async_create_entry(
                title=self.title,
                data={
                    "username": self.user_account_setup["username"],
                    "password": self.user_account_setup["password"],
                    "prefer_cache": True,
                },
            )
        return self.async_show_form(
            step_id="request_ips",
            data_schema=vol.Schema(data_schema),
            description_placeholders=self.user_account_setup,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Kumo."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            if user_input[EDIT_KEY] == EDIT_TIMEOUT:
                return await self.async_step_timeout_settings()
            if user_input[EDIT_KEY] == EDIT_UNITS:
                return await self.async_step_unit_select()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(EDIT_KEY, default=EDIT_TIMEOUT): vol.In(
                        [EDIT_TIMEOUT, EDIT_UNITS]
                    )
                },
            ),
        )

    async def async_step_timeout_settings(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required("connect_timeout", default=1.2): vol.Coerce(float),
                vol.Required("response_timeout", default=8): vol.Coerce(float),
            }
        )

        return self.async_show_form(step_id="timeout_settings", data_schema=data_schema)

    async def async_step_unit_select(self, user_input=None):
        """Handle options flow."""
        kumo_cache = await self.hass.async_add_executor_job(
            load_json, self.hass.config.path(KUMO_CONFIG_CACHE)
        )

        kumo_unit_list = {}
        for serial, raw_unit in _iter_zone_units(kumo_cache):
            label = _get_unit_label(raw_unit, serial)
            kumo_unit_list[label] = (str(raw_unit.get("address", "empty")),)

        if user_input is not None:
            _set_unit_address(kumo_cache, user_input["unit_label"], user_input["ip_address"])
            await self.hass.async_add_executor_job(
                save_json, self.hass.config.path(KUMO_CONFIG_CACHE), kumo_cache
            )
            return self.async_create_entry(title="", data=None)

        data_schema = vol.Schema(
            {
                vol.Required("unit_label"): vol.In(kumo_unit_list.keys()),
                vol.Optional("ip_address"): str,
            }
        )

        return self.async_show_form(step_id="unit_select", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
