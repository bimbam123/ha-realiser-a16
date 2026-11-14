"""v0.3.0: source and rendering selects, test/HT switches, new sensors."""

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

DEVICE = "media_player.realiser_a16"
SOURCE = "select.realiser_a16_source"
RENDERING = "select.realiser_a16_rendering"
TEST = "switch.realiser_a16_test_signal"
HT = "button.realiser_a16_ht_display"


async def _call(hass, domain, service, entity, **data):
    await hass.services.async_call(
        domain, service, {"entity_id": entity, **data}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)


# --- source select: same state as the device player ---


async def test_source_select_follows_device_player(hass, setup_integration):
    client = setup_integration
    st = hass.states.get(SOURCE)
    assert st.state == "HDMI 1"
    assert "Optical" in st.attributes["options"]

    await _call(hass, "select", "select_option", SOURCE, option="Optical")
    assert client.sent[-1] == "29"
    assert hass.states.get(SOURCE).state == "Optical"
    assert hass.states.get(DEVICE).attributes["source"] == "Optical"

    await _call(hass, "media_player", "select_source", DEVICE, source="USB")
    assert hass.states.get(SOURCE).state == "USB"

    client.push(b"IN=eARC")  # changed with the remote
    await hass.async_block_till_done()
    assert hass.states.get(SOURCE).state == "eARC"


async def test_source_select_invalid(hass, setup_integration):
    with pytest.raises(ServiceValidationError):
        await _call(hass, "select", "select_option", SOURCE, option="VGA")


# --- rendering select: SVS headphone (4d) / AV or stereo mixdown (5e) ---


async def test_rendering_select(hass, setup_integration):
    client = setup_integration
    assert hass.states.get(RENDERING).state == "svs"
    await _call(hass, "select", "select_option", RENDERING, option="av_mix")
    assert client.sent[-1] == "5e"
    # AV mode off in the preset: the speaker key gives stereo mixdown
    assert hass.states.get(RENDERING).state == "av_mix"
    assert hass.states.get("sensor.realiser_a16_rendering_mode").state == "mix"

    # AV mode on in the preset: AV loudspeaker mode, same select option
    client.push(b"MODE=AV")
    await hass.async_block_till_done()
    assert hass.states.get(RENDERING).state == "av_mix"
    assert hass.states.get("sensor.realiser_a16_rendering_mode").state == "av"

    await _call(hass, "select", "select_option", RENDERING, option="svs")
    assert client.sent[-1] == "4d"
    assert hass.states.get(RENDERING).state == "svs"
    assert hass.states.get("sensor.realiser_a16_rendering_mode").state == "svs"


async def test_rendering_keeps_unique_ids(hass, setup_integration):
    """Renamed from Output/Mode in 0.3.0b2: unique IDs stay the same."""
    reg = er.async_get(hass)
    assert reg.async_get(RENDERING).unique_id.endswith("_output")
    sensor = reg.async_get("sensor.realiser_a16_rendering_mode")
    assert sensor.unique_id.endswith("_mode")


async def test_mode_sensor_is_diagnostic(hass, setup_integration):
    entry = er.async_get(hass).async_get("sensor.realiser_a16_rendering_mode")
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC


# --- test signal: toggle 08, state from af ---


async def test_test_signal_switch(hass, setup_integration):
    client = setup_integration
    assert hass.states.get(TEST).state == "off"
    await _call(hass, "switch", "turn_on", TEST)
    assert client.sent == ["08"]
    assert hass.states.get(TEST).state == "on"
    await _call(hass, "switch", "turn_on", TEST)  # already on
    assert client.sent == ["08"]
    await _call(hass, "switch", "turn_off", TEST)
    assert client.sent == ["08", "08"]
    assert hass.states.get(TEST).state == "off"


async def test_ignored_test_toggle_is_sent_again(hass, setup_integration):
    client = setup_integration
    client.drop_codes["08"] = 1
    await _call(hass, "switch", "turn_on", TEST)
    assert client.sent == ["08", "af", "08"]
    assert client.device_test == "LOOP"
    assert hass.states.get(TEST).state == "on"


# --- HT display: button, sends 42 once, never repeated blindly ---


async def test_ht_display_button_sends_42_once(hass, setup_integration):
    client = setup_integration
    await _call(hass, "button", "press", HT)
    assert client.sent == ["42"]


async def test_ht_display_button_not_repeated_without_answer(hass, setup_integration):
    client = setup_integration
    client.drop_codes["42"] = 1
    with pytest.raises(HomeAssistantError):
        await _call(hass, "button", "press", HT)
    assert client.sent == ["42"]


# --- new sensors ---


async def test_format_and_preset_sensors(hass, setup_integration):
    client = setup_integration
    assert hass.states.get("sensor.realiser_a16_decoder").state == "PCM 2ch"
    assert hass.states.get("sensor.realiser_a16_listening_mode").state == "2.1.0"
    assert hass.states.get("sensor.realiser_a16_upmixer").state == "OFF"
    assert hass.states.get("sensor.realiser_a16_legacy_decoding").state == "OFF"
    assert hass.states.get("sensor.realiser_a16_users").state == "DUAL"
    hpeq = hass.states.get("sensor.realiser_a16_hpeq_a")
    assert hpeq.state == "HD800S Subject 1"
    assert hpeq.attributes["headphone"] == "HD800S"
    assert hpeq.attributes["type"] == "flatEQ"
    assert hass.states.get("binary_sensor.realiser_a16_tactile_a").state == "on"
    assert (
        hass.states.get("binary_sensor.realiser_a16_tactile_b").state == STATE_UNKNOWN
    )

    # empty ATACT=: the room has no tactile output -> off, not unknown
    client.push(b"ATACT=")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.realiser_a16_tactile_a").state == "off"
    client.push(b"ATACT=ON")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.realiser_a16_tactile_a").state == "on"

    client.push(b"DEC=Dolby Atmos\x00LM=7.1.4")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.realiser_a16_decoder").state == "Dolby Atmos"
    assert hass.states.get("sensor.realiser_a16_listening_mode").state == "7.1.4"
