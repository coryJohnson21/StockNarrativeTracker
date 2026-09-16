import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, Date, DateTime, ForeignKey, UniqueConstraint, Boolean
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
    # Multiplier applied to this source's mentions in live momentum scoring, derived
    # from its channel's realized call track record (see services/reliability.py).
    # 1.0 = unknown or coin-flip; above 1 has been right more than chance, below 1 wrong.
    reliability_weight = Column(Float, nullable=False, default=1.0, server_default="1.0")
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
    is_public = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    mentions = relationship("StockMention", back_populates="stock", cascade="all, delete-orphan")
    momentum = relationship("StockMomentum", back_populates="stock", uselist=False, cascade="all, delete-orphan")


class Theme(Base):
    __tablename__ = "themes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    # Whether this theme is on the user's curated tracked list -- shown on the trending
    # page and recognized by name in future extraction. Themes GPT-4o discovers on its
    # own that aren't already tracked are still created (as a candidate pool) but start
    # untracked/hidden until the user promotes them via the Add Theme flow.
    is_tracked = Column(Boolean, nullable=False, default=False, server_default="false")
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
    # True when this mention's source was filed/published by the same company being
    # mentioned (e.g. MSFT mentioned within MSFT's own 8-K press release) -- as opposed
    # to a cross-mention, like MSFT mentioned in NVDA's earnings release. Self-mentions
    # get downweighted in momentum scoring since a company talking about itself in its
    # own press release isn't an independent signal the way outside coverage is.
    is_self_mention = Column(Boolean, nullable=False, default=False, server_default="false")

    source = relationship("Source", back_populates="stock_mentions")
    stock = relationship("Stock", back_populates="mentions")


class StockCall(Base):
    """An explicit buy/sell/hold/avoid/watch recommendation a source made about a
    stock, with the price target and reasoning if stated. One row per (source, stock)
    so a channel's track record can be scored against realized forward returns."""
    __tablename__ = "stock_calls"
    __table_args__ = (UniqueConstraint("source_id", "stock_id", name="uq_stock_calls_source_stock"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    call = Column(String(10), nullable=False)  # buy, sell, hold, avoid, watch
    price_target = Column(Float)
    reasoning = Column(Text)
    called_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source")
    stock = relationship("Stock")


class SourceReliability(Base):
    """A channel's (podcast, YouTube channel, subreddit, or source type when no
    channel is known) track record on the explicit calls it made, scored against
    realized SPY-excess returns."""
    __tablename__ = "source_reliability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_key = Column(String(300), unique=True, nullable=False)
    source_type = Column(String(20))
    horizon = Column(Integer, nullable=False)
    n_calls = Column(Integer, nullable=False, default=0)
    n_scored = Column(Integer, nullable=False, default=0)
    hits = Column(Integer, nullable=False, default=0)
    hit_rate = Column(Float)
    wilson_lower = Column(Float)
    mean_alpha_pct = Column(Float)
    weight = Column(Float, nullable=False, default=1.0)
    computed_at = Column(DateTime, default=datetime.utcnow)


class StockPrice(Base):
    """Daily closing price, the ground truth every narrative signal is tested against."""
    __tablename__ = "stock_prices"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_stock_prices_stock_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    close = Column(Float, nullable=False)


class MomentumSnapshot(Base):
    """What the momentum score *was* for a stock on a given day, rebuilt from mention
    timestamps so the history is point-in-time (only mentions published on or before
    that day count). Joined to stock_prices to measure forward returns."""
    __tablename__ = "momentum_snapshots"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_momentum_snapshots_stock_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    score = Column(Float, nullable=False)
    mention_count_7d = Column(Integer, nullable=False, default=0)
    mention_count_30d = Column(Integer, nullable=False, default=0)
    avg_sentiment = Column(Float, nullable=False, default=0.0)
    unique_sources = Column(Integer, nullable=False, default=0)
    share_of_voice = Column(Float, nullable=False, default=0.0)
    label = Column(String(20))


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
    label = Column(String(20))
    previous_label = Column(String(20))
    current_price = Column(Float)
    market_cap = Column(Float)
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
    # AI-generated ripple-effect analysis: {"rising": [...], "falling": [...]}, each entry
    # {target, target_type (theme/stock/market), direction (up/down), label, rationale}.
    # Cached alongside description since it's the same "expensive to regenerate" shape.
    impact_analysis = Column(JSONB, nullable=True)
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


class RedditFeed(Base):
    """A subreddit polled periodically for new hot posts — each post becomes a Source
    that runs through the text extraction pipeline (no audio, so no transcription step)."""
    __tablename__ = "reddit_feeds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subreddit = Column(String(100), unique=True, nullable=False)
    last_polled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    source_type = Column(String(20), default="podcast")
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
    label = Column(String(20))
    previous_label = Column(String(20))
    computed_at = Column(DateTime, default=datetime.utcnow)

    theme = relationship("Theme", back_populates="momentum")
