"""ClaudeCode orchestration layer."""

import uuid
from typing import List, Optional

from src.api_clients import ClaudeClient
from src.execution import CodexExecutor
from src.orchestration.completion import CompletionEvaluator
from src.state import StateManager, TaskStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """ClaudeCode orchestration layer."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        completion_evaluator: Optional[CompletionEvaluator] = None,
    ):
        self.claude_client = ClaudeClient()
        self.codex_executor = CodexExecutor()
        self.state_manager = state_manager or StateManager()
        self.completion_evaluator = completion_evaluator or CompletionEvaluator()

    def execute_workflow(self, task_description: str, max_iterations: Optional[int] = None) -> dict:
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

            plan = self.claude_client.plan_task(task_description)
            subtasks = plan.get("subtasks", [task_description])

            round_results = []
            for idx, subtask in enumerate(subtasks):
                subtask_id = f"{workflow_id}-{iteration}-{idx}"
                self.state_manager.create_subtask(workflow_id, subtask_id, subtask)

                result = self._execute_subtask(workflow_id, subtask_id, subtask)
                round_results.append(result)
                all_results.append(result)

            # 获取Claude的评估
            evaluation = self.claude_client.evaluate_completion(original_task, all_results)

            # 使用增强的完成评估器
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
                }

            # 更新任务描述以包含next_steps
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
        }

    def _execute_subtask(self, workflow_id: str, subtask_id: str, subtask: str) -> dict:
        """Execute a single subtask."""
        logger.info("subtask_started", workflow_id=workflow_id, subtask_id=subtask_id)

        self.state_manager.update_subtask_status(
            workflow_id, subtask_id, TaskStatus.EXECUTING
        )

        execution_result = self.codex_executor.execute_task(subtask)

        if execution_result["success"]:
            result_text = execution_result["result"]
            review = self.claude_client.review_result(subtask, result_text)

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
                workflow_id,
                subtask_id,
                TaskStatus.FAILED,
                error=execution_result.get("error"),
            )

            logger.error(
                "subtask_failed",
                workflow_id=workflow_id,
                subtask_id=subtask_id,
                error=execution_result.get("error"),
            )

            return {
                "subtask_id": subtask_id,
                "subtask": subtask,
                "error": execution_result.get("error"),
                "status": "failed",
            }

    def close(self):
        """Close all clients."""
        self.claude_client.close()
        self.codex_executor.close()

    def get_metrics(self) -> dict:
        """Get orchestrator metrics."""
        return {
            "claude": self.claude_client.get_metrics(),
            "codex": self.codex_executor.get_metrics(),
        }
