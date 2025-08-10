# %%
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class AppConfig(BaseModel):
    """Application configuration using Pydantic"""

    prompt_templates_dir: Path
    data_dir: Path
    results_dir: Path
    log_llm_responses: bool
    path_logging_llm_responses: Path
    openai_api_key: str | None
    anthropic_api_key: str | None

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )


_config_instance: AppConfig | None = None


def get_config() -> AppConfig:
    """
    Get the singleton config instance
    Either use the default config or load from environment variables.
    """

    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig(
            prompt_templates_dir=Path(os.getenv("AILA_PROMPT_TEMPLATES_DIR", "prompt_templates")),
            data_dir=Path(os.getenv("AILA_DATA_DIR", "data")),
            results_dir=Path(os.getenv("AILA_RESULTS_DIR", "results")),
            log_llm_responses=os.getenv("AILA_LOG_LLM_RESPONSE", "true").lower() == "true",
            path_logging_llm_responses=Path(os.getenv("AILA_PATH_LOGGING_LLM_RESPONSES", "logs/llm_responses.log")),
            openai_api_key=os.getenv("AILA_OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("AILA_ANTHROPIC_API_KEY"),
        )
    return _config_instance


def set_config(config: AppConfig) -> None:
    """
    Set the singleton config instance.
    This is useful for testing or overriding the default configuration.
    """
    global _config_instance
    _config_instance = config
