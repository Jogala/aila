# test_class_oop_two_paths.py
from __future__ import annotations

from typing import Any, Protocol, TypedDict

import pytest


# ---------- Typed shapes ----------
class ChatMessage(TypedDict):
    role: str
    content: str


class ChatCompletionsProto(Protocol):
    def create(self, *, model: str, messages: list[ChatMessage], temperature: float, max_tokens: int) -> Any: ...


class ChatProto(Protocol):
    completions: ChatCompletionsProto


class OpenAIProto(Protocol):
    chat: ChatProto


# ---------- Minimal fakes (typed) ----------
class FakeRecorder(ChatCompletionsProto):
    def __init__(self, content: str = "OK") -> None:
        self.last_kwargs: dict[str, Any] | None = None
        self._content = content

    def create(  # <-- fully typed now
        self, *, model: str, messages: list[ChatMessage], temperature: float, max_tokens: int
    ) -> Any:
        self.last_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # minimal response shape
        return type(
            "Resp", (), {"choices": [type("Choice", (), {"message": type("M", (), {"content": self._content})()})]}
        )


class Chat(ChatProto):
    def __init__(self, completions: ChatCompletionsProto) -> None:
        self.completions: ChatCompletionsProto = completions


class FakeOpenAI(OpenAIProto):
    def __init__(self, content: str = "OK") -> None:
        self.rec = FakeRecorder(content)
        self.chat: ChatProto = Chat(self.rec)


# ---------- “Prod-like” class with hidden dependency ----------
def get_openai_client() -> OpenAIProto:
    """In prod: builds real SDK client; here we raise unless patched."""
    raise RuntimeError("real factory would hit env/network")


class Provider:
    def __init__(self, *, model: str, system_prompt: str, max_tokens: int, temperature: float) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature

    def analyze(self, prompt: str) -> str:
        client = get_openai_client()  # hidden dep
        r = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return r.choices[0].message.content or ""


# ---------- Alternative OOP: subclass with injected client ----------
class TestableProvider(Provider):
    def __init__(self, *, client: OpenAIProto, **kwargs) -> None:
        super().__init__(**kwargs)
        self._client = client

    def analyze(self, prompt: str) -> str:
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return r.choices[0].message.content or ""


# ---------- Tests: two ways to test OOP code ----------
def test_oop_with_monkeypatch_is_brittle(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Monkeypatching works, but is brittle:
    - must know exact import path ('module.symbol') of the hidden factory
    - breaks if symbol moves/renames
    - sidesteps static types at the seam
    """
    fake = FakeOpenAI(content="summary")
    # In a real package you'd patch "package.module.get_openai_client"
    monkeypatch.setattr(__name__, "get_openai_client", lambda: fake)

    p = Provider(model="gpt-4o-mini", system_prompt="Summarize contracts.", max_tokens=512, temperature=0.1)
    out = p.analyze("Summarize this.")
    assert out == "summary"

    k = fake.rec.last_kwargs
    assert k is not None and k["model"] == "gpt-4o-mini" and k["temperature"] == 0.1 and k["max_tokens"] == 512


def test_oop_with_subclass_injection_is_cleaner() -> None:
    """
    Subclass injection avoids monkeypatching (but adds boilerplate and duplication risk).
    """
    fake = FakeOpenAI(content="summary")
    p = TestableProvider(
        client=fake,
        model="gpt-4o-mini",
        system_prompt="Summarize contracts.",
        max_tokens=512,
        temperature=0.1,
    )
    out = p.analyze("Summarize this.")
    assert out == "summary"

    k = fake.rec.last_kwargs
    assert k is not None and k["model"] == "gpt-4o-mini" and k["temperature"] == 0.1 and k["max_tokens"] == 512
