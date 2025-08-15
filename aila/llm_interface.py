import os
from enum import StrEnum
from typing import Callable, Literal, TypedDict, overload

import anthropic
import openai
import pydantic

from aila.config import get_config
from aila.llm_models import LlmConfig, ProviderName, get_model_properties


class LlmInterface(pydantic.BaseModel):
    llm_config: LlmConfig
    analyze_fn: Callable[[str], str]

    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )


def init_llm_interface(llm_config: LlmConfig) -> LlmInterface:
    if llm_config.provider_name == ProviderName.OPENAI:
        return create_open_ai_interface(llm_config)
    elif llm_config.provider_name == ProviderName.ANTHROPIC:
        return create_anthropic_interface(llm_config)
    else:
        raise ValueError(f"Unknown provider: {llm_config.provider_name}")


def create_open_ai_interface(llm_config: LlmConfig) -> LlmInterface:
    def analyze(prompt: str) -> str:
        client = openai.OpenAI(api_key=get_config().openai_api_key)
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

    return LlmInterface(analyze_fn=analyze, llm_config=llm_config)


def create_anthropic_interface(llm_config: LlmConfig) -> LlmInterface:
    def analyze(prompt: str) -> str:
        client = anthropic.Anthropic(api_key=get_config().anthropic_api_key)
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

    return LlmInterface(analyze_fn=analyze, llm_config=llm_config)
