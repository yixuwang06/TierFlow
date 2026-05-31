"""Skill system for extensible task execution."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SkillMetadata:
    """Metadata for a skill."""

    name: str  # Skill名称
    description: str  # 技能描述
    category: str  # 分类（如：code, data, web, system）
    version: str = "1.0.0"  # 版本
    author: Optional[str] = None  # 作者
    tags: List[str] = None  # 标签

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class Skill(ABC):
    """Base class for all skills."""

    def __init__(self):
        self.metadata = self.get_metadata()
        logger.info("skill_initialized", name=self.metadata.name)

    @abstractmethod
    def get_metadata(self) -> SkillMetadata:
        """Return skill metadata."""
        pass

    @abstractmethod
    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute the skill.

        Args:
            context: Execution context with workflow state
            **kwargs: Skill-specific parameters

        Returns:
            Dict with:
                - success: bool
                - result: Any
                - error: Optional[str]
                - metadata: Optional[Dict]
        """
        pass

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters. Override if needed."""
        return True

    def get_required_params(self) -> List[str]:
        """Return list of required parameter names."""
        return []

    def get_optional_params(self) -> Dict[str, Any]:
        """Return dict of optional parameters with defaults."""
        return {}


class SkillRegistry:
    """Registry for managing skills."""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.categories: Dict[str, List[str]] = {}

    def register(self, skill: Skill):
        """Register a skill."""
        name = skill.metadata.name
        if name in self.skills:
            logger.warning("skill_already_registered", name=name)
            return

        self.skills[name] = skill

        # Update category index
        category = skill.metadata.category
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(name)

        logger.info(
            "skill_registered",
            name=name,
            category=category,
            version=skill.metadata.version,
        )

    def unregister(self, name: str):
        """Unregister a skill."""
        if name not in self.skills:
            logger.warning("skill_not_found", name=name)
            return

        skill = self.skills[name]
        category = skill.metadata.category

        del self.skills[name]

        if category in self.categories:
            self.categories[category].remove(name)
            if not self.categories[category]:
                del self.categories[category]

        logger.info("skill_unregistered", name=name)

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def list_skills(self, category: Optional[str] = None) -> List[SkillMetadata]:
        """List all skills or skills in a category."""
        if category:
            skill_names = self.categories.get(category, [])
            return [self.skills[name].metadata for name in skill_names]
        else:
            return [skill.metadata for skill in self.skills.values()]

    def list_categories(self) -> List[str]:
        """List all categories."""
        return list(self.categories.keys())

    def execute_skill(
        self, name: str, context: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Execute a skill by name."""
        skill = self.get(name)
        if not skill:
            logger.error("skill_not_found", name=name)
            return {
                "success": False,
                "error": f"Skill '{name}' not found",
            }

        # Validate required parameters
        required = skill.get_required_params()
        missing = [p for p in required if p not in kwargs]
        if missing:
            logger.error("missing_required_params", skill=name, missing=missing)
            return {
                "success": False,
                "error": f"Missing required parameters: {missing}",
            }

        # Validate input
        if not skill.validate_input(**kwargs):
            logger.error("invalid_input", skill=name)
            return {
                "success": False,
                "error": "Invalid input parameters",
            }

        # Execute skill
        try:
            logger.info("executing_skill", name=name, params=list(kwargs.keys()))
            result = skill.execute(context, **kwargs)
            logger.info("skill_executed", name=name, success=result.get("success"))
            return result
        except Exception as e:
            logger.error("skill_execution_failed", name=name, error=str(e))
            return {
                "success": False,
                "error": f"Skill execution failed: {str(e)}",
            }


# Global skill registry
_global_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    return _global_registry


def register_skill(skill: Skill):
    """Register a skill to the global registry."""
    _global_registry.register(skill)


def execute_skill(name: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Execute a skill from the global registry."""
    return _global_registry.execute_skill(name, context, **kwargs)
