"""Config flow for Kumo integration."""
import logging
from requests.exceptions import ConnectionError
import voluptuous as vol
from pykumo import KumoCloudAccount
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
from .const import DOMAIN
DEFAULT_PREFER_CACHE = False
_LOGGER = logging.getLogger(__name__)


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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Kumo."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required("connect_timeout", default=1.2): str,
                vol.Required("response_timeout", default=8): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
