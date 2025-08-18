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
        self.completions = completions  # plain attribute (mutable)


class FakeOpenAI:
    def __init__(self, content: str = "OK") -> None:
        self.rec = FakeRecorder(content)
        self.chat = Chat(self.rec)


# ---- Tests: two clean “paths” with functional DI ----
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
