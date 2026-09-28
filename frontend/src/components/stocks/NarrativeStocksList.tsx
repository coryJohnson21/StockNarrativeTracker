"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, TrendingUp, X } from "lucide-react";
import type { StockTrending, Stage } from "@/types";
import { getTrendingStocks, type SourceCategory, type MediaChannel } from "@/lib/api";
import { isStage } from "@/lib/stages";
import { SignalFilterPills } from "./SignalFilterPills";
import { StockRow, ROW_GRID, COL1_GRID } from "./StockRow";
import { StockDetailPanel } from "./StockDetailPanel";

type SortKey =
  | "ticker"
  | "score"
  | "themes"
  | "avg_sentiment"
  | "current_price"
  | "market_cap"
  | "rsi_14";

const STRING_KEYS: SortKey[] = ["ticker", "themes"];

/** Below this width the detail panel stops being a column and becomes a drawer:
 *  at 1100px the two-column layout leaves the list too narrow for the narrative
 *  text that is the whole point of the design. */
const PANEL_BREAKPOINT = 1100;

interface Props {
  limit?: number;
  category?: SourceCategory;
  channel?: MediaChannel;
}

export function NarrativeStocksList({ limit = 100, category, channel }: Props) {
  const router = useRouter();
  const [stocks, setStocks] = useState<StockTrending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [stageFilter, setStageFilter] = useState<Stage | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [wide, setWide] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    getTrendingStocks({ limit, category, channel })
      .then((r) => setStocks(r.stocks))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [limit, category, channel]);

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${PANEL_BREAKPOINT}px)`);
    const apply = () => setWide(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(STRING_KEYS.includes(key) ? "asc" : "desc");
    }
  }

  /** Counts come from the whole dataset, never the filtered view, so the pills
   *  keep describing the full list once one of them is active. */
  const stageCounts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const s of stocks) if (isStage(s.label)) out[s.label] = (out[s.label] ?? 0) + 1;
    return out;
  }, [stocks]);

  const changedToday = useMemo(
    () => stocks.filter((s) => s.previous_label && s.previous_label !== s.label).length,
    [stocks]
  );

  const visible = useMemo(() => {
    const rows = stageFilter ? stocks.filter((s) => s.label === stageFilter) : [...stocks];
    const dir = sortDir === "desc" ? -1 : 1;

    return rows.sort((a, b) => {
      // Sorting by "themes" means the first theme's name -- what the column
      // actually shows -- not a count the row never displays.
      const av = sortKey === "themes" ? a.themes?.[0] ?? null : a[sortKey as keyof StockTrending];
      const bv = sortKey === "themes" ? b.themes?.[0] ?? null : b[sortKey as keyof StockTrending];

      // Missing sinks to the bottom in both directions -- unknown is not "large".
      const aMissing = av == null || ((sortKey === "market_cap" || sortKey === "current_price") && av === 0);
      const bMissing = bv == null || ((sortKey === "market_cap" || sortKey === "current_price") && bv === 0);
      if (aMissing || bMissing) return aMissing && bMissing ? 0 : aMissing ? 1 : -1;

      if (typeof av === "string" || typeof bv === "string") {
        return String(av).localeCompare(String(bv)) * dir;
      }
      return ((av as number) - (bv as number)) * dir;
    });
  }, [stocks, stageFilter, sortKey, sortDir]);

  // Default to the first row, and keep the selection valid when filtering or
  // sorting removes whatever was selected.
  useEffect(() => {
    if (visible.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !visible.some((s) => s.id === selectedId)) {
      setSelectedId(visible[0].id);
    }
  }, [visible, selectedId]);

  const selected = useMemo(
    () => visible.find((s) => s.id === selectedId) ?? null,
    [visible, selectedId]
  );

  const select = useCallback(
    (id: string) => {
      setSelectedId(id);
      if (!wide) setDrawerOpen(true);
    },
    [wide]
  );

  /** ↑/↓ move the selection, Enter opens full research. Ignored while the user
   *  is typing, so the page search box keeps its own arrow-key behaviour. */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = document.activeElement as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      if (visible.length === 0) return;

      const i = visible.findIndex((s) => s.id === selectedId);
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedId(visible[Math.min(i + 1, visible.length - 1)].id);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedId(visible[Math.max(i - 1, 0)].id);
      } else if (e.key === "Enter" && selected) {
        e.preventDefault();
        router.push(`/stocks/${selected.ticker}`);
      } else if (e.key === "Escape" && drawerOpen) {
        setDrawerOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible, selectedId, selected, router, drawerOpen]);

  // Keep the keyboard-selected row within view as it moves.
  useEffect(() => {
    if (!selectedId || !listRef.current) return;
    listRef.current
      .querySelector(`[data-row-id="${selectedId}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (error) return <p className="p-4 text-sm text-down">Error: {error}</p>;
  if (stocks.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <TrendingUp className="mx-auto mb-3 h-8 w-8 opacity-25" />
        <p className="text-sm">No stocks tracked yet. Add content to get started.</p>
      </div>
    );
  }

  const header = (label: string, key: SortKey, align: "left" | "right" = "left") => {
    const active = sortKey === key;
    return (
      <button
        type="button"
        onClick={() => handleSort(key)}
        className={`font-mono text-[11px] font-medium tracking-[0.06em] transition-colors ${
          align === "right" ? "text-right" : "text-left"
        } ${active ? "text-[#e8e6e3]" : "text-[#6f6f75] hover:text-[#a9a7a3]"}`}
      >
        {label}
        <span aria-hidden="true" className={active ? "ml-1" : "ml-1 opacity-0"}>
          {sortDir === "asc" ? "▴" : "▾"}
        </span>
      </button>
    );
  };

  return (
    <div
      className="grid"
      style={{ gridTemplateColumns: wide ? "minmax(0,1fr) 340px" : "minmax(0,1fr)" }}
    >
      <div className={wide ? "border-r border-[#1c1c1f]" : ""}>
        <div className="flex items-end justify-between gap-4 px-[22px] pb-3 pt-1 flex-wrap">
          <div>
            <h1 className="text-[18px] font-semibold leading-tight">Stocks</h1>
            <p className="font-mono text-[12px] text-[#6f6f75]">
              {changedToday} changed signal today
            </p>
          </div>
          <SignalFilterPills counts={stageCounts} active={stageFilter} onChange={setStageFilter} />
        </div>

        {/* Sticky column header, on the same grid as the rows. */}
        <div
          className="dock-thead-1b grid items-center gap-4 border-b border-[#1c1c1f] bg-background px-[22px] py-[10px]"
          style={{ gridTemplateColumns: ROW_GRID }}
        >
          <div className="grid min-w-0 gap-[14px]" style={{ gridTemplateColumns: COL1_GRID }}>
            {header("TICKER", "ticker")}
            {header("SIGNAL", "score")}
            {header("THEMES · WHY", "themes")}
          </div>
          {header("SENTIMENT", "avg_sentiment")}
          <div className="text-right">{header("PRICE", "current_price", "right")}</div>
          <div className="text-right">{header("MKT CAP", "market_cap", "right")}</div>
          <div className="text-right">{header("RSI", "rsi_14", "right")}</div>
        </div>

        <div ref={listRef} role="rowgroup">
          {visible.map((s) => (
            <div key={s.id} data-row-id={s.id}>
              <StockRow stock={s} selected={s.id === selectedId} onSelect={() => select(s.id)} />
            </div>
          ))}
          {visible.length === 0 && (
            <p className="px-[22px] py-8 text-center text-[13px] text-[#6f6f75]">
              No stocks in this stage.
            </p>
          )}
        </div>
      </div>

      {wide && selected && <StockDetailPanel stock={selected} />}

      {/* Narrow viewports: the panel becomes a dismissible drawer instead of
          stealing width the narrative columns need. */}
      {!wide && drawerOpen && selected && (
        <div className="fixed inset-0 z-50 flex">
          <button
            aria-label="Close details"
            className="flex-1 bg-black/60"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative w-[min(360px,88vw)] overflow-y-auto border-l border-[#1c1c1f] bg-background">
            <button
              type="button"
              aria-label="Close details"
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-3 z-10 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
            <StockDetailPanel stock={selected} />
          </div>
        </div>
      )}
    </div>
  );
}
