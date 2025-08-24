from __future__ import annotations

import atexit
import hashlib
import threading
import time
from types import TracebackType
from typing import Any, Callable, NewType, Type

from pydantic import BaseModel, ConfigDict

from aila.llm_models import ProviderName

Sha256EncodedApiKey = NewType("Sha256EncodedApiKey", str)
ProviderKey = tuple[ProviderName, Sha256EncodedApiKey]


class Entry(BaseModel):
    client: Any
    last_used: float
    created_at: float

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class PoolState(BaseModel):
    entries: dict[ProviderKey, Entry]
    ttl_seconds: int
    max_size: int

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class ClientPool:
    def __init__(self, ttl_seconds: int = 10 * 60, max_size: int = 128) -> None:
        self._lock = threading.Lock()
        self._state = PoolState(entries={}, ttl_seconds=ttl_seconds, max_size=max_size)
        atexit.register(self.shutdown)

    def __enter__(self) -> "ClientPool":
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    def __del__(self) -> None:
        # best-effort only; not guaranteed to run
        try:
            self.shutdown()
        except Exception:
            pass

    def get_client(self, provider: ProviderName, api_key: str, factory: Callable[[str], Any]) -> Any:
        if not api_key:
            raise ValueError("API key must not be empty")
        # Use monotonic time for TTL accounting to avoid wall-clock jumps
        now = time.monotonic()
        to_close: list[Any] = []

        with self._lock:
            exists, key, pool2, keys_to_close = ensure_entry(self._state, provider, api_key, now)
            for k in keys_to_close:
                to_close.append(self._state.entries[k].client)
            self._state = pool2

            if exists:
                self._state = record_use(self._state, key, now)
                client = self._state.entries[key].client
            else:
                client = factory(api_key)
                self._state = insert_entry(self._state, key, client, now)
                self._state, victims, victims_clients = evict_if_needed(self._state)
                to_close.extend(victims_clients)

        # Close victims outside the lock
        for c in to_close:
            if c is not None:
                self._maybe_close(c)

        return client

    def shutdown(self) -> None:
        with self._lock:
            entries = list(self._state.entries.values())
            # Replace state with a fresh, empty snapshot (avoid mutating frozen internals)
            self._state = PoolState(entries={}, ttl_seconds=self._state.ttl_seconds, max_size=self._state.max_size)
        for e in entries:
            self._maybe_close(e.client)

    @staticmethod
    def _maybe_close(obj: Any) -> None:
        closer = getattr(obj, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass


def sha_key(provider: ProviderName, api_key: str) -> ProviderKey:
    return provider, Sha256EncodedApiKey(hashlib.sha256(api_key.encode("utf-8")).hexdigest())


def purge_expired(pool: PoolState, now: float) -> tuple[PoolState, list[ProviderKey]]:
    victims: list[ProviderKey] = []
    for key, entry in pool.entries.items():
        if now - entry.last_used > pool.ttl_seconds:
            victims.append(key)
    if not victims:
        return pool, victims
    new_entries = {k: v for k, v in pool.entries.items() if k not in victims}
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size), victims


def record_use(pool: PoolState, key: ProviderKey, now: float) -> PoolState:
    entry = pool.entries.get(key)
    if entry is None:
        return pool
    new_entry = Entry(client=entry.client, last_used=now, created_at=entry.created_at)
    new_entries = dict(pool.entries)
    new_entries[key] = new_entry
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size)


def insert_entry(pool: PoolState, key: ProviderKey, client: Any, now: float) -> PoolState:
    new_entries = dict(pool.entries)
    new_entries[key] = Entry(client=client, last_used=now, created_at=now)
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size)


def evict_if_needed(pool: PoolState) -> tuple[PoolState, list[ProviderKey], list[Any]]:
    if len(pool.entries) <= pool.max_size:
        return pool, [], []
    # LRU by last_used (ascending)
    ordered = sorted(pool.entries.items(), key=lambda kv: kv[1].last_used)
    to_remove = len(pool.entries) - pool.max_size
    victims = [k for k, _ in ordered[:to_remove]]
    victims_clients: list[Any] = [pool.entries[k].client for k in victims]
    new_entries = {k: v for k, v in pool.entries.items() if k not in victims}
    return (
        PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size),
        victims,
        victims_clients,
    )


def ensure_entry(
    pool: PoolState, provider: ProviderName, api_key: str, now: float
) -> tuple[bool, ProviderKey, PoolState, list[ProviderKey]]:
    key = sha_key(provider, api_key)
    pool2, to_close = purge_expired(pool, now)
    exists = key in pool2.entries
    return exists, key, pool2, to_close
