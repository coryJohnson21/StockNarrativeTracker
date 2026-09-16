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
    # Set ENABLE_AUTO_INGEST=true in .env to allow periodic podcast/Reddit
    # polling + market data refresh. Defaults to false to avoid unexpected spend.
    enable_auto_ingest: bool = False
    # Separate switch just for the daily SEC filing scan (new S&P 500
    # 10-K/10-Q/8-K filings only -- never backfills), independent of the
    # podcast/Reddit auto-ingest above.
    enable_auto_sec_scan: bool = False
    # Optional Reddit "script" app credentials (reddit.com/prefs/apps). With them,
    # posts and comments come from the official OAuth API; without them we fall
    # back to the public Atom feed, which Reddit still serves but which has no
    # comments and is subject to anti-bot blocking.
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
