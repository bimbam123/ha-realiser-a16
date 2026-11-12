"""Tests for A16Client against the fake A16 server."""

import asyncio

import pytest

from pya16 import A16Client, A16ConnectionError, A16TimeoutError
from pya16.protocol import encode_command, expected_keys, preset_command


def _client(server, **kw) -> A16Client:
    opts = {
        "keepalive_interval": 60,
        "response_timeout": 0.5,
        "connect_timeout": 1,
        "backoff_initial": 0.05,
        "backoff_max": 0.4,
        "command_gap": 0.0,
        "unknown_response_wait": 0.05,
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
        assert fake_a16.received[:7] == ["2e", "64", "80", "83", "a0", "a3", "37"]
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


async def test_keepalive_keeps_connection(fake_a16):
    events = []
    client = _client(fake_a16, keepalive_interval=0.05, response_timeout=0.3)
    client.add_connection_listener(events.append)
    await client.start()
    try:
        await client.wait_connected(2)
        await asyncio.sleep(0.6)
        assert fake_a16.received.count("2e") >= 5
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
