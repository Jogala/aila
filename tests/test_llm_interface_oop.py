# test_class_oop_two_paths.py
from __future__ import annotations

from typing import Any

import pytest


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


class FakeOpenAI:
    def __init__(self, content: str = "OK") -> None:
        self.rec = FakeRecorder(content)
        self.chat = type("Chat", (), {"completions": self.rec})()


# ---- “Prod-like” class with a hidden dependency (factory) ----
def get_openai_client():
    # In prod this would use env/config; here it deliberately raises.
    raise RuntimeError("real factory would hit env/network")


class Provider:
    def __init__(self, *, model: str, system_prompt: str, max_tokens: int, temperature: float) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature

    def analyze(self, prompt: str) -> str:
        client = get_openai_client()  # <- hidden dep
        r = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return r.choices[0].message.content or ""


# ---- Alternative OOP: subclass that injects the client (no patching) ----
class TestableProvider(Provider):
    def __init__(self, *, client: FakeOpenAI, **kwargs) -> None:
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


# ---- Tests: two ways to test OOP code ----


def test_oop_with_monkeypatch_is_brittle(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Monkeypatching works, but is brittle:
    - must know exact import path ('module.symbol') of the hidden factory
    - breaks silently if the symbol moves/renames
    - sidesteps type checks; easy to inject wrong shape at runtime
    """
    fake = FakeOpenAI(content="summary")
    # If this file were in a real module, you'd patch "package.module.get_openai_client"
    monkeypatch.setattr(__name__, "get_openai_client", lambda: fake)

    p = Provider(model="gpt-4o-mini", system_prompt="Summarize contracts.", max_tokens=512, temperature=0.1)
    out = p.analyze("Summarize this.")
    assert out == "summary"

    k = fake.rec.last_kwargs
    assert k is not None and k["model"] == "gpt-4o-mini" and k["temperature"] == 0.1 and k["max_tokens"] == 512


def test_oop_with_subclass_injection_is_cleaner() -> None:
    """
    Subclass injection avoids monkeypatching:
    - no global state patching or import-path juggling
    - still OOP, but requires a dedicated test subclass (extra boilerplate)
    - risk of logic drift if overridden method diverges from production
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
