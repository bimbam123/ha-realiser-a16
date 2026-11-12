"""Setup, unload, availability and update filtering."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE

ENTITY = "media_player.realiser_a16_user_a"


async def test_setup_and_unload(hass, setup_integration, config_entry):
    client = setup_integration
    assert config_entry.state is ConfigEntryState.LOADED
    assert len(client.__class__.instances) == 1  # one connection per device
    assert hass.states.get(ENTITY).state == "on"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert client.stopped


async def test_not_reachable_retries_setup(hass, mock_client, config_entry):
    mock_client.next_fail_connect = True
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_client.instances[-1].stopped


async def test_entities_unavailable_while_disconnected(hass, setup_integration):
    client = setup_integration
    client.set_connected(False)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get("select.realiser_a16_preset_a").state == STATE_UNAVAILABLE
    client.set_connected(True)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "on"


async def test_only_relevant_changes_notify(hass, setup_integration, config_entry):
    client = setup_integration
    coordinator = config_entry.runtime_data
    calls = []
    unsub = coordinator.async_add_listener(lambda: calls.append(1))
    client.push(b"L1=10\x00AHL=20")  # level meters: not used by entities
    client.push(b"FOO=1")  # unknown field
    client.push(b"VA=64")  # unchanged value
    assert calls == []
    client.push(b"VA=65")
    assert calls == [1]
    unsub()


async def test_device_info(hass, setup_integration, config_entry):
    from homeassistant.helpers import device_registry as dr

    from .conftest import SERIAL

    device = dr.async_get(hass).async_get_device_by_identifier(
        ("realiser_a16", SERIAL), config_entry.entry_id
    )
    assert device.manufacturer == "Smyth Research"
    assert device.model == "Realiser A16"
    assert device.sw_version == "2.17 Jan 26 2024"


async def test_firmware_change_updates_device(hass, setup_integration, config_entry):
    from homeassistant.helpers import device_registry as dr

    from .conftest import SERIAL

    setup_integration.push(b"A16FW=2.18 Test")
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("realiser_a16", SERIAL), config_entry.entry_id
    )
    assert device.sw_version == "2.18 Test"
