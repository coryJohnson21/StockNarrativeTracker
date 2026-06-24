export interface Source {
  id: string;
  type: "youtube" | "upload" | "earnings_call" | "10-K" | "10-Q" | "8-K";
  url?: string;
  title?: string;
  channel?: string;
  published_at?: string;
  duration_seconds?: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  source_metadata?: { ticker?: string; cik?: string; accession_number?: string; is_exhibit?: boolean };
  created_at: string;
  updated_at: string;
}

export interface SP500Company {
  ticker: string;
  company: string;
  sector: string;
  cik: string;
}

export interface StockTrending {
  id: string;
  ticker: string;
  company_name?: string;
  sector?: string;
  score: number;
  mention_count: number;
  mention_count_7d: number;
  mention_count_30d: number;
  mention_growth_rate: number;
  avg_sentiment: number;
  unique_sources: number;
  ai_summary?: string;
  computed_at: string;
}

export interface ThemeTrending {
  id: string;
  name: string;
  description?: string;
  score: number;
  mention_count: number;
  mention_count_7d: number;
  mention_count_30d: number;
  mention_growth_rate: number;
  avg_sentiment: number;
  unique_sources: number;
  ai_summary?: string;
  computed_at: string;
}

export interface DashboardStats {
  total_sources: number;
  sources_processing: number;
  total_stocks_tracked: number;
  total_themes_tracked: number;
  top_stock?: string;
  top_theme?: string;
}

export interface StockProfile {
  ticker: string;
  company_name?: string;
  sector?: string;
  description?: string;
  price: { open?: number; current?: number; currency?: string };
  fundamentals: {
    market_cap?: number;
    pe_ratio?: number;
    price_to_book?: number;
    price_to_sales?: number;
  };
  momentum_score?: number;
  mention_breakdown: {
    filing: { mention_count: number; avg_sentiment: number; unique_sources: number };
    media: { mention_count: number; avg_sentiment: number; unique_sources: number };
  };
  self_vs_external_breakdown: {
    self: { mention_count: number; avg_sentiment: number; unique_sources: number };
    external: { mention_count: number; avg_sentiment: number; unique_sources: number };
  };
  narrative_summary?: string;
}

export interface ThemeProfile {
  name: string;
  description?: string;
  momentum_score?: number;
  mention_breakdown: {
    filing: { mention_count: number; avg_sentiment: number; unique_sources: number };
    media: { mention_count: number; avg_sentiment: number; unique_sources: number };
  };
  top_stocks: { ticker: string; company_name?: string; co_mentions: number }[];
}

export interface BasketBreakdown {
  mention_count: number;
  avg_sentiment: number;
  unique_sources: number;
}

export interface WatchlistItem {
  ticker: string;
  company_name?: string;
  momentum_score?: number;
  added_at: string;
  baskets: {
    youtube: BasketBreakdown;
    news: BasketBreakdown;
    reddit: BasketBreakdown;
    filing: BasketBreakdown;
  };
}

export interface PodcastFeed {
  id: string;
  url: string;
  label: string;
  source_type: string;
  last_polled_at?: string;
  created_at: string;
  episode_count: number;
}

export interface Mention {
  source_title?: string;
  source_type?: string;
  source_channel?: string;
  source_url?: string;
  sentiment_score: number;
  context: string;
  mentioned_at: string;
}
