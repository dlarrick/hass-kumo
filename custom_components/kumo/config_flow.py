"""Config flow for Kumo integration."""
import logging

import voluptuous as vol
from pykumo import KumoCloudAccount
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util.json import load_json, save_json
from .const import (
    DOMAIN,
    KUMO_DATA,
    KUMO_CONFIG_CACHE,
    CONF_PREFER_CACHE,
    CONF_CONNECT_TIMEOUT,
    CONF_RESPONSE_TIMEOUT,
)  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("prefer_cache", default=False): bool,
        vol.Optional("connect_timeout", default=10): int,
        vol.Optional("response_timeout", default=10): int,
    }
)


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
    result = await hass.async_add_executor_job(account.try_setup)
    if not result:
        raise InvalidAuth
    else:
        return {"title": data["username"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kumo."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                # info = await self.hass.async_add_executor_job(
                #    KumoCloudAccount, CONF_USERNAME, CONF_PASSWORD
                # )
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "prefer_cache": user_input["prefer_cache"],
                        "connect_timeout": user_input["connect_timeout"],
                        "response_timeout": user_input["response_timeout"],
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
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
