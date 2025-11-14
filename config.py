"""Configuration management for Databricks connectivity."""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabricksConfig(BaseSettings):
    """Databricks configuration with validation and sensible defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = Field(..., alias="DATABRICKS_HOST")
    http_path: str = Field(..., alias="DATABRICKS_HTTP_PATH")
    token: str = Field(..., alias="DATABRICKS_TOKEN")

    catalog: str = Field(..., alias="DATABRICKS_CATALOG")
    schema_: str = Field(..., alias="DATABRICKS_SCHEMA")
    content_table: str = Field(default="content_info", alias="DATABRICKS_CONTENT_TABLE")

    max_retries: int = Field(default=3, alias="DATABRICKS_MAX_RETRIES")
    connection_timeout: int = Field(default=30, alias="DATABRICKS_CONNECTION_TIMEOUT")
    query_timeout: int = Field(default=60, alias="DATABRICKS_QUERY_TIMEOUT")
    max_rows_per_batch: int = Field(default=1000, alias="DATABRICKS_MAX_ROWS_PER_BATCH")
    enable_arrow: bool = Field(default=True, alias="DATABRICKS_ENABLE_ARROW")

    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")
    cache_max_size: int = Field(default=1000, alias="CACHE_MAX_SIZE")

    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # AI providers
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    @property
    def fully_qualified_table(self) -> str:
        """Return catalog.schema.table string."""
        return f"{self.catalog}.{self.schema_}.{self.content_table}"

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("https://"):
            value = value[len("https://") :]
        if value.startswith("http://"):
            value = value[len("http://") :]
        if not value.endswith(".databricks.com"):
            raise ValueError("host must end with .databricks.com")
        return value

    @field_validator("http_path")
    @classmethod
    def validate_http_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/sql/"):
            raise ValueError("http_path must begin with /sql/")
        return value

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if not value or value == "replace_with_pat":
            raise ValueError("Provide a Databricks personal access token")
        return value

    @field_validator("max_retries")
    @classmethod
    def validate_retries(cls, value: int) -> int:
        if not 0 <= value <= 10:
            raise ValueError("max_retries must be between 0 and 10")
        return value

    @field_validator("max_rows_per_batch")
    @classmethod
    def validate_batch_size(cls, value: int) -> int:
        if not 1 <= value <= 10_000:
            raise ValueError("max_rows_per_batch must be between 1 and 10_000")
        return value


@lru_cache(maxsize=1)
def get_config() -> DatabricksConfig:
    """Return cached configuration object."""
    return DatabricksConfig()

