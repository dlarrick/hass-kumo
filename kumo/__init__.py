"""Support for Mitsubishi KumoCloud devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util.json import save_json, load_json
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from .pykumo import pykumo

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kumo"
KUMO_DATA = "kumo_data"
KUMO_CONFIG_CACHE = "kumo_cache.json"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

class KumoData:
    """Hold object representing KumoCloud account. """

    def __init__(self, account):
        """Init KumoCloudAccount object."""
        self._account = account
    def get_account(self):
        """Retrieve account."""
        return self._account
    def get_raw_json(self):
        """Retrieve raw JSON config from account."""
        return self._account.get_raw_json()

def setup_kumo(hass, config):
    """Set up the Kumo indoor units."""
    hass.async_create_task(async_load_platform(hass, "climate", DOMAIN, {},
                                               config))

async def async_setup(hass, config):
    """ Set up the Kumo Cloud devices.

    Will create climate and sensor components to support
    devices listed on the provided Kumo Cloud account.
    """

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    # Check if account retrieved units successfully.
    # If so, cache raw JSON in config file.
    # If not, load raw JSON from cached config file.
    account = pykumo.KumoCloudAccount(username, password)
    if account.try_setup():
        await hass.async_add_executor_job(
            save_json, hass.config.path(KUMO_CONFIG_CACHE),
            account.get_raw_json())
        _LOGGER.info("Loaded config from KumoCloud server")
    else:
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE))
        if cached_json:
            account = pykumo.KumoCloudAccount(
                username, password, kumo_dict=cached_json)
            _LOGGER.info("Loaded config from local cache")
        else:
            _LOGGER.warning("Could not load KumoCloud cache")

    hass.data[KUMO_DATA] = KumoData(account)

    setup_kumo(hass, config)

    return True
