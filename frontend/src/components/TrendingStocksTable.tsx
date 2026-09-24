"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, TrendingUp } from "lucide-react";
import { SentimentBadge } from "./SentimentBadge";
import { SignalChip } from "./SignalChip";
import { SortableHeader } from "./SortableHeader";
import { SymbolStatusBadge } from "./SymbolStatusBadge";
import { RsiValue } from "./RsiValue";
import { getTrendingStocks, type SourceCategory, type MediaChannel } from "@/lib/api";
import { formatPrice, formatLargeNumber } from "@/lib/utils";
import type { StockTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
  channel?: MediaChannel;
}

type SortKey =
  | "ticker"
  | "company_name"
  | "score"
  | "avg_sentiment"
  | "current_price"
  | "market_cap"
  | "rsi_14";

const STRING_KEYS: SortKey[] = ["ticker", "company_name"];

export function TrendingStocksTable({ limit = 20, compact = false, category, channel }: Props) {
  const router = useRouter();
  const [stocks, setStocks] = useState<StockTrending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    setLoading(true);
    getTrendingStocks({ limit, category, channel })
      .then((r) => setStocks(r.stocks))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [limit, category, channel]);

  function handleSort(key: string) {
    const k = key as SortKey;
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(STRING_KEYS.includes(k) ? "asc" : "desc");
    }
  }

  /** A private company, an ETF, or an unpriced ticker has no market cap or price to
   *  rank. Treat those as "missing" rather than as a number: zero is how the API
   *  spells absent for some feeds, and a real traded stock never has either at 0. */
  function isMissing(key: SortKey, v: unknown): boolean {
    if (v == null) return true;
    return (key === "market_cap" || key === "current_price") && v === 0;
  }

  const sortedStocks = useMemo(() => {
    const dir = sortDir === "desc" ? -1 : 1;
    return [...stocks].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      // Missing values sink to the bottom in BOTH directions -- they are unknown,
      // not "larger than every real value". Sorting the array and reversing it
      // would carry them to the top of a descending sort.
      const aMissing = isMissing(sortKey, av);
      const bMissing = isMissing(sortKey, bv);
      if (aMissing || bMissing) return aMissing && bMissing ? 0 : aMissing ? 1 : -1;
      if (typeof av === "string" || typeof bv === "string") {
        return String(av).localeCompare(String(bv)) * dir;
      }
      return ((av as number) - (bv as number)) * dir;
    });
  }, [stocks, sortKey, sortDir]);

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
      <table className="w-full text-sm table-fixed">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3 w-8">#</th>
            <SortableHeader label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-20" />
            {!compact && (
              <SortableHeader label="Company" sortKey="company_name" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            )}
            <th className="text-left py-2 px-3 w-28">Signal</th>
            {!compact && (
              <th className="text-left py-2 px-3 w-24 text-muted-foreground">Previous</th>
            )}
            <SortableHeader label="Sentiment" sortKey="avg_sentiment" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-32" />
            {!compact && (
              <>
                <SortableHeader label="Price" sortKey="current_price" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-24" />
                <SortableHeader label="Mkt Cap" sortKey="market_cap" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-24" />
                <SortableHeader label="RSI 14" sortKey="rsi_14" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-20" />
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedStocks.map((stock, i) => (
            <tr
              key={stock.id}
              className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/stocks/${stock.ticker}`)}
            >
              <td className="py-3 px-3 text-muted-foreground">{i + 1}</td>
              <td className="py-3 px-3">
                {/* Stacked, not inline: the ticker column is too narrow to hold both
                    without the badge wrapping into the company name beside it. */}
                <span className="font-bold text-foreground font-mono">{stock.ticker}</span>
                <SymbolStatusBadge status={stock.symbol_status} className="mt-1 flex w-fit" />
              </td>
              {!compact && (
                <td className="py-3 px-3 text-muted-foreground truncate max-w-0">
                  {stock.company_name || "—"}
                </td>
              )}
              <td className="py-3 px-3">
                <div className="flex items-center gap-1.5">
                  <SignalChip label={stock.label} />
                  {stock.novelty_7d != null && stock.mention_count_7d > 0 && (
                    <span
                      className={`text-[10px] uppercase tracking-wide ${stock.novelty_7d >= 0.5 ? "text-violet-400" : "text-muted-foreground/70"}`}
                      title={`Novelty ${stock.novelty_7d.toFixed(2)} — ${stock.novelty_7d >= 0.5 ? "new things are being said this week" : "this week mostly repeats earlier coverage"}`}
                    >
                      {stock.novelty_7d >= 0.5 ? "new" : "echo"}
                    </span>
                  )}
                </div>
              </td>
              {!compact && (
                <td className="py-3 px-3">
                  <SignalChip label={stock.previous_label} dim />
                </td>
              )}
              <td className="py-3 px-3">
                <div className="flex items-center gap-2">
                  <SentimentBadge score={stock.avg_sentiment} />
                  <span
                    className={`text-[10px] tabular-nums ${stock.confidence === "low" ? "text-amber-500" : "text-muted-foreground"}`}
                    title={`${stock.mention_count} mentions across ${stock.unique_sources} sources — ${stock.confidence ?? "unknown"} confidence`}
                  >
                    n={stock.mention_count}
                  </span>
                </div>
              </td>
              {!compact && (
                <>
                  <td className="py-3 px-3 text-right tabular-nums text-foreground">
                    {stock.is_public === false
                      ? <span className="text-muted-foreground text-xs">Private</span>
                      : formatPrice(stock.current_price)}
                  </td>
                  <td className="py-3 px-3 text-right tabular-nums text-muted-foreground">
                    {stock.is_public === false
                      ? <span className="text-xs">Private</span>
                      : stock.market_cap ? `$${formatLargeNumber(stock.market_cap)}` : "—"}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {stock.is_public === false
                      ? <span className="text-xs text-muted-foreground">Private</span>
                      : <RsiValue value={stock.rsi_14} />}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
