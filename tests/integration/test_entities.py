"""Media player, preset select and sensor tests."""

import pytest
from homeassistant.exceptions import ServiceValidationError

PLAYER = "media_player.realiser_a16_user_a"
PRESET = "select.realiser_a16_preset_a"


async def _call(hass, domain, service, entity, **data):
    await hass.services.async_call(
        domain, service, {"entity_id": entity, **data}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)


# --- media player ----------------------------------------------------------------


async def test_player_state_and_attributes(hass, setup_integration):
    st = hass.states.get(PLAYER)
    assert st.state == "on"
    assert st.attributes["volume_level"] == pytest.approx((64 - 27) / 72)
    assert st.attributes["source"] == "HDMI 1"
    assert "Optical" in st.attributes["source_list"]
    assert st.attributes["power_state"] == "on"
    assert st.attributes["preset"] == 6


async def test_power_states(hass, setup_integration):
    client = setup_integration
    client.push(b"PWR=STANDBY")
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == "off"

    await _call(hass, "media_player", "turn_on", PLAYER)
    st = hass.states.get(PLAYER)
    assert client.sent[-1] == "2c"
    assert st.state == "on"  # BOOT is shown as on
    assert st.attributes["power_state"] == "boot"

    await _call(hass, "media_player", "turn_on", PLAYER)
    assert client.sent.count("2c") == 1  # no second 2c while booting

    await _call(hass, "media_player", "turn_off", PLAYER)
    assert client.sent[-1] == "2d"
    assert hass.states.get(PLAYER).state == "off"


async def test_set_volume_steps_to_target(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "volume_set", PLAYER, volume_level=0.5)
    assert client.state.user_a.volume == 63  # 27 + 0.5 * 72
    assert client.sent.count("31") == 1  # 64 -> 63


async def test_latest_volume_target_wins(hass, setup_integration, config_entry):
    client = setup_integration
    coordinator = config_entry.runtime_data
    await coordinator.async_set_volume("a", 70)
    await coordinator.async_set_volume("a", 60)  # replaces 70 while stepping
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.state.user_a.volume == 60
    assert client.sent.count("30") < 6  # did not walk all the way to 70


async def test_volume_step(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "volume_up", PLAYER)
    assert client.sent == ["30"]
    assert client.state.user_a.volume == 65
    await _call(hass, "media_player", "volume_down", PLAYER)
    assert client.sent == ["30", "31"]


async def test_mute_with_unknown_state_toggles_until_confirmed(hass, setup_integration):
    client = setup_integration
    client.device_muted = True  # device is muted, HA does not know (None)
    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    # first toggle unmuted the device, second toggle muted it again
    assert client.sent == ["32", "32"]
    assert hass.states.get(PLAYER).attributes["is_volume_muted"] is True

    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    assert client.sent == ["32", "32"]  # known state: nothing to do

    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=False)
    assert client.sent == ["32", "32", "32"]
    assert hass.states.get(PLAYER).attributes["is_volume_muted"] is False


async def test_mute_without_answer_becomes_unknown(hass, setup_integration):
    from homeassistant.exceptions import HomeAssistantError

    client = setup_integration
    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    assert hass.states.get(PLAYER).attributes["is_volume_muted"] is True
    client.timeout_codes.add("32")
    with pytest.raises(HomeAssistantError):
        await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=False)
    # there is no query command for mute: the state is unknown now
    assert "is_volume_muted" not in hass.states.get(PLAYER).attributes


async def test_select_source(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "select_source", PLAYER, source="HDMI 2")
    assert client.sent == ["22"]
    assert hass.states.get(PLAYER).attributes["source"] == "HDMI 2"

    with pytest.raises(ServiceValidationError):
        await _call(hass, "media_player", "select_source", PLAYER, source="VGA")


# --- preset select -------------------------------------------------------------------


async def test_preset_select_learns_names(hass, setup_integration):
    client = setup_integration
    st = hass.states.get(PRESET)
    assert st.state == "6 – Room 1 / Subject 1"
    assert len(st.attributes["options"]) == 16
    assert st.attributes["options"][2] == "3"  # not active yet -> no name

    await _call(hass, "select", "select_option", PRESET, option="3")
    assert client.sent == ["72"]
    st = hass.states.get(PRESET)
    assert st.state == "3 – Room 3 / Subject 3"
    assert st.attributes["options"][2] == "3 – Room 3 / Subject 3"
    assert st.attributes["options"][5] == "6 – Room 1 / Subject 1"  # kept


async def test_preset_select_invalid(hass, setup_integration):
    with pytest.raises(ServiceValidationError):
        await _call(hass, "select", "select_option", PRESET, option="17")


# --- sensors ---


async def test_sensors(hass, setup_integration):
    client = setup_integration
    assert hass.states.get("sensor.realiser_a16_mode").state == "svs"
    assert hass.states.get("sensor.realiser_a16_head_tracking_mode").state == "Gyro"
    assert hass.states.get("sensor.realiser_a16_firmware").state == "2.17 Jan 26 2024"
    client.push(b"MODE=AV")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.realiser_a16_mode").state == "av"
