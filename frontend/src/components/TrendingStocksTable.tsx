"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, TrendingUp } from "lucide-react";
import { SentimentBadge } from "./SentimentBadge";
import { MomentumBar } from "./MomentumBadge";
import { getTrendingStocks, type SourceCategory } from "@/lib/api";
import { growthLabel, growthColor, timeAgo } from "@/lib/utils";
import type { StockTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
}

export function TrendingStocksTable({ limit = 20, compact = false, category }: Props) {
  const router = useRouter();
  const [stocks, setStocks] = useState<StockTrending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getTrendingStocks({ limit, category })
      .then((r) => setStocks(r.stocks))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [limit, category]);

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

  if (stocks.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No stocks tracked yet. Add content to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3 w-8">#</th>
            <th className="text-left py-2 px-3">Ticker</th>
            {!compact && <th className="text-left py-2 px-3">Company</th>}
            <th className="text-left py-2 px-3">Momentum</th>
            <th className="text-right py-2 px-3">Mentions</th>
            <th className="text-right py-2 px-3">7d Growth</th>
            <th className="text-left py-2 px-3">Sentiment</th>
            {!compact && <th className="text-right py-2 px-3">Sources</th>}
            {!compact && <th className="text-right py-2 px-3">Updated</th>}
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock, i) => (
            <tr
              key={stock.id}
              className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/stocks/${stock.ticker}`)}
            >
              <td className="py-3 px-3 text-muted-foreground">{i + 1}</td>
              <td className="py-3 px-3">
                <span className="font-bold text-foreground font-mono">{stock.ticker}</span>
              </td>
              {!compact && (
                <td className="py-3 px-3 text-muted-foreground max-w-[200px] truncate">
                  {stock.company_name || "—"}
                </td>
              )}
              <td className="py-3 px-3">
                <MomentumBar score={stock.score} />
              </td>
              <td className="py-3 px-3 text-right tabular-nums">{stock.mention_count}</td>
              <td className={`py-3 px-3 text-right tabular-nums font-medium ${growthColor(stock.mention_growth_rate)}`}>
                {growthLabel(stock.mention_growth_rate)}
              </td>
              <td className="py-3 px-3">
                <SentimentBadge score={stock.avg_sentiment} />
              </td>
              {!compact && (
                <td className="py-3 px-3 text-right tabular-nums text-muted-foreground">
                  {stock.unique_sources}
                </td>
              )}
              {!compact && (
                <td className="py-3 px-3 text-right text-muted-foreground text-xs">
                  {timeAgo(stock.computed_at)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
