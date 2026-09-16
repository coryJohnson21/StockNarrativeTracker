"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, Landmark, Newspaper, ExternalLink, Building2, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SentimentBadge } from "@/components/SentimentBadge";
import { MomentumBar } from "@/components/MomentumBadge";
import { getStockProfile, getStockFilings } from "@/lib/api";
import { formatLargeNumber, formatRatio, formatPrice } from "@/lib/utils";
import { StockPriceChart } from "@/components/StockPriceChart";
import { MomentumHistoryChart } from "@/components/MomentumHistoryChart";
import type { StockProfile, StockFiling, CallType } from "@/types";

const CALL_ORDER: CallType[] = ["buy", "hold", "watch", "avoid", "sell"];
const CALL_STYLES: Record<CallType, string> = {
  buy: "bg-green-500/10 text-green-400 border-green-500/20",
  hold: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  watch: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  avoid: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  sell: "bg-red-500/10 text-red-400 border-red-500/20",
};

function CallChip({ call, count }: { call: CallType; count?: number }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${CALL_STYLES[call]}`}>
      {call}
      {count !== undefined && <span className="tabular-nums opacity-80">{count}</span>}
    </span>
  );
}

function consensusLabel(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  if (value >= 0.5) return "Strongly bullish";
  if (value >= 0.15) return "Leaning bullish";
  if (value > -0.15) return "Split";
  if (value > -0.5) return "Leaning bearish";
  return "Strongly bearish";
}

function filingPeriodLabel(f: StockFiling): string {
  if (f.period) return f.period;
  if (f.published_at) return new Date(f.published_at).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  return f.type;
}

function filingSnippet(f: StockFiling): string | undefined {
  if (f.teaser) return f.teaser;
  return f.summary?.split(/(?<=[.!?])\s/)[0];
}

function pctLabel(pct?: number): string | undefined {
  if (pct === undefined || pct === null) return undefined;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

const GUIDANCE_VARIANT: Record<string, "bullish" | "bearish" | "neutral" | "secondary"> = {
  raised: "bullish",
  lowered: "bearish",
  maintained: "neutral",
  initiated: "secondary",
};

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

          {profile.calls && profile.calls.latest.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Explicit Calls</CardTitle>
                <CardDescription>
                  Recommendations stated outright in the sources — not inferred from tone.
                  {profile.calls.total > 0 && (
                    <> Last {profile.calls.window_days} days: <span className="text-foreground">{consensusLabel(profile.calls.consensus)}</span> across {profile.calls.total}.</>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {CALL_ORDER.filter((t) => profile.calls.counts[t] > 0).map((t) => (
                    <CallChip key={t} call={t} count={profile.calls.counts[t]} />
                  ))}
                </div>
                <ul className="space-y-3">
                  {profile.calls.latest.map((c, i) => (
                    <li key={i} className="text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <CallChip call={c.call} />
                        {c.price_target != null && (
                          <span className="text-xs text-muted-foreground tabular-nums">
                            target {formatPrice(c.price_target, profile.price.currency)}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {c.source_channel || c.source_type}
                          {" · "}
                          {new Date(c.called_at).toLocaleDateString()}
                        </span>
                      </div>
                      {c.reasoning && <p className="text-muted-foreground mt-1 leading-snug">{c.reasoning}</p>}
                      {c.source_title && (
                        c.source_url ? (
                          <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-muted-foreground hover:text-foreground hover:underline inline-flex items-center gap-1 mt-0.5">
                            <ExternalLink className="h-3 w-3" />
                            {c.source_title}
                          </a>
                        ) : (
                          <p className="text-xs text-muted-foreground mt-0.5">{c.source_title}</p>
                        )
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

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
                            {(f.revenue != null || f.eps != null || f.guidance_direction) && (
                              <div className="flex flex-wrap items-start gap-x-6 gap-y-1.5 mt-2 pl-[22px] text-xs">
                                {f.revenue != null && (
                                  <div className="flex items-start gap-1.5">
                                    <span>
                                      <span className="text-muted-foreground">Revenue </span>
                                      <span className="font-medium text-foreground">${formatLargeNumber(f.revenue)}</span>
                                    </span>
                                    {(f.revenue_yoy_pct != null || f.revenue_qoq_pct != null) && (
                                      <div className="flex flex-col leading-tight">
                                        {f.revenue_yoy_pct != null && (
                                          <span className={f.revenue_yoy_pct >= 0 ? "text-green-400" : "text-red-400"}>
                                            {pctLabel(f.revenue_yoy_pct)} YoY
                                          </span>
                                        )}
                                        {f.revenue_qoq_pct != null && (
                                          <span className={f.revenue_qoq_pct >= 0 ? "text-green-400" : "text-red-400"}>
                                            {pctLabel(f.revenue_qoq_pct)} QoQ
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                                {f.eps != null && (
                                  <div className="flex items-start gap-1.5">
                                    <span>
                                      <span className="text-muted-foreground">EPS </span>
                                      <span className="font-medium text-foreground">${f.eps.toFixed(2)}</span>
                                    </span>
                                    {(f.eps_yoy_pct != null || f.eps_qoq_pct != null) && (
                                      <div className="flex flex-col leading-tight">
                                        {f.eps_yoy_pct != null && (
                                          <span className={f.eps_yoy_pct >= 0 ? "text-green-400" : "text-red-400"}>
                                            {pctLabel(f.eps_yoy_pct)} YoY
                                          </span>
                                        )}
                                        {f.eps_qoq_pct != null && (
                                          <span className={f.eps_qoq_pct >= 0 ? "text-green-400" : "text-red-400"}>
                                            {pctLabel(f.eps_qoq_pct)} QoQ
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                                {f.guidance_direction && (
                                  <Badge variant={GUIDANCE_VARIANT[f.guidance_direction]} className="capitalize">
                                    Guidance {f.guidance_direction}
                                  </Badge>
                                )}
                              </div>
                            )}
                            {f.capital_returns && (
                              <p className="text-[11px] text-muted-foreground mt-1.5 pl-[22px]">
                                <span className="text-foreground font-medium">Capital returns — </span>
                                {f.capital_returns}
                              </p>
                            )}
                            {f.strategic_actions && (
                              <p className="text-[11px] text-muted-foreground mt-1 pl-[22px]">
                                <span className="text-foreground font-medium">Strategic — </span>
                                {f.strategic_actions}
                              </p>
                            )}
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
