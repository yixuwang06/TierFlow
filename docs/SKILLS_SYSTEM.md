# Skills System

## Overview

The Skills system provides extensible, domain-specific task execution capabilities. Skills are specialized modules that handle specific types of tasks more efficiently than general-purpose LLM execution.

## Architecture

```
┌─────────────────────────────────────────┐
│   SkillAwareOrchestrator                │
│   - Identifies skill-compatible tasks   │
│   - Routes to skill or LLM executor     │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌─────────────┐  ┌─────────────┐
│   Skills    │  │  LLM Exec   │
│  Registry   │  │  (GPT-5.5)  │
└─────────────┘  └─────────────┘
```

## Built-in Skills

### 1. Code Analysis (`code_analysis`)

Analyze code quality, complexity, and structure.

**Parameters:**
- `code` (required): Code to analyze
- `language` (optional): Programming language (default: "python")
- `metrics` (optional): Metrics to compute

**Returns:**
- `total_lines`: Total line count
- `non_empty_lines`: Non-empty line count
- `functions`: Function count
- `classes`: Class count
- `avg_line_length`: Average line length

**Example:**
```python
from src.skills import execute_skill

result = execute_skill(
    "code_analysis",
    context={},
    code="def hello():\n    print('Hello')",
    language="python"
)
```

### 2. Data Processing (`data_processing`)

Process, filter, and transform data.

**Parameters:**
- `data` (required): List of data items
- `operation` (required): Operation type (filter, sort, count)
- `condition` (optional): Filter condition
- `key` (optional): Sort key

**Returns:**
- Processed data or count

**Example:**
```python
result = execute_skill(
    "data_processing",
    context={},
    data=[1, 2, 3, 4, 5],
    operation="filter",
    condition="item > 2"
)
# Returns: [3, 4, 5]
```

### 3. Text Summary (`text_summary`)

Summarize and extract key information from text.

**Parameters:**
- `text` (required): Text to summarize
- `max_length` (optional): Maximum summary length (default: 200)
- `extract_keywords` (optional): Extract keywords (default: True)

**Returns:**
- `summary`: Text summary
- `word_count`: Word count
- `sentence_count`: Sentence count
- `char_count`: Character count

**Example:**
```python
result = execute_skill(
    "text_summary",
    context={},
    text="Long text here...",
    max_length=100
)
```

### 4. File Operation (`file_operation`)

Perform file operations.

**Parameters:**
- `operation` (required): Operation type (read, write, exists, delete)
- `path` (required): File path
- `content` (optional): Content for write operation

**Returns:**
- Operation-specific results

**Example:**
```python
result = execute_skill(
    "file_operation",
    context={},
    operation="read",
    path="/path/to/file.txt"
)
```

## Creating Custom Skills

### Step 1: Define Skill Class

```python
from src.skills.base import Skill, SkillMetadata
from typing import Any, Dict

class MyCustomSkill(Skill):
    """My custom skill description."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="my_custom_skill",
            description="What this skill does",
            category="custom",
            tags=["tag1", "tag2"],
            version="1.0.0",
            author="Your Name",
        )

    def get_required_params(self):
        return ["param1", "param2"]

    def get_optional_params(self):
        return {
            "param3": "default_value",
        }

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute the skill."""
        param1 = kwargs.get("param1")
        param2 = kwargs.get("param2")
        
        try:
            # Your skill logic here
            result = self._do_something(param1, param2)
            
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _do_something(self, param1, param2):
        """Helper method."""
        return f"Processed {param1} and {param2}"
```

### Step 2: Register Skill

```python
from src.skills import register_skill

# Register your skill
register_skill(MyCustomSkill())
```

### Step 3: Use in Workflow

```python
from src.orchestration import SkillAwareOrchestrator

orchestrator = SkillAwareOrchestrator()

# The orchestrator will automatically detect and use your skill
result = orchestrator.execute_workflow("Use my custom skill with param1 and param2")
```

## Skill Registry

### List Available Skills

```python
from src.skills import get_skill_registry

registry = get_skill_registry()

# List all skills
all_skills = registry.list_skills()

# List skills by category
code_skills = registry.list_skills(category="code")

# List categories
categories = registry.list_categories()
```

### Execute Skill Directly

```python
from src.skills import execute_skill

result = execute_skill(
    "code_analysis",
    context={"workflow_id": "123"},
    code="print('hello')",
    language="python"
)

if result["success"]:
    print(result["result"])
else:
    print(f"Error: {result['error']}")
```

## SkillAwareOrchestrator

The `SkillAwareOrchestrator` automatically identifies tasks that can be handled by skills and routes them appropriately.

### Automatic Skill Detection

The orchestrator uses keyword matching to identify skill-compatible tasks:

- **Code Analysis**: "analyze code", "code quality", "code analysis"
- **Data Processing**: "process data", "filter data", "transform data"
- **Text Summary**: "summarize", "summary", "extract key"
- **File Operation**: "read file", "write file", "file operation"

### Usage

```python
from src.orchestration import SkillAwareOrchestrator

orchestrator = SkillAwareOrchestrator()

# This will use code_analysis skill
result = orchestrator.execute_workflow("Analyze the code quality of my Python script")

# Check which skills were used
print(result["skills_used"])  # ['code_analysis']
```

### Mixed Execution

The orchestrator can use both skills and LLM execution in the same workflow:

```python
result = orchestrator.execute_workflow(
    "Analyze this code and then write documentation for it"
)

# First subtask uses code_analysis skill
# Second subtask uses GPT-5.5 executor
```

## Benefits

### 1. Performance

Skills execute faster than LLM calls for specific tasks:
- No API latency
- No token costs
- Deterministic results

### 2. Reliability

Skills provide consistent, predictable behavior:
- No hallucinations
- Guaranteed output format
- Explicit error handling

### 3. Cost Efficiency

Skills reduce API costs:
- No tokens consumed
- No rate limiting
- Unlimited usage

### 4. Extensibility

Easy to add new capabilities:
- Plugin architecture
- No code changes to orchestrator
- Automatic integration

## Best Practices

### 1. Skill Naming

- Use descriptive, action-oriented names
- Follow snake_case convention
- Keep names concise (2-3 words)

### 2. Parameter Design

- Minimize required parameters
- Provide sensible defaults
- Validate inputs thoroughly

### 3. Error Handling

- Always return `{"success": bool, ...}`
- Include descriptive error messages
- Handle edge cases gracefully

### 4. Documentation

- Document all parameters
- Provide usage examples
- Explain return values

### 5. Testing

- Test with various inputs
- Test error conditions
- Verify parameter validation

## Example: Complete Custom Skill

```python
from src.skills.base import Skill, SkillMetadata
from typing import Any, Dict
import requests

class WebScraperSkill(Skill):
    """Scrape content from web pages."""

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_scraper",
            description="Fetch and extract content from web pages",
            category="web",
            tags=["scraping", "http", "extraction"],
            version="1.0.0",
        )

    def get_required_params(self):
        return ["url"]

    def get_optional_params(self):
        return {
            "timeout": 10,
            "extract": "text",  # text, html, json
        }

    def validate_input(self, **kwargs) -> bool:
        url = kwargs.get("url", "")
        return url.startswith("http://") or url.startswith("https://")

    def execute(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 10)
        extract = kwargs.get("extract", "text")

        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            if extract == "json":
                content = response.json()
            elif extract == "html":
                content = response.text
            else:
                # Simple text extraction
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                content = soup.get_text()

            return {
                "success": True,
                "result": {
                    "content": content,
                    "status_code": response.status_code,
                    "url": url,
                },
            }

        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"Failed to fetch {url}: {str(e)}",
            }

# Register the skill
from src.skills import register_skill
register_skill(WebScraperSkill())
```

## Future Enhancements

- **LLM-based parameter extraction**: Use LLM to parse task descriptions and extract skill parameters
- **Skill composition**: Chain multiple skills together
- **Async execution**: Support async skills for I/O-bound operations
- **Skill marketplace**: Share and discover community skills
- **Skill versioning**: Support multiple versions of the same skill
