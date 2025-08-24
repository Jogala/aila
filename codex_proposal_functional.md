# Functional Client Pooling: Design Proposal

## Summary
- Reframe the client cache as a functional core with an imperative shell.
- Maintain a pool of LLM clients (OpenAI/Anthropic) using TTL + LRU, but encode the state as a value and evolve it via pure functions.
- Side effects (client creation/close, locking, and updating shared state) are handled at the application edge.

## Goals
- Performance: Reuse HTTP clients to reduce connection setup overhead.
- Security: Avoid indefinite retention of user API keys and clients in memory.
- Resource control: Enforce TTL + LRU, close clients on eviction, and bound growth.
- Testability: Pure functions for state transitions enable straightforward unit tests.

## Architecture (Functional Core / Imperative Shell)
- Pool state is an immutable value passed into pure functions and returned updated.
- Pure functions compute: expirations, evictions, and whether to create/return a client.
- Imperative shell performs the effects: construct/close SDK clients, synchronize with a lock, and store new state.

## Data Structures
- `ProviderKey = tuple[ProviderName, str]  # (provider, sha256(api_key))`
- `Entry = { client: Any, last_used: float, created_at: float }`
- `PoolState = { entries: dict[ProviderKey, Entry], ttl_seconds: int, max_size: int }`

## Pure Operations (No Side Effects)
- `purge_expired(pool: PoolState, now: float) -> tuple[PoolState, list[ProviderKey]]`
  - Removes entries idle beyond `ttl_seconds`; returns new pool and keys to close.
- `record_use(pool: PoolState, key: ProviderKey, now: float) -> PoolState`
  - Updates `last_used` for an existing entry.
- `insert_entry(pool: PoolState, key: ProviderKey, client: Any, now: float) -> PoolState`
  - Adds new entry (with timestamps). Client object is treated as opaque data here.
- `evict_if_needed(pool: PoolState) -> tuple[PoolState, list[ProviderKey]]`
  - If `len(entries) > max_size`, evicts least-recently-used entries.
- `ensure_entry(pool: PoolState, provider: ProviderName, api_key: str, now: float) -> tuple[bool, ProviderKey, PoolState, list[ProviderKey]]`
  - Computes whether an entry exists; if not, indicates that a client must be created.
  - Returns `(exists, key, updated_pool, keys_to_close)`.

## Impure Integration (Application Edge)
- Hold `PoolState` in app state (e.g., `app.state.llm_pool`) and protect with a `threading.Lock`.
- On each request:
  1. Acquire lock; `pool1, to_close1 = purge_expired(pool, now)`.
  2. `exists, key, pool2, to_close2 = ensure_entry(pool1, provider, api_key, now)`.
  3. If `exists`: `pool3 = record_use(pool2, key, now)`, `client = pool3.entries[key].client`.
  4. If not: release lock temporarily, create client (side effect), re-acquire lock, `pool3 = insert_entry(pool2, key, client, now)`.
  5. `pool4, to_close3 = evict_if_needed(pool3)`; set app state to `pool4`.
  6. Close clients for `to_close = to_close1 + to_close2 + to_close3` outside the lock (best-effort `close()`).
- On shutdown: iterate current entries and close clients.

## Concurrency
- Single process: one lock around read-modify-write of `PoolState`.
- Multi-worker (uvicorn/gunicorn): one pool per process, acceptable for our use case.

## Security Considerations
- Use `sha256(api_key)` as index; do not store plaintext keys as map keys.
- TTL ensures keys/clients do not persist indefinitely.
- Closing clients releases connection pools and related resources.

## Configuration
- Defaults: `ttl_seconds = 15 * 60`, `max_size = 128`.
- Optional: bind to env vars (e.g., `AILA_LLM_CLIENT_TTL`, `AILA_LLM_POOL_MAX`).

## Example Sketch (Types Simplified)
```python
@dataclass(frozen=True)
class PoolState:
    entries: dict[ProviderKey, Entry]
    ttl_seconds: int = 900
    max_size: int = 128

def sha_key(provider: ProviderName, api_key: str) -> ProviderKey:
    return provider, hashlib.sha256(api_key.encode()).hexdigest()

def purge_expired(pool: PoolState, now: float) -> tuple[PoolState, list[ProviderKey]]:
    to_close = [k for k, e in pool.entries.items() if now - e.last_used > pool.ttl_seconds]
    new_entries = {k: v for k, v in pool.entries.items() if k not in to_close}
    return replace(pool, entries=new_entries), to_close

def ensure_entry(pool: PoolState, provider: ProviderName, api_key: str, now: float) -> tuple[bool, ProviderKey, PoolState, list[ProviderKey]]:
    key = sha_key(provider, api_key)
    if key in pool.entries:
        return True, key, pool, []
    return False, key, pool, []

def record_use(pool: PoolState, key: ProviderKey, now: float) -> PoolState:
    e = pool.entries[key]
    e.last_used = now
    return pool  # or rebuild entry if using frozen structures

def insert_entry(pool: PoolState, key: ProviderKey, client: Any, now: float) -> PoolState:
    pool.entries[key] = Entry(client=client, last_used=now, created_at=now)
    return pool

def evict_if_needed(pool: PoolState) -> tuple[PoolState, list[ProviderKey]]:
    if len(pool.entries) <= pool.max_size:
        return pool, []
    # LRU by last_used
    ordered = sorted(pool.entries.items(), key=lambda kv: kv[1].last_used)
    to_remove = len(pool.entries) - pool.max_size
    victims = [k for k, _ in ordered[:to_remove]]
    for k in victims:
        del pool.entries[k]
    return pool, victims
```

Note: In real code, use persistent/frozen structures or rebuild dicts for pure immutability, or accept pragmatic in-place mutation inside a locked critical section while keeping functional API boundaries.

## Migration from Current Implementation
- Keep current external API (`get_llm_interface`) unchanged.
- Internally, create a small module (`client_pool.py`) that implements the above pure functions and an imperative wrapper.
- Replace direct `_get_client(...)` calls with a wrapper that interacts with the functional pool.

## Alternatives Considered
- Keep module-level mutable pool (current solution): simpler wiring, fewer allocations; less “functional”.
- Use `functools.lru_cache`: lacks TTL and eviction callbacks; retains secrets longer; not suitable.
- Background reaper: can be added later if time-based eviction must occur without access.

## Rollout
- Implement `client_pool.py` with unit tests for pure functions (purge/evict/ensure).
- Integrate into `llm_interface.py` via a thin wrapper guarding lock/side-effects.
- Validate under load; monitor memory/FD usage to confirm bounded behavior.
