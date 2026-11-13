"""v0.3.0: source and output selects, test/HT switches, new sensors."""

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

DEVICE = "media_player.realiser_a16"
SOURCE = "select.realiser_a16_source"
OUTPUT = "select.realiser_a16_output"
TEST = "switch.realiser_a16_test_signal"
HT = "switch.realiser_a16_head_tracking"


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


# --- output select: headphones (4d) / speakers (5e) ---


async def test_output_select(hass, setup_integration):
    client = setup_integration
    assert hass.states.get(OUTPUT).state == "headphones"
    await _call(hass, "select", "select_option", OUTPUT, option="speakers")
    assert client.sent[-1] == "5e"
    assert hass.states.get(OUTPUT).state == "speakers"
    assert hass.states.get("sensor.realiser_a16_mode").state == "mix"

    client.push(b"MODE=AV")
    await hass.async_block_till_done()
    assert hass.states.get(OUTPUT).state == "speakers"

    await _call(hass, "select", "select_option", OUTPUT, option="headphones")
    assert client.sent[-1] == "4d"
    assert hass.states.get(OUTPUT).state == "headphones"


async def test_mode_sensor_is_diagnostic(hass, setup_integration):
    entry = er.async_get(hass).async_get("sensor.realiser_a16_mode")
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


# --- head tracking: toggle 42, no query ---


async def test_head_tracking_starts_unknown_and_is_assumed(hass, setup_integration):
    st = hass.states.get(HT)
    assert st.state == STATE_UNKNOWN
    assert st.attributes["assumed_state"] is True


async def test_head_tracking_unknown_state_is_corrected(hass, setup_integration):
    client = setup_integration
    client.device_ht = "ACTIVE"
    await _call(hass, "switch", "turn_on", HT)
    assert client.sent == ["42", "42"]  # first answer was OFF
    assert hass.states.get(HT).state == "on"
    await _call(hass, "switch", "turn_off", HT)
    assert client.sent == ["42", "42", "42"]
    assert hass.states.get(HT).state == "off"


async def test_head_tracking_without_answer_becomes_unknown(hass, setup_integration):
    client = setup_integration
    await _call(hass, "switch", "turn_on", HT)
    client.drop_codes["42"] = 2
    with pytest.raises(HomeAssistantError):
        await _call(hass, "switch", "turn_off", HT)
    assert client.sent.count("42") == 3
    assert hass.states.get(HT).state == STATE_UNKNOWN


async def test_head_tracking_pushed_from_remote(hass, setup_integration):
    client = setup_integration
    client.push(b"HT=ACTIVE")
    await hass.async_block_till_done()
    assert hass.states.get(HT).state == "on"


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

    client.push(b"DEC=Dolby Atmos\x00LM=7.1.4")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.realiser_a16_decoder").state == "Dolby Atmos"
    assert hass.states.get("sensor.realiser_a16_listening_mode").state == "7.1.4"
