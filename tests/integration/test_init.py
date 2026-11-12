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
    for entity in (
        "media_player.realiser_a16",
        "media_player.realiser_a16_user_b",
        "number.realiser_a16_volume_a",
        "select.realiser_a16_preset_b",
        "sensor.realiser_a16_mode",
    ):
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
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


async def test_entities_created(hass, setup_integration, config_entry):
    from homeassistant.helpers import entity_registry as er

    entries = er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    )
    assert sorted(e.entity_id for e in entries) == [
        "media_player.realiser_a16",
        "media_player.realiser_a16_user_a",
        "media_player.realiser_a16_user_b",
        "number.realiser_a16_volume_a",
        "number.realiser_a16_volume_b",
        "select.realiser_a16_preset_a",
        "select.realiser_a16_preset_b",
        "sensor.realiser_a16_firmware",
        "sensor.realiser_a16_head_tracking_mode",
        "sensor.realiser_a16_mode",
    ]
    # User A keeps the unique ID of v0.2.0 (same entity ID after the update)
    from .conftest import SERIAL

    player_a = er.async_get(hass).async_get("media_player.realiser_a16_user_a")
    assert player_a.unique_id == f"{SERIAL}_user_a_player"


async def test_diagnostics(hass, setup_integration, config_entry):
    from custom_components.realiser_a16.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["connection"]["connected"] is True
    assert diag["connection"]["settings"]["min_step_interval"] == 1.5
    assert "commands_sent" in diag["connection"]["stats"]
    assert diag["state"]["firmware"]["serial"] == "**REDACTED**"
    assert diag["state"]["user_a"]["room"] == "**REDACTED**"
    assert diag["state"]["user_a"]["volume"] == 64
    assert diag["entry"]["title"] == "**REDACTED**"
    assert diag["learned_preset_names"]["a"] == [6]
