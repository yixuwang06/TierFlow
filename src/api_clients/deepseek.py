"""DeepSeek API client."""

from typing import Any, Optional

from openai import OpenAI

from src.api_clients.base import BaseAPIClient
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DeepSeekClient(BaseAPIClient):
    """DeepSeek v4 Pro API client for fallback execution."""

    def __init__(self):
        super().__init__(
            api_key=settings.deepseek_api_key,
            rate_limit=settings.deepseek_rate_limit,
            model=settings.fallback_execution_model,
        )
        self.deepseek_client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
        )

    def _execute_request(
        self,
        messages: list,
        max_tokens: int = 8000,
        temperature: float = 0.7,
    ) -> Any:
        """Execute DeepSeek API request."""
        response = self.deepseek_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 8000,
        temperature: float = 0.7,
    ) -> str:
        """Generate response from DeepSeek."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._make_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return response.choices[0].message.content

    def execute_task(self, task_description: str, context: Optional[str] = None) -> str:
        """Execute a specific task."""
        system_prompt = """You are a code execution expert. Execute the given task precisely and return the result."""

        prompt = task_description
        if context:
            prompt = f"Context: {context}\n\nTask: {task_description}"

        result = self.generate(prompt, system=system_prompt, temperature=0.5)

        logger.info("task_executed_fallback", task=task_description, result_length=len(result))

        return result
