"""Support for Mitsubishi KumoCloud devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util.json import save_json, load_json
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pykumo==0.1.0']
DOMAIN = "kumo"
KUMO_DATA = "kumo_data"
KUMO_CONFIG_CACHE = "kumo_cache.json"
CONF_PREFER_CACHE = "prefer_cache"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PREFER_CACHE, default=False): cv.boolean,
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
    import pykumo

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    prefer_cache = config[DOMAIN].get(CONF_PREFER_CACHE)

    # Read config from either remote KumoCloud server or
    # cached JSON.
    cached_json = {}
    if prefer_cache:
        cached_json = await hass.async_add_executor_job(
            load_json, hass.config.path(KUMO_CONFIG_CACHE))
    account = pykumo.KumoCloudAccount(username, password)
    if not cached_json and account.try_setup():
        await hass.async_add_executor_job(
            save_json, hass.config.path(KUMO_CONFIG_CACHE),
            account.get_raw_json())
        _LOGGER.info("Loaded config from KumoCloud server")
    else:
        if cached_json:
            account = pykumo.KumoCloudAccount(
                username, password, kumo_dict=cached_json)
            _LOGGER.info("Loaded config from local cache")
        else:
            _LOGGER.warning("Could not load KumoCloud cache")

    hass.data[KUMO_DATA] = KumoData(account)

    setup_kumo(hass, config)

    return True
