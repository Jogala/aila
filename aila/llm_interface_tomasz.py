import os
from enum import StrEnum
from typing import Callable, Literal, TypedDict, overload

import anthropic
import openai
import pydantic
import tiktoken

from aila.config import get_config
from aila.llm_models import LLM_MODELS, LlmConfig, LlmModelProperties, ProviderName, properties_dict


def init_llm_interface(llm_config: LlmConfig):  # Joachim: NO RETURN TYPE!!!!
    if llm_config.provider_name == ProviderName.OPENAI:
        return OpenAIProvider(config=llm_config)
    elif llm_config.provider_name == ProviderName.ANTHROPIC:
        return AnthropicProvider(config=llm_config)
    else:
        raise ValueError(f"Unknown provider: {llm_config.provider_name}")


class BaseProvider:  # Joachim: <---- no types used! Better use pydantic or dataclass. leads to errors later
    def __init__(self, config):
        self.config = config
        self.properties = properties_dict[config.model]  # Joachim: <--- use @property decorator?

    # Joachim: The analyze function is missing! You must create an abstract BaseClass! Otherwise the whole thing makes no sense.


class OpenAIProvider(BaseProvider):
    def analyze(self, prompt: str) -> str:
        api_key = get_config().anthropic_api_key
        client = openai.OpenAI(api_key=api_key)

        messages = [
            {
                "role": "system",
                "content": "You are a legal document analysis expert specializing in contract changes and their implications.",
            },
            {"role": "user", "content": prompt},
        ]
        temperature = 0.1

        if self.config.model == "gpt-5":
            response = client.chat.completions.create(
                model=self.model,  # Joachim: <---- self.model is not defined! (no pyright/mypy)
                messages=messages,  # type: ignore
                temperature=1,
                max_completion_tokens=self.llm_properties.output_token_max,
            )
        else:
            response = client.chat.completions.create(
                model=self.model,  # Joachim: <---- self.model is not defined! (no pyright/mypy)
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=self.config.output_token_max,
            )

        content = response.choices[0].message.content
        return content if content is not None else ""

    def count_tokens(self, text):
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


class AnthropicProvider(BaseProvider):
    def analyze(self, prompt: str) -> str:
        api_key = get_config().openai_api_key
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=self.config.model,
            max_tokens=self.properties.output_token_max,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        if not isinstance(response.content[0], anthropic.types.TextBlock):
            raise ValueError(f"Expected TextBlock, got {type(response.content[0])}")

        return response.content[0].text

    def count_tokens(self, text):
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception as e:
            # Fallback to character-based estimation
            estimated_tokens = len(text) // 4  # Rough estimate: 4 chars per token
            return estimated_tokens
