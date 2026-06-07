"""Enhanced orchestration with model configuration support."""

import uuid
from typing import List, Optional

from src.api_clients.factory import ModelClientFactory
from src.config.models import ModelConfigManager, ModelRole
from src.execution import CodexExecutor
from src.orchestration.completion import CompletionEvaluator
from src.state import StateManager, TaskStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _strip_code_fence(text: str) -> str:
    """Strip a leading/trailing markdown code fence (```json ... ```) if present."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _subtask_to_str(subtask) -> str:
    """Coerce a subtask (string or dict) into a description string."""
    if isinstance(subtask, str):
        return subtask
    if isinstance(subtask, dict):
        for key in ("description", "task", "name", "subtask", "title"):
            if subtask.get(key):
                return str(subtask[key])
        return str(subtask)
    return str(subtask)


class ConfigurableOrchestrator:
    """Orchestrator with flexible model configuration."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        completion_evaluator: Optional[CompletionEvaluator] = None,
        model_config_manager: Optional[ModelConfigManager] = None,
        model_config_path: Optional[str] = None,
    ):
        # 初始化模型配置
        if model_config_path:
            self.model_config_manager = ModelConfigManager(model_config_path)
        else:
            self.model_config_manager = model_config_manager or ModelConfigManager()

        # 初始化客户端工厂
        self.client_factory = ModelClientFactory(self.model_config_manager)

        # 初始化其他组件
        self.state_manager = state_manager or StateManager()
        self.completion_evaluator = completion_evaluator or CompletionEvaluator()

        # 获取各角色的客户端
        self.planner_client = self.client_factory.get_client_for_role(ModelRole.PLANNER)
        self.reviewer_client = self.client_factory.get_client_for_role(ModelRole.REVIEWER)
        self.orchestrator_client = self.client_factory.get_client_for_role(
            ModelRole.ORCHESTRATOR
        )

        # 初始化执行器（带容灾）
        self.executor = self._create_executor()

        logger.info(
            "orchestrator_initialized",
            planner=self.planner_client.model if self.planner_client else None,
            reviewer=self.reviewer_client.model if self.reviewer_client else None,
            orchestrator=self.orchestrator_client.model if self.orchestrator_client else None,
        )

    def _create_executor(self):
        """Create executor with fallback chain."""
        executor_chain = self.model_config_manager.get_fallback_chain(ModelRole.EXECUTOR)

        if not executor_chain:
            raise ValueError("No executor models configured")

        logger.info("executor_chain_configured", models=executor_chain)

        return ConfigurableExecutor(
            client_factory=self.client_factory,
            model_chain=executor_chain,
        )

    def execute_workflow(
        self, task_description: str, max_iterations: Optional[int] = None
    ) -> dict:
        """Execute complete workflow with multi-round iteration."""
        workflow_id = str(uuid.uuid4())
        max_iter = max_iterations or 100

        logger.info("workflow_started", workflow_id=workflow_id, task=task_description)

        self.state_manager.create_workflow(workflow_id, task_description, max_iter)

        iteration = 0
        all_results = []
        original_task = task_description

        while iteration < max_iter:
            iteration += 1
            self.state_manager.increment_iteration(workflow_id)

            logger.info("workflow_iteration", workflow_id=workflow_id, iteration=iteration)

            # 使用planner规划任务
            plan = self._plan_task(task_description)
            subtasks = plan.get("subtasks", [task_description])

            round_results = []
            for idx, subtask in enumerate(subtasks):
                subtask_id = f"{workflow_id}-{iteration}-{idx}"
                self.state_manager.create_subtask(workflow_id, subtask_id, subtask)

                result = self._execute_subtask(workflow_id, subtask_id, subtask)
                round_results.append(result)
                all_results.append(result)

            # 使用orchestrator评估完成度
            evaluation = self._evaluate_completion(original_task, all_results)

            # 使用完成评估器
            decision = self.completion_evaluator.evaluate(
                evaluation, round_results, iteration
            )

            logger.info(
                "completion_decision",
                workflow_id=workflow_id,
                iteration=iteration,
                should_complete=decision.should_complete,
                reason=decision.reason,
                overall_score=decision.metrics.overall_score,
                partial_success=decision.partial_success,
            )

            if decision.should_complete:
                status = "completed" if not decision.partial_success else "partial_success"

                if decision.can_continue:
                    self.state_manager.update_workflow_status(workflow_id, TaskStatus.COMPLETED)
                else:
                    self.state_manager.update_workflow_status(workflow_id, TaskStatus.FAILED)

                return {
                    "workflow_id": workflow_id,
                    "status": status,
                    "iterations": iteration,
                    "results": all_results,
                    "evaluation": evaluation,
                    "decision": {
                        "reason": decision.reason,
                        "metrics": {
                            "overall": decision.metrics.overall_score,
                            "correctness": decision.metrics.correctness_score,
                            "completeness": decision.metrics.completeness_score,
                            "quality": decision.metrics.quality_score,
                            "progress": decision.metrics.progress_score,
                            "confidence": decision.metrics.confidence,
                        },
                        "partial_success": decision.partial_success,
                        "can_continue": decision.can_continue,
                    },
                    "models_used": self._get_models_used(),
                }

            # 更新任务描述
            next_steps = decision.next_steps
            if next_steps:
                task_description = f"{original_task}\n\nNext steps: {', '.join(next_steps)}"
            else:
                task_description = original_task

            # 定期创建检查点
            if iteration % 5 == 0:
                self.state_manager.create_checkpoint(
                    workflow_id,
                    {
                        "iteration": iteration,
                        "results": all_results,
                        "task": task_description,
                        "metrics": {
                            "overall": decision.metrics.overall_score,
                            "correctness": decision.metrics.correctness_score,
                            "completeness": decision.metrics.completeness_score,
                        },
                    },
                )

        logger.warning("workflow_max_iterations", workflow_id=workflow_id, max_iterations=max_iter)
        self.state_manager.update_workflow_status(workflow_id, TaskStatus.FAILED)

        return {
            "workflow_id": workflow_id,
            "status": "max_iterations_reached",
            "iterations": iteration,
            "results": all_results,
            "models_used": self._get_models_used(),
        }

    def _plan_task(self, task_description: str) -> dict:
        """Plan task using configured planner."""
        if not self.planner_client:
            return {"subtasks": [task_description], "dependencies": [], "estimated_complexity": 5}

        system_prompt = """You are a task planning expert. Break down complex tasks into clear, executable subtasks.
Return a JSON structure with:
- subtasks: list of subtask descriptions
- dependencies: list of dependencies between subtasks
- estimated_complexity: overall complexity score (1-10)"""

        prompt = f"""Task to plan: {task_description}

Please decompose this into subtasks with clear dependencies."""

        try:
            response = self.client_factory.generate_for_role(
                ModelRole.PLANNER, prompt, system=system_prompt, temperature=0.3
            )
        except Exception as e:
            logger.error("planning_failed", error=str(e)[:200])
            return {"subtasks": [task_description], "dependencies": [], "estimated_complexity": 5}

        import json
        try:
            plan = json.loads(_strip_code_fence(response))
        except json.JSONDecodeError:
            return {"subtasks": [task_description], "dependencies": [], "estimated_complexity": 5}

        # Reasoning models sometimes return subtasks as dicts ({"id", "description"})
        # instead of plain strings. Normalize to strings so downstream (state DB,
        # executor prompts) gets consistent input.
        raw_subtasks = plan.get("subtasks") or [task_description]
        plan["subtasks"] = [_subtask_to_str(s) for s in raw_subtasks]
        return plan

    def _evaluate_completion(self, original_task: str, results: list) -> dict:
        """Evaluate completion using configured orchestrator."""
        if not self.orchestrator_client:
            return {"complete": False, "score": 0.5, "next_steps": []}

        system_prompt = """Evaluate task completion with multiple dimensions:

Return JSON with:
{
  "complete": bool,
  "score": 0-1 (overall score),
  "correctness_score": 0-1,
  "completeness_score": 0-1,
  "quality_score": 0-1,
  "confidence": 0-1,
  "next_steps": [],
  "issues": [],
  "achievements": []
}"""

        results_text = "\n".join([f"- {r}" for r in results])
        prompt = f"""Original task: {original_task}

Completed subtasks:
{results_text}

Evaluate the completion status with detailed metrics."""

        try:
            response = self.client_factory.generate_for_role(
                ModelRole.ORCHESTRATOR, prompt, system=system_prompt, temperature=0.2
            )
        except Exception as e:
            logger.error("evaluation_failed", error=str(e)[:200])
            return {"complete": False, "score": 0.5, "next_steps": []}

        import json
        try:
            result = json.loads(_strip_code_fence(response))
            result.setdefault("complete", False)
            result.setdefault("score", 0.5)
            result.setdefault("correctness_score", result["score"])
            result.setdefault("completeness_score", result["score"])
            result.setdefault("quality_score", result["score"])
            result.setdefault("confidence", 0.7)
            result.setdefault("next_steps", [])
            return result
        except json.JSONDecodeError:
            return {"complete": False, "score": 0.5, "next_steps": []}

    def _execute_subtask(self, workflow_id: str, subtask_id: str, subtask: str) -> dict:
        """Execute a single subtask."""
        logger.info("subtask_started", workflow_id=workflow_id, subtask_id=subtask_id)

        self.state_manager.update_subtask_status(workflow_id, subtask_id, TaskStatus.EXECUTING)

        execution_result = self.executor.execute_task(subtask)

        if execution_result["success"]:
            result_text = execution_result["result"]

            # 使用reviewer评审
            review = self._review_result(subtask, result_text)

            self.state_manager.update_subtask_status(
                workflow_id,
                subtask_id,
                TaskStatus.COMPLETED,
                result=result_text,
                executor=execution_result["executor"],
            )

            logger.info(
                "subtask_completed",
                workflow_id=workflow_id,
                subtask_id=subtask_id,
                review_score=review.get("score"),
            )

            return {
                "subtask_id": subtask_id,
                "subtask": subtask,
                "result": result_text,
                "review": review,
                "executor": execution_result["executor"],
            }
        else:
            self.state_manager.update_subtask_status(
                workflow_id, subtask_id, TaskStatus.FAILED, error=execution_result.get("error")
            )

            return {
                "subtask_id": subtask_id,
                "subtask": subtask,
                "error": execution_result.get("error"),
                "status": "failed",
            }

    def _review_result(self, task: str, result: str) -> dict:
        """Review result using configured reviewer."""
        if not self.reviewer_client:
            return {"score": 0.7, "issues": [], "suggestions": []}

        system_prompt = """You are a code review expert. Evaluate the execution result for:
- correctness
- completeness
- quality
Return JSON with: {score: 0-1, issues: [], suggestions: []}"""

        prompt = f"""Task: {task}

Result: {result}

Please review this result."""

        try:
            response = self.client_factory.generate_for_role(
                ModelRole.REVIEWER, prompt, system=system_prompt, temperature=0.2
            )
        except Exception as e:
            logger.error("review_failed", error=str(e)[:200])
            return {"score": 0.7, "issues": [], "suggestions": []}

        import json
        try:
            return json.loads(_strip_code_fence(response))
        except json.JSONDecodeError:
            return {"score": 0.7, "issues": [], "suggestions": []}

    def _get_models_used(self) -> dict:
        """Get information about models used."""
        return {
            "planner": self.planner_client.model if self.planner_client else None,
            "reviewer": self.reviewer_client.model if self.reviewer_client else None,
            "orchestrator": self.orchestrator_client.model if self.orchestrator_client else None,
            "executor_chain": self.executor.get_model_chain(),
        }

    def close(self):
        """Close all clients."""
        self.client_factory.close_all()
        self.executor.close()

    def get_metrics(self) -> dict:
        """Get orchestrator metrics."""
        return {
            "planner": self.planner_client.get_metrics() if self.planner_client else {},
            "reviewer": self.reviewer_client.get_metrics() if self.reviewer_client else {},
            "orchestrator": self.orchestrator_client.get_metrics()
            if self.orchestrator_client
            else {},
            "executor": self.executor.get_metrics(),
        }


class ConfigurableExecutor:
    """Executor with configurable model fallback chain."""

    def __init__(self, client_factory: ModelClientFactory, model_chain: List[str]):
        self.client_factory = client_factory
        self.model_chain = model_chain
        self.current_model_index = 0
        self.failed_models = set()

    def execute_task(self, task_description: str, context: Optional[str] = None) -> dict:
        """Execute task with automatic fallback through model chain."""
        import time

        start_time = time.time()

        for attempt, model_name in enumerate(self.model_chain):
            if model_name in self.failed_models:
                continue

            try:
                client = self.client_factory.get_client_by_name(model_name)
                if not client:
                    continue

                system_prompt = """You are a code execution expert. Execute the given task precisely and return the result."""

                prompt = task_description
                if context:
                    prompt = f"Context: {context}\n\nTask: {task_description}"

                result = client.generate(prompt, system=system_prompt, temperature=0.5)

                logger.info("task_executed", model=model_name, attempt=attempt + 1)

                return {
                    "success": True,
                    "result": result,
                    "executor": model_name,
                    "latency": time.time() - start_time,
                    "attempt": attempt + 1,
                }

            except Exception as e:
                logger.warning("executor_failed", model=model_name, error=str(e))
                self.failed_models.add(model_name)
                continue

        logger.error("all_executors_failed", chain=self.model_chain)
        return {
            "success": False,
            "error": "All executor models failed",
            "executor": "none",
            "latency": time.time() - start_time,
        }

    def get_model_chain(self) -> List[str]:
        """Get the executor model chain."""
        return self.model_chain

    def reset_failures(self):
        """Reset failed models to retry them."""
        self.failed_models.clear()

    def close(self):
        """Close executor."""
        pass

    def get_metrics(self) -> dict:
        """Get executor metrics."""
        return {
            "model_chain": self.model_chain,
            "failed_models": list(self.failed_models),
            "available_models": [m for m in self.model_chain if m not in self.failed_models],
        }
