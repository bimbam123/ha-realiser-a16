"""Persistent asyncio client for the Realiser A16 IP command server.

Design (see CLAUDE.md):
- exactly one TCP connection, owned by a single connection loop task
  (the A16 serves only one client at a time)
- commands are serialised through a queue; each waits for its response keys
- pushes and command responses go through the same parser/state path
- keepalive 2e every 20 s; no PWR= within 3 s -> connection is dead ->
  reconnect with exponential backoff
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .parser import Packet, StreamParser
from .protocol import (
    CMD_POWER_ON,
    CMD_POWER_STATUS,
    CMD_STANDBY,
    DEFAULT_PORT,
    INFO_QUERY,
    IR_KEYS,
    MUTE_TOGGLE,
    REFRESH_COMMANDS,
    SOURCES,
    VOLUME_DOWN,
    VOLUME_MAX,
    VOLUME_MIN,
    VOLUME_QUERY,
    VOLUME_UP,
    User,
    encode_command,
    expected_keys,
    is_idempotent,
    normalize_code,
    preset_command,
)
from .state import A16State

_LOGGER = logging.getLogger(__name__)

StateListener = Callable[[A16State, set[str]], None]
ConnectionListener = Callable[[bool], None]

_DEFAULT = object()
_INFO_BLOCK_KEYS = frozenset({"AUR", "BUR"})


class A16Error(Exception):
    """Base error."""


class A16ConnectionError(A16Error):
    """Not connected, or the connection was lost."""


class A16TimeoutError(A16Error):
    """The A16 did not answer a command in time."""


class _ConnectionLost(Exception):
    """Internal: ends the current connection."""


@dataclass(slots=True)
class _Request:
    code: str
    expect: frozenset[str]
    timeout: float
    future: asyncio.Future[dict[str, str | None]]


@dataclass(slots=True)
class _Waiter:
    expect: frozenset[str]
    future: asyncio.Future[dict[str, str | None]]
    collected: dict[str, str | None] = field(default_factory=dict)


class A16Client:
    """Client for one Realiser A16."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        keepalive_interval: float = 20.0,
        response_timeout: float = 3.0,
        connect_timeout: float = 5.0,
        command_gap: float = 0.05,
        unknown_response_wait: float = 0.3,
        backoff_initial: float = 1.0,
        backoff_max: float = 60.0,
        refresh_on_connect: bool = True,
        keepalive_retries: int = 1,
        ready_timeout: float = 3.0,
        command_retries: int = 1,
    ) -> None:
        self.command_retries = command_retries
        self.host = host
        self.port = port
        self.keepalive_interval = keepalive_interval
        self.keepalive_retries = keepalive_retries
        self.ready_timeout = ready_timeout
        self.response_timeout = response_timeout
        self.connect_timeout = connect_timeout
        self.command_gap = command_gap
        self.unknown_response_wait = unknown_response_wait
        self.backoff_initial = backoff_initial
        self.backoff_max = backoff_max
        self.refresh_on_connect = refresh_on_connect

        self.state = A16State()
        self._listeners: list[StateListener] = []
        self._conn_listeners: list[ConnectionListener] = []
        self._run_task: asyncio.Task | None = None
        self._queue: asyncio.Queue[_Request] | None = None
        self._waiter: _Waiter | None = None
        self._connected = asyncio.Event()
        self._stopping = False

    # --- public API ------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def start(self) -> None:
        """Start the connection loop (idempotent; never opens a 2nd socket)."""
        if self._run_task is None or self._run_task.done():
            self._stopping = False
            self._run_task = asyncio.create_task(
                self._run(), name=f"a16-{self.host}:{self.port}"
            )

    async def wait_connected(self, timeout: float | None = None) -> None:
        """Wait until connected. Raises A16ConnectionError on timeout."""
        try:
            async with asyncio.timeout(timeout):
                await self._connected.wait()
        except TimeoutError as err:
            raise A16ConnectionError(
                f"Could not connect to {self.host}:{self.port}"
            ) from err

    async def stop(self) -> None:
        """Close the connection and stop reconnecting."""
        self._stopping = True
        if self._run_task is not None:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task
            self._run_task = None

    def add_listener(self, listener: StateListener) -> Callable[[], None]:
        """Call ``listener(state, changed_paths)`` on every state change."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def add_connection_listener(
        self, listener: ConnectionListener
    ) -> Callable[[], None]:
        """Call ``listener(connected)`` when the connection comes up or goes down."""
        self._conn_listeners.append(listener)
        return lambda: self._conn_listeners.remove(listener)

    async def send_command(
        self,
        code: str,
        *,
        expect: Iterable[str] | None | object = _DEFAULT,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> dict[str, str | None]:
        """Queue a command and wait for its response.

        Returns the fields with an expected key received after sending
        (empty for commands without known response). Raises
        A16ConnectionError when not connected and A16TimeoutError when the
        answer does not arrive within ``timeout`` (default response_timeout).

        The A16 occasionally drops a command, so idempotent commands
        (queries, power, source, preset) are retried ``retries`` times
        (default ``command_retries``). Toggles and steps are never retried
        automatically, since a late answer would make them apply twice.
        """
        code = normalize_code(code)
        keys = expected_keys(code) if expect is _DEFAULT else (expect or ())
        if retries is None:
            retries = self.command_retries if is_idempotent(code) else 0
        for attempt in range(retries + 1):
            try:
                return await self._send_once(code, keys, timeout)
            except A16TimeoutError:
                if attempt == retries:
                    raise
                _LOGGER.debug("No answer to %s, retrying", code)
        raise AssertionError("unreachable")

    async def _send_once(
        self, code: str, keys: Iterable[str], timeout: float | None
    ) -> dict[str, str | None]:
        if self._queue is None or not self.connected:
            raise A16ConnectionError("Not connected to the A16")
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put(
            _Request(
                code,
                frozenset(keys),
                self.response_timeout if timeout is None else timeout,
                future,
            )
        )
        return await future

    async def refresh(self) -> None:
        """Query everything the state model covers. Timeouts are logged only."""
        for code in REFRESH_COMMANDS:
            try:
                await self.send_command(code)
            except A16TimeoutError:
                _LOGGER.debug("No answer to refresh command %s", code)

    async def power_on(self) -> None:
        await self.send_command(CMD_POWER_ON)

    async def standby(self) -> None:
        await self.send_command(CMD_STANDBY)

    async def select_source(self, source: str) -> None:
        for name, code in SOURCES.items():
            if name.lower() == source.lower():
                await self.send_command(code)
                return
        raise ValueError(f"Unknown source {source!r}; valid: {', '.join(SOURCES)}")

    async def select_preset(self, user: User, preset: int) -> None:
        await self.send_command(preset_command(user, preset))

    async def volume_up(self, user: User) -> None:
        await self.send_command(VOLUME_UP[user])

    async def volume_down(self, user: User) -> None:
        await self.send_command(VOLUME_DOWN[user])

    async def toggle_mute(self, user: User) -> None:
        await self.send_command(MUTE_TOGGLE[user])

    async def set_mute(self, user: User, muted: bool) -> None:
        if self.state.user(user).muted is not muted:
            await self.toggle_mute(user)

    async def set_volume(self, user: User, target: int) -> None:
        """Step the volume to ``target`` (27-99) with vol+/vol- commands.

        The protocol has no absolute volume command. Stops early if a step
        does not change the reported volume.
        """
        target = max(VOLUME_MIN, min(VOLUME_MAX, target))
        us = self.state.user(user)
        if us.volume is None:
            await self.send_command(VOLUME_QUERY[user])
        if us.volume is None:
            raise A16Error("Current volume unknown")
        for _ in range(VOLUME_MAX - VOLUME_MIN + 1):
            current = us.volume
            if current == target:
                return
            await (self.volume_up if target > current else self.volume_down)(user)
            if us.volume == current:
                _LOGGER.warning(
                    "Volume %s did not change, stopping at %s", user, current
                )
                return

    async def press_key(self, key: str) -> None:
        """Send an IR remote key by name (see protocol.IR_KEYS)."""
        try:
            code = IR_KEYS[key.lower()]
        except KeyError:
            raise ValueError(f"Unknown key {key!r}") from None
        await self.send_command(code)

    async def query_user_info(self, user: User) -> None:
        await self.send_command(INFO_QUERY[user])

    # --- connection loop -------------------------------------------------------

    async def _run(self) -> None:
        backoff = self.backoff_initial
        while not self._stopping:
            healthy = False
            try:
                healthy = await self._connection()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep reconnecting whatever happens
                _LOGGER.exception("Unexpected error in A16 connection")
            if self._stopping:
                break
            if healthy:
                backoff = self.backoff_initial
            _LOGGER.debug("Reconnecting to %s in %.1f s", self.host, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.backoff_max)

    async def _connection(self) -> bool:
        """Run one connection until it fails. Returns True if it was healthy."""
        try:
            async with asyncio.timeout(self.connect_timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port)
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("Connect to %s:%s failed: %r", self.host, self.port, err)
            return False

        parser = StreamParser()
        healthy = asyncio.Event()
        self._queue = asyncio.Queue()
        self._set_connected(True)
        tasks = [
            asyncio.create_task(self._reader(reader, parser, healthy)),
            asyncio.create_task(self._worker(writer, healthy)),
            asyncio.create_task(self._keepalive()),
        ]
        refresh_task = (
            asyncio.create_task(self.refresh()) if self.refresh_on_connect else None
        )
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if (exc := task.exception()) is not None:
                    _LOGGER.debug("A16 connection ended: %r", exc)
        finally:
            for task in [*tasks, *([refresh_task] if refresh_task else [])]:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if refresh_task:
                await asyncio.gather(refresh_task, return_exceptions=True)
            self._fail_pending(A16ConnectionError("Connection to the A16 lost"))
            self._queue = None
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            self._set_connected(False)
        return healthy.is_set()

    async def _reader(
        self, reader: asyncio.StreamReader, parser: StreamParser, healthy: asyncio.Event
    ) -> None:
        while True:
            try:
                data = await reader.read(4096)
            except OSError as err:
                raise _ConnectionLost(repr(err)) from err
            if not data:
                raise _ConnectionLost("EOF")
            for packet in parser.feed(data):
                healthy.set()
                self._handle_packet(packet)

    async def _worker(self, writer: asyncio.StreamWriter, ready: asyncio.Event) -> None:
        assert self._queue is not None
        # The A16 ignores commands sent right after connecting; its first push
        # (~1.6 s after connect) shows it is ready. Proceed anyway after
        # ready_timeout (e.g. if it does not push in standby).
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(self.ready_timeout):
                await ready.wait()
        while True:
            req = await self._queue.get()
            if req.future.done():  # caller gave up
                continue
            waiter = _Waiter(req.expect, req.future) if req.expect else None
            self._waiter = waiter
            try:
                writer.write(encode_command(req.code))
                await writer.drain()
            except OSError as err:
                self._waiter = None
                if not req.future.done():
                    req.future.set_exception(A16ConnectionError(repr(err)))
                raise _ConnectionLost(repr(err)) from err
            _LOGGER.debug("Sent %s", req.code)
            if waiter is None:
                await asyncio.sleep(self.unknown_response_wait)
                if not req.future.done():
                    req.future.set_result({})
            else:
                try:
                    async with asyncio.timeout(req.timeout):
                        await asyncio.shield(req.future)
                except TimeoutError:
                    if not req.future.done():
                        req.future.set_exception(
                            A16TimeoutError(f"No answer to command {req.code}")
                        )
                except Exception:  # noqa: BLE001 - result/exception goes to caller
                    pass
                finally:
                    self._waiter = None
            await asyncio.sleep(self.command_gap)

    async def _keepalive(self) -> None:
        # The A16 occasionally drops a single command on a healthy connection
        # (1 of 18 in a 6 min test), so one miss is retried immediately.
        while True:
            await asyncio.sleep(self.keepalive_interval)
            for attempt in range(self.keepalive_retries + 1):
                try:
                    await self.send_command(
                        CMD_POWER_STATUS,
                        expect=("PWR",),
                        timeout=self.response_timeout,
                        retries=0,  # retried by the loop below
                    )
                    break
                except A16TimeoutError as err:
                    if attempt == self.keepalive_retries:
                        raise _ConnectionLost("Keepalive not answered") from err
                    _LOGGER.debug("Keepalive not answered, retrying")

    # --- packet handling -------------------------------------------------------

    def _handle_packet(self, packet: Packet) -> None:
        waiter = self._waiter
        keys = {f.key for f in packet}
        # The A16 pushes the full user info block (AUR.../BUR...) about once a
        # second. It also contains VA/PA/IN, so it must not confirm e.g. a
        # dropped volume step; it only counts for the info queries themselves.
        is_info_block = bool(keys & _INFO_BLOCK_KEYS)
        if (
            waiter is not None
            and not waiter.future.done()
            and (not is_info_block or waiter.expect & _INFO_BLOCK_KEYS)
        ):
            for f in packet:
                if f.key in waiter.expect:
                    waiter.collected[f.key] = f.value
            if waiter.collected:
                # Keep the rest of this packet too (e.g. all 64 fields).
                for f in packet:
                    waiter.collected.setdefault(f.key, f.value)
                waiter.future.set_result(waiter.collected)

        changed = self.state.apply_packet(packet)
        if changed:
            for listener in list(self._listeners):
                try:
                    listener(self.state, changed)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Error in A16 state listener")

    def _set_connected(self, connected: bool) -> None:
        if connected == self.connected:
            return
        if connected:
            self._connected.set()
        else:
            self._connected.clear()
        _LOGGER.info(
            "%s A16 at %s:%s",
            "Connected to" if connected else "Lost",
            self.host,
            self.port,
        )
        for listener in list(self._conn_listeners):
            try:
                listener(connected)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in A16 connection listener")

    def _fail_pending(self, exc: Exception) -> None:
        if self._waiter is not None and not self._waiter.future.done():
            self._waiter.future.set_exception(exc)
        self._waiter = None
        if self._queue is not None:
            while not self._queue.empty():
                req = self._queue.get_nowait()
                if not req.future.done():
                    req.future.set_exception(exc)
