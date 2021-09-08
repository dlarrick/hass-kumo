"""Config flow for Kumo integration."""
import logging

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
from homeassistant.util.json import load_json, save_json
from pykumo import KumoCloudAccount
from requests.exceptions import ConnectionError

from .const import DOMAIN, KUMO_CONFIG_CACHE

DEFAULT_PREFER_CACHE = False
_LOGGER = logging.getLogger(__name__)
EDIT_KEY = "edit_selection"
EDIT_TIMEOUT = "Timeouts"
EDIT_UNITS = "Unit Settings"


class PlaceholderAccount:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, username, password):
        """Initialize."""
        self.username = username
        self.password = password


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    account = KumoCloudAccount(data["username"], data["password"])
    try:
        result = await hass.async_add_executor_job(account.try_setup)
    except ConnectionError:
        raise CannotConnect
    if not result:
        raise InvalidAuth
    else:
        return {"title": data["username"]}


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

                account = KumoCloudAccount(
                    user_input["username"], user_input["password"]
                )
                await self.hass.async_add_executor_job(account.try_setup)
                self.kumo_cache = await self.hass.async_add_executor_job(
                    account.get_raw_json
                )
                self.user_account_setup = user_input
                self.title = info["title"]
                self.units = []
                for child in self.kumo_cache[2]["children"]:
                    for raw_unit in child["zoneTable"].values():
                        self.units.append(
                            {
                                "label": raw_unit["label"],
                                "ip_address": raw_unit.get("address", "empty"),
                                "mac": raw_unit["mac"],
                            }
                        )
                    if "children" in child:
                        for grandchild in child["children"]:
                            for raw_unit in grandchild["zoneTable"].values():
                                self.units.append(
                                    {
                                        "label": raw_unit["label"],
                                        "ip_address": raw_unit.get("address", "empty"),
                                        "mac": raw_unit["mac"],
                                    }
                                )
                ip_addresses = []
                for x in self.units:
                    ip_addresses.append(x["ip_address"])
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
            for x in user_input.keys():
                for child in self.kumo_cache[2]["children"]:
                    for raw_unit in child["zoneTable"].values():
                        if x == raw_unit["label"]:
                            raw_unit["address"] = user_input[x]
                    if "children" in child:
                        for grandchild in child["children"]:
                            for raw_unit in grandchild["zoneTable"].values():
                                if x == raw_unit["label"]:
                                    raw_unit["address"] = user_input[x]
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
            step_id="confirm",
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
                vol.Required("connect_timeout", default=1.2): str,
                vol.Required("response_timeout", default=8): str,
            }
        )

        return self.async_show_form(step_id="timeout_settings", data_schema=data_schema)

    async def async_step_unit_select(self, user_input=None):
        """Handle options flow."""

        kumo_cache = await self.hass.async_add_executor_job(
            load_json, self.hass.config.path(KUMO_CONFIG_CACHE)
        )
        kumo_unit_list = {}
        for child in kumo_cache[2]["children"]:
            for raw_unit in child["zoneTable"].values():
                kumo_unit_list[str(raw_unit["label"])] = (
                    str(raw_unit.get("address", "empty")),
                )
            if "children" in child:
                for grandchild in child["children"]:
                    for raw_unit in grandchild["zoneTable"].values():
                        kumo_unit_list[str(raw_unit["label"])] = (
                            str(raw_unit.get("address", "empty")),
                        )

        if user_input is not None:
            for child in kumo_cache[2]["children"]:
                for raw_unit in child["zoneTable"].values():
                    if raw_unit["label"] == user_input["unit_label"]:
                        raw_unit["address"] = user_input["ip_address"]
                    if "children" in child:
                        for grandchild in child["children"]:
                            for raw_unit in grandchild["zoneTable"].values():
                                if raw_unit["label"] == user_input["unit_label"]:
                                    raw_unit["address"] = user_input["ip_address"]
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
