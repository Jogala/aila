# LLM Client Pooling: Design Proposal

## Summary
- Replace unbounded `@lru_cache` clients with a bounded, TTL-based client pool for OpenAI and Anthropic clients.
- Treat all API keys the same (no special server-side handling).
- Reuse clients within a time window to reduce connection overhead; evict idle/old entries and close clients to control resources.

## Goals
- Performance: Reuse HTTP clients to avoid repeated TCP/TLS handshakes.
- Security: Avoid indefinite retention of user-provided API keys in memory.
- Resource control: Bound memory/FD usage with TTL and LRU eviction, and close clients on eviction and shutdown.
- Simplicity: No external caches or background daemons; in-process only.

## Current Issues (Pre-Change)
- `@lru_cache()` keeps API keys and clients indefinitely (process lifetime).
- No explicit `close()` on clients; potential accumulation of connection pools/resources.
- Unbounded growth with unique keys; no TTL.

## Proposed Architecture
- Central in-process pool keyed by `(provider, sha256(api_key))` → entry contains `{client, last_used, created_at}`.
- On fetch:
  - Purge expired entries (idle beyond TTL).
  - If present, update `last_used` and return client.
  - Else, create client, insert, then enforce LRU eviction if over capacity.
- Close clients on eviction and on process exit (via `atexit`).
- Synchronize with a single `threading.Lock` (FastAPI is multi-thread capable under uvicorn workers).

## Key Policies
- Uniform handling for all keys (server or user): same TTL and LRU.
- Default TTL: 15 minutes since last use.
- Default max size: 128 entries.
- Constants are module-level to keep changes localized; can be made env-configurable later.

## Data Structures
- `_POOL: dict[tuple[ProviderName, str], _ClientEntry]`
- `_ClientEntry = { client: Any, last_used: float, created_at: float }`
- `_LOCK: threading.Lock()`

## Lifecycle
- Creation: `_make_client(provider, api_key)` returns provider-specific client.
- Access: `_get_client(provider, api_key)` handles purge, fetch, create, LRU.
- Expiry: `_purge_expired()` removes idle entries based on TTL.
- Eviction: `_evict_if_needed()` removes oldest by `last_used` beyond capacity.
- Shutdown: `_shutdown_client_pool()` closes all remaining clients.

## Concurrency
- All mutations wrapped by `_LOCK`.
- Operations are O(n log n) at worst for eviction (sorting up to pool size), but bounded by max size.

## Security Considerations
- API keys are never stored as plaintext in indices; a SHA-256 hash is used.
- Keys still live inside instantiated client objects—as required to authenticate—but are removed from memory when clients are evicted or on shutdown.
- TTL ensures user-provided keys do not persist indefinitely.

## Changes in Code (aila/llm_interface.py)
- Removed `@lru_cache` functions. Added:
  - `_get_client(provider, api_key)`
  - `_make_client(provider, api_key)`
  - `_purge_expired()`, `_evict_if_needed()`, `_maybe_close()`
  - `@atexit` shutdown handler
- `_build_openai_analyzer` and `_build_anthropic_analyzer` now call `_get_client(...)`.

## Configuration (defaults)
- `_USER_CLIENT_TTL_SECONDS = 15 * 60`
- `_USER_POOL_MAX_SIZE = 128`
- Future: make these environment-configurable (e.g., `AILA_LLM_CLIENT_TTL`, `AILA_LLM_POOL_MAX`).

## Alternatives Considered
- Keep `@lru_cache` with `maxsize`: limits entries but lacks TTL; still retains keys indefinitely.
- Per-request client creation: safest but higher latency and CPU due to repeated handshakes.
- Background reaper thread: more timely purging but increases complexity; current on-access purge is simpler and sufficient.
- External cache/store: unnecessary complexity for this use case.

## Edge Cases & Behavior
- Empty API key: rejected with `ValueError` at `_get_client` (API layer already guards).
- Client close semantics: best-effort; if `close()` missing or raises, ignore.
- Multiple workers: pool is per-process; acceptable and typical for uvicorn/gunicorn.

## Observability (Optional Future Work)
- Add debug logging or counters for: creations, cache hits, purges, evictions.
- Expose a lightweight `/debug/clients` endpoint (guarded) for ops inspection.

## Rollout Plan
- Change is internal to `aila/llm_interface.py`; API surface unchanged.
- Validate locally by making repeated calls with the same and different keys.
- Monitor memory and FD counts under load to confirm plateauing behavior.

## Next Steps (Optional)
- Make TTL and max-size configurable via env.
- Add metrics hooks (Prometheus) if running in production.
- Consider sharing HTTP transport if provider SDKs allow injecting an httpx client.
