"""Coordinator to gather data for the Kumo integration"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)
from pykumo import PyKumoBase

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
MAX_AVAILABILITY_TRIES = 3

T = TypeVar("T")


class KumoDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific Kumo device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: PyKumoBase,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific Kumo device."""
        self.device = device
        self._available = False
        self._unavailable_count = 0
        self._additional_update_methods = []
        super().__init__(
            hass,
            _LOGGER,
            name=f"kumo_{device.get_serial()}",
            update_interval=SCAN_INTERVAL,
        )

    def get_device(self) -> PyKumoBase:
        return self.device

    def get_available(self) -> bool:
        return self._available

    def add_update_method(self, update_method: Callable[[], Awaitable[T]]) -> None:
        """Register update methods that will be called after updating status"""
        self._additional_update_methods.append(update_method)

    async def _async_update_data(self) -> None:
        """Fetch data from Kumo device."""
        success = await self.hass.async_add_executor_job(self.device.update_status)
        self._update_availability(success)
        if success:
            for update_method in self._additional_update_methods:
                await update_method()
        else:
            raise UpdateFailed(f"Failed to update Kumo device: {self.device.get_name()}")

    def _update_availability(self, success: bool) -> None:
        if success:
            self._available = True
            self._unavailable_count = 0
        else:
            self._unavailable_count += 1
            if self._unavailable_count >= MAX_AVAILABILITY_TRIES:
                self._available = False
