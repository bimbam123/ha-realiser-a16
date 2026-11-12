"""Config and options flow tests."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.realiser_a16.const import DOMAIN
from custom_components.realiser_a16.pya16 import A16ConnectionError

from .conftest import HOST, SERIAL


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


async def test_options_flow_changes_port_and_reloads(hass, setup_integration):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"port": 5000}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {"port": 5000}
    from .conftest import MockA16Client

    assert setup_integration.stopped
    assert MockA16Client.instances[-1].port == 5000
