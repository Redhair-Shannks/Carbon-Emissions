from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CarbonSight GHG Platform"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ghg_platform"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    seed_workbook_path: str = "GHG Sheet.xlsx"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()
