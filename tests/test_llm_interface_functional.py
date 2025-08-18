from __future__ import annotations

from typing import Any, Callable, Protocol


# ---- Minimal SUT (functional + DI) ----
class AnalyzeFn(Protocol):
    def __call__(self, prompt: str) -> str: ...


def build_openai_analyzer(
    *, client: Any, model: str, system_prompt: str, max_tokens: int, temperature: float
) -> AnalyzeFn:
    def analyze(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    return analyze


# ---- Decorators (show advantage: easy composition with functions) ----
def with_retry(fn: AnalyzeFn, attempts: int = 3) -> AnalyzeFn:
    def wrapped(prompt: str) -> str:
        last_err: Exception | None = None
        for _ in range(attempts):
            try:
                return fn(prompt)
            except TimeoutError as e:
                last_err = e
                continue
        raise RuntimeError("unrecoverable") from last_err

    return wrapped


def with_logging(fn: AnalyzeFn, sink: list[str]) -> AnalyzeFn:
    def wrapped(prompt: str) -> str:
        sink.append(f"calling with: {prompt[:20]}")
        return fn(prompt)

    return wrapped


# ---- Minimal fakes (shared) ----
class FakeRecorder:
    def __init__(self, content: str = "OK") -> None:
        self.last_kwargs: dict[str, Any] | None = None
        self._content = content

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return type(
            "Resp", (), {"choices": [type("Choice", (), {"message": type("M", (), {"content": self._content})()})]}
        )


class Chat:
    def __init__(self, completions: FakeRecorder) -> None:
        self.completions = completions  # mutable attribute


class FakeOpenAI:
    def __init__(self, content: str = "OK") -> None:
        self.rec = FakeRecorder(content)
        self.chat = Chat(self.rec)


# ---- Tests: clean “paths” with functional DI ----
def test_functional_with_direct_injection_is_trivial() -> None:
    """No monkeypatching, no subclasses: inject the fake client directly."""
    client = FakeOpenAI(content="summary")
    analyze = build_openai_analyzer(
        client=client,
        model="gpt-4o-mini",
        system_prompt="Summarize contracts.",
        max_tokens=512,
        temperature=0.1,
    )
    out = analyze("Summarize this.")
    assert out == "summary"

    k = client.rec.last_kwargs
    assert k is not None
    assert k["model"] == "gpt-4o-mini"
    assert k["temperature"] == 0.1
    assert k["max_tokens"] == 512
    assert k["messages"][0]["role"] == "system"


def test_functional_with_retry_and_logging_composition() -> None:
    """Showcase advantage: add retry+logging as simple decorators over AnalyzeFn."""
    attempts = {"n": 0}
    logs: list[str] = []

    class FlakyRecorder(FakeRecorder):
        def create(self, **kwargs):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise TimeoutError("boom")
            return super().create(**kwargs)

    client = FakeOpenAI(content="recovered")
    client.rec = FlakyRecorder("recovered")
    client.chat = Chat(client.rec)  # replace whole chat object

    base = build_openai_analyzer(
        client=client,
        model="gpt-4o-mini",
        system_prompt="sys",
        max_tokens=64,
        temperature=0.0,
    )

    analyze: AnalyzeFn = with_logging(with_retry(base), logs)
    assert analyze("x") == "recovered"  # recovered after one retry
    assert attempts["n"] == 2  # one failure + one success
    assert any("calling with:" in m for m in logs)
