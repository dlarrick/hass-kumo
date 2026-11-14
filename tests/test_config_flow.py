"""Tests for the Kumo config flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.kumo.const import DOMAIN


async def test_user_form(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}


async def test_user_form_invalid_auth(hass: HomeAssistant):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.kumo.config_flow.KumoCloudAccount.try_setup",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "prefer_cache": False,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_form_success(hass: HomeAssistant):
    """Test we create an entry on success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "custom_components.kumo.config_flow.KumoCloudAccount.try_setup",
            return_value=True,
        ),
        patch(
            "custom_components.kumo.config_flow.KumoCloudAccount.get_raw_json",
            return_value=[{}, {}, {"children": []}],
        ),
        patch(
            "custom_components.kumo.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "prefer_cache": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "prefer_cache": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery(hass: HomeAssistant):
    """Test DHCP discovery."""
    from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

    discovery_info = DhcpServiceInfo(
        ip="192.168.1.100",
        macaddress="112233445566",
        hostname="kumo_device",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=discovery_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Verify candidate IP was stored
    from custom_components.kumo.const import DHCP_DISCOVERED_KEY

    assert hass.data[DHCP_DISCOVERED_KEY]["112233445566"] == "192.168.1.100"

    # Verify the flow unique_id is set
    flows = hass.config_entries.flow.async_progress()
    for flow in flows:
        if flow["handler"] == DOMAIN:
            assert flow["context"]["unique_id"] == "112233445566"


async def test_dhcp_discovery_already_configured(hass: HomeAssistant):
    """Test DHCP discovery when already configured."""
    from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)

    discovery_info = DhcpServiceInfo(
        ip="192.168.1.101",
        macaddress="aabbccddeeff",
        hostname="kumo_device_2",
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=discovery_info
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify candidate IP was still stored
    from custom_components.kumo.const import DHCP_DISCOVERED_KEY

    assert hass.data[DHCP_DISCOVERED_KEY]["aabbccddeeff"] == "192.168.1.101"

    # Verify reload was scheduled
    mock_reload.assert_called_once_with(entry.entry_id)


async def test_options_flow_timeout_settings(hass: HomeAssistant):
    """Test updating timeout settings via options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "u", "password": "p"},
        options={"connect_timeout": 2.0, "response_timeout": 10.0},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"edit_selection": "Timeouts"}
    )
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "timeout_settings"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "connect_timeout": 3.0,
            "response_timeout": 12.0,
            "scan_interval": 45,
            "post_command_refresh_delay": 1.5,
        },
    )
    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        "connect_timeout": 3.0,
        "response_timeout": 12.0,
        "scan_interval": 45,
        "post_command_refresh_delay": 1.5,
    }


async def test_options_flow_unit_select_preserves_options(hass: HomeAssistant):
    """Test editing a unit IP via options flow preserves existing options."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    existing_options = {
        "connect_timeout": 2.5,
        "response_timeout": 9.0,
        "scan_interval": 30,
        "post_command_refresh_delay": 1.0,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "u", "password": "p"},
        options=existing_options,
    )
    entry.add_to_hass(hass)

    kumo_cache = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "SERIAL1": {"label": "Living Room", "address": "192.168.1.10"}
                    }
                }
            ]
        },
    ]

    with (
        patch("custom_components.kumo.config_flow.load_json", return_value=kumo_cache),
        patch("custom_components.kumo.config_flow.save_json") as mock_save,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"edit_selection": "Unit Settings"}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "unit_select"

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"unit_label": "Living Room", "ip_address": "192.168.1.20"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["data"] == existing_options
    mock_save.assert_called_once()
    assert (
        kumo_cache[2]["children"][0]["zoneTable"]["SERIAL1"]["address"]
        == "192.168.1.20"
    )
