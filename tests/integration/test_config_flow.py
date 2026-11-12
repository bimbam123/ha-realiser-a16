"""Config flow and reconfigure tests."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.realiser_a16.api import A16DeviceInfo
from custom_components.realiser_a16.const import DOMAIN
from custom_components.realiser_a16.pya16 import A16ConnectionError

from .conftest import HOST, SERIAL, MockA16Client


async def test_user_flow_creates_entry(hass, mock_client, mock_device_info):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4101}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": HOST, "port": 4101}
    assert result["result"].unique_id == SERIAL
    mock_device_info.assert_awaited_once_with(HOST, 4101, 10.0)


async def test_user_flow_cannot_connect(hass, mock_client, mock_device_info):
    mock_device_info.side_effect = A16ConnectionError("nope")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4101}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # recovers after the error
    mock_device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4101}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(hass, mock_client, mock_device_info):
    mock_device_info.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4101}
    )
    assert result["errors"] == {"base": "unknown"}


async def test_same_host_aborts_without_connecting(
    hass, mock_client, mock_device_info, config_entry
):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4101}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_device_info.assert_not_called()


async def test_same_serial_new_host_updates_entry(
    hass, mock_client, mock_device_info, config_entry
):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.99", "port": 4101}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "192.0.2.99"


async def _reconfigure(hass, entry, data):
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_reconfigure_new_host_same_device(
    hass, setup_integration, mock_device_info, config_entry
):
    result = await _reconfigure(
        hass, config_entry, {"host": "192.0.2.50", "port": 4101}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_device_info.assert_awaited_once_with("192.0.2.50", 4101, 10.0)
    await hass.async_block_till_done()
    assert config_entry.data == {"host": "192.0.2.50", "port": 4101}
    assert setup_integration.stopped  # old connection closed by the reload
    assert MockA16Client.instances[-1].host == "192.0.2.50"


async def test_reconfigure_new_host_other_device(
    hass, setup_integration, mock_device_info, config_entry
):
    mock_device_info.return_value = A16DeviceInfo("OTHER", None, None, None, None)
    result = await _reconfigure(
        hass, config_entry, {"host": "192.0.2.50", "port": 4101}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data["host"] == HOST


async def test_reconfigure_new_host_not_reachable(
    hass, setup_integration, mock_device_info, config_entry
):
    mock_device_info.side_effect = A16ConnectionError("nope")
    result = await _reconfigure(
        hass, config_entry, {"host": "192.0.2.50", "port": 4101}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert config_entry.data["host"] == HOST


async def test_reconfigure_port_only_without_test(
    hass, setup_integration, mock_device_info, config_entry
):
    result = await _reconfigure(hass, config_entry, {"host": HOST, "port": 5000})
    assert result["reason"] == "reconfigure_successful"
    mock_device_info.assert_not_called()  # the integration holds the connection
    await hass.async_block_till_done()
    assert config_entry.data["port"] == 5000
    assert MockA16Client.instances[-1].port == 5000


async def test_reconfigure_takes_over_port_from_old_options(
    hass, mock_client, mock_device_info
):
    """v0.2.0 stored a changed port in the options; reconfigure moves it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={"host": HOST, "port": 4101},
        options={"port": 4200},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert MockA16Client.instances[-1].port == 4200

    result = await entry.start_reconfigure_flow(hass)
    schema_defaults = {
        str(k): k.description["suggested_value"] for k in result["data_schema"].schema
    }
    assert schema_defaults == {"host": HOST, "port": 4200}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 4200}
    )
    await hass.async_block_till_done()
    assert entry.data["port"] == 4200
    assert entry.options == {}
