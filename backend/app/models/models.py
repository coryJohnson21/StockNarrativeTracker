import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(20), nullable=False)  # youtube, upload, earnings_call
    url = Column(Text)
    title = Column(Text)
    channel = Column(Text)
    published_at = Column(DateTime)
    duration_seconds = Column(Integer)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    source_metadata = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="source", uselist=False, cascade="all, delete-orphan")
    stock_mentions = relationship("StockMention", back_populates="source", cascade="all, delete-orphan")
    theme_mentions = relationship("ThemeMention", back_populates="source", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), unique=True)
    content = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="transcript")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), unique=True, nullable=False)
    company_name = Column(Text)
    sector = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    mentions = relationship("StockMention", back_populates="stock", cascade="all, delete-orphan")
    momentum = relationship("StockMomentum", back_populates="stock", uselist=False, cascade="all, delete-orphan")


class Theme(Base):
    __tablename__ = "themes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    mentions = relationship("ThemeMention", back_populates="theme", cascade="all, delete-orphan")
    momentum = relationship("ThemeMomentum", back_populates="theme", uselist=False, cascade="all, delete-orphan")


class StockMention(Base):
    __tablename__ = "stock_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"))
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"))
    sentiment_score = Column(Float)
    context = Column(Text)
    mentioned_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="stock_mentions")
    stock = relationship("Stock", back_populates="mentions")


class ThemeMention(Base):
    __tablename__ = "theme_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"))
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"))
    sentiment_score = Column(Float)
    context = Column(Text)
    mentioned_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="theme_mentions")
    theme = relationship("Theme", back_populates="mentions")


class StockMomentum(Base):
    __tablename__ = "stock_momentum"
    __table_args__ = (UniqueConstraint("stock_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), unique=True)
    score = Column(Float, default=0.0)
    mention_count = Column(Integer, default=0)
    mention_count_7d = Column(Integer, default=0)
    mention_count_30d = Column(Integer, default=0)
    mention_growth_rate = Column(Float, default=0.0)
    avg_sentiment = Column(Float, default=0.0)
    unique_sources = Column(Integer, default=0)
    ai_summary = Column(Text)
    computed_at = Column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", back_populates="momentum")


class StockProfile(Base):
    """AI-condensed company description, cached separately from live market data
    (price/fundamentals are fetched fresh on each request; descriptions rarely change
    so they're not worth re-generating with GPT-4o on every page view)."""
    __tablename__ = "stock_profiles"
    __table_args__ = (UniqueConstraint("stock_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), unique=True)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock = relationship("Stock")


class ThemeProfile(Base):
    """AI-generated theme definition, cached separately so it's not re-generated with
    GPT-4o on every page view (analogous to StockProfile)."""
    __tablename__ = "theme_profiles"
    __table_args__ = (UniqueConstraint("theme_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), unique=True)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    theme = relationship("Theme")


class StockNarrative(Base):
    """AI-generated synthesis of what's actually being said about a stock across filings
    and media, and why it reads bullish/bearish. Cached and keyed to a mention-count
    snapshot so it's only regenerated with GPT-4o once new mentions actually arrive,
    rather than on every page view."""
    __tablename__ = "stock_narratives"
    __table_args__ = (UniqueConstraint("stock_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), unique=True)
    summary = Column(Text)
    mention_count_snapshot = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock = relationship("Stock")


class WatchlistItem(Base):
    """A ticker the user wants pinned and tracked across media baskets
    (YouTube, news, Reddit/forums) and filings, independent of global momentum rankings."""
    __tablename__ = "watchlist_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), unique=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)


class PodcastFeed(Base):
    """An RSS feed (e.g. a CNBC or Bloomberg podcast) polled periodically for new
    episodes — each new episode becomes a Source that runs through the normal
    download -> transcribe -> extract pipeline, same as a pasted YouTube URL."""
    __tablename__ = "podcast_feeds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String(1000), unique=True, nullable=False)
    label = Column(String(200), nullable=False)
    source_type = Column(String(20), default="news")
    last_polled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ThemeMomentum(Base):
    __tablename__ = "theme_momentum"
    __table_args__ = (UniqueConstraint("theme_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), unique=True)
    score = Column(Float, default=0.0)
    mention_count = Column(Integer, default=0)
    mention_count_7d = Column(Integer, default=0)
    mention_count_30d = Column(Integer, default=0)
    mention_growth_rate = Column(Float, default=0.0)
    avg_sentiment = Column(Float, default=0.0)
    unique_sources = Column(Integer, default=0)
    ai_summary = Column(Text)
    computed_at = Column(DateTime, default=datetime.utcnow)

    theme = relationship("Theme", back_populates="momentum")
