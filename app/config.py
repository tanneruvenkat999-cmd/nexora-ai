from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    database_url: str = "sqlite:///./nexora.db"
    jwt_secret: str = ""
    admin_email: str = ""
    admin_password: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    github_token: str = ""
    cors_origins: str = "http://localhost:8000"

    @field_validator("database_url")
    @classmethod
    def render_postgres_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
