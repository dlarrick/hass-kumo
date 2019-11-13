"""Support for Mitsubishi KumoCloud devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from .pykumo import pykumo

_LOGGER = logging.getLogger(__name__)


DOMAIN = "kumo"
KUMO_DATA = "kumo_data"

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

    def __init__(self, config):
        """Init KumoCloudAccount object."""
        username = config[DOMAIN].get(CONF_USERNAME)
        password = config[DOMAIN].get(CONF_PASSWORD)
        self._account = pykumo.KumoCloudAccount(username, password)
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
    hass.data[KUMO_DATA] = KumoData(config)

    setup_kumo(hass, config)

    return True
