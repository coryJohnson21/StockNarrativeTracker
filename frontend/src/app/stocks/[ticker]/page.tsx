"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, Landmark, Newspaper, ExternalLink, Building2, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SentimentBadge } from "@/components/SentimentBadge";
import { MomentumBar } from "@/components/MomentumBadge";
import { getStockProfile, getStockMentions } from "@/lib/api";
import { formatLargeNumber, formatRatio, formatPrice } from "@/lib/utils";
import { StockPriceChart } from "@/components/StockPriceChart";
import { MomentumHistoryChart } from "@/components/MomentumHistoryChart";
import type { StockProfile, Mention } from "@/types";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export default function StockDetailPage() {
  const params = useParams();
  const ticker = (params.ticker as string)?.toUpperCase();

  const [profile, setProfile] = useState<StockProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filings, setFilings] = useState<Mention[]>([]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getStockProfile(ticker)
      .then(setProfile)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    getStockMentions(ticker, 50, "filing")
      .then((r) => {
        const seen = new Set<string>();
        const unique = r.mentions.filter((m) => {
          if (!m.source_url || seen.has(m.source_url)) return false;
          seen.add(m.source_url);
          return true;
        });
        setFilings(unique.slice(0, 10));
      })
      .catch(() => setFilings([]));
  }, [ticker]);

  return (
    <div className="space-y-6">
      <Link href="/stocks" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
        <ArrowLeft className="h-4 w-4" />
        Back to Trending Stocks
      </Link>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : profile ? (
        <>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight font-mono">{profile.ticker}</h1>
              <p className="text-muted-foreground mt-1">{profile.company_name}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold tabular-nums">
                {formatPrice(profile.price.current, profile.price.currency)}
              </p>
              <p className="text-sm text-muted-foreground">
                Open: {formatPrice(profile.price.open, profile.price.currency)}
              </p>
            </div>
          </div>

          <Card>
            <CardContent className="pt-6">
              <StockPriceChart ticker={profile.ticker} currency={profile.price.currency} />
            </CardContent>
          </Card>

          {profile.description && (
            <Card>
              <CardContent className="pt-6 text-sm leading-relaxed text-muted-foreground">
                {profile.description}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Summary Statistics</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-6">
              <StatTile label="Market Cap" value={formatLargeNumber(profile.fundamentals.market_cap)} />
              <StatTile label="P/E Ratio" value={formatRatio(profile.fundamentals.pe_ratio)} />
              <StatTile label="Price / Book" value={formatRatio(profile.fundamentals.price_to_book)} />
              <StatTile label="Price / Sales" value={formatRatio(profile.fundamentals.price_to_sales)} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Narrative Momentum</CardTitle>
              <CardDescription>Where mentions are coming from and what the sentiment looks like.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.momentum_score !== undefined && profile.momentum_score !== null && (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground uppercase tracking-wide w-32">Overall score</span>
                  <MomentumBar score={profile.momentum_score} />
                </div>
              )}

              {profile.narrative_summary && (
                <p className="text-sm leading-relaxed text-muted-foreground border-l-2 border-primary/40 pl-4">
                  {profile.narrative_summary}
                </p>
              )}

              <div className="space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wide">
                  Momentum over time
                </p>
                <MomentumHistoryChart ticker={profile.ticker} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Landmark className="h-4 w-4 text-emerald-400" />
                    Press Releases & Earnings
                  </div>
                  <p className="text-2xl font-bold tabular-nums">
                    {profile.mention_breakdown.filing.mention_count}{" "}
                    <span className="text-sm font-normal text-muted-foreground">mentions</span>
                  </p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{profile.mention_breakdown.filing.unique_sources} source(s)</span>
                    <SentimentBadge score={profile.mention_breakdown.filing.avg_sentiment} showNumber />
                  </div>
                  {filings.length > 0 && (
                    <ul className="space-y-1 pt-1 border-t">
                      {filings.map((m, i) => (
                        <li key={i}>
                          <a
                            href={m.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:underline truncate"
                          >
                            <ExternalLink className="h-3 w-3 shrink-0" />
                            <span className="truncate">
                              {m.source_type} &middot;{" "}
                              {m.mentioned_at ? new Date(m.mentioned_at).toLocaleDateString() : ""}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Newspaper className="h-4 w-4 text-blue-400" />
                    Media Tracking
                  </div>
                  <p className="text-2xl font-bold tabular-nums">
                    {profile.mention_breakdown.media.mention_count}{" "}
                    <span className="text-sm font-normal text-muted-foreground">mentions</span>
                  </p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{profile.mention_breakdown.media.unique_sources} source(s)</span>
                    <SentimentBadge score={profile.mention_breakdown.media.avg_sentiment} showNumber />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wide">
                  Self vs. external mentions
                </p>
                <p className="text-xs text-muted-foreground">
                  How much of this stock&apos;s narrative comes from the company talking about
                  itself vs. independent coverage. Self-mentions count for less toward the
                  momentum score above.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="rounded-lg border p-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Building2 className="h-4 w-4 text-amber-400" />
                      Self-mentions
                    </div>
                    <p className="text-2xl font-bold tabular-nums">
                      {profile.self_vs_external_breakdown.self.mention_count}{" "}
                      <span className="text-sm font-normal text-muted-foreground">mentions</span>
                    </p>
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{profile.self_vs_external_breakdown.self.unique_sources} source(s)</span>
                      <SentimentBadge score={profile.self_vs_external_breakdown.self.avg_sentiment} showNumber />
                    </div>
                  </div>

                  <div className="rounded-lg border p-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Globe className="h-4 w-4 text-purple-400" />
                      External mentions
                    </div>
                    <p className="text-2xl font-bold tabular-nums">
                      {profile.self_vs_external_breakdown.external.mention_count}{" "}
                      <span className="text-sm font-normal text-muted-foreground">mentions</span>
                    </p>
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{profile.self_vs_external_breakdown.external.unique_sources} source(s)</span>
                      <SentimentBadge score={profile.self_vs_external_breakdown.external.avg_sentiment} showNumber />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
