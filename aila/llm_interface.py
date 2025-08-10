import os
from enum import StrEnum
from typing import Callable, Literal, TypedDict, overload

import anthropic
import openai
import pydantic
import tiktoken

from aila.config import get_config
from aila.llm_models import LLM_MODELS, LlmConfig, LlmModelProperties, ProviderName, get_model_properties


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
    if llm_config.provider_name != ProviderName.OPENAI:
        raise ValueError("OpenAI interface can only be created for OPENAI provider")

    def analyze(prompt: str) -> str:
        client = get_api_client(ProviderName.OPENAI)
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
    if llm_config.provider_name != ProviderName.ANTHROPIC:
        raise ValueError("Anthropic interface can only be created for ANTHROPIC provider")

    def analyze(prompt: str) -> str:
        client = get_api_client(ProviderName.ANTHROPIC)
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


def get_api_key(provider_name: ProviderName) -> str:
    if provider_name == ProviderName.ANTHROPIC:
        api_key = get_config().anthropic_api_key
        if api_key is None:
            raise ValueError("Please set the ANTHROPIC_API_KEY environment variable")

    elif provider_name == ProviderName.OPENAI:
        api_key = get_config().openai_api_key
        if api_key is None:
            raise ValueError("Please set the OPENAI_API_KEY environment variable")

    else:
        raise ValueError(f"Unknown provider: {provider_name}")
    return api_key


@overload
def get_api_client(provider_name: Literal[ProviderName.OPENAI]) -> openai.OpenAI: ...
@overload
def get_api_client(provider_name: Literal[ProviderName.ANTHROPIC]) -> anthropic.Anthropic: ...


def get_api_client(provider_name: ProviderName) -> openai.OpenAI | anthropic.Anthropic:
    api_key = get_api_key(provider_name)
    if provider_name == ProviderName.ANTHROPIC:
        return anthropic.Anthropic(api_key=api_key)
    if provider_name == ProviderName.OPENAI:
        return openai.OpenAI(api_key=api_key)
    raise ValueError(f"Unknown provider: {provider_name}")


def count_tokens(text: str, model: str) -> int:
    """Count tokens in text for the given model."""
    if model.startswith("claude"):
        # For Claude models, use GPT-4 tokenizer as approximation
        # This is a reasonable approximation since both use similar tokenization approaches
        try:
            enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
            token_count = len(enc.encode(text))
            return token_count
        except Exception as e:
            # Fallback to character-based estimation
            estimated_tokens = len(text) // 4  # Rough estimate: 4 chars per token
            return estimated_tokens
    else:
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception as e:
            # Fallback to character-based estimation
            estimated_tokens = len(text) // 4  # Rough estimate: 4 chars per token
            return estimated_tokens
