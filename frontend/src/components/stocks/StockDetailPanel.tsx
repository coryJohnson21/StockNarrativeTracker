"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Star, Loader2 } from "lucide-react";
import type { StockTrending, SignalTransition } from "@/types";
import { stageColor, stageLabel, isStage } from "@/lib/stages";
import { getStockSignalHistory, addToWatchlist, removeFromWatchlist, getWatchlist } from "@/lib/api";
import { formatLargeNumber } from "@/lib/utils";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[11px] font-semibold tracking-[0.08em] text-[#6f6f75]">
      {children}
    </div>
  );
}

const MIX_ROWS = [
  { key: "filings", label: "Filings" },
  { key: "media", label: "Media" },
  { key: "reddit", label: "Reddit" },
] as const;

export function StockDetailPanel({ stock }: { stock: StockTrending }) {
  const [history, setHistory] = useState<SignalTransition[] | null>(null);
  const [watched, setWatched] = useState(false);
  const [busy, setBusy] = useState(false);

  // Signal history is one query per stock, so it is fetched only for the
  // selected row rather than for all 100 in the list.
  useEffect(() => {
    let alive = true;
    setHistory(null);
    getStockSignalHistory(stock.ticker)
      .then((r) => alive && setHistory(r.history))
      .catch(() => alive && setHistory([]));
    return () => {
      alive = false;
    };
  }, [stock.ticker]);

  useEffect(() => {
    let alive = true;
    getWatchlist()
      .then((r) => alive && setWatched(r.items.some((i) => i.ticker === stock.ticker)))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [stock.ticker]);

  async function toggleWatch() {
    setBusy(true);
    const next = !watched;
    try {
      if (next) await addToWatchlist(stock.ticker);
      else await removeFromWatchlist(stock.ticker);
      setWatched(next);
    } catch {
      /* Leave the toggle where it was if the call failed. */
    } finally {
      setBusy(false);
    }
  }

  const mix = stock.source_mix;
  const mixTotal = mix ? mix.filings + mix.media + mix.reddit : 0;

  return (
    <div className="sticky top-11 max-h-[calc(100vh-2.75rem)] overflow-y-auto px-5 py-5 space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-[22px] font-semibold leading-none text-foreground">
            {stock.ticker}
          </div>
          <div className="mt-1.5 truncate text-[13px] text-[#7c7c82]">{stock.company_name}</div>
        </div>
        <button
          type="button"
          onClick={toggleWatch}
          disabled={busy}
          aria-pressed={watched}
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-sm border px-2 py-1 text-[12px] transition-colors ${
            watched
              ? "border-[#e8b04a]/40 text-[#e8b04a]"
              : "border-[#26262a] text-muted-foreground hover:text-foreground"
          }`}
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Star className="h-3 w-3" fill={watched ? "currentColor" : "none"} />
          )}
          {watched ? "Watching" : "Watch"}
        </button>
      </div>

      {stock.summary && (
        <div className="space-y-1.5">
          <SectionLabel>WHY IT&apos;S MOVING</SectionLabel>
          <p className="text-[14px] leading-[1.5] text-foreground/90">{stock.summary}</p>
        </div>
      )}

      {(stock.themes?.length ?? 0) > 0 && (
        <div className="space-y-1.5">
          <SectionLabel>THEMES</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {stock.themes!.map((t) => (
              <Link
                key={t}
                href={`/themes/${encodeURIComponent(t)}`}
                className="rounded-sm border border-[#26262a] px-1.5 py-0.5 text-[12px] text-[#cfcdc9] hover:border-[#35353b] hover:text-foreground transition-colors"
              >
                {t}
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <SectionLabel>SIGNAL HISTORY</SectionLabel>
        {history === null ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : history.length === 0 ? (
          <p className="text-[12px] text-[#6f6f75]">No recorded transitions yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {history.map((h) => (
              <li key={`${h.date}-${h.stage}`} className="flex items-center gap-2.5 text-[12px]">
                <span className="font-mono text-[#6f6f75]">{h.date}</span>
                <span
                  aria-hidden="true"
                  className="h-1.5 w-1.5 rounded-full shrink-0"
                  style={{ background: stageColor(h.stage) }}
                />
                <span style={{ color: stageColor(h.stage) }}>
                  {isStage(h.stage) ? stageLabel(h.stage) : h.stage}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {mix && mixTotal > 0 && (
        <div className="space-y-2">
          <SectionLabel>SOURCE MIX · {mixTotal} MENTIONS</SectionLabel>
          <div className="space-y-1.5">
            {MIX_ROWS.map(({ key, label }) => {
              const n = mix[key];
              return (
                <div key={key} className="flex items-center gap-2.5 text-[12px]">
                  <span className="w-12 shrink-0 text-[#7c7c82]">{label}</span>
                  <div className="h-1 flex-1 rounded-full bg-[#1f1f23] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#4a4a52]"
                      style={{ width: `${mixTotal ? (n / mixTotal) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="w-8 shrink-0 text-right font-mono text-[#6f6f75]">{n}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 border-t border-[#1c1c1f] pt-4">
        <div>
          <SectionLabel>MKT CAP</SectionLabel>
          <div className="mt-1 font-mono text-[13px] text-foreground">
            {stock.market_cap ? `$${formatLargeNumber(stock.market_cap)}` : "·"}
          </div>
        </div>
        <div>
          <SectionLabel>RSI</SectionLabel>
          <div className="mt-1 font-mono text-[13px] text-foreground">
            {stock.rsi_14 != null ? stock.rsi_14.toFixed(1) : "·"}
          </div>
        </div>
        <div>
          <SectionLabel>DAY</SectionLabel>
          <div
            className="mt-1 font-mono text-[13px]"
            style={{
              color:
                stock.day_change_pct == null
                  ? undefined
                  : stock.day_change_pct >= 0
                  ? "var(--up-c)"
                  : "var(--down-c)",
            }}
          >
            {stock.day_change_pct == null
              ? "·"
              : `${stock.day_change_pct >= 0 ? "+" : ""}${stock.day_change_pct.toFixed(2)}%`}
          </div>
        </div>
      </div>

      <Link
        href={`/stocks/${stock.ticker}`}
        className="block rounded-sm bg-[#e8e6e3] px-3 py-2 text-center text-[13px] font-medium text-[#0b0b0c] hover:bg-white transition-colors"
      >
        Open full research →
      </Link>
    </div>
  );
}
