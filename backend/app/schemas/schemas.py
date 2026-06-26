from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# --- Ingest ---

class YouTubeIngestRequest(BaseModel):
    url: str
    source_type: str = "youtube"

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not any(domain in v for domain in ["youtube.com", "youtu.be"]):
            raise ValueError("URL must be a YouTube link")
        return v


class TranscriptUploadRequest(BaseModel):
    title: str
    content: str
    source_type: str = "upload"
    channel: Optional[str] = None
    published_at: Optional[datetime] = None


# --- Sources ---

class SourceResponse(BaseModel):
    id: UUID
    type: str
    url: Optional[str]
    title: Optional[str]
    channel: Optional[str]
    published_at: Optional[datetime]
    duration_seconds: Optional[int]
    status: str
    error_message: Optional[str]
    source_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    sources: List[SourceResponse]
    total: int


# --- Stocks ---

class StockMomentumResponse(BaseModel):
    id: UUID
    ticker: str
    company_name: Optional[str]
    sector: Optional[str]
    score: float
    mention_count: int
    mention_count_7d: int
    mention_count_30d: int
    mention_growth_rate: float
    avg_sentiment: float
    unique_sources: int
    ai_summary: Optional[str]
    computed_at: datetime

    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    stocks: List[StockMomentumResponse]
    total: int


# --- Themes ---

class ThemeMomentumResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    score: float
    mention_count: int
    mention_count_7d: int
    mention_count_30d: int
    mention_growth_rate: float
    avg_sentiment: float
    unique_sources: int
    ai_summary: Optional[str]
    computed_at: datetime

    class Config:
        from_attributes = True


class ThemeListResponse(BaseModel):
    themes: List[ThemeMomentumResponse]
    total: int


# --- Watchlist ---

class WatchlistAddRequest(BaseModel):
    ticker: str


class BasketBreakdown(BaseModel):
    mention_count: int
    avg_sentiment: float
    unique_sources: int


class WatchlistItemResponse(BaseModel):
    ticker: str
    company_name: Optional[str]
    momentum_score: Optional[float]
    added_at: datetime
    baskets: dict[str, BasketBreakdown]


class WatchlistListResponse(BaseModel):
    items: List[WatchlistItemResponse]


# --- Podcast Feeds ---

class PodcastFeedAddRequest(BaseModel):
    url: str
    label: str
    source_type: str = "news"


class PodcastFeedResponse(BaseModel):
    id: UUID
    url: str
    label: str
    source_type: str
    last_polled_at: Optional[datetime]
    created_at: datetime
    episode_count: int = 0

    class Config:
        from_attributes = True


class PodcastFeedListResponse(BaseModel):
    feeds: List[PodcastFeedResponse]


# --- Reddit Feeds ---

class RedditFeedAddRequest(BaseModel):
    subreddit: str


class RedditFeedResponse(BaseModel):
    id: UUID
    subreddit: str
    last_polled_at: Optional[datetime]
    created_at: datetime
    post_count: int = 0

    class Config:
        from_attributes = True


class RedditFeedListResponse(BaseModel):
    feeds: List[RedditFeedResponse]


# --- Dashboard Stats ---

class DashboardStats(BaseModel):
    total_sources: int
    sources_processing: int
    total_stocks_tracked: int
    total_themes_tracked: int
    top_stock: Optional[str]
    top_theme: Optional[str]


# --- Processing result (internal) ---

class ExtractionResult(BaseModel):
    stocks: List[dict]
    themes: List[dict]
    summary: str
