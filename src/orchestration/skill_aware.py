"""Enhanced orchestrator with skills support."""

import uuid
from typing import Dict, List, Optional

from src.api_clients.factory import ModelClientFactory
from src.config.models import ModelConfigManager, ModelRole
from src.execution import CodexExecutor
from src.orchestration.completion import CompletionEvaluator
from src.skills import execute_skill, get_skill_registry
from src.state import StateManager, TaskStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SkillAwareOrchestrator:
    """Orchestrator with skills support for specialized task execution."""

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

        # 初始化执行器
        self.executor = self._create_executor()

        # 获取skills注册表
        self.skill_registry = get_skill_registry()

        logger.info(
            "skill_aware_orchestrator_initialized",
            available_skills=len(self.skill_registry.skills),
            skill_categories=self.skill_registry.list_categories(),
        )

    def _create_executor(self):
        """Create executor with fallback chain."""
        from src.orchestration.configurable import ConfigurableExecutor

        executor_chain = self.model_config_manager.get_fallback_chain(ModelRole.EXECUTOR)
        return ConfigurableExecutor(
            client_factory=self.client_factory,
            model_chain=executor_chain,
        )

    def _identify_skill(self, task_description: str) -> Optional[str]:
        """Identify if a task can be handled by a skill."""
        # Simple keyword matching for skill identification
        task_lower = task_description.lower()

        if any(kw in task_lower for kw in ["analyze code", "code analysis", "code quality"]):
            return "code_analysis"
        elif any(kw in task_lower for kw in ["process data", "filter data", "transform data"]):
            return "data_processing"
        elif any(kw in task_lower for kw in ["summarize", "summary", "extract key"]):
            return "text_summary"
        elif any(kw in task_lower for kw in ["read file", "write file", "file operation"]):
            return "file_operation"

        return None

    def _execute_with_skill(
        self, skill_name: str, task_description: str, context: Dict
    ) -> Dict:
        """Execute task using a skill."""
        logger.info("executing_with_skill", skill=skill_name, task=task_description)

        # Extract parameters from task description (simplified)
        # In production, use LLM to extract parameters
        params = self._extract_skill_params(task_description, skill_name)

        result = execute_skill(skill_name, context, **params)

        return {
            "success": result.get("success", False),
            "result": result.get("result"),
            "executor": f"skill:{skill_name}",
            "error": result.get("error"),
        }

    def _extract_skill_params(self, task_description: str, skill_name: str) -> Dict:
        """Extract parameters for skill execution from task description."""
        # Simplified parameter extraction
        # In production, use LLM to parse task and extract parameters
        params = {}

        if skill_name == "code_analysis":
            # Example: extract code from task
            if "```" in task_description:
                code_start = task_description.find("```") + 3
                code_end = task_description.find("```", code_start)
                params["code"] = task_description[code_start:code_end].strip()

        elif skill_name == "text_summary":
            # Use the task description itself as text to summarize
            params["text"] = task_description

        return params

    def execute_workflow(
        self, task_description: str, max_iterations: Optional[int] = None
    ) -> dict:
        """Execute workflow with skills support."""
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

                # 尝试使用skill执行
                skill_name = self._identify_skill(subtask)
                if skill_name:
                    result = self._execute_subtask_with_skill(
                        workflow_id, subtask_id, subtask, skill_name
                    )
                else:
                    result = self._execute_subtask(workflow_id, subtask_id, subtask)

                round_results.append(result)
                all_results.append(result)

            # 评估完成度
            evaluation = self._evaluate_completion(original_task, all_results)
            decision = self.completion_evaluator.evaluate(
                evaluation, round_results, iteration
            )

            logger.info(
                "completion_decision",
                workflow_id=workflow_id,
                iteration=iteration,
                should_complete=decision.should_complete,
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
                        },
                    },
                    "models_used": self._get_models_used(),
                    "skills_used": self._get_skills_used(all_results),
                }

            # 更新任务描述
            next_steps = decision.next_steps
            if next_steps:
                task_description = f"{original_task}\n\nNext steps: {', '.join(next_steps)}"
            else:
                task_description = original_task

        logger.warning("workflow_max_iterations", workflow_id=workflow_id)
        self.state_manager.update_workflow_status(workflow_id, TaskStatus.FAILED)

        return {
            "workflow_id": workflow_id,
            "status": "max_iterations_reached",
            "iterations": iteration,
            "results": all_results,
        }

    def _execute_subtask_with_skill(
        self, workflow_id: str, subtask_id: str, subtask: str, skill_name: str
    ) -> dict:
        """Execute subtask using a skill."""
        logger.info("subtask_with_skill", workflow_id=workflow_id, skill=skill_name)

        self.state_manager.update_subtask_status(workflow_id, subtask_id, TaskStatus.EXECUTING)

        context = {"workflow_id": workflow_id, "subtask_id": subtask_id}
        execution_result = self._execute_with_skill(skill_name, subtask, context)

        if execution_result["success"]:
            self.state_manager.update_subtask_status(
                workflow_id,
                subtask_id,
                TaskStatus.COMPLETED,
                result=str(execution_result["result"]),
                executor=execution_result["executor"],
            )

            return {
                "subtask_id": subtask_id,
                "subtask": subtask,
                "result": execution_result["result"],
                "executor": execution_result["executor"],
            }
        else:
            self.state_manager.update_subtask_status(
                workflow_id,
                subtask_id,
                TaskStatus.FAILED,
                error=execution_result.get("error"),
            )

            return {
                "subtask_id": subtask_id,
                "subtask": subtask,
                "error": execution_result.get("error"),
                "status": "failed",
            }

    def _execute_subtask(self, workflow_id: str, subtask_id: str, subtask: str) -> dict:
        """Execute subtask using regular executor."""
        logger.info("subtask_started", workflow_id=workflow_id, subtask_id=subtask_id)

        self.state_manager.update_subtask_status(workflow_id, subtask_id, TaskStatus.EXECUTING)

        execution_result = self.executor.execute_task(subtask)

        if execution_result["success"]:
            result_text = execution_result["result"]
            review = self._review_result(subtask, result_text)

            self.state_manager.update_subtask_status(
                workflow_id,
                subtask_id,
                TaskStatus.COMPLETED,
                result=result_text,
                executor=execution_result["executor"],
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

    def _plan_task(self, task_description: str) -> dict:
        """Plan task using configured planner."""
        if not self.planner_client:
            return {"subtasks": [task_description]}

        system_prompt = """You are a task planning expert. Break down complex tasks into clear, executable subtasks.
Return a JSON structure with:
- subtasks: list of subtask descriptions"""

        prompt = f"""Task to plan: {task_description}

Please decompose this into subtasks."""

        response = self.planner_client.generate(prompt, system=system_prompt, temperature=0.3)

        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"subtasks": [task_description]}

    def _evaluate_completion(self, original_task: str, results: list) -> dict:
        """Evaluate completion."""
        if not self.orchestrator_client:
            return {"complete": False, "score": 0.5}

        system_prompt = """Evaluate task completion. Return JSON with: {complete: bool, score: 0-1}"""

        results_text = "\n".join([f"- {r}" for r in results])
        prompt = f"""Task: {original_task}\n\nResults:\n{results_text}\n\nIs complete?"""

        response = self.orchestrator_client.generate(prompt, system=system_prompt, temperature=0.2)

        import json
        try:
            result = json.loads(response)
            result.setdefault("complete", False)
            result.setdefault("score", 0.5)
            return result
        except json.JSONDecodeError:
            return {"complete": False, "score": 0.5}

    def _review_result(self, task: str, result: str) -> dict:
        """Review result."""
        if not self.reviewer_client:
            return {"score": 0.7}

        system_prompt = """Review the result. Return JSON with: {score: 0-1}"""
        prompt = f"""Task: {task}\n\nResult: {result}\n\nReview:"""

        response = self.reviewer_client.generate(prompt, system=system_prompt, temperature=0.2)

        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"score": 0.7}

    def _get_models_used(self) -> dict:
        """Get models used."""
        return {
            "planner": self.planner_client.model if self.planner_client else None,
            "reviewer": self.reviewer_client.model if self.reviewer_client else None,
            "orchestrator": self.orchestrator_client.model if self.orchestrator_client else None,
            "executor_chain": self.executor.get_model_chain(),
        }

    def _get_skills_used(self, results: List[dict]) -> List[str]:
        """Get list of skills used in execution."""
        skills = set()
        for result in results:
            executor = result.get("executor", "")
            if executor.startswith("skill:"):
                skills.add(executor.replace("skill:", ""))
        return list(skills)

    def list_available_skills(self) -> List[dict]:
        """List all available skills."""
        return [
            {
                "name": meta.name,
                "description": meta.description,
                "category": meta.category,
                "tags": meta.tags,
            }
            for meta in self.skill_registry.list_skills()
        ]

    def close(self):
        """Close all clients."""
        self.client_factory.close_all()
        self.executor.close()
