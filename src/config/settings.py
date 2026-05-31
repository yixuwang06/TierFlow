"""Configuration management."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API Keys
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")

    # Database
    database_url: str = Field(default="sqlite:///data/workflow.db", alias="DATABASE_URL")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/workflow.log", alias="LOG_FILE")

    # Rate Limiting
    claude_rate_limit: int = Field(default=50, alias="CLAUDE_RATE_LIMIT")
    gpt_rate_limit: int = Field(default=100, alias="GPT_RATE_LIMIT")
    deepseek_rate_limit: int = Field(default=60, alias="DEEPSEEK_RATE_LIMIT")

    # Health Monitoring
    health_check_interval: int = Field(default=60, alias="HEALTH_CHECK_INTERVAL")
    heartbeat_timeout: int = Field(default=300, alias="HEARTBEAT_TIMEOUT")

    # Task Execution
    max_task_iterations: int = Field(default=100, alias="MAX_TASK_ITERATIONS")
    task_timeout: int = Field(default=600, alias="TASK_TIMEOUT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    # Resource Management
    max_memory_mb: int = Field(default=2048, alias="MAX_MEMORY_MB")
    context_window_limit: int = Field(default=100000, alias="CONTEXT_WINDOW_LIMIT")

    # Models
    orchestration_model: str = Field(default="claude-opus-4-7")
    primary_execution_model: str = Field(default="gpt-5.5")
    fallback_execution_model: str = Field(default="deepseek-chat")


settings = Settings()
