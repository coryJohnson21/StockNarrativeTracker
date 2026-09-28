"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, TrendingUp } from "lucide-react";
import { SentimentValue } from "./SentimentValue";
import { SignalChip } from "./SignalChip";
import { SignalDelta } from "./SignalDelta";
import { SortableHeader } from "./SortableHeader";
import { SymbolStatusBadge } from "./SymbolStatusBadge";
import { MentionSparkline } from "./MentionSparkline";
import { DayChange } from "./DayChange";
import { RsiValue } from "./RsiValue";
import { getTrendingStocks, type SourceCategory, type MediaChannel } from "@/lib/api";
import { formatPrice, formatLargeNumber } from "@/lib/utils";
import type { StockTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
  channel?: MediaChannel;
  /** Pin the header under a docked toolbar (see .dock-thead). Only for a
   *  full-page table that owns the scroll: an embedded 10-row table must leave
   *  this off, or its header floats over its own rows as the page scrolls past. */
  stickyHeader?: boolean;
}

type SortKey =
  | "ticker"
  | "company_name"
  | "score"
  | "avg_sentiment"
  | "mention_count_7d"
  | "current_price"
  | "day_change_pct"
  | "market_cap"
  | "rsi_14";

const STRING_KEYS: SortKey[] = ["ticker", "company_name"];

export function TrendingStocksTable({ limit = 20, compact = false, category, channel, stickyHeader = false }: Props) {
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
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-down p-4">Error: {error}</p>;
  }

  if (stocks.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <TrendingUp className="h-8 w-8 mx-auto mb-3 opacity-25" />
        <p className="text-sm">No stocks tracked yet. Add content to get started.</p>
      </div>
    );
  }

  // Rows carry a hairline divider OR zebra striping, never both. The divider is
  // the quieter of the two at this density.
  const cell = "px-2.5 py-0 h-8";

  return (
    <div className={stickyHeader ? "table-scroll" : "overflow-x-auto"}>
      <table className="w-full text-[13px] table-fixed border-collapse">
        <thead>
          <tr className={`${stickyHeader ? "dock-thead" : "[&>*]:border-b [&>*]:border-border"} bg-background text-muted-foreground text-[11px] uppercase tracking-wider`}>
            <th scope="col" className="h-8 px-2.5 text-left font-medium w-9">
              #
            </th>
            <SortableHeader label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className={compact ? "w-[132px]" : "w-[230px]"} />
            <SortableHeader label="Signal" sortKey="score" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[112px]" title="Narrative signal, sorted by momentum score" />
            {!compact && (
              <th scope="col" className="h-8 px-2.5 text-left font-medium w-[88px]" title="Change in signal since the last scoring run">
                Δ
              </th>
            )}
            <SortableHeader label="Sent" sortKey="avg_sentiment" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[96px]" title="Average sentiment (-100..+100) and mention count" />
            <SortableHeader label="Mentions 7d" sortKey="mention_count_7d" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[120px]" title="Daily mentions over the trailing 7 days" />
            <SortableHeader label="Price" sortKey="current_price" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[92px]" />
            <SortableHeader label="Day" sortKey="day_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[84px]" title="Change between the last two stored daily closes" />
            {!compact && (
              <SortableHeader label="Mkt Cap" sortKey="market_cap" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[88px]" />
            )}
            <SortableHeader label="RSI" sortKey="rsi_14" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[64px]" title="Wilder's 14-period RSI on daily closes" />
          </tr>
        </thead>
        <tbody>
          {sortedStocks.map((stock, i) => (
            <tr
              key={stock.id}
              className="border-b border-border/40 hover:bg-accent/40 cursor-pointer transition-colors"
              onClick={() => router.push(`/stocks/${stock.ticker}`)}
            >
              <td className={`${cell} text-muted-foreground/50 tnum`}>{i + 1}</td>
              <td className={cell}>
                <span className="flex items-baseline gap-1.5 min-w-0">
                  <span className="font-mono font-semibold text-foreground shrink-0">
                    {stock.ticker}
                  </span>
                  {/* Company name rides alongside the ticker instead of holding a
                      column of its own -- it is context for the ticker, and the
                      separate column cost ~180px to repeat what the ticker says. */}
                  <span className="text-muted-foreground/70 truncate text-[12px]">
                    {stock.company_name}
                  </span>
                  <SymbolStatusBadge status={stock.symbol_status} className="shrink-0" />
                </span>
              </td>
              <td className={cell}>
                <span className="flex items-center gap-1.5">
                  <SignalChip label={stock.label} />
                  {/* Only surfaces when it applies. "Echo" on every row was noise. */}
                  {stock.novelty_7d != null &&
                    stock.mention_count_7d > 0 &&
                    stock.novelty_7d >= 0.5 && (
                      <span
                        className="text-[9px] uppercase tracking-wide text-primary/90 cursor-help"
                        title={`Novelty ${stock.novelty_7d.toFixed(2)} — new things are being said this week, not a rehash of earlier coverage.`}
                      >
                        new
                      </span>
                    )}
                </span>
              </td>
              {!compact && (
                <td className={cell}>
                  <SignalDelta current={stock.label} previous={stock.previous_label} />
                </td>
              )}
              <td className={`${cell} text-right`}>
                <SentimentValue
                  score={stock.avg_sentiment}
                  n={stock.mention_count}
                  confidence={stock.confidence}
                  sources={stock.unique_sources}
                />
              </td>
              <td className={`${cell} text-right`}>
                <MentionSparkline data={stock.mention_spark_7d} />
              </td>
              <td className={`${cell} text-right tnum text-foreground`}>
                {stock.is_public === false ? (
                  <span className="text-muted-foreground/60 text-[12px]">Private</span>
                ) : (
                  formatPrice(stock.current_price)
                )}
              </td>
              <td className={`${cell} text-right`}>
                {stock.is_public === false ? (
                  <span className="text-muted-foreground/40">·</span>
                ) : (
                  <DayChange value={stock.day_change_pct} />
                )}
              </td>
              {!compact && (
                <td className={`${cell} text-right tnum text-muted-foreground`}>
                  {stock.is_public === false || !stock.market_cap ? (
                    <span className="text-muted-foreground/40">·</span>
                  ) : (
                    `$${formatLargeNumber(stock.market_cap)}`
                  )}
                </td>
              )}
              <td className={`${cell} text-right`}>
                {stock.is_public === false ? (
                  <span className="text-muted-foreground/40">·</span>
                ) : (
                  <RsiValue value={stock.rsi_14} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
