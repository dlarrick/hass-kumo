"""Config flow for Kumo integration."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pykumo import KumoCloudAccount
from requests.exceptions import ConnectionError

from .const import (
    CONF_CONNECT_TIMEOUT,
    CONF_POST_COMMAND_REFRESH_DELAY,
    CONF_RESPONSE_TIMEOUT,
    CONF_SCAN_INTERVAL,
    DEFAULT_POST_COMMAND_REFRESH_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DHCP_DISCOVERED_KEY,
    DOMAIN,
)
from .storage import async_load_kumo_cache, async_save_kumo_cache

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


def _set_unit_fields(
    kumo_cache,
    label: str,
    address: str | None = None,
    password: str | None = None,
    crypto_serial: str | None = None,
) -> None:
    """Set address and/or unit credentials for the unit matching `label`."""
    for serial, raw_unit in _iter_zone_units(kumo_cache):
        if _get_unit_label(raw_unit, serial) == label:
            if address and address.strip():
                raw_unit["address"] = address.strip()
            if password and password.strip():
                raw_unit["password"] = password.strip()
            if crypto_serial and crypto_serial.strip():
                raw_unit["cryptoSerial"] = crypto_serial.strip()
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
    """Validate the user input and return an authenticated account.

    Returns {"title": ..., "account": KumoCloudAccount}.
    """
    # Collect DHCP-discovered IPs
    candidate_ips = hass.data.get(DHCP_DISCOVERED_KEY, {})

    account = KumoCloudAccount(data["username"], data["password"])
    try:
        result = await hass.async_add_executor_job(
            account.try_setup, candidate_ips, True
        )
    except ConnectionError:
        raise CannotConnect

    if not result:
        raise InvalidAuth

    return {"title": data["username"], "account": account}


# ── Config Flow ─────────────────────────────────────────────


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kumo."""

    VERSION = 1

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo):
        """Handle discovery of a Kumo adapter via DHCP."""
        _LOGGER.info(
            "Discovered Kumo adapter via DHCP: %s (%s)",
            discovery_info.ip,
            discovery_info.macaddress,
        )
        # Store the MAC->IP mapping for later use during setup
        discovered = self.hass.data.setdefault(DHCP_DISCOVERED_KEY, {})
        discovered[discovery_info.macaddress] = discovery_info.ip

        # Use MAC address as unique ID for this flow to allow users to ignore
        # specific false-positive discoveries.
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured()

        # If we already have any Kumo entry, we just absorb the discovery
        # silently into the candidate list and trigger a reload to pick it up.
        current_entries = self._async_current_entries()
        if current_entries:
            for entry in current_entries:
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_abort(reason="already_configured")

        # Prompt the user to set up the integration
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }
        errors = {}
        if user_input is not None:
            # Set unique ID to the domain for the actual config entry.
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                account = info["account"]

                self.kumo_cache = await self.hass.async_add_executor_job(
                    account.get_raw_json
                )
                self.user_account_setup = user_input
                self.title = info["title"]

                # Merge cached addresses so manually-configured IPs aren't lost
                cached_json = await async_load_kumo_cache(self.hass)
                if cached_json and _merge_cache_addresses(self.kumo_cache, cached_json):
                    _LOGGER.info("Merged IP addresses from existing cache")

                # Build unit list
                self.units = []
                for serial, raw_unit in _iter_zone_units(self.kumo_cache):
                    self.units.append(
                        {
                            "label": _get_unit_label(raw_unit, serial),
                            "ip_address": raw_unit.get("address", "empty") or "empty",
                            "mac": raw_unit.get("mac", "unknown"),
                            "serial": serial,
                        }
                    )

                ip_addresses = [u["ip_address"] for u in self.units]
                if "empty" in ip_addresses:
                    return await self.async_step_request_ips()
                await async_save_kumo_cache(self.hass, self.kumo_cache)
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
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
                _set_unit_fields(self.kumo_cache, label, address=ip_addr)
            await async_save_kumo_cache(self.hass, self.kumo_cache)
            return self.async_create_entry(
                title=self.title,
                data={
                    "username": self.user_account_setup["username"],
                    "password": self.user_account_setup["password"],
                },
            )
        return self.async_show_form(
            step_id="request_ips",
            data_schema=vol.Schema(data_schema),
            description_placeholders=self.user_account_setup,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm reauthentication with updated KumoCloud credentials."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        "username": user_input["username"],
                        "password": user_input["password"],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "username",
                        default=reauth_entry.data.get("username", ""),
                    ): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of KumoCloud account credentials."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                account = info["account"]
                new_cache = await self.hass.async_add_executor_job(account.get_raw_json)
                cached_json = await async_load_kumo_cache(self.hass)
                if cached_json:
                    _merge_cache_addresses(new_cache, cached_json)
                await async_save_kumo_cache(self.hass, new_cache)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        "username": user_input["username"],
                        "password": user_input["password"],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "username",
                        default=reconfigure_entry.data.get("username", ""),
                    ): str,
                    vol.Required(
                        "password",
                        default=reconfigure_entry.data.get("password", ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Kumo."""

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

        current = self.config_entry.options
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECT_TIMEOUT,
                    default=float(current.get(CONF_CONNECT_TIMEOUT, 1.2)),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_RESPONSE_TIMEOUT,
                    default=float(current.get(CONF_RESPONSE_TIMEOUT, 8)),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Required(
                    CONF_POST_COMMAND_REFRESH_DELAY,
                    default=float(
                        current.get(
                            CONF_POST_COMMAND_REFRESH_DELAY,
                            DEFAULT_POST_COMMAND_REFRESH_DELAY,
                        )
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=30.0)),
            }
        )

        return self.async_show_form(step_id="timeout_settings", data_schema=data_schema)

    async def async_step_unit_select(self, user_input=None):
        """Select which indoor unit to edit."""
        kumo_cache = await async_load_kumo_cache(self.hass)

        kumo_unit_list = {}
        for serial, raw_unit in _iter_zone_units(kumo_cache):
            label = _get_unit_label(raw_unit, serial)
            kumo_unit_list[label] = raw_unit

        if user_input is not None:
            self._selected_unit_label = user_input["unit_label"]
            return await self.async_step_unit_edit()

        data_schema = vol.Schema(
            {
                vol.Required("unit_label"): vol.In(kumo_unit_list.keys()),
            }
        )

        return self.async_show_form(step_id="unit_select", data_schema=data_schema)

    async def async_step_unit_edit(self, user_input=None):
        """Edit the selected unit's IP address and credentials, pre-loading existing values."""
        kumo_cache = await async_load_kumo_cache(self.hass)
        selected_unit = {}
        for serial, raw_unit in _iter_zone_units(kumo_cache):
            if _get_unit_label(raw_unit, serial) == self._selected_unit_label:
                selected_unit = raw_unit
                break

        if user_input is not None:
            _set_unit_fields(
                kumo_cache,
                self._selected_unit_label,
                address=user_input.get("ip_address"),
                password=user_input.get("unit_password"),
                crypto_serial=user_input.get("crypto_serial"),
            )
            if kumo_cache is not None:
                await async_save_kumo_cache(self.hass, kumo_cache)
            return self.async_create_entry(
                title="", data=dict(self.config_entry.options)
            )

        plain_text = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        data_schema = vol.Schema(
            {
                vol.Optional(
                    "ip_address",
                    default=selected_unit.get("address") or "",
                ): plain_text,
                vol.Optional(
                    "unit_password",
                    default=selected_unit.get("password") or "",
                ): plain_text,
                vol.Optional(
                    "crypto_serial",
                    default=selected_unit.get("cryptoSerial") or "",
                ): plain_text,
            }
        )

        return self.async_show_form(step_id="unit_edit", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
