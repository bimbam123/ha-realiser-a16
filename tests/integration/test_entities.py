"""Device player, user players (volume 1:1), preset selects and sensors."""

import pytest
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

DEVICE = "media_player.realiser_a16"
PLAYER_A = "media_player.realiser_a16_user_a"
PLAYER_B = "media_player.realiser_a16_user_b"
PRESET_A = "select.realiser_a16_preset_a"
PRESET_B = "select.realiser_a16_preset_b"


async def _call(hass, domain, service, entity, **data):
    await hass.services.async_call(
        domain, service, {"entity_id": entity, **data}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)


# --- device player: power and source ---


async def test_device_player(hass, setup_integration):
    st = hass.states.get(DEVICE)
    assert st.state == "on"
    assert st.attributes["source"] == "HDMI 1"
    assert "Optical" in st.attributes["source_list"]
    assert st.attributes["power_state"] == "on"
    assert st.attributes["user_mode"] == "DUAL"
    features = st.attributes["supported_features"]
    assert features & MediaPlayerEntityFeature.TURN_ON
    assert not features & MediaPlayerEntityFeature.VOLUME_SET


async def test_power_states(hass, setup_integration):
    client = setup_integration
    client.push(b"PWR=STANDBY")
    await hass.async_block_till_done()
    for entity in (DEVICE, PLAYER_A, PLAYER_B):
        assert hass.states.get(entity).state == "off"

    await _call(hass, "media_player", "turn_on", DEVICE)
    assert client.sent[-1] == "2c"
    st = hass.states.get(DEVICE)
    assert st.state == "on"  # BOOT is shown as on
    assert st.attributes["power_state"] == "boot"
    assert hass.states.get(PLAYER_B).state == "on"

    await _call(hass, "media_player", "turn_on", DEVICE)
    assert client.sent.count("2c") == 1  # no second 2c while booting

    await _call(hass, "media_player", "turn_off", DEVICE)
    assert client.sent[-1] == "2d"
    assert hass.states.get(DEVICE).state == "off"


async def test_select_source(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "select_source", DEVICE, source="HDMI 2")
    assert client.sent == ["22"]
    assert hass.states.get(DEVICE).attributes["source"] == "HDMI 2"

    with pytest.raises(ServiceValidationError):
        await _call(hass, "media_player", "select_source", DEVICE, source="VGA")


# --- user players: volume 1:1 and mute ---


async def test_user_players_have_no_power_or_source(hass, setup_integration):
    for entity in (PLAYER_A, PLAYER_B):
        features = hass.states.get(entity).attributes["supported_features"]
        assert features & MediaPlayerEntityFeature.VOLUME_SET
        assert features & MediaPlayerEntityFeature.VOLUME_STEP
        assert features & MediaPlayerEntityFeature.VOLUME_MUTE
        assert not features & MediaPlayerEntityFeature.TURN_ON
        assert not features & MediaPlayerEntityFeature.TURN_OFF
        assert not features & MediaPlayerEntityFeature.SELECT_SOURCE


async def test_volume_is_shown_one_to_one(hass, setup_integration):
    a = hass.states.get(PLAYER_A).attributes
    assert a["volume_level"] == pytest.approx(0.64)  # A16 value 64 -> 64 %
    assert a["volume_raw"] == 64
    assert a["preset"] == 6
    b = hass.states.get(PLAYER_B).attributes
    assert b["volume_level"] == pytest.approx(0.65)
    assert b["layout"] == "9.1.6"


async def test_set_volume_one_to_one(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "volume_set", PLAYER_A, volume_level=0.66)
    assert client.state.user_a.volume == 66
    assert client.sent.count("30") == 2
    assert hass.states.get(PLAYER_A).attributes["volume_level"] == pytest.approx(0.66)

    await _call(hass, "media_player", "volume_set", PLAYER_B, volume_level=0.63)
    assert client.state.user_b.volume == 63
    assert client.sent.count("34") == 2


async def test_set_volume_is_limited_to_a16_range(hass, setup_integration):
    client = setup_integration
    client.state.user_a.volume = 28
    await _call(hass, "media_player", "volume_set", PLAYER_A, volume_level=0.10)
    assert client.state.user_a.volume == 27  # below 27 -> 27
    assert client.sent == ["31"]


async def test_latest_volume_target_wins(hass, setup_integration, config_entry):
    client = setup_integration
    coordinator = config_entry.runtime_data
    await coordinator.async_set_volume("a", 70)
    await coordinator.async_set_volume("a", 60)  # replaces 70 while stepping
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.state.user_a.volume == 60
    assert client.sent.count("30") < 6  # did not walk all the way to 70


async def test_volume_target_survives_ignored_steps(hass, setup_integration):
    client = setup_integration
    client.ignore_steps = 3  # A16 ignores three steps in a row
    await _call(hass, "media_player", "volume_set", PLAYER_A, volume_level=0.66)
    assert client.state.user_a.volume == 66
    assert client.sent.count("30") == 5


async def test_volume_target_gives_up_after_five_failures(hass, setup_integration):
    client = setup_integration
    client.ignore_steps = 100
    await _call(hass, "media_player", "volume_set", PLAYER_A, volume_level=0.70)
    assert client.state.user_a.volume == 64
    assert client.sent.count("30") == 5


async def test_volume_step_is_one_a16_step(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "volume_up", PLAYER_A)
    assert client.sent == ["30"]
    assert client.state.user_a.volume == 65
    await _call(hass, "media_player", "volume_down", PLAYER_B)
    assert client.sent == ["30", "34"]
    assert client.state.user_b.volume == 64


async def test_mute_starts_unknown(hass, setup_integration):
    # the A16 reports mute only when it is toggled
    assert "is_volume_muted" not in hass.states.get(PLAYER_A).attributes


async def test_mute_with_unknown_state_toggles_until_confirmed(hass, setup_integration):
    client = setup_integration
    client.device_muted["a"] = True  # device is muted, HA does not know (None)
    await _call(hass, "media_player", "volume_mute", PLAYER_A, is_volume_muted=True)
    # first toggle unmuted the device, second toggle muted it again
    assert client.sent == ["32", "32"]
    assert hass.states.get(PLAYER_A).attributes["is_volume_muted"] is True

    await _call(hass, "media_player", "volume_mute", PLAYER_A, is_volume_muted=True)
    assert client.sent == ["32", "32"]  # known state: nothing to do

    await _call(hass, "media_player", "volume_mute", PLAYER_B, is_volume_muted=True)
    assert client.sent == ["32", "32", "35"]
    assert hass.states.get(PLAYER_B).attributes["is_volume_muted"] is True


async def test_mute_without_answer_becomes_unknown(hass, setup_integration):
    client = setup_integration
    await _call(hass, "media_player", "volume_mute", PLAYER_A, is_volume_muted=True)
    assert hass.states.get(PLAYER_A).attributes["is_volume_muted"] is True
    client.timeout_codes.add("32")
    with pytest.raises(HomeAssistantError):
        await _call(
            hass, "media_player", "volume_mute", PLAYER_A, is_volume_muted=False
        )
    # there is no query command for mute: the state is unknown now
    assert "is_volume_muted" not in hass.states.get(PLAYER_A).attributes


async def test_mute_pushed_from_remote(hass, setup_integration):
    client = setup_integration
    client.push(b"MUTEB=MUTE")
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER_B).attributes["is_volume_muted"] is True


# --- preset selects ---


async def test_preset_a_learns_names(hass, setup_integration):
    client = setup_integration
    st = hass.states.get(PRESET_A)
    assert st.state == "6 – Room 1 / Subject 1"
    assert len(st.attributes["options"]) == 16
    assert st.attributes["options"][2] == "3"  # not active yet -> no name

    await _call(hass, "select", "select_option", PRESET_A, option="3")
    assert client.sent == ["72"]
    st = hass.states.get(PRESET_A)
    assert st.state == "3 – Room 3 / Subject 3"
    assert st.attributes["options"][5] == "6 – Room 1 / Subject 1"  # kept


async def test_preset_b_queries_user_b_info(hass, setup_integration):
    client = setup_integration
    assert hass.states.get(PRESET_B).state == "7 – Room B7 / Subject B7"

    await _call(hass, "select", "select_option", PRESET_B, option="10")
    # answer is only PB=10; the room/subject come from the a0 query
    assert client.sent[:2] == ["99", "a0"]
    st = hass.states.get(PRESET_B)
    assert st.state == "10 – Room B10 / Subject B10"
    assert st.attributes["options"][6] == "7 – Room B7 / Subject B7"


async def test_preset_select_invalid(hass, setup_integration):
    with pytest.raises(ServiceValidationError):
        await _call(hass, "select", "select_option", PRESET_A, option="17")


# --- sensors ---


async def test_sensors(hass, setup_integration):
    client = setup_integration
    assert hass.states.get("sensor.realiser_a16_mode").state == "svs"
    assert hass.states.get("sensor.realiser_a16_head_tracking_mode").state == "Gyro"
    assert hass.states.get("sensor.realiser_a16_firmware").state == "2.17 Jan 26 2024"
    client.push(b"MODE=AV")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.realiser_a16_mode").state == "av"
