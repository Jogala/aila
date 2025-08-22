import atexit
import hashlib
import threading
import time
from typing import Protocol, runtime_checkable, TypedDict, Any, Callable

import anthropic
import openai
import pydantic

from aila.llm_models import LlmConfig, ProviderName, get_model_properties


# Protocol instead of AnalyzeFn = Callable[[str], str], s.t. IDE knows argument names when calling function
@runtime_checkable
class AnalyzeFn(Protocol):
    def __call__(self, prompt: str) -> str: ...


class LlmInterface(pydantic.BaseModel):
    llm_config: LlmConfig
    analyze_fn: AnalyzeFn

    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )


def get_llm_interface(llm_config: LlmConfig) -> LlmInterface:
    if llm_config.provider_name == ProviderName.OPENAI:
        analyzer = _build_openai_analyzer(llm_config)
    elif llm_config.provider_name == ProviderName.ANTHROPIC:
        analyzer = _build_anthropic_analyzer(llm_config)
    else:
        raise ValueError(f"Unknown provider: {llm_config.provider_name}")
    return LlmInterface(analyze_fn=analyzer, llm_config=llm_config)


def _build_openai_analyzer(llm_config: LlmConfig) -> AnalyzeFn:
    def analyze(prompt: str) -> str:
        client = _get_client(ProviderName.OPENAI, api_key=llm_config.api_key)
        llm_properties = get_model_properties(ProviderName.OPENAI, llm_config.model)

        messages = [
            {
                "role": "system",
                "content": "You are a legal document analysis expert specializing in contract changes and their implications.",
            },
            {"role": "user", "content": prompt},
        ]
        temperature = 0.1

        if llm_config.model == "gpt-5":
            response = client.chat.completions.create(
                model=llm_config.model,
                messages=messages,  # type: ignore
                temperature=1,
                max_completion_tokens=llm_properties.output_token_max,
            )
        else:
            response = client.chat.completions.create(
                model=llm_config.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=llm_properties.output_token_max,
            )

        content = response.choices[0].message.content
        return content if content is not None else ""

    return analyze


def _build_anthropic_analyzer(llm_config: LlmConfig) -> AnalyzeFn:
    def analyze(prompt: str) -> str:
        client = _get_client(ProviderName.ANTHROPIC, api_key=llm_config.api_key)
        llm_properties = get_model_properties(ProviderName.ANTHROPIC, llm_config.model)
        response = client.messages.create(
            model=llm_config.model,
            max_tokens=llm_properties.output_token_max,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        if not isinstance(response.content[0], anthropic.types.TextBlock):
            raise ValueError(f"Expected TextBlock, got {type(response.content[0])}")

        return response.content[0].text

    return analyze


# ----- Client pooling with TTL & cleanup -----

class _ClientEntry(TypedDict):
    client: Any
    last_used: float
    created_at: float


_LOCK = threading.Lock()
_POOL: dict[tuple[ProviderName, str], _ClientEntry] = {}

# User-provided keys: short TTL and bounded pool; Server keys: effectively sticky
_USER_CLIENT_TTL_SECONDS = 15 * 60  # 15 minutes
_USER_POOL_MAX_SIZE = 128


def _hash_key(key: str) -> str:
    """Hash API key for use as cache key to avoid storing plaintext in indices."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _make_client(provider: ProviderName, api_key: str) -> Any:
    if provider == ProviderName.OPENAI:
        return openai.OpenAI(api_key=api_key)
    elif provider == ProviderName.ANTHROPIC:
        return anthropic.Anthropic(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _maybe_close(obj: Any) -> None:
    closer: Any = getattr(obj, "close", None)
    if callable(closer):
        try:
            closer()
        except Exception:
            # Best-effort close; ignore errors
            pass


def _evict_if_needed() -> None:
    """Evict least-recently-used clients when pool exceeds max size."""
    entries: list[tuple[tuple[ProviderName, str], _ClientEntry]] = list(_POOL.items())
    if len(entries) <= _USER_POOL_MAX_SIZE:
        return
    # Sort by last_used ascending (LRU)
    entries.sort(key=lambda item: item[1]["last_used"])  # oldest first
    to_remove = len(entries) - _USER_POOL_MAX_SIZE
    for i in range(to_remove):
        key, entry = entries[i]
        _maybe_close(entry["client"])
        _POOL.pop(key, None)


def _purge_expired(now: float | None = None) -> None:
    ts = now or time.time()
    expired_keys: list[tuple[ProviderName, str]] = []
    for key, entry in _POOL.items():
        if ts - entry["last_used"] > _USER_CLIENT_TTL_SECONDS:
            expired_keys.append(key)
    for key in expired_keys:
        entry = _POOL.pop(key, None)
        if entry is not None:
            _maybe_close(entry["client"])


def _get_client(provider: ProviderName, api_key: str) -> Any:
    """
    Get a client with bounded, TTL-based reuse for all keys.
    - Reuse for 15 minutes since last use; evict LRU beyond pool size.
    - API keys are hashed for indexing to avoid storing plaintext in map keys.
    """
    if api_key == "":
        # Should not happen here (API layer already handles fallback), but guard anyway
        raise ValueError("API key must not be empty")

    key_hash = _hash_key(api_key)
    idx = (provider, key_hash)

    now = time.time()
    with _LOCK:
        _purge_expired(now)

        entry = _POOL.get(idx)
        if entry is not None:
            entry["last_used"] = now
            return entry["client"]

        # Create new client, record entry
        client = _make_client(provider, api_key)
        _POOL[idx] = _ClientEntry(client=client, last_used=now, created_at=now)

        _evict_if_needed()

        return client


@atexit.register
def _shutdown_client_pool() -> None:
    with _LOCK:
        for entry in list(_POOL.values()):
            _maybe_close(entry["client"])
        _POOL.clear()
