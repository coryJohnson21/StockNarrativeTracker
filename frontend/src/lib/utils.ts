import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSentiment(score: number): string {
  if (score >= 60) return "Very Bullish";
  if (score >= 20) return "Bullish";
  if (score > -20) return "Neutral";
  if (score > -60) return "Bearish";
  return "Very Bearish";
}

export function sentimentColor(score: number): string {
  if (score >= 20) return "text-green-500";
  if (score > -20) return "text-yellow-500";
  return "text-red-500";
}

export function sentimentBg(score: number): string {
  if (score >= 20) return "bg-green-500/10 text-green-400 border-green-500/20";
  if (score > -20) return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
  return "bg-red-500/10 text-red-400 border-red-500/20";
}

export function scoreColor(score: number): string {
  if (score >= 70) return "text-green-400";
  if (score >= 40) return "text-yellow-400";
  return "text-muted-foreground";
}

export function growthLabel(rate: number): string {
  const pct = Math.round(rate * 100);
  if (pct > 0) return `+${pct}%`;
  return `${pct}%`;
}

export function growthColor(rate: number): string {
  if (rate > 0.1) return "text-green-400";
  if (rate > -0.1) return "text-muted-foreground";
  return "text-red-400";
}

export function formatDuration(seconds?: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatLargeNumber(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  return value.toLocaleString();
}

export function formatRatio(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(2);
}

export function formatPrice(value?: number | null, currency?: string | null): string {
  if (value === null || value === undefined) return "—";
  return `${currency === "USD" || !currency ? "$" : currency + " "}${value.toFixed(2)}`;
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
