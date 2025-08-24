from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable

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
        with maybe_closing(openai.OpenAI(api_key=llm_config.api_key)) as client:
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
                    messages=messages,
                    temperature=1,
                    max_completion_tokens=llm_properties.output_token_max,
                )
            else:
                response = client.chat.completions.create(
                    model=llm_config.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=llm_properties.output_token_max,
                )

        content = response.choices[0].message.content
        return content if content is not None else ""

    return analyze


def _build_anthropic_analyzer(llm_config: LlmConfig) -> AnalyzeFn:
    def analyze(prompt: str) -> str:
        with maybe_closing(anthropic.Anthropic(api_key=llm_config.api_key)) as client:
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


@contextmanager
def maybe_closing(obj: Any):
    """
    Context manager that calls obj.close() on exit if the method exists.

    - If obj has a close() method: it gets called (ensuring cleanup).
    - If no close(): it silently does nothing (safe fallback).
    """
    try:
        yield obj
    finally:
        closer = getattr(obj, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass
