from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://narrativetracker:narrativetracker@localhost:5432/narrativetracker"
    openai_api_key: str = ""
    cors_origins: List[str] = ["http://localhost:3000"]
    environment: str = "development"
    temp_dir: str = "/tmp/narrativetracker"
    sec_contact_email: str = "admin@example.com"
    sec_scan_interval_hours: int = 24

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
