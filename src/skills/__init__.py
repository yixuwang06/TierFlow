"""Skills system for extensible task execution."""

from src.skills.base import (
    Skill,
    SkillMetadata,
    SkillRegistry,
    execute_skill,
    get_skill_registry,
    register_skill,
)
from src.skills.builtin import (
    CodeAnalysisSkill,
    DataProcessingSkill,
    FileOperationSkill,
    TextSummarySkill,
)

# Register built-in skills
_registry = get_skill_registry()
_registry.register(CodeAnalysisSkill())
_registry.register(DataProcessingSkill())
_registry.register(TextSummarySkill())
_registry.register(FileOperationSkill())

__all__ = [
    "Skill",
    "SkillMetadata",
    "SkillRegistry",
    "get_skill_registry",
    "register_skill",
    "execute_skill",
    "CodeAnalysisSkill",
    "DataProcessingSkill",
    "TextSummarySkill",
    "FileOperationSkill",
]
