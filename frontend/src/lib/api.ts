import type { Source, StockTrending, ThemeTrending, DashboardStats, Mention, SP500Company, StockProfile, ThemeProfile, WatchlistItem, PodcastFeed } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// --- Ingest ---

export async function ingestYouTube(url: string): Promise<Source> {
  return apiFetch<Source>("/api/ingest/youtube", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function ingestTranscript(data: {
  title: string;
  content: string;
  channel?: string;
  source_type?: string;
}): Promise<Source> {
  return apiFetch<Source>("/api/ingest/transcript", {
    method: "POST",
    body: JSON.stringify({ source_type: "upload", ...data }),
  });
}

// --- SEC ---

export async function getSP500List(): Promise<{ companies: SP500Company[]; total: number }> {
  return apiFetch("/api/sec/sp500");
}

export async function scanSecTicker(
  ticker: string
): Promise<{ ticker: string; new_sources: string[]; count: number }> {
  return apiFetch(`/api/sec/scan/${ticker}`, { method: "POST" });
}

// --- Sources ---

export async function getSources(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ sources: Source[]; total: number }> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiFetch(`/api/sources?${q}`);
}

export async function getSource(id: string): Promise<Source> {
  return apiFetch(`/api/sources/${id}`);
}

export async function deleteSource(id: string): Promise<void> {
  await apiFetch(`/api/sources/${id}`, { method: "DELETE" });
}

// --- Stocks ---

export type SourceCategory = "filing" | "media";

export async function getTrendingStocks(params?: {
  limit?: number;
  offset?: number;
  min_score?: number;
  category?: SourceCategory;
}): Promise<{ stocks: StockTrending[]; total: number }> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.min_score !== undefined) q.set("min_score", String(params.min_score));
  if (params?.category) q.set("category", params.category);
  return apiFetch(`/api/stocks/trending?${q}`);
}

export async function getStockProfile(ticker: string): Promise<StockProfile> {
  return apiFetch(`/api/stocks/${ticker}/profile`);
}

export type PriceRange = "1mo" | "3mo" | "6mo" | "1y" | "5y";

export async function getStockPriceHistory(
  ticker: string,
  range: PriceRange = "6mo"
): Promise<{ ticker: string; range: PriceRange; points: { date: string; close: number }[] }> {
  return apiFetch(`/api/stocks/${ticker}/price-history?range=${range}`);
}

export interface MentionHistoryPoint {
  date: string;
  mention_count: number;
  avg_sentiment: number;
}

export async function getStockMentionHistory(
  ticker: string,
  range: PriceRange = "6mo"
): Promise<{ ticker: string; range: PriceRange; points: MentionHistoryPoint[] }> {
  return apiFetch(`/api/stocks/${ticker}/mention-history?range=${range}`);
}

export async function getStockMentions(
  ticker: string,
  limit = 20,
  category?: SourceCategory
): Promise<{ ticker: string; company: string; mentions: Mention[] }> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (category) q.set("category", category);
  return apiFetch(`/api/stocks/${ticker}/mentions?${q}`);
}

// --- Themes ---

export async function getTrendingThemes(params?: {
  limit?: number;
  offset?: number;
  min_score?: number;
  category?: SourceCategory;
}): Promise<{ themes: ThemeTrending[]; total: number }> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.min_score !== undefined) q.set("min_score", String(params.min_score));
  if (params?.category) q.set("category", params.category);
  return apiFetch(`/api/themes/trending?${q}`);
}

export async function getThemeProfile(name: string): Promise<ThemeProfile> {
  return apiFetch(`/api/themes/${encodeURIComponent(name)}/profile`);
}

export async function getThemeMentions(
  name: string,
  limit = 20,
  category?: SourceCategory
): Promise<{ theme: string; mentions: Mention[] }> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (category) q.set("category", category);
  return apiFetch(`/api/themes/${encodeURIComponent(name)}/mentions?${q}`);
}

// --- Watchlist ---

export async function getWatchlist(): Promise<{ items: WatchlistItem[] }> {
  return apiFetch("/api/watchlist");
}

export async function addToWatchlist(ticker: string): Promise<WatchlistItem> {
  return apiFetch<WatchlistItem>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await apiFetch(`/api/watchlist/${ticker}`, { method: "DELETE" });
}

// --- Podcast Feeds ---

export async function getPodcastFeeds(): Promise<{ feeds: PodcastFeed[] }> {
  return apiFetch("/api/podcasts");
}

export async function addPodcastFeed(data: {
  url: string;
  label: string;
  source_type?: string;
}): Promise<PodcastFeed> {
  return apiFetch<PodcastFeed>("/api/podcasts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function removePodcastFeed(id: string): Promise<void> {
  await apiFetch(`/api/podcasts/${id}`, { method: "DELETE" });
}

export async function pollPodcastFeedNow(id: string): Promise<{ status: string; detail: string }> {
  return apiFetch(`/api/podcasts/${id}/poll`, { method: "POST" });
}

// --- Dashboard ---

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiFetch("/api/dashboard/stats");
}
