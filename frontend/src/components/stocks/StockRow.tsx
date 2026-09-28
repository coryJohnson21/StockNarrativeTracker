"use client";

import type { StockTrending } from "@/types";
import { stageColor, stageLabel, stageDirection, isStage } from "@/lib/stages";
import { formatPrice, formatLargeNumber } from "@/lib/utils";

/** The grid both the rows and the sticky header row use. Declared once and
 *  imported by the header so the two can never drift out of alignment -- the
 *  whole point of this layout is that signal, themes and why line up in straight
 *  columns down the page. */
export const ROW_GRID = "minmax(0,1fr) 140px 96px 70px 64px";
export const COL1_GRID = "140px 112px minmax(0,1fr)";

function Sentiment({ score, sources }: { score: number; sources: number }) {
  // Scale runs -100..+100; the bar shows magnitude, the colour shows sign.
  const pct = Math.min(100, Math.abs(score));
  const positive = score >= 0;
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="font-mono text-[12px]"
          style={{ color: positive ? "var(--up-c)" : "var(--down-c)" }}
        >
          {positive ? "+" : ""}
          {Math.round(score)}
        </span>
        <span className="font-mono text-[11px] text-[#6f6f75]">{sources} src</span>
      </div>
      <div className="mt-1 h-1 w-full rounded-full bg-[#1f1f23] overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: positive ? "var(--up-c)" : "var(--down-c)",
          }}
        />
      </div>
    </div>
  );
}

export function StockRow({
  stock,
  selected,
  onSelect,
}: {
  stock: StockTrending;
  selected: boolean;
  onSelect: () => void;
}) {
  const dir = stageDirection(stock.previous_label, stock.label);
  const themes = stock.themes ?? [];
  const rsi = stock.rsi_14;
  const overbought = rsi != null && rsi >= 70;
  const oversold = rsi != null && rsi <= 30;

  return (
    <div
      role="row"
      tabIndex={-1}
      aria-selected={selected}
      onClick={onSelect}
      className={`grid items-start gap-4 px-[22px] py-[14px] cursor-pointer border-b border-[#161618] transition-colors ${
        selected ? "bg-[#16161a] shadow-[inset_3px_0_0_#e8e6e3]" : "hover:bg-[#141417]"
      }`}
      style={{ gridTemplateColumns: ROW_GRID }}
    >
      {/* Column 1: ticker, signal and narrative, each on its own sub-column so
          they align vertically across every row. */}
      <div className="grid min-w-0 gap-[14px] items-start" style={{ gridTemplateColumns: COL1_GRID }}>
        <div className="min-w-0">
          <div className="font-mono text-[15px] font-semibold text-foreground">{stock.ticker}</div>
          <div className="truncate text-[12px] text-[#7c7c82]">{stock.company_name}</div>
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full shrink-0"
              style={{ background: stageColor(stock.label) }}
            />
            <span className="text-[13px] font-medium" style={{ color: stageColor(stock.label) }}>
              {isStage(stock.label) ? stageLabel(stock.label) : "—"}
            </span>
            {stock.is_new && (
              <span className="font-mono text-[10px] font-semibold text-[#e8b04a]">NEW</span>
            )}
          </div>
          {/* Only rendered on an actual change -- no "·" placeholder, so the eye
              can scan this sub-column for the rows that moved. */}
          {dir && (
            <div
              className="ml-[13px] mt-0.5 text-[11.5px]"
              style={{ color: dir === "up" ? "var(--up-c)" : "var(--down-c)" }}
            >
              {dir === "up" ? "↑" : "↓"} from {stageLabel(stock.previous_label as never)}
            </div>
          )}
        </div>

        <div className="min-w-0">
          {themes.length > 0 && (
            <div className="truncate text-[13px] text-[#cfcdc9]">{themes.join("  ·  ")}</div>
          )}
          {stock.summary && (
            <div className="truncate text-[13px] text-[#7c7c82]" title={stock.summary}>
              {stock.summary}
            </div>
          )}
        </div>
      </div>

      <Sentiment score={stock.avg_sentiment} sources={stock.unique_sources} />

      <div className="text-right font-mono">
        <div className="text-[14px] text-foreground">
          {stock.is_public === false ? (
            <span className="text-[12px] text-[#6f6f75]">Private</span>
          ) : (
            formatPrice(stock.current_price)
          )}
        </div>
        {stock.day_change_pct != null && (
          <div
            className="text-[12px]"
            style={{
              color: stock.day_change_pct >= 0 ? "var(--up-c)" : "var(--down-c)",
            }}
          >
            {stock.day_change_pct >= 0 ? "+" : ""}
            {stock.day_change_pct.toFixed(2)}%
          </div>
        )}
      </div>

      <div className="text-right font-mono text-[13px] text-[#a9a7a3]">
        {stock.market_cap ? `$${formatLargeNumber(stock.market_cap)}` : "·"}
      </div>

      <div className="text-right font-mono text-[13px]">
        {rsi == null ? (
          <span className="text-[#6f6f75]">·</span>
        ) : overbought || oversold ? (
          <span
            className="inline-block rounded px-1 py-0.5 text-[11px]"
            style={
              overbought
                ? { background: "oklch(0.35 0.08 70)", color: "oklch(0.9 0.12 80)" }
                : { background: "oklch(0.32 0.08 25)", color: "oklch(0.88 0.12 25)" }
            }
          >
            {overbought ? "OB" : "OS"} {rsi.toFixed(1)}
          </span>
        ) : (
          <span className="text-[#a9a7a3]">{rsi.toFixed(1)}</span>
        )}
      </div>
    </div>
  );
}
