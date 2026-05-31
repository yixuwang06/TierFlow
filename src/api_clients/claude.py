"""Claude Opus API client."""

from typing import Any, Dict, Optional

from anthropic import Anthropic

from src.api_clients.base import BaseAPIClient
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeClient(BaseAPIClient):
    """Claude Opus API client for orchestration."""

    def __init__(self):
        super().__init__(
            api_key=settings.anthropic_api_key,
            rate_limit=settings.claude_rate_limit,
            model=settings.orchestration_model,
        )
        self.anthropic_client = Anthropic(api_key=self.api_key)

    def _execute_request(
        self,
        messages: list,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> Any:
        """Execute Claude API request."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = self.anthropic_client.messages.create(**kwargs)
        return response

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        """Generate response from Claude."""
        messages = [{"role": "user", "content": prompt}]

        response = self._make_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
        )

        return response.content[0].text

    def plan_task(self, task_description: str) -> Dict[str, Any]:
        """Plan and decompose a task into subtasks."""
        system_prompt = """You are a task planning expert. Break down complex tasks into clear, executable subtasks.
Return a JSON structure with:
- subtasks: list of subtask descriptions
- dependencies: list of dependencies between subtasks
- estimated_complexity: overall complexity score (1-10)"""

        prompt = f"""Task to plan: {task_description}

Please decompose this into subtasks with clear dependencies."""

        response = self.generate(prompt, system=system_prompt, temperature=0.3)

        logger.info("task_planned", task=task_description, response_length=len(response))

        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "subtasks": [task_description],
                "dependencies": [],
                "estimated_complexity": 5,
            }

    def review_result(self, task: str, result: str) -> Dict[str, Any]:
        """Review execution result."""
        system_prompt = """You are a code review expert. Evaluate the execution result for:
- correctness
- completeness
- quality
Return JSON with: {score: 0-1, issues: [], suggestions: []}"""

        prompt = f"""Task: {task}

Result: {result}

Please review this result."""

        response = self.generate(prompt, system=system_prompt, temperature=0.2)

        logger.info("result_reviewed", task=task)

        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"score": 0.5, "issues": [], "suggestions": []}

    def evaluate_completion(self, original_task: str, results: list) -> Dict[str, Any]:
        """Evaluate overall task completion with detailed metrics."""
        system_prompt = """Evaluate task completion with multiple dimensions:

Return JSON with:
{
  "complete": bool,
  "score": 0-1 (overall score),
  "correctness_score": 0-1 (how correct the results are),
  "completeness_score": 0-1 (how complete the task is),
  "quality_score": 0-1 (code/output quality),
  "confidence": 0-1 (confidence in this evaluation),
  "next_steps": [list of specific next actions if not complete],
  "issues": [list of remaining issues],
  "achievements": [list of what was accomplished]
}

Be specific in next_steps - provide actionable items, not vague suggestions."""

        results_text = "\n".join([f"- {r}" for r in results])
        prompt = f"""Original task: {original_task}

Completed subtasks:
{results_text}

Evaluate the completion status with detailed metrics."""

        response = self.generate(prompt, system=system_prompt, temperature=0.2)

        logger.info("completion_evaluated", task=original_task)

        import json
        try:
            result = json.loads(response)
            # 确保所有必需字段存在
            result.setdefault("complete", False)
            result.setdefault("score", 0.5)
            result.setdefault("correctness_score", result["score"])
            result.setdefault("completeness_score", result["score"])
            result.setdefault("quality_score", result["score"])
            result.setdefault("confidence", 0.7)
            result.setdefault("next_steps", [])
            result.setdefault("issues", [])
            result.setdefault("achievements", [])
            return result
        except json.JSONDecodeError:
            return {
                "complete": False,
                "score": 0.5,
                "correctness_score": 0.5,
                "completeness_score": 0.5,
                "quality_score": 0.5,
                "confidence": 0.5,
                "next_steps": [],
                "issues": ["Failed to parse evaluation"],
                "achievements": [],
            }
