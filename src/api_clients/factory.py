"""Enhanced API client factory with model configuration support."""

import os
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI

from src.api_clients.base import BaseAPIClient
from src.config.models import ModelConfig, ModelConfigManager, ModelProvider, ModelRole
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UniversalAPIClient(BaseAPIClient):
    """Universal API client that works with any configured model."""

    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config

        # 获取API密钥
        api_key = os.getenv(model_config.api_key_env, "EMPTY")

        super().__init__(
            api_key=api_key,
            rate_limit=model_config.permissions.rate_limit or 60,
            model=model_config.name,
        )

        # 初始化对应的客户端
        if model_config.provider == ModelProvider.ANTHROPIC:
            anthropic_kwargs = {"api_key": api_key}
            if model_config.base_url:
                anthropic_kwargs["base_url"] = model_config.base_url
            self.client = Anthropic(**anthropic_kwargs)
            self.provider_type = "anthropic"
        elif model_config.provider in (ModelProvider.OPENAI, ModelProvider.CUSTOM):
            base_url = model_config.base_url
            self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            self.provider_type = "openai"
        elif model_config.provider == ModelProvider.DEEPSEEK:
            base_url = model_config.base_url or "https://api.deepseek.com"
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.provider_type = "openai"
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

    def _execute_request(self, messages: list, max_tokens: int = 4000, temperature: float = 0.7, system: Optional[str] = None):
        """Execute API request based on provider."""
        # 应用权限限制
        if self.model_config.permissions.max_tokens:
            max_tokens = min(max_tokens, self.model_config.permissions.max_tokens)

        if self.provider_type == "anthropic":
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system:
                kwargs["system"] = system
            return self.client.messages.create(**kwargs)
        else:  # openai-compatible
            if system:
                messages = [{"role": "system", "content": system}] + messages
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 4000, temperature: float = 0.7) -> str:
        """Generate response."""
        messages = [{"role": "user", "content": prompt}]

        response = self._make_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
        )

        if self.provider_type == "anthropic":
            return response.content[0].text
        else:
            message = response.choices[0].message
            content = message.content
            if content:
                return content
            # Reasoning models (e.g. qwen3.6-reasoner) may return content=null
            # with the answer in reasoning_content, especially when output is
            # truncated by max_tokens. Fall back to reasoning_content.
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning:
                logger.warning(
                    "empty_content_using_reasoning",
                    model=self.model,
                    finish_reason=response.choices[0].finish_reason,
                )
                return reasoning
            logger.error(
                "empty_response",
                model=self.model,
                finish_reason=response.choices[0].finish_reason,
            )
            return ""


class ModelClientFactory:
    """Factory for creating API clients based on model configuration."""

    def __init__(self, model_config_manager: Optional[ModelConfigManager] = None):
        self.model_config_manager = model_config_manager or ModelConfigManager()
        self._client_cache = {}

    def get_client_for_role(
        self, role: ModelRole, exclude: Optional[list] = None
    ) -> Optional[UniversalAPIClient]:
        """Get API client for a specific role with fallback support."""
        model_config = self.model_config_manager.get_model_for_role(role, exclude)

        if not model_config:
            logger.error("no_model_available", role=role)
            return None

        # 检查缓存
        cache_key = model_config.name
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        # 创建新客户端
        try:
            client = UniversalAPIClient(model_config)
            self._client_cache[cache_key] = client
            logger.info(
                "client_created",
                role=role,
                model=model_config.name,
                provider=model_config.provider,
            )
            return client
        except Exception as e:
            logger.error(
                "client_creation_failed",
                role=role,
                model=model_config.name,
                error=str(e),
            )
            return None

    def get_client_by_name(self, model_name: str) -> Optional[UniversalAPIClient]:
        """Get API client by model name."""
        if model_name in self._client_cache:
            return self._client_cache[model_name]

        model_config = self.model_config_manager.models.get(model_name)
        if not model_config:
            logger.error("model_not_found", model=model_name)
            return None

        try:
            client = UniversalAPIClient(model_config)
            self._client_cache[model_name] = client
            return client
        except Exception as e:
            logger.error("client_creation_failed", model=model_name, error=str(e))
            return None

    def generate_for_role(
        self,
        role: ModelRole,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response for a role, walking its fallback chain at call time.

        Unlike resolving a single client at init, this retries the next model in
        the role's chain when the upstream returns errors (e.g. the proxy's 503
        "model temporarily unavailable"), giving every role real disaster recovery.
        """
        chain = self.model_config_manager.get_fallback_chain(role)
        if not chain:
            raise RuntimeError(f"No models configured for role {role}")

        last_error: Optional[Exception] = None
        for model_name in chain:
            client = self.get_client_by_name(model_name)
            if not client:
                continue
            try:
                return client.generate(
                    prompt, system=system, max_tokens=max_tokens, temperature=temperature
                )
            except Exception as e:
                last_error = e
                logger.warning("role_model_failed", role=role, model=model_name, error=str(e)[:200])
                continue

        logger.error("all_role_models_failed", role=role, chain=chain)
        raise last_error or RuntimeError(f"All models failed for role {role}")

    def close_all(self):
        """Close all cached clients."""
        for client in self._client_cache.values():
            client.close()
        self._client_cache.clear()
        logger.info("all_clients_closed")
