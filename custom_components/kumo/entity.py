"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KumoDataUpdateCoordinator


class CoordinatedKumoEntitty(CoordinatorEntity):
    """Defines a base Kumo entity."""

    def __init__(
        self,
        coordinator: KumoDataUpdateCoordinator
    ) -> None:
        """Initialize the Kumo entity."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._pykumo = coordinator.get_device()
        self._identifier = self._pykumo.get_serial()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this IPP device."""
        if self._identifier is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._identifier)},
            manufacturer="Mitsubishi",
            name=self._pykumo.get_name(),
        )

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def available(self):
        """Return whether Home Assistant is able to read the state and control the underlying device."""
        return self._coordinator.get_available()

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name
