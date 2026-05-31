"""Model configuration system with permissions and fallback priorities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import yaml

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelRole(str, Enum):
    """Model role in the workflow."""

    ORCHESTRATOR = "orchestrator"  # 上层编排
    EXECUTOR = "executor"  # 下层执行
    REVIEWER = "reviewer"  # 评审
    PLANNER = "planner"  # 规划


class ModelProvider(str, Enum):
    """Model provider."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


@dataclass
class ModelPermissions:
    """Permissions for a model."""

    can_plan: bool = True  # 可以规划任务
    can_execute: bool = True  # 可以执行任务
    can_review: bool = True  # 可以评审结果
    can_evaluate: bool = True  # 可以评估完成度
    max_tokens: Optional[int] = None  # 最大token限制
    rate_limit: Optional[int] = None  # 速率限制（请求/分钟）


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    name: str  # 模型名称，如 "claude-opus-4-7"
    provider: ModelProvider  # 提供商
    api_key_env: str  # API密钥环境变量名
    permissions: ModelPermissions = field(default_factory=ModelPermissions)
    priority: int = 0  # 优先级，数字越小优先级越高
    enabled: bool = True  # 是否启用
    cost_per_1k_tokens: float = 0.0  # 每1k tokens成本（用于成本优化）
    base_url: Optional[str] = None  # 自定义API端点


@dataclass
class RoleModelConfig:
    """Model configuration for a specific role with fallback chain."""

    role: ModelRole
    primary_model: str  # 主模型名称
    fallback_models: List[str] = field(default_factory=list)  # 备用模型列表（按优先级）
    auto_fallback: bool = True  # 是否自动切换到备用模型
    fallback_on_error: bool = True  # 错误时切换
    fallback_on_rate_limit: bool = True  # 速率限制时切换
    fallback_on_timeout: bool = True  # 超时时切换


class ModelConfigManager:
    """Manage model configurations and fallback strategies."""

    def __init__(self, config_path: Optional[str] = None):
        self.models: Dict[str, ModelConfig] = {}
        self.role_configs: Dict[ModelRole, RoleModelConfig] = {}

        if config_path:
            self.load_from_file(config_path)
        else:
            self._load_defaults()

    def _load_defaults(self):
        """Load default model configurations."""
        # Claude Opus - 上层编排
        self.register_model(
            ModelConfig(
                name="claude-opus-4-7",
                provider=ModelProvider.ANTHROPIC,
                api_key_env="ANTHROPIC_API_KEY",
                permissions=ModelPermissions(
                    can_plan=True,
                    can_execute=False,
                    can_review=True,
                    can_evaluate=True,
                    max_tokens=4000,
                    rate_limit=50,
                ),
                priority=0,
                cost_per_1k_tokens=0.015,
            )
        )

        # Claude Sonnet - 备用编排
        self.register_model(
            ModelConfig(
                name="claude-sonnet-4-6",
                provider=ModelProvider.ANTHROPIC,
                api_key_env="ANTHROPIC_API_KEY",
                permissions=ModelPermissions(
                    can_plan=True,
                    can_execute=True,
                    can_review=True,
                    can_evaluate=True,
                    max_tokens=4000,
                    rate_limit=100,
                ),
                priority=1,
                cost_per_1k_tokens=0.003,
            )
        )

        # GPT-5.5 - 主执行器
        self.register_model(
            ModelConfig(
                name="gpt-5.5",
                provider=ModelProvider.OPENAI,
                api_key_env="OPENAI_API_KEY",
                permissions=ModelPermissions(
                    can_plan=True,
                    can_execute=True,
                    can_review=True,
                    can_evaluate=True,
                    max_tokens=8000,
                    rate_limit=100,
                ),
                priority=0,
                cost_per_1k_tokens=0.005,
            )
        )

        # DeepSeek - 备用执行器
        self.register_model(
            ModelConfig(
                name="deepseek-chat",
                provider=ModelProvider.DEEPSEEK,
                api_key_env="DEEPSEEK_API_KEY",
                permissions=ModelPermissions(
                    can_plan=True,
                    can_execute=True,
                    can_review=True,
                    can_evaluate=True,
                    max_tokens=8000,
                    rate_limit=60,
                ),
                priority=1,
                cost_per_1k_tokens=0.001,
            )
        )

        # 配置角色
        self.configure_role(
            RoleModelConfig(
                role=ModelRole.ORCHESTRATOR,
                primary_model="claude-opus-4-7",
                fallback_models=["claude-sonnet-4-6"],
                auto_fallback=True,
            )
        )

        self.configure_role(
            RoleModelConfig(
                role=ModelRole.EXECUTOR,
                primary_model="gpt-5.5",
                fallback_models=["deepseek-chat", "claude-sonnet-4-6"],
                auto_fallback=True,
            )
        )

        self.configure_role(
            RoleModelConfig(
                role=ModelRole.PLANNER,
                primary_model="claude-opus-4-7",
                fallback_models=["claude-sonnet-4-6"],
                auto_fallback=True,
            )
        )

        self.configure_role(
            RoleModelConfig(
                role=ModelRole.REVIEWER,
                primary_model="claude-opus-4-7",
                fallback_models=["claude-sonnet-4-6", "gpt-5.5"],
                auto_fallback=True,
            )
        )

        logger.info("default_models_loaded", model_count=len(self.models))

    def register_model(self, config: ModelConfig):
        """Register a model configuration."""
        self.models[config.name] = config
        logger.info(
            "model_registered",
            name=config.name,
            provider=config.provider,
            priority=config.priority,
        )

    def configure_role(self, role_config: RoleModelConfig):
        """Configure models for a specific role."""
        self.role_configs[role_config.role] = role_config
        logger.info(
            "role_configured",
            role=role_config.role,
            primary=role_config.primary_model,
            fallbacks=role_config.fallback_models,
        )

    def get_model_for_role(
        self, role: ModelRole, exclude: Optional[List[str]] = None
    ) -> Optional[ModelConfig]:
        """Get the best available model for a role."""
        exclude = exclude or []
        role_config = self.role_configs.get(role)

        if not role_config:
            logger.error("role_not_configured", role=role)
            return None

        # 尝试主模型
        if role_config.primary_model not in exclude:
            model = self.models.get(role_config.primary_model)
            if model and model.enabled and self._check_permissions(model, role):
                return model

        # 尝试备用模型
        if role_config.auto_fallback:
            for fallback_name in role_config.fallback_models:
                if fallback_name not in exclude:
                    model = self.models.get(fallback_name)
                    if model and model.enabled and self._check_permissions(model, role):
                        logger.info(
                            "using_fallback_model",
                            role=role,
                            model=fallback_name,
                        )
                        return model

        logger.error("no_available_model", role=role, exclude=exclude)
        return None

    def _check_permissions(self, model: ModelConfig, role: ModelRole) -> bool:
        """Check if model has required permissions for role."""
        perms = model.permissions

        if role == ModelRole.ORCHESTRATOR:
            return perms.can_plan and perms.can_evaluate
        elif role == ModelRole.EXECUTOR:
            return perms.can_execute
        elif role == ModelRole.PLANNER:
            return perms.can_plan
        elif role == ModelRole.REVIEWER:
            return perms.can_review

        return True

    def get_fallback_chain(self, role: ModelRole) -> List[str]:
        """Get the complete fallback chain for a role."""
        role_config = self.role_configs.get(role)
        if not role_config:
            return []

        chain = [role_config.primary_model] + role_config.fallback_models
        return [m for m in chain if m in self.models and self.models[m].enabled]

    def load_from_file(self, config_path: str):
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)

            # 加载模型配置
            for model_data in config_data.get("models", []):
                permissions = ModelPermissions(**model_data.get("permissions", {}))
                model = ModelConfig(
                    name=model_data["name"],
                    provider=ModelProvider(model_data["provider"]),
                    api_key_env=model_data["api_key_env"],
                    permissions=permissions,
                    priority=model_data.get("priority", 0),
                    enabled=model_data.get("enabled", True),
                    cost_per_1k_tokens=model_data.get("cost_per_1k_tokens", 0.0),
                    base_url=model_data.get("base_url"),
                )
                self.register_model(model)

            # 加载角色配置
            for role_data in config_data.get("roles", []):
                role_config = RoleModelConfig(
                    role=ModelRole(role_data["role"]),
                    primary_model=role_data["primary_model"],
                    fallback_models=role_data.get("fallback_models", []),
                    auto_fallback=role_data.get("auto_fallback", True),
                    fallback_on_error=role_data.get("fallback_on_error", True),
                    fallback_on_rate_limit=role_data.get("fallback_on_rate_limit", True),
                    fallback_on_timeout=role_data.get("fallback_on_timeout", True),
                )
                self.configure_role(role_config)

            logger.info("config_loaded_from_file", path=config_path)

        except Exception as e:
            logger.error("config_load_failed", path=config_path, error=str(e))
            self._load_defaults()

    def save_to_file(self, config_path: str):
        """Save configuration to YAML file."""
        config_data = {
            "models": [
                {
                    "name": model.name,
                    "provider": model.provider.value,
                    "api_key_env": model.api_key_env,
                    "permissions": {
                        "can_plan": model.permissions.can_plan,
                        "can_execute": model.permissions.can_execute,
                        "can_review": model.permissions.can_review,
                        "can_evaluate": model.permissions.can_evaluate,
                        "max_tokens": model.permissions.max_tokens,
                        "rate_limit": model.permissions.rate_limit,
                    },
                    "priority": model.priority,
                    "enabled": model.enabled,
                    "cost_per_1k_tokens": model.cost_per_1k_tokens,
                }
                for model in self.models.values()
            ],
            "roles": [
                {
                    "role": role_config.role.value,
                    "primary_model": role_config.primary_model,
                    "fallback_models": role_config.fallback_models,
                    "auto_fallback": role_config.auto_fallback,
                    "fallback_on_error": role_config.fallback_on_error,
                    "fallback_on_rate_limit": role_config.fallback_on_rate_limit,
                    "fallback_on_timeout": role_config.fallback_on_timeout,
                }
                for role_config in self.role_configs.values()
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        logger.info("config_saved_to_file", path=config_path)

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get model information."""
        model = self.models.get(model_name)
        if not model:
            return None

        return {
            "name": model.name,
            "provider": model.provider.value,
            "priority": model.priority,
            "enabled": model.enabled,
            "permissions": {
                "can_plan": model.permissions.can_plan,
                "can_execute": model.permissions.can_execute,
                "can_review": model.permissions.can_review,
                "can_evaluate": model.permissions.can_evaluate,
            },
            "rate_limit": model.permissions.rate_limit,
            "cost_per_1k_tokens": model.cost_per_1k_tokens,
        }

    def list_models(self, role: Optional[ModelRole] = None) -> List[Dict]:
        """List all models or models for a specific role."""
        if role:
            chain = self.get_fallback_chain(role)
            return [self.get_model_info(name) for name in chain if name in self.models]
        else:
            return [self.get_model_info(name) for name in self.models.keys()]
