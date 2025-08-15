from enum import StrEnum
from typing import List

import tiktoken
from pydantic import BaseModel, ConfigDict, Field


class ProviderName(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LlmModelProperties(BaseModel):
    """Properties and limits for a specific LLM model."""

    provider_name: ProviderName = Field(..., description="The provider of the model")
    model: str = Field(..., description="The model identifier/name")
    context_token_max: int = Field(..., gt=0, description="Maximum context/input tokens")
    output_token_max: int = Field(..., gt=0, description="Maximum output/generation tokens")

    model_config = ConfigDict(frozen=True)


class LlmConfig(BaseModel):
    provider_name: ProviderName
    model: str
    temperature: float

    model_config = ConfigDict(frozen=True)


default_llm_config = LlmConfig(
    provider_name=ProviderName.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
    temperature=0.1,
)


LLM_MODELS: List[LlmModelProperties] = [
    # Anthropic Models
    LlmModelProperties(
        provider_name=ProviderName.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        context_token_max=200_000,
        output_token_max=8_192,
    ),
    LlmModelProperties(
        provider_name=ProviderName.ANTHROPIC,
        model="claude-3-5-haiku-20241022",
        context_token_max=200_000,
        output_token_max=8_192,
    ),
    LlmModelProperties(
        provider_name=ProviderName.ANTHROPIC,
        model="claude-3-opus-20240229",
        context_token_max=200_000,
        output_token_max=4_096,
    ),
    LlmModelProperties(
        provider_name=ProviderName.ANTHROPIC,
        model="claude-3-sonnet-20240229",
        context_token_max=200_000,
        output_token_max=4_096,
    ),
    LlmModelProperties(
        provider_name=ProviderName.ANTHROPIC,
        model="claude-3-haiku-20240307",
        context_token_max=200_000,
        output_token_max=4_096,
    ),
    # OpenAI Models
    LlmModelProperties(
        provider_name=ProviderName.OPENAI,
        model="gpt-4-turbo-preview",
        context_token_max=128_000,
        output_token_max=4_096,
    ),
    LlmModelProperties(
        provider_name=ProviderName.OPENAI,
        model="gpt-4o",
        context_token_max=128_000,
        output_token_max=16_384,
    ),
    LlmModelProperties(
        provider_name=ProviderName.OPENAI,
        model="gpt-4o-mini",
        context_token_max=128_000,
        output_token_max=16_000,
    ),
    LlmModelProperties(
        provider_name=ProviderName.OPENAI,
        model="gpt-5",
        context_token_max=400_000,
        output_token_max=128_000,
    ),
]


def get_model_properties(provider_name: ProviderName, model: str) -> LlmModelProperties:
    """
    Get the properties for a specific model and provider.

    Args:
        provider_name: The LLM provider (openai, anthropic)
        model: The model identifier

    Returns:
        LlmModelProperties for the specified model

    Raises:
        ValueError: If the model/provider combination is not found
    """
    for model_props in LLM_MODELS:
        if model_props.provider_name == provider_name and model_props.model == model:
            return model_props

    raise ValueError(
        f"Model '{model}' not found for provider '{provider_name}'. "
        f"Available models: {[f'{m.provider_name}/{m.model}' for m in LLM_MODELS]}"
    )


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
