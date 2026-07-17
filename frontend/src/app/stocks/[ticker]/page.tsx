"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, Landmark, Newspaper, ExternalLink, Building2, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SentimentBadge } from "@/components/SentimentBadge";
import { MomentumBar } from "@/components/MomentumBadge";
import { getStockProfile, getStockFilings } from "@/lib/api";
import { formatLargeNumber, formatRatio, formatPrice } from "@/lib/utils";
import { StockPriceChart } from "@/components/StockPriceChart";
import { MomentumHistoryChart } from "@/components/MomentumHistoryChart";
import type { StockProfile, StockFiling } from "@/types";

function filingPeriodLabel(f: StockFiling): string {
  if (f.period) return f.period;
  if (f.published_at) return new Date(f.published_at).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  return f.type;
}

function filingSnippet(f: StockFiling): string | undefined {
  if (f.teaser) return f.teaser;
  return f.summary?.split(/(?<=[.!?])\s/)[0];
}

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
  const [filings, setFilings] = useState<StockFiling[]>([]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getStockProfile(ticker)
      .then(setProfile)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    getStockFilings(ticker, 10)
      .then((r) => setFilings(r.filings))
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

              <div className="space-y-4">
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
                    <ul className="space-y-4 pt-3 border-t">
                      {filings.map((f) => {
                        const snippet = filingSnippet(f);
                        return (
                          <li key={f.id}>
                            <a
                              href={f.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="group flex items-start gap-2 hover:underline"
                            >
                              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-0.5 text-muted-foreground group-hover:text-foreground" />
                              <span className="text-sm font-semibold text-foreground leading-snug">
                                {filingPeriodLabel(f)}
                                {snippet && <>: {snippet}</>}
                              </span>
                            </a>
                            <p className="text-[11px] text-muted-foreground mt-0.5 pl-[22px]">
                              {f.type}
                              {f.published_at ? ` · ${new Date(f.published_at).toLocaleDateString()}` : ""}
                            </p>
                            {(f.filing_summary || f.summary) && (
                              <p className="text-xs text-muted-foreground leading-relaxed mt-1.5 pl-[22px]">
                                {f.filing_summary || f.summary}
                              </p>
                            )}
                          </li>
                        );
                      })}
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
                <div className="space-y-4">
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
