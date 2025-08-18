from functools import lru_cache
from typing import Protocol

import anthropic
import openai
import pydantic

from aila.config import get_config
from aila.llm_models import LlmConfig, ProviderName, get_model_properties


# duck typing instead of coupling through abstract class
class LlmInterface(Protocol):
    llm_config: LlmConfig

    def analyze(self, prompt: str) -> str: ...


class LlmInterfaceOpenAi(pydantic.BaseModel):
    llm_config: LlmConfig

    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )

    def analyze(self, prompt: str) -> str:
        client = _get_openai_client(api_key=get_config().openai_api_key)
        llm_properties = get_model_properties(ProviderName.OPENAI, self.llm_config.model)

        messages = [
            {
                "role": "system",
                "content": "You are a legal document analysis expert specializing in contract changes and their implications.",
            },
            {"role": "user", "content": prompt},
        ]
        temperature = 0.1

        if self.llm_config.model == "gpt-5":
            response = client.chat.completions.create(
                model=self.llm_config.model,
                messages=messages,  # type: ignore
                temperature=1,
                max_completion_tokens=llm_properties.output_token_max,
            )
        else:
            response = client.chat.completions.create(
                model=self.llm_config.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=llm_properties.output_token_max,
            )

        content = response.choices[0].message.content
        return content if content is not None else ""


class LlmInterfaceAnthropic(pydantic.BaseModel):
    llm_config: LlmConfig

    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )

    def analyze(self, prompt: str) -> str:
        client = _get_anthropic_client(api_key=get_config().anthropic_api_key)
        llm_properties = get_model_properties(ProviderName.ANTHROPIC, self.llm_config.model)
        response = client.messages.create(
            model=self.llm_config.model,
            max_tokens=llm_properties.output_token_max,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        if not isinstance(response.content[0], anthropic.types.TextBlock):
            raise ValueError(f"Expected TextBlock, got {type(response.content[0])}")

        return response.content[0].text


# very simple to create even LLM Interfaces that are not only provider specific, but also model specifc!
def get_llm_interface(llm_config: LlmConfig) -> LlmInterface:
    if llm_config.provider_name == ProviderName.OPENAI:
        return LlmInterfaceOpenAi(llm_config=llm_config)
    elif llm_config.provider_name == ProviderName.ANTHROPIC:
        return LlmInterfaceAnthropic(llm_config=llm_config)
    else:
        raise ValueError(f"Unknown provider: {llm_config.provider_name}")


@lru_cache()
def _get_openai_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key)


@lru_cache()
def _get_anthropic_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)
