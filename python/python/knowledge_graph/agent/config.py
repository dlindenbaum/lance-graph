"""Configuration for the graph review agent with LiteLLM router."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for a single LLM model."""

    model_name: str = Field(..., description="LiteLLM model identifier")
    litellm_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to LiteLLM (api_key, api_base, etc.)",
    )
    model_info: Dict[str, Any] = Field(
        default_factory=dict, description="Model metadata (cost, context window, etc.)"
    )


class RouterConfig(BaseModel):
    """Configuration for LiteLLM router with multiple models."""

    models: List[ModelConfig] = Field(
        default_factory=list, description="List of models for routing"
    )
    routing_strategy: str = Field(
        default="usage-based-routing",
        description="Strategy: simple-shuffle, least-busy, usage-based-routing, latency-based-routing",
    )
    fallbacks: List[Dict[str, Any]] = Field(
        default_factory=list, description="Fallback configurations"
    )
    retry_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "num_retries": 2,
            "timeout": 30,
            "retry_after": 5,
        },
        description="Retry configuration",
    )
    cooldown_time: int = Field(
        default=60, description="Cooldown time for failed models (seconds)"
    )

    @classmethod
    def from_env(cls) -> "RouterConfig":
        """Create router config from environment variables."""
        models = []
        fallbacks = []

        # Primary model (OpenAI GPT-4o-mini by default)
        if os.getenv("OPENAI_API_KEY"):
            models.append(
                ModelConfig(
                    model_name="gpt-4o-mini",
                    litellm_params={
                        "api_key": os.getenv("OPENAI_API_KEY"),
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                    model_info={
                        "mode": "chat",
                        "supports_function_calling": True,
                    },
                )
            )

        # Google Gemini fallback
        if os.getenv("GEMINI_API_KEY"):
            models.append(
                ModelConfig(
                    model_name="gemini/gemini-1.5-flash",
                    litellm_params={
                        "api_key": os.getenv("GEMINI_API_KEY"),
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                    model_info={
                        "mode": "chat",
                        "supports_function_calling": True,
                    },
                )
            )

        # Anthropic Claude fallback
        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(
                ModelConfig(
                    model_name="claude-3-5-sonnet-20241022",
                    litellm_params={
                        "api_key": os.getenv("ANTHROPIC_API_KEY"),
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                    model_info={
                        "mode": "chat",
                        "supports_function_calling": True,
                    },
                )
            )

        # Azure OpenAI
        if os.getenv("AZURE_API_KEY"):
            models.append(
                ModelConfig(
                    model_name="azure/gpt-4o-mini",
                    litellm_params={
                        "api_key": os.getenv("AZURE_API_KEY"),
                        "api_base": os.getenv("AZURE_API_BASE"),
                        "api_version": os.getenv("AZURE_API_VERSION", "2024-02-01"),
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                    model_info={
                        "mode": "chat",
                        "supports_function_calling": True,
                    },
                )
            )

        # Set up fallback chain if multiple models available
        if len(models) > 1:
            for i in range(len(models) - 1):
                fallbacks.append({models[i].model_name: [models[i + 1].model_name]})

        return cls(
            models=models,
            fallbacks=fallbacks,
            routing_strategy=os.getenv(
                "LITELLM_ROUTING_STRATEGY", "usage-based-routing"
            ),
        )

    @classmethod
    def default(cls) -> "RouterConfig":
        """Create a default configuration with common models."""
        return cls(
            models=[
                ModelConfig(
                    model_name="gpt-4o-mini",
                    litellm_params={
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                ),
                ModelConfig(
                    model_name="gemini/gemini-1.5-flash",
                    litellm_params={
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                ),
            ],
            fallbacks=[{"gpt-4o-mini": ["gemini/gemini-1.5-flash"]}],
        )


class AgentConfig(BaseModel):
    """Complete agent configuration."""

    router: RouterConfig = Field(default_factory=RouterConfig.from_env)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)
    enable_caching: bool = Field(
        default=True, description="Enable LiteLLM caching"
    )
    log_level: str = Field(default="INFO", description="Logging level")

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create agent config from environment variables."""
        return cls(
            router=RouterConfig.from_env(),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "2000")),
            enable_caching=os.getenv("AGENT_ENABLE_CACHING", "true").lower()
            == "true",
            log_level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
        )
