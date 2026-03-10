"""
LLM Provider configuration.

Extracted from app.py to provide a typed interface for the 7 supported
LLM providers. All providers use the OpenAI-compatible API format.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Typed configuration for an LLM provider."""

    api_key: str
    base_url: str
    model: str
    provider: str


# Provider-specific env var defaults
_DEFAULTS = {
    "local": {
        "base_url": "http://localhost:8080/v1",
        "model": "phi-3.5-mini",
    },
    "github": {
        "base_url": "https://models.github.ai/inference",
        "model": "gpt-4o-mini",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "azure": {
        "base_url": "",  # Built from endpoint + deployment
        "model": "",  # Uses deployment name
    },
    "azure_ai": {
        "base_url": "https://models.inference.ai.azure.com/v1",
        "model": "gpt-4o-mini",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
    },
}

SUPPORTED_PROVIDERS = list(_DEFAULTS.keys())


def get_llm_config(provider: str | None = None) -> LLMConfig:
    """
    Get LLM configuration for the specified or default provider.

    Args:
        provider: Provider name. If None, reads from LLM_PROVIDER env var.

    Returns:
        LLMConfig with api_key, base_url, model, and provider name.

    Raises:
        ValueError: If provider is unknown or required env vars are missing.
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "local")
    provider = provider.lower()

    if provider == "local":
        base_url = os.getenv("LOCAL_AI_BASE_URL", _DEFAULTS["local"]["base_url"])
        model = os.getenv("LOCAL_AI_MODEL", _DEFAULTS["local"]["model"])
        logger.info(f"Using LocalAI at {base_url} ({model})")
        return LLMConfig(api_key="local", base_url=base_url, model=model, provider=provider)

    if provider == "github":
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            raise ValueError("GITHUB_TOKEN not set. Get one at: https://github.com/settings/tokens")
        model = os.getenv("GITHUB_MODEL", _DEFAULTS["github"]["model"])
        logger.info(f"Using GitHub Models ({model})")
        return LLMConfig(api_key=token, base_url=_DEFAULTS["github"]["base_url"], model=model, provider=provider)

    if provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set. Get one at: https://openrouter.ai/keys")
        model = os.getenv("OPENROUTER_MODEL", _DEFAULTS["openrouter"]["model"])
        logger.info(f"Using OpenRouter ({model})")
        return LLMConfig(api_key=key, base_url=_DEFAULTS["openrouter"]["base_url"], model=model, provider=provider)

    if provider == "azure":
        key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        if not key or not endpoint:
            raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT required")
        base_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        logger.info(f"Using Azure OpenAI ({deployment})")
        return LLMConfig(api_key=key, base_url=base_url, model=deployment, provider=provider)

    if provider == "azure_ai":
        key = os.getenv("AZURE_AI_API_KEY", "")
        if not key:
            raise ValueError("AZURE_AI_API_KEY not set. Get one at: https://ai.azure.com")
        base_url = os.getenv("AZURE_AI_BASE_URL", _DEFAULTS["azure_ai"]["base_url"])
        model = os.getenv("AZURE_AI_MODEL", _DEFAULTS["azure_ai"]["model"])
        logger.info(f"Using Azure AI Inference ({model})")
        return LLMConfig(api_key=key, base_url=base_url, model=model, provider=provider)

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        model = os.getenv("OPENAI_MODEL", _DEFAULTS["openai"]["model"])
        logger.info(f"Using OpenAI ({model})")
        return LLMConfig(api_key=key, base_url=_DEFAULTS["openai"]["base_url"], model=model, provider=provider)

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY not set. Get one at: https://aistudio.google.com/apikey")
        model = os.getenv("GEMINI_MODEL", _DEFAULTS["gemini"]["model"])
        logger.info(f"Using Google Gemini ({model})")
        return LLMConfig(api_key=key, base_url=_DEFAULTS["gemini"]["base_url"], model=model, provider=provider)

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider}. Options: {', '.join(SUPPORTED_PROVIDERS)}"
    )
