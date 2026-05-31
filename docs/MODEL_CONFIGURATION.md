# Model Configuration System

## Overview

The model configuration system provides flexible control over which models are used for different roles in the workflow, with support for permissions, priorities, and automatic fallback chains.

## Features

### 1. Model Registration

Each model is registered with:
- **Name**: Model identifier (e.g., "claude-opus-4-7")
- **Provider**: anthropic, openai, deepseek, or custom
- **API Key**: Environment variable name for the API key
- **Permissions**: What the model can do
- **Priority**: Lower number = higher priority
- **Cost**: Per 1k tokens for cost optimization
- **Enabled**: Whether the model is active

### 2. Model Permissions

Fine-grained control over model capabilities:
```python
ModelPermissions(
    can_plan=True,        # Can plan and decompose tasks
    can_execute=True,     # Can execute code/tasks
    can_review=True,      # Can review results
    can_evaluate=True,    # Can evaluate completion
    max_tokens=4000,      # Token limit
    rate_limit=50,        # Requests per minute
)
```

### 3. Role-Based Configuration

Four roles with independent model assignments:
- **Orchestrator**: High-level coordination and evaluation
- **Planner**: Task planning and decomposition
- **Executor**: Code/task execution
- **Reviewer**: Result review and quality assessment

### 4. Automatic Fallback Chains

Each role has a primary model and fallback chain:
```yaml
roles:
  - role: executor
    primary_model: gpt-5.5
    fallback_models:
      - deepseek-chat
      - claude-sonnet-4-6
    auto_fallback: true
    fallback_on_error: true
    fallback_on_rate_limit: true
    fallback_on_timeout: true
```

## Configuration File

### YAML Format (`config/models.yaml`)

```yaml
models:
  - name: claude-opus-4-7
    provider: anthropic
    api_key_env: ANTHROPIC_API_KEY
    permissions:
      can_plan: true
      can_execute: false
      can_review: true
      can_evaluate: true
      max_tokens: 4000
      rate_limit: 50
    priority: 0
    enabled: true
    cost_per_1k_tokens: 0.015

  - name: gpt-5.5
    provider: openai
    api_key_env: OPENAI_API_KEY
    permissions:
      can_plan: true
      can_execute: true
      can_review: true
      can_evaluate: true
      max_tokens: 8000
      rate_limit: 100
    priority: 0
    enabled: true
    cost_per_1k_tokens: 0.005

roles:
  - role: orchestrator
    primary_model: claude-opus-4-7
    fallback_models:
      - claude-sonnet-4-6
    auto_fallback: true

  - role: executor
    primary_model: gpt-5.5
    fallback_models:
      - deepseek-chat
      - claude-sonnet-4-6
    auto_fallback: true
```

## Usage

### Basic Usage

```python
from src.orchestration import ConfigurableOrchestrator

# Use default configuration
orchestrator = ConfigurableOrchestrator()

# Use custom configuration file
orchestrator = ConfigurableOrchestrator(
    model_config_path="config/models.yaml"
)

result = orchestrator.execute_workflow("Build REST API")
```

### Command Line

```bash
# Run with default configuration
python -m src.main run "Build REST API"

# Run with custom configuration
python -m src.main run "Build REST API" --model-config config/custom_models.yaml

# List configured models
python -m src.main list-models

# Export configuration
python -m src.main export-config --output config/my_models.yaml
```

### Programmatic Configuration

```python
from src.config.models import (
    ModelConfig,
    ModelConfigManager,
    ModelPermissions,
    ModelProvider,
    ModelRole,
    RoleModelConfig,
)

# Create manager
manager = ModelConfigManager()

# Register custom model
manager.register_model(
    ModelConfig(
        name="custom-model",
        provider=ModelProvider.OPENAI,
        api_key_env="CUSTOM_API_KEY",
        permissions=ModelPermissions(
            can_plan=True,
            can_execute=True,
            max_tokens=8000,
            rate_limit=100,
        ),
        priority=0,
        cost_per_1k_tokens=0.002,
    )
)

# Configure role
manager.configure_role(
    RoleModelConfig(
        role=ModelRole.EXECUTOR,
        primary_model="custom-model",
        fallback_models=["gpt-5.5", "deepseek-chat"],
        auto_fallback=True,
    )
)

# Use in orchestrator
orchestrator = ConfigurableOrchestrator(
    model_config_manager=manager
)
```

## Fallback Behavior

### Automatic Fallback

When a model fails, the system automatically tries the next model in the fallback chain:

1. **Primary model fails** → Try first fallback
2. **First fallback fails** → Try second fallback
3. **All models fail** → Return error

### Fallback Triggers

Configurable per role:
- `fallback_on_error`: API errors, exceptions
- `fallback_on_rate_limit`: Rate limit exceeded
- `fallback_on_timeout`: Request timeout

### Model Exclusion

Temporarily exclude failed models:
```python
# Get model excluding failed ones
model = manager.get_model_for_role(
    ModelRole.EXECUTOR,
    exclude=["gpt-5.5"]  # Skip this model
)
```

## Permission Enforcement

Models are automatically filtered based on role requirements:

```python
# Orchestrator role requires can_plan and can_evaluate
# Only models with these permissions will be selected
orchestrator_model = manager.get_model_for_role(ModelRole.ORCHESTRATOR)
```

## Cost Optimization

Track costs across models:
```python
# Models include cost information
model_info = manager.get_model_info("claude-opus-4-7")
print(f"Cost: ${model_info['cost_per_1k_tokens']}/1k tokens")

# Choose cheaper fallbacks for non-critical tasks
```

## Default Configuration

Out of the box, the system includes:

**Upper Layer (Orchestration)**:
- Primary: claude-opus-4-7
- Fallback: claude-sonnet-4-6

**Lower Layer (Execution)**:
- Primary: gpt-5.5
- Fallback: deepseek-chat, claude-sonnet-4-6

**Planner**:
- Primary: claude-opus-4-7
- Fallback: claude-sonnet-4-6

**Reviewer**:
- Primary: claude-opus-4-7
- Fallback: claude-sonnet-4-6, gpt-5.5

## Testing

Run model configuration tests:
```bash
python tests/test_model_config.py
```

Tests cover:
- Model registration
- Role configuration
- Fallback chains
- Model exclusion
- Permissions
- YAML loading/saving

## Benefits

1. **Flexibility**: Easy to add/remove/configure models
2. **Reliability**: Automatic fallback on failures
3. **Cost Control**: Choose models based on cost
4. **Permission Control**: Enforce what each model can do
5. **Multi-Provider**: Support multiple AI providers
6. **Hot Reload**: Change configuration without code changes

## Example Configurations

### Cost-Optimized

Use cheaper models with expensive fallbacks:
```yaml
roles:
  - role: executor
    primary_model: deepseek-chat  # Cheapest
    fallback_models:
      - gpt-5.5
      - claude-sonnet-4-6
```

### Quality-Optimized

Use best models with quality fallbacks:
```yaml
roles:
  - role: orchestrator
    primary_model: claude-opus-4-7  # Best
    fallback_models:
      - gpt-5.5
      - claude-sonnet-4-6
```

### Balanced

Mix of quality and cost:
```yaml
roles:
  - role: planner
    primary_model: claude-opus-4-7  # Quality for planning
  - role: executor
    primary_model: gpt-5.5  # Balanced for execution
    fallback_models:
      - deepseek-chat  # Cost-effective fallback
```
