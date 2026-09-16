export interface Source {
  id: string;
  type: "youtube" | "upload" | "earnings_call" | "10-K" | "10-Q" | "8-K" | "podcast" | "news" | "reddit" | "twitter" | "x";
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
  is_public?: boolean;
  label?: string;
  previous_label?: string;
  confidence?: Confidence;
  current_price?: number;
  market_cap?: number;
  novelty_7d?: number | null;
  computed_at: string;
}

export type Confidence = "low" | "medium" | "high";

export interface NarrativeCluster {
  size: number;
  first_seen: string;
  last_seen: string;
  avg_sentiment: number;
  unique_sources: number;
  representative?: string | null;
  source_title?: string | null;
  source_channel?: string | null;
  novelty?: number | null;
}

export interface StockNarratives {
  window_days: number;
  mention_count: number;
  embedded_count: number;
  distinct_narratives: number;
  echo_ratio: number | null;
  novelty_7d: number | null;
  clusters: NarrativeCluster[];
}

export interface StockSearchResult {
  ticker: string;
  company_name?: string;
  sector?: string;
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
  confidence?: Confidence;
  ai_summary?: string;
  label?: string;
  previous_label?: string;
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
  calls: StockCallSummary;
  narratives: StockNarratives;
  signals: StockSignals;
}

export interface StockSignal {
  key: "management_vs_media" | "narrative_vs_price" | "crowding";
  severity: "info" | "watch" | "alert";
  title: string;
  detail: string;
  metrics: Record<string, number | string | null>;
}

export interface StockSignals {
  signals: StockSignal[];
  inputs: {
    guidance_direction: string | null;
    sentiment_7d: number | null;
    mentions_7d: number;
    sentiment_prior_23d: number | null;
    mentions_prior_23d: number;
    price_return_20d_pct: number | null;
    attention_percentile: number | null;
    novelty_7d: number | null;
  };
}

export interface ResearchStatus {
  snapshots: number;
  snapshot_from: string | null;
  snapshot_to: string | null;
  price_rows: number;
  price_stocks: number;
  price_from: string | null;
  price_to: string | null;
  benchmark_available: boolean;
  horizons: number[];
}

export interface BacktestBucket {
  bucket: number;
  n: number;
  score_min: number;
  score_max: number;
  mean_return_pct: number;
  mean_excess_pct: number | null;
  median_excess_pct: number | null;
  hit_rate: number | null;
}

export interface FactorIC {
  factor: "score" | "avg_sentiment" | "mention_count_7d" | "share_of_voice";
  ic: number | null;
  n: number;
  mean_daily_ic: number | null;
  t_stat: number | null;
  n_dates: number;
}

export interface BacktestResult {
  horizon: number;
  min_mentions_7d: number;
  n_observations: number;
  n_dates: number;
  date_from: string | null;
  date_to: string | null;
  benchmark: string;
  benchmark_available: boolean;
  buckets: BacktestBucket[];
  spread_excess_pct: number | null;
  factor_ic: FactorIC[];
}

export interface SourceReliability {
  channel_key: string;
  source_type: string | null;
  horizon: number;
  n_calls: number;
  n_scored: number;
  hits: number;
  hit_rate: number | null;
  wilson_lower: number | null;
  mean_alpha_pct: number | null;
  weight: number;
  computed_at: string;
}

export type CallType = "buy" | "sell" | "hold" | "avoid" | "watch";

export interface StockCall {
  call: CallType;
  price_target?: number | null;
  reasoning?: string | null;
  called_at: string;
  source_title?: string | null;
  source_type: string;
  source_channel?: string | null;
  source_url?: string | null;
}

export interface StockCallSummary {
  window_days: number;
  total: number;
  counts: Record<CallType, number>;
  consensus?: number | null;
  latest: StockCall[];
}

export interface ThemeImpactEntry {
  target: string;
  target_type: "theme" | "market" | "stock";
  direction: "up" | "down";
  label: "Positive correlation" | "Negative correlation" | "Neutral" | "Historically correlated" | "Currently diverging";
  rationale: string;
}

export interface ThemeImpactAnalysis {
  rising: ThemeImpactEntry[];
  falling: ThemeImpactEntry[];
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
  impact_analysis?: ThemeImpactAnalysis;
}

export interface ThemeIndexPoint {
  date: string;
  value: number;
  constituents: number;
}

export interface ThemeWeek {
  week: string;
  index_value: number | null;
  index_return_pct: number | null;
  mention_count: number;
  avg_sentiment: number | null;
}

export interface LeadLag {
  leads: number | null;
  coincident: number | null;
  lags: number | null;
  n_weeks: number;
  verdict: "leads" | "coincident" | "lags" | "none" | null;
}

export interface ThemeIndex {
  theme: string;
  window_days: number;
  constituents: { ticker: string; company_name?: string | null; co_mentions: number; has_prices: boolean }[];
  index: ThemeIndexPoint[];
  weekly: ThemeWeek[];
  lead_lag: { avg_sentiment: LeadLag; mention_count: LeadLag };
  index_return_pct: number | null;
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
  latest_episode_at?: string;
}

export interface PodcastEpisode {
  id: string;
  title?: string;
  published_at?: string;
  status: "pending" | "processing" | "completed" | "failed";
  duration_seconds?: number;
  error_message?: string;
  summary?: string;
}

export interface PodcastFeedDetail extends PodcastFeed {
  episodes: PodcastEpisode[];
}

export interface PodcastSearchResult {
  title: string;
  publisher?: string;
  artwork_url?: string;
  feed_url: string;
}

export interface YoutubeChannelResolution {
  channel_id: string;
  title: string;
  feed_url: string;
}

export interface RedditFeed {
  id: string;
  subreddit: string;
  last_polled_at?: string;
  created_at: string;
  post_count: number;
}

export interface StockFiling {
  id: string;
  type: string;
  url?: string;
  title?: string;
  published_at?: string;
  period?: string;
  teaser?: string;
  summary?: string;
  filing_summary?: string;
  revenue?: number;
  revenue_yoy_pct?: number;
  revenue_qoq_pct?: number;
  eps?: number;
  eps_yoy_pct?: number;
  eps_qoq_pct?: number;
  net_income?: number;
  guidance_direction?: "raised" | "lowered" | "maintained" | "initiated";
  capital_returns?: string;
  strategic_actions?: string;
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
