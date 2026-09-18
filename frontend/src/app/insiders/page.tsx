"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { UserRoundCheck, Loader2, AlertCircle, Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RecentInsiderTrades } from "@/components/RecentInsiderTrades";
import { getInsiderOverview } from "@/lib/api";
import { formatLargeNumber } from "@/lib/utils";
import type { InsiderOverview } from "@/types";

const WINDOWS = [30, 90, 180, 365];

function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "green" | "red" }) {
  const toneClass = tone === "green" ? "text-green-400" : tone === "red" ? "text-red-400" : "text-foreground";
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ClusterBuys({ overview }: { overview: InsiderOverview }) {
  if (overview.cluster_buys.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-4 w-4 text-green-400" />
            Cluster Buying
          </CardTitle>
          <CardDescription>
            Companies where three or more insiders made unscheduled open-market purchases in the window.
            Several independent buyers at once is the insider pattern with the strongest forward record.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-6 text-center">
            No cluster buying in the last {overview.window_days} days. Try a longer window.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Users className="h-4 w-4 text-green-400" />
          Cluster Buying
          <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-400">
            {overview.cluster_buys.length}
          </span>
        </CardTitle>
        <CardDescription>
          Companies where three or more insiders made unscheduled open-market purchases in the last{" "}
          {overview.window_days} days. Several independent buyers at once is the insider pattern with the
          strongest forward record.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
                <th className="text-left py-2 px-4 w-24">Ticker</th>
                <th className="text-left py-2 px-4">Company</th>
                <th className="text-right py-2 px-4 w-24">Buyers</th>
                <th className="text-right py-2 px-4 w-28">Bought</th>
                <th className="text-right py-2 px-4 w-28">Latest</th>
              </tr>
            </thead>
            <tbody>
              {overview.cluster_buys.map((c) => (
                <tr key={c.ticker} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                  <td className="py-3 px-4">
                    <Link href={`/stocks/${c.ticker}`} className="font-bold font-mono text-foreground hover:text-primary">
                      {c.ticker}
                    </Link>
                  </td>
                  <td className="py-3 px-4 text-muted-foreground truncate max-w-0">{c.company_name || "—"}</td>
                  <td className="py-3 px-4 text-right tabular-nums text-green-400 font-medium">{c.buyers}</td>
                  <td className="py-3 px-4 text-right tabular-nums">${formatLargeNumber(Math.round(c.value))}</td>
                  <td className="py-3 px-4 text-right tabular-nums text-xs text-muted-foreground">
                    {new Date(c.latest).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InsidersPage() {
  const [days, setDays] = useState(30);
  const [includeInstitutions, setIncludeInstitutions] = useState(false);
  const [overview, setOverview] = useState<InsiderOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getInsiderOverview({ days, includeInstitutions })
      .then(setOverview)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days, includeInstitutions]);

  const netPct = overview?.net_ratio == null ? null : Math.round(overview.net_ratio * 100);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <UserRoundCheck className="h-7 w-7 text-amber-400" />
          Insider Activity
        </h1>
        <p className="text-muted-foreground mt-1 max-w-3xl">
          Open-market purchases and sales by officers, directors, and 10% holders, from SEC Form 4 filings.
          Grants, option exercises, and tax withholding are excluded — they say nothing about what an insider
          thinks the stock is worth. Scheduled 10b5-1 sales are marked and left out of the signals.
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground whitespace-nowrap">Window</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {WINDOWS.map((d) => (
              <option key={d} value={d}>
                Last {d} days
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={includeInstitutions}
            onChange={(e) => setIncludeInstitutions(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-input accent-amber-500"
          />
          Include 10% holders
          <span className="text-muted-foreground/60">
            (funds and holding entities — they trade in blocks that dwarf officer activity)
          </span>
        </label>
      </div>

      {error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : loading && !overview ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : overview ? (
        <>
          <Card>
            <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-6 pt-6">
              <Tile
                label="Bought"
                value={`$${formatLargeNumber(Math.round(overview.buy_value))}`}
                hint={`${overview.buys} trade${overview.buys === 1 ? "" : "s"}`}
                tone="green"
              />
              <Tile
                label="Sold"
                value={`$${formatLargeNumber(Math.round(overview.sell_value))}`}
                hint={`${overview.sells} trade${overview.sells === 1 ? "" : "s"}`}
                tone="red"
              />
              <Tile
                label="Net"
                value={netPct === null ? "—" : `${netPct >= 0 ? "+" : ""}${netPct}%`}
                hint="+100% all buying · −100% all selling"
                tone={netPct !== null && netPct >= 0 ? "green" : "red"}
              />
              <Tile label="Companies" value={String(overview.stocks)} hint="with insider trades" />
              <Tile label="Insiders" value={String(overview.insiders)} hint="distinct filers" />
            </CardContent>
          </Card>

          <ClusterBuys overview={overview} />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-400">
                    Buys
                  </span>
                  Biggest Insider Purchases
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <RecentInsiderTrades side="buys" days={days} limit={25} includeInstitutions={includeInstitutions} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="inline-flex items-center rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-400">
                    Sells
                  </span>
                  Biggest Insider Sales
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <RecentInsiderTrades side="sells" days={days} limit={25} includeInstitutions={includeInstitutions} />
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
