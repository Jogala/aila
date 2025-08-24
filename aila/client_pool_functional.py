from __future__ import annotations

import atexit
import hashlib
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, NewType

from pydantic import BaseModel, ConfigDict

from aila.llm_models import ProviderName

Sha256EncodedApiKey = NewType("Sha256EncodedApiKey", str)
ProviderKey = tuple[ProviderName, Sha256EncodedApiKey]


# ---------------------------
# Frozen Pydantic data models
# ---------------------------
class Entry(BaseModel):
    client: Any
    last_used: float
    created_at: float  # monotonic creation time
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class PoolState(BaseModel):
    entries: dict[ProviderKey, Entry]
    ttl_seconds: float
    max_size: int
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


# ---------------------------
# Pure state-transition helpers
# ---------------------------
def sha_key(provider: ProviderName, api_key: str) -> ProviderKey:
    return provider, Sha256EncodedApiKey(hashlib.sha256(api_key.encode("utf-8")).hexdigest())


def purge_expired(pool: PoolState, now: float) -> tuple[PoolState, list[ProviderKey]]:
    victims: list[ProviderKey] = [k for k, e in pool.entries.items() if now - e.last_used > pool.ttl_seconds]
    if not victims:
        return pool, []
    new_entries = {k: v for k, v in pool.entries.items() if k not in victims}
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size), victims


def record_use(pool: PoolState, key: ProviderKey, now: float) -> PoolState:
    e = pool.entries.get(key)
    if e is None:
        return pool
    new_entries = dict(pool.entries)
    new_entries[key] = Entry(client=e.client, last_used=now, created_at=e.created_at)
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size)


def insert_entry(pool: PoolState, key: ProviderKey, client: Any, now: float) -> PoolState:
    new_entries = dict(pool.entries)
    new_entries[key] = Entry(client=client, last_used=now, created_at=now)
    return PoolState(entries=new_entries, ttl_seconds=pool.ttl_seconds, max_size=pool.max_size)


def evict_if_needed(pool: PoolState) -> tuple[PoolState, list[ProviderKey], list[Any]]:
    if len(pool.entries) <= pool.max_size:
        return pool, [], []
    ordered = sorted(pool.entries.items(), key=lambda kv: kv[1].last_used)  # LRU ascending
    to_remove = len(pool.entries) - pool.max_size
    victims = [k for k, _ in ordered[:to_remove]]
    victims_clients = [pool.entries[k].client for k in victims]
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
    pool2, expired = purge_expired(pool, now)
    return key in pool2.entries, key, pool2, expired


# -------------------------------------
# Functional, closure-based context mgr
# -------------------------------------


@contextmanager
def client_pool(*, ttl_seconds: float = 600.0, max_size: int = 128):
    lock = threading.Lock()
    state = PoolState(entries={}, ttl_seconds=ttl_seconds, max_size=max_size)
    closed = False

    def _maybe_close(obj: Any) -> None:
        closer = getattr(obj, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass

    def shutdown() -> None:
        nonlocal state, closed
        if closed:
            return
        closed = True
        with lock:
            entries = list(state.entries.values())
            state = PoolState(entries={}, ttl_seconds=state.ttl_seconds, max_size=state.max_size)
        for e in entries:
            _maybe_close(e.client)

    # Safety net if user forgets the `with` block
    atexit.register(shutdown)

    def get_client(provider: ProviderName, api_key: str, factory: Callable[[str], Any]) -> Any:
        if not api_key:
            raise ValueError("API key must not be empty")
        now = time.monotonic()
        to_close: list[Any] = []
        nonlocal state
        with lock:
            exists, key, s2, expired = ensure_entry(state, provider, api_key, now)
            # collect expired clients from the old state before swapping
            to_close.extend(state.entries[k].client for k in expired)
            state = s2
            if exists:
                state = record_use(state, key, now)
                client = state.entries[key].client
            else:
                client = factory(api_key)
                state = insert_entry(state, key, client, now)
                state, _, victims_clients = evict_if_needed(state)
                to_close.extend(victims_clients)
        # close outside the lock
        for c in to_close:
            if c is not None:
                _maybe_close(c)
        return client

    try:
        yield get_client
    finally:
        shutdown()


# -----------------
# Tiny usage example
# -----------------
if __name__ == "__main__":

    class MockClient:
        def __init__(self, key: str) -> None:
            self.tag = key[-4:]

        def close(self) -> None:
            print(f"closed ...{self.tag}")

    def factory(api_key: str) -> Any:
        return MockClient(api_key)

    with client_pool(ttl_seconds=5, max_size=2) as get_client:
        c1 = get_client(ProviderName.OPENAI, "sk-AAA111", factory)  # create
        c2 = get_client(ProviderName.OPENAI, "sk-AAA111", factory)  # reuse
        c3 = get_client(ProviderName.OPENAI, "sk-BBB222", factory)  # create; may trigger LRU when capped
# <- automatic shutdown closes remaining clients
