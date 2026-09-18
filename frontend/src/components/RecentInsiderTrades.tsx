"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Landmark } from "lucide-react";
import { getRecentInsiderTrades } from "@/lib/api";
import { formatLargeNumber } from "@/lib/utils";
import type { RecentInsiderTrade } from "@/types";

interface Props {
  days?: number;
  limit?: number;
  side: "buys" | "sells";
  includeInstitutions?: boolean;
}

function TradeRow({ trade, side }: { trade: RecentInsiderTrade; side: "buys" | "sells" }) {
  const router = useRouter();
  const buy = side === "buys";
  return (
    <tr
      className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
      onClick={() => router.push(`/stocks/${trade.ticker}`)}
    >
      <td className="py-3 px-3">
        <span className="font-bold text-foreground font-mono">{trade.ticker}</span>
      </td>
      <td className="py-3 px-3 max-w-0">
        <div className="truncate text-foreground">{trade.owner_name}</div>
        {trade.owner_role && (
          <div className="truncate text-xs text-muted-foreground">{trade.owner_role}</div>
        )}
      </td>
      <td className="py-3 px-3 text-xs text-muted-foreground tabular-nums whitespace-nowrap">
        {new Date(trade.transaction_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        {trade.is_10b5_1 && (
          <span
            className="ml-1.5 text-[10px] uppercase tracking-wide text-muted-foreground/70"
            title="Sold under a pre-arranged 10b5-1 plan — scheduled, not a fresh decision"
          >
            plan
          </span>
        )}
      </td>
      <td className={`py-3 px-3 text-right tabular-nums font-medium whitespace-nowrap ${buy ? "text-green-400" : "text-red-400"}`}>
        ${formatLargeNumber(Math.round(trade.value))}
        {trade.lines > 1 && (
          <div
            className="text-[10px] font-normal text-muted-foreground/70"
            title={`${trade.lines} Form 4 lines on this date, combined into one decision`}
          >
            {trade.lines} trades
          </div>
        )}
      </td>
    </tr>
  );
}

export function RecentInsiderTrades({ days = 30, limit = 10, side, includeInstitutions = true }: Props) {
  const [trades, setTrades] = useState<RecentInsiderTrade[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getRecentInsiderTrades({ days, limit, includeInstitutions })
      .then((r) => setTrades(side === "buys" ? r.buys : r.sells))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days, limit, side, includeInstitutions]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-red-400 p-4">Error: {error}</p>;
  }

  if (!trades || trades.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Landmark className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">
          No open-market insider {side === "buys" ? "purchases" : "sales"} in the last {days} days.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm table-fixed">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3 w-20">Ticker</th>
            <th className="text-left py-2 px-3">Insider</th>
            <th className="text-left py-2 px-3 w-24">Date</th>
            <th className="text-right py-2 px-3 w-28">Value</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <TradeRow key={`${t.ticker}-${t.owner_name}-${t.transaction_date}`} trade={t} side={side} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
