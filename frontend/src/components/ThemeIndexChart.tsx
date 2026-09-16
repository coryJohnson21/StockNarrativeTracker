"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Bar, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getThemeIndex } from "@/lib/api";
import type { LeadLag, ThemeIndex } from "@/types";

const WINDOWS = [
  { days: 90, label: "3M" },
  { days: 180, label: "6M" },
  { days: 365, label: "1Y" },
];

function verdictText(name: string, ll: LeadLag): { text: string; className: string } {
  if (ll.verdict === null) return { text: `${name}: not enough overlapping weeks yet (${ll.n_weeks})`, className: "text-muted-foreground" };
  const sign = (v: number | null) => (v === null ? "" : v > 0 ? "positively" : "inversely");
  switch (ll.verdict) {
    case "leads":
      return { text: `${name} led the basket by a week (${sign(ll.leads)}, ρ ${ll.leads?.toFixed(2)})`, className: "text-green-400" };
    case "lags":
      return { text: `${name} chased the basket — it followed last week's move (ρ ${ll.lags?.toFixed(2)})`, className: "text-amber-400" };
    case "coincident":
      return { text: `${name} moved with the basket in the same week (ρ ${ll.coincident?.toFixed(2)})`, className: "text-foreground" };
    default:
      return { text: `${name} showed no clear relationship to basket returns over ${ll.n_weeks} weeks`, className: "text-muted-foreground" };
  }
}

export function ThemeIndexChart({ themeName }: { themeName: string }) {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<ThemeIndex | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getThemeIndex(themeName, days)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [themeName, days]);

  const priced = data?.constituents.filter((c) => c.has_prices) ?? [];
  const weeks = data?.weekly.filter((w) => w.index_value !== null || w.mention_count > 0) ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base">Theme Basket vs. Narrative</CardTitle>
            <CardDescription>
              Equal-weight index (base 100) of the {priced.length > 0 ? priced.length : "top"} most co-mentioned stocks
              {priced.length > 0 && <> — {priced.map((c) => c.ticker).join(", ")}</>}
              , against weekly mention volume for the theme.
              {data?.index_return_pct != null && (
                <> Basket {data.index_return_pct >= 0 ? "+" : ""}{data.index_return_pct.toFixed(1)}% over the window.</>
              )}
            </CardDescription>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {WINDOWS.map((w) => (
              <button
                key={w.days}
                onClick={() => setDays(w.days)}
                className={`text-xs px-2 py-1 rounded-md transition-colors ${days === w.days ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent/50"}`}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : !data || priced.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No priced constituents yet. Run <span className="text-foreground">Refresh prices &amp; snapshots</span> on the Research page so the
            theme&apos;s co-mentioned stocks have daily closes to build a basket from.
          </p>
        ) : (
          <>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weeks} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis yAxisId="idx" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
                  <YAxis yAxisId="n" orientation="right" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: "currentColor", fillOpacity: 0.04 }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const w = payload[0].payload as (typeof weeks)[number];
                      return (
                        <div className="rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow space-y-0.5">
                          <div className="font-medium">week of {w.week}</div>
                          <div className="text-muted-foreground">
                            basket {w.index_value?.toFixed(1) ?? "—"}{w.index_return_pct != null && ` (${w.index_return_pct >= 0 ? "+" : ""}${w.index_return_pct.toFixed(1)}%)`}
                          </div>
                          <div className="text-muted-foreground">{w.mention_count} mentions{w.avg_sentiment != null && ` · sentiment ${w.avg_sentiment >= 0 ? "+" : ""}${w.avg_sentiment.toFixed(0)}`}</div>
                        </div>
                      );
                    }}
                  />
                  <Bar yAxisId="n" dataKey="mention_count" fill="rgb(139 92 246)" fillOpacity={0.35} radius={[3, 3, 0, 0]} />
                  <Line yAxisId="idx" type="monotone" dataKey="index_value" stroke="rgb(74 222 128)" strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <ul className="text-xs space-y-1">
              {(["avg_sentiment", "mention_count"] as const).map((k) => {
                const v = verdictText(k === "avg_sentiment" ? "Sentiment" : "Mention volume", data.lead_lag[k]);
                return <li key={k} className={v.className}>{v.text}</li>;
              })}
            </ul>
            <p className="text-xs text-muted-foreground leading-relaxed">
              &ldquo;Leads&rdquo; means this week&apos;s narrative correlated with <em>next</em> week&apos;s basket return; &ldquo;chased&rdquo; means it
              followed last week&apos;s. Weekly buckets over a few months are a small sample — a verdict here is a hypothesis to watch, not a result.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
