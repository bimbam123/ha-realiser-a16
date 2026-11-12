"""Tests for A16Client against the fake A16 server."""

import asyncio

import pytest

from pya16 import A16Client, A16ConnectionError, A16TimeoutError
from pya16.protocol import encode_command, expected_keys, preset_command


@pytest.fixture(autouse=True)
def _allow_loopback_sockets(request):
    """These tests use a fake A16 on 127.0.0.1.

    pytest-homeassistant-custom-component (installed for the integration
    tests on Linux) blocks sockets by default; re-enable them here.
    """
    try:
        request.getfixturevalue("socket_enabled")
    except pytest.FixtureLookupError:
        pass  # plugin not installed (e.g. Windows): sockets are allowed anyway


def _client(server, **kw) -> A16Client:
    opts = {
        "keepalive_interval": 60,
        "response_timeout": 0.5,
        "connect_timeout": 1,
        "backoff_initial": 0.05,
        "backoff_max": 0.4,
        "command_gap": 0.0,
        "unknown_response_wait": 0.05,
        "min_command_interval": 0.0,
        "min_step_interval": 0.0,
        "step_confirm_wait": 0.3,
        "refresh_on_connect": False,
    }
    opts.update(kw)
    return A16Client("127.0.0.1", server.port, **opts)


async def _wait_for(cond, timeout=3.0):
    async with asyncio.timeout(timeout):
        while not cond():
            await asyncio.sleep(0.01)


def test_protocol_helpers():
    assert encode_command("2E") == b"2e\r\n"
    assert preset_command("a", 1) == "70"
    assert preset_command("a", 16) == "7f"
    assert preset_command("b", 10) == "99"
    assert expected_keys("2e") == ("PWR",)
    assert expected_keys("21") == ("IN",)
    assert expected_keys("75") == ("PA",)
    assert expected_keys("43") == ("KEY",)
    assert expected_keys("b1") == ()
    with pytest.raises(ValueError):
        encode_command("2e\r\n")
    with pytest.raises(ValueError):
        preset_command("a", 17)


async def test_refresh_populates_state(fake_a16):
    client = _client(fake_a16, refresh_on_connect=True)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.assignments_b)
        s = client.state
        assert s.power == "ON"
        assert s.firmware.serial == "A16HS0000#000000"
        assert s.user_b.name == "Listener 2"
        assert s.user_a.volume == 64
        await _wait_for(lambda: client.state.mode is not None)
        assert client.state.mode == "SVS"
        assert fake_a16.received[:8] == ["2e", "64", "80", "83", "a0", "a3", "37", "af"]
    finally:
        await client.stop()
    assert fake_a16.max_active == 1


async def test_commands_are_serialised(fake_a16):
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        results = await asyncio.gather(
            client.send_command("64"),
            client.send_command("2e"),
            client.send_command("a0"),
        )
        assert results[0]["A16SN"] == "A16HS0000#000000"
        assert results[1]["PWR"] == "ON"
        assert results[2]["BUR"] == "Listener 2"
        assert fake_a16.received == ["64", "2e", "a0"]
    finally:
        await client.stop()


async def test_timeout_when_no_answer(fake_a16):
    fake_a16.ignore.add("64")
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        with pytest.raises(A16TimeoutError):
            await client.send_command("64")
        # The connection is still usable afterwards.
        assert (await client.send_command("2e"))["PWR"] == "ON"
    finally:
        await client.stop()


async def test_not_connected_raises():
    client = A16Client("127.0.0.1", 1)
    with pytest.raises(A16ConnectionError):
        await client.send_command("2e")


async def test_keepalive_miss_triggers_reconnect(fake_a16):
    events = []
    client = _client(fake_a16, keepalive_interval=0.1, response_timeout=0.2)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.silent = True  # like the real silent drop
        await _wait_for(lambda: events.count(False) >= 1)
        fake_a16.silent = False
        await _wait_for(lambda: events.count(True) >= 2)
        assert fake_a16.connections_total >= 2
        assert fake_a16.max_active == 1
        assert fake_a16.rejected == 0
        assert (await client.send_command("2e"))["PWR"] == "ON"
    finally:
        await client.stop()


async def test_single_dropped_keepalive_does_not_reconnect(fake_a16):
    events = []
    client = _client(fake_a16, keepalive_interval=0.1, response_timeout=0.2)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: "2e" in fake_a16.received)
        fake_a16.drop_next["2e"] = 1  # one lost keepalive -> retried
        await asyncio.sleep(0.8)
        assert events == [True]
        assert fake_a16.connections_total == 1
    finally:
        await client.stop()


async def test_two_dropped_keepalives_reconnect(fake_a16):
    events = []
    client = _client(fake_a16, keepalive_interval=0.1, response_timeout=0.2)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: "2e" in fake_a16.received)
        fake_a16.drop_next["2e"] = 2  # keepalive and its retry lost
        await _wait_for(lambda: events.count(True) >= 2)
        assert fake_a16.max_active == 1
    finally:
        await client.stop()


async def test_no_command_before_device_is_ready(fake_a16):
    fake_a16.push_interval = 0.3
    client = _client(fake_a16, refresh_on_connect=True)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.firmware.serial is not None)
        assert fake_a16.ignored_early == []
    finally:
        await client.stop()


async def test_keepalive_keeps_connection(fake_a16):
    events = []
    client = _client(fake_a16, keepalive_interval=0.05, response_timeout=0.3)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: fake_a16.received.count("2e") >= 5)
        assert events == [True]
    finally:
        await client.stop()


async def test_backoff_grows_when_device_unreachable():
    attempts = []

    async def refuse(reader, writer):
        attempts.append(asyncio.get_running_loop().time())
        writer.close()

    server = await asyncio.start_server(refuse, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = A16Client(
        "127.0.0.1", port, backoff_initial=0.05, backoff_max=1, refresh_on_connect=False
    )
    await client.start()
    try:
        await _wait_for(lambda: len(attempts) >= 4, timeout=5)
    finally:
        await client.stop()
        server.close()
        await server.wait_closed()
    gaps = [b - a for a, b in zip(attempts, attempts[1:], strict=False)]
    assert gaps[2] > gaps[0] * 1.5


async def test_start_twice_uses_one_connection(fake_a16):
    client = _client(fake_a16)
    await client.start()
    await client.start()
    try:
        await client.wait_connected(2)
        await asyncio.sleep(0.2)
        assert fake_a16.connections_total == 1
        assert fake_a16.rejected == 0
    finally:
        await client.stop()


async def test_listener_and_pushes(fake_a16):
    changes = []
    client = _client(fake_a16)
    client.add_listener(lambda state, changed: changes.append(changed))
    await client.start()
    try:
        await client.wait_connected(2)
        # Pushes alone (no command) fill user A.
        await _wait_for(lambda: client.state.user_a.preset == 6)
        n = len(changes)
        await asyncio.sleep(0.5)  # identical pushes -> no further callbacks
        assert len(changes) == n
    finally:
        await client.stop()


async def test_set_volume_steps(fake_a16):
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await client.set_volume("a", 67)
        assert client.state.user_a.volume == 67
        assert fake_a16.received.count("30") == 3
        await client.set_volume("b", 10)  # clamped to 27
        assert client.state.user_b.volume == 27
    finally:
        await client.stop()


async def test_convenience_commands(fake_a16):
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await client.select_source("hdmi-1")
        await client.select_preset("a", 6)
        await client.standby()
        assert client.state.power == "STANDBY"
        assert fake_a16.received == ["21", "75", "2d"]
        with pytest.raises(ValueError):
            await client.select_source("VGA")
    finally:
        await client.stop()


async def test_dropped_query_is_retried(fake_a16):
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.drop_next["64"] = 1
        result = await client.send_command("64")
        assert result["A16SN"] == "A16HS0000#000000"
        assert fake_a16.received.count("64") == 2
    finally:
        await client.stop()


async def test_toggle_is_not_retried(fake_a16):
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.drop_next["30"] = 1
        with pytest.raises(A16TimeoutError):
            await client.volume_up("a")
        assert fake_a16.received.count("30") == 1
    finally:
        await client.stop()


def test_idempotent_classification():
    from pya16.protocol import is_idempotent

    for code in ("2e", "2c", "2d", "64", "80", "37", "21", "75", "9f"):
        assert is_idempotent(code), code
    for code in ("30", "31", "32", "1a", "43", "11", "b1", "38"):
        assert not is_idempotent(code), code


async def test_boot_does_not_trigger_reconnect_until_device_resets(fake_a16):
    fake_a16.reset_after_boot = 1.0
    events = []
    client = _client(fake_a16, keepalive_interval=0.1, response_timeout=0.2)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.power_on()
        assert client.state.power == "BOOT"
        await asyncio.sleep(0.8)  # several unanswered keepalives while booting
        assert events == [True]
        # The fake resets the connection after the boot; the client reconnects.
        await _wait_for(lambda: events.count(True) >= 2)
        assert (await client.send_command("2e"))["PWR"] == "ON"
        assert fake_a16.max_active == 1
    finally:
        await client.stop()


async def test_boot_timeout_still_detects_dead_connection(fake_a16):
    fake_a16.reset_after_boot = 3  # device "hangs" longer than boot_timeout
    events = []
    client = _client(
        fake_a16, keepalive_interval=0.1, response_timeout=0.2, boot_timeout=0.5
    )
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.power_on()
        await _wait_for(lambda: False in events, timeout=3)
    finally:
        await client.stop()


async def test_corrupted_info_block_does_not_confirm_volume(fake_a16):
    # After a boot the A16 sends the user A block without "AUR=" (" 1").
    fake_a16.push_packet = (
        b" 1\x00PA=06\x00VA=64\x00AROOM=Room 1\x00ANAME=Subject 1\x00\r"
    )
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset == 6)
        fake_a16.drop_next["30"] = 1
        with pytest.raises(A16TimeoutError):
            await client.volume_up("a")
    finally:
        await client.stop()


async def test_stale_volume_duplicate_does_not_stop_stepping(fake_a16):
    # A late, stale VA= of the previous step must not confirm the next step:
    # the client waits until the volume really changes.
    fake_a16.volume_answer_delay = 0.2
    fake_a16.duplicate_volume_after = 0.1
    client = _client(fake_a16, response_timeout=1.0)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.set_volume("a", 66)  # from 64: two steps
        assert client.state.user_a.volume == 66
        assert fake_a16.received.count("30") == 2
    finally:
        await client.stop()


async def test_step_volume_at_limit_returns_none(fake_a16):
    fake_a16.volume["a"] = 99
    client = _client(fake_a16, response_timeout=0.3)
    await client.start()
    try:
        await client.wait_connected(2)
        await client.send_command("83")
        assert client.state.user_a.volume == 99
        assert await client.step_volume("a", up=True) is None
    finally:
        await client.stop()


async def test_ignored_step_is_sent_again(fake_a16):
    # Real A16: a step that comes too soon is ignored but answered with the
    # unchanged VA=. The client sends it once more.
    client = _client(fake_a16)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.ignore_next_steps = 1
        assert await client.step_volume("a", up=True) == 65
        assert fake_a16.received.count("30") == 2
        assert fake_a16.ignored == ["30"]
    finally:
        await client.stop()


async def test_min_command_interval_avoids_ignored_commands(fake_a16):
    fake_a16.min_interval = 0.15
    client = _client(fake_a16, min_command_interval=0.2)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.set_volume("a", 67)
        await client.toggle_mute("a")
        await client.toggle_mute("a")
        assert client.state.user_a.volume == 67
        assert fake_a16.ignored == []
        assert fake_a16.received.count("30") == 3
    finally:
        await client.stop()


async def test_without_interval_the_fake_ignores_fast_commands(fake_a16):
    # Sanity check of the emulation: no interval -> commands get ignored.
    fake_a16.min_interval = 0.15
    client = _client(fake_a16, min_command_interval=0.0, response_timeout=0.3)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.send_command("2e")
        with pytest.raises(A16TimeoutError):
            await client.send_command("64", retries=0)
        assert "64" in fake_a16.ignored
    finally:
        await client.stop()


async def test_immediate_resets_do_not_flap_connected(fake_a16):
    # Real A16 (~1 min after another client disconnected): accepts TCP and
    # resets it within ~70 ms. That must not be reported as connected.
    fake_a16.reset_first_connections = 2
    events = []
    client = _client(fake_a16)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(3)
        await asyncio.sleep(0.3)
        assert fake_a16.connections_total == 3
        assert events == [True]
    finally:
        await client.stop()


async def test_lost_step_is_detected_by_query_and_sent_again(fake_a16):
    # The step never reached the device: the volume query shows no change,
    # so sending it again is safe.
    client = _client(fake_a16, response_timeout=0.3)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.drop_next["30"] = 1
        assert await client.step_volume("a", up=True) == 65
        sent = [c for c in fake_a16.received if c in ("30", "83")]
        assert sent == ["30", "83", "30"]
    finally:
        await client.stop()


async def test_lost_answer_of_applied_step_is_not_sent_again(fake_a16):
    # The step was applied but its answer got lost: the query shows the new
    # volume, so the step must not be sent a second time.
    client = _client(fake_a16, response_timeout=0.3)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        fake_a16.lose_answer_next["30"] = 1
        assert await client.step_volume("a", up=True) == 65
        assert [c for c in fake_a16.received if c in ("30", "83")] == ["30", "83"]
        assert fake_a16.volume["a"] == 65
    finally:
        await client.stop()


async def test_volume_steps_use_their_own_interval(fake_a16):
    # Other commands may be faster; steps get min_step_interval.
    fake_a16.min_interval = 0.15
    client = _client(fake_a16, min_command_interval=0.0, min_step_interval=0.2)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.set_volume("a", 67)
        assert client.state.user_a.volume == 67
        assert fake_a16.ignored == []
        assert fake_a16.received.count("30") == 3
    finally:
        await client.stop()


async def test_stats_are_counted(fake_a16):
    client = _client(fake_a16, response_timeout=0.3)
    await client.start()
    try:
        await client.wait_connected(2)
        await _wait_for(lambda: client.state.user_a.preset is not None)
        await client.send_command("2e")
        fake_a16.drop_next["30"] = 1
        await client.step_volume("a", up=True)
        await asyncio.sleep(0.05)  # the worker counts after the caller resumes
        stats = client.stats.as_dict()
        assert stats["connects"] == 1
        assert stats["commands_sent"] == 4  # 2e, 30 (lost), 83, 30
        assert stats["timeouts"] == 1
        assert stats["volume_steps_lost"] == 1
        assert stats["response_time_s"]["samples"] == 3
    finally:
        await client.stop()
