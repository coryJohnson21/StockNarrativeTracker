"use client";

import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getBacktest, getResearchStatus, refreshResearch } from "@/lib/api";
import type { BacktestResult, FactorIC, ResearchStatus } from "@/types";

const HORIZONS = [5, 20, 60];

const FACTOR_LABELS: Record<FactorIC["factor"], string> = {
  score: "Momentum score",
  avg_sentiment: "Sentiment",
  mention_count_7d: "Mentions (7d)",
  share_of_voice: "Share of voice",
};

function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function num(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(digits);
}

function tStatVerdict(t: number | null): { text: string; className: string } {
  if (t === null) return { text: "not enough dates", className: "text-muted-foreground" };
  const a = Math.abs(t);
  if (a >= 2.5) return { text: t > 0 ? "significant, right way" : "significant, inverted", className: t > 0 ? "text-green-400" : "text-red-400" };
  if (a >= 1.5) return { text: "suggestive", className: "text-yellow-400" };
  return { text: "indistinguishable from noise", className: "text-muted-foreground" };
}

export default function ResearchPage() {
  const [status, setStatus] = useState<ResearchStatus | null>(null);
  const [horizon, setHorizon] = useState(20);
  const [minMentions, setMinMentions] = useState(1);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, r] = await Promise.all([getResearchStatus(), getBacktest({ horizon, min_mentions_7d: minMentions })]);
      setStatus(s);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load research data");
    } finally {
      setLoading(false);
    }
  }, [horizon, minMentions]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshResearch();
      // The refresh runs in the background; prices for many tickers take a while.
      await new Promise((r) => setTimeout(r, 4000));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  const hasData = (status?.snapshots ?? 0) > 0 && (status?.price_rows ?? 0) > 0;
  const chartData = result?.buckets.map((b) => ({
    name: `Q${b.bucket}`,
    value: b.mean_excess_pct ?? b.mean_return_pct,
    range: `${b.score_min}–${b.score_max}`,
    n: b.n,
  })) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <FlaskConical className="h-7 w-7 text-violet-400" />
            Research
          </h1>
          <p className="text-muted-foreground mt-1 max-w-2xl">
            Does narrative momentum predict returns? Every stock-day since the first mention is scored with only the
            information available that day, then compared to what the stock did next.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing} className="shrink-0">
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh prices & snapshots
        </Button>
      </div>

      {status && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground tabular-nums">
          <span><span className="text-foreground font-medium">{status.snapshots.toLocaleString()}</span> stock-day snapshots{status.snapshot_from && ` · ${status.snapshot_from} → ${status.snapshot_to}`}</span>
          <span><span className="text-foreground font-medium">{status.price_rows.toLocaleString()}</span> daily closes across {status.price_stocks} tickers{status.price_to && ` · through ${status.price_to}`}</span>
          <span>Benchmark {status.benchmark_available ? <span className="text-foreground">SPY loaded</span> : <span className="text-amber-500">SPY missing — raw returns only</span>}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !hasData ? (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground space-y-2">
            <p>No research data yet. Click <span className="text-foreground">Refresh prices &amp; snapshots</span> to pull a year of daily closes for every tracked stock (plus SPY) and rebuild the score history from mention timestamps.</p>
            <p>This takes a few minutes the first time — Yahoo is rate-limited to roughly four tickers a second.</p>
          </CardContent>
        </Card>
      ) : result && (
        <>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground mr-1">Forward window</span>
              {HORIZONS.map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`text-xs px-2.5 py-1 rounded-md transition-colors ${horizon === h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent/50"}`}
                >
                  {h}d
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground mr-1">Min mentions that week</span>
              {[0, 1, 3].map((m) => (
                <button
                  key={m}
                  onClick={() => setMinMentions(m)}
                  className={`text-xs px-2.5 py-1 rounded-md transition-colors ${minMentions === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent/50"}`}
                >
                  {m}
                </button>
              ))}
            </div>
            <span className="text-xs text-muted-foreground tabular-nums ml-auto">
              {result.n_observations.toLocaleString()} observations over {result.n_dates} days
              {result.date_from && ` · ${result.date_from} → ${result.date_to}`}
            </span>
          </div>

          {result.n_observations === 0 ? (
            <Card>
              <CardContent className="pt-6 text-sm text-muted-foreground">
                No observations with a realized {horizon}-day return yet. Either the snapshots are too recent for
                prices {horizon} trading days later to exist, or no stock had {minMentions}+ mentions in a week. Try a
                shorter window or a lower mention floor.
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 lg:grid-cols-5">
              <Card className="lg:col-span-3">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Forward {horizon}-day {result.benchmark_available ? "excess" : ""} return by score quintile</CardTitle>
                  <CardDescription>
                    Q1 is the lowest-scoring fifth of stock-days, Q5 the highest.
                    {result.benchmark_available ? ` Returns are relative to ${result.benchmark} over the same window.` : " Raw returns (benchmark not loaded)."}
                    {result.spread_excess_pct !== null && (
                      <> Top-minus-bottom spread: <span className={result.spread_excess_pct >= 0 ? "text-green-400" : "text-red-400"}>{pct(result.spread_excess_pct)}</span>.</>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
                        <ReferenceLine y={0} stroke="currentColor" strokeOpacity={0.25} />
                        <Tooltip
                          cursor={{ fill: "currentColor", fillOpacity: 0.04 }}
                          content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const d = payload[0].payload as { name: string; value: number; range: string; n: number };
                            return (
                              <div className="rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow">
                                <div className="font-medium">{d.name} · score {d.range}</div>
                                <div className="text-muted-foreground">{pct(d.value)} mean · n={d.n}</div>
                              </div>
                            );
                          }}
                        />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                          {chartData.map((d, i) => (
                            <Cell key={i} fill={d.value >= 0 ? "rgb(74 222 128)" : "rgb(248 113 113)"} fillOpacity={0.85} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <table className="w-full text-xs mt-4 tabular-nums">
                    <thead className="text-muted-foreground uppercase tracking-wide">
                      <tr className="border-b border-border">
                        <th className="text-left py-1.5">Quintile</th>
                        <th className="text-right py-1.5">Score</th>
                        <th className="text-right py-1.5">n</th>
                        <th className="text-right py-1.5">Mean</th>
                        <th className="text-right py-1.5">Excess</th>
                        <th className="text-right py-1.5">Median</th>
                        <th className="text-right py-1.5">Hit rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.buckets.map((b) => (
                        <tr key={b.bucket} className="border-b border-border/50">
                          <td className="py-1.5">Q{b.bucket}</td>
                          <td className="py-1.5 text-right text-muted-foreground">{b.score_min}–{b.score_max}</td>
                          <td className="py-1.5 text-right text-muted-foreground">{b.n}</td>
                          <td className="py-1.5 text-right">{pct(b.mean_return_pct)}</td>
                          <td className={`py-1.5 text-right ${b.mean_excess_pct === null ? "" : b.mean_excess_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{pct(b.mean_excess_pct)}</td>
                          <td className="py-1.5 text-right">{pct(b.median_excess_pct)}</td>
                          <td className="py-1.5 text-right">{b.hit_rate === null ? "—" : `${(b.hit_rate * 100).toFixed(0)}%`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Which factor actually ranks returns?</CardTitle>
                  <CardDescription>
                    Rank correlation (IC) between each factor and the forward {result.benchmark_available ? "excess " : ""}return.
                    The t-stat is over per-day ICs, so a single lucky week can&apos;t carry a factor. Anything under |1.5| is noise.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {result.factor_ic.map((f) => {
                      const verdict = tStatVerdict(f.t_stat);
                      return (
                        <li key={f.factor} className="rounded-lg border p-3">
                          <div className="flex items-baseline justify-between gap-3">
                            <span className="text-sm font-medium">{FACTOR_LABELS[f.factor]}</span>
                            <span className={`text-lg font-semibold tabular-nums ${f.ic === null ? "text-muted-foreground" : f.ic >= 0 ? "text-green-400" : "text-red-400"}`}>
                              {num(f.ic)}
                            </span>
                          </div>
                          <div className="flex flex-wrap justify-between gap-x-4 text-xs text-muted-foreground tabular-nums mt-1">
                            <span>daily IC {num(f.mean_daily_ic)} · t {f.t_stat === null ? "—" : f.t_stat.toFixed(2)} · {f.n_dates} days</span>
                            <span className={verdict.className}>{verdict.text}</span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
                    A positive, significant IC on sentiment means the crowd is right and narrative leads price. A
                    negative one means attention peaks late — a contrarian signal. An IC on mentions but not sentiment
                    says volume matters and direction doesn&apos;t. The sample is small; treat anything under a few
                    hundred observations across 20+ days as a hypothesis, not a result.
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
