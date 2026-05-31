"""Built-in skills for common tasks."""

from typing import Any, Dict

from src.skills.base import Skill, SkillMetadata


class CodeAnalysisSkill(Skill):
    """Analyze code quality and structure."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_analysis",
            description="Analyze code quality, complexity, and structure",
            category="code",
            tags=["analysis", "quality", "metrics"],
        )

    def get_required_params(self):
        return ["code"]

    def get_optional_params(self):
        return {
            "language": "python",
            "metrics": ["complexity", "lines", "functions"],
        }

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Analyze code."""
        code = kwargs.get("code")
        language = kwargs.get("language", "python")

        # Simple analysis
        lines = code.split("\n")
        line_count = len(lines)
        non_empty_lines = len([l for l in lines if l.strip()])

        # Count functions/classes (simple heuristic)
        functions = len([l for l in lines if "def " in l])
        classes = len([l for l in lines if "class " in l])

        return {
            "success": True,
            "result": {
                "language": language,
                "total_lines": line_count,
                "non_empty_lines": non_empty_lines,
                "functions": functions,
                "classes": classes,
                "avg_line_length": sum(len(l) for l in lines) / max(line_count, 1),
            },
        }


class DataProcessingSkill(Skill):
    """Process and transform data."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="data_processing",
            description="Process, filter, and transform data",
            category="data",
            tags=["processing", "transformation", "filtering"],
        )

    def get_required_params(self):
        return ["data", "operation"]

    def get_optional_params(self):
        return {
            "operation": "filter",  # filter, map, reduce, sort
            "condition": None,
        }

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process data."""
        data = kwargs.get("data")
        operation = kwargs.get("operation")

        if not isinstance(data, list):
            return {
                "success": False,
                "error": "Data must be a list",
            }

        try:
            if operation == "filter":
                # Simple filtering example
                condition = kwargs.get("condition")
                if condition:
                    result = [item for item in data if eval(condition, {"item": item})]
                else:
                    result = data

            elif operation == "sort":
                key = kwargs.get("key")
                result = sorted(data, key=lambda x: x.get(key) if isinstance(x, dict) else x)

            elif operation == "count":
                result = len(data)

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                }

            return {
                "success": True,
                "result": result,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
            }


class TextSummarySkill(Skill):
    """Summarize text content."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="text_summary",
            description="Summarize and extract key information from text",
            category="text",
            tags=["summary", "nlp", "extraction"],
        )

    def get_required_params(self):
        return ["text"]

    def get_optional_params(self):
        return {
            "max_length": 200,
            "extract_keywords": True,
        }

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Summarize text."""
        text = kwargs.get("text")
        max_length = kwargs.get("max_length", 200)

        # Simple summarization (first N chars + stats)
        summary = text[:max_length]
        if len(text) > max_length:
            summary += "..."

        # Basic stats
        words = text.split()
        sentences = text.split(".")

        return {
            "success": True,
            "result": {
                "summary": summary,
                "word_count": len(words),
                "sentence_count": len(sentences),
                "char_count": len(text),
            },
        }


class FileOperationSkill(Skill):
    """Perform file operations."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="file_operation",
            description="Read, write, and manipulate files",
            category="system",
            tags=["file", "io", "system"],
        )

    def get_required_params(self):
        return ["operation", "path"]

    def get_optional_params(self):
        return {
            "operation": "read",  # read, write, exists, delete
            "content": None,
        }

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Perform file operation."""
        import os

        operation = kwargs.get("operation")
        path = kwargs.get("path")

        try:
            if operation == "read":
                with open(path, "r") as f:
                    content = f.read()
                return {
                    "success": True,
                    "result": {"content": content, "size": len(content)},
                }

            elif operation == "write":
                content = kwargs.get("content", "")
                with open(path, "w") as f:
                    f.write(content)
                return {
                    "success": True,
                    "result": {"bytes_written": len(content)},
                }

            elif operation == "exists":
                exists = os.path.exists(path)
                return {
                    "success": True,
                    "result": {"exists": exists},
                }

            elif operation == "delete":
                if os.path.exists(path):
                    os.remove(path)
                return {
                    "success": True,
                    "result": {"deleted": True},
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"File operation failed: {str(e)}",
            }
