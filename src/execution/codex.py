"""Codex execution layer with failover."""

import time
from typing import Optional

from src.api_clients import DeepSeekClient, GPTClient
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CodexExecutor:
    """Codex execution layer with automatic failover."""

    def __init__(self):
        self.gpt_client = GPTClient()
        self.deepseek_client = DeepSeekClient()
        self.failover_timeout = 30
        self.use_fallback = False

    def execute_task(self, task_description: str, context: Optional[str] = None) -> dict:
        """Execute task with automatic failover."""
        start_time = time.time()

        try:
            if not self.use_fallback:
                result = self._execute_with_primary(task_description, context)
                return {
                    "success": True,
                    "result": result,
                    "executor": "gpt-5.5",
                    "latency": time.time() - start_time,
                }
        except Exception as e:
            logger.warning(
                "primary_executor_failed",
                error=str(e),
                switching_to_fallback=True,
            )
            self.use_fallback = True

        try:
            result = self._execute_with_fallback(task_description, context)
            return {
                "success": True,
                "result": result,
                "executor": "deepseek-v4-pro",
                "latency": time.time() - start_time,
            }
        except Exception as e:
            logger.error(
                "both_executors_failed",
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
                "executor": "none",
                "latency": time.time() - start_time,
            }

    def _execute_with_primary(self, task_description: str, context: Optional[str] = None) -> str:
        """Execute with GPT-5.5."""
        logger.info("executing_with_primary", task=task_description)
        return self.gpt_client.execute_task(task_description, context)

    def _execute_with_fallback(self, task_description: str, context: Optional[str] = None) -> str:
        """Execute with DeepSeek v4 Pro."""
        logger.info("executing_with_fallback", task=task_description)
        return self.deepseek_client.execute_task(task_description, context)

    def reset_failover(self):
        """Reset failover state to try primary again."""
        logger.info("resetting_failover_state")
        self.use_fallback = False

    def close(self):
        """Close all clients."""
        self.gpt_client.close()
        self.deepseek_client.close()

    def get_metrics(self) -> dict:
        """Get executor metrics."""
        return {
            "primary": self.gpt_client.get_metrics(),
            "fallback": self.deepseek_client.get_metrics(),
            "using_fallback": self.use_fallback,
        }
