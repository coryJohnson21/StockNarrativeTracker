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
    podcast_poll_interval_minutes: int = 60
    reddit_poll_interval_minutes: int = 120
    # Set ENABLE_AUTO_INGEST=true in .env to allow periodic background pulls.
    # Defaults to false to avoid unexpected OpenAI spend.
    enable_auto_ingest: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
