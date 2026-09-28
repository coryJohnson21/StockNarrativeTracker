"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Layers, X } from "lucide-react";
import { SentimentValue } from "./SentimentValue";
import { SignalChip } from "./SignalChip";
import { SignalDelta } from "./SignalDelta";
import { SortableHeader } from "./SortableHeader";
import { getTrendingThemes, type SourceCategory, type MediaChannel } from "@/lib/api";
import type { ThemeTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
  channel?: MediaChannel;
  refreshToken?: number;
  onUntrack?: (name: string) => void;
  /** See TrendingStocksTable: only for a full-page table that owns the scroll. */
  stickyHeader?: boolean;
}

type SortKey = "name" | "score" | "avg_sentiment";

const STRING_KEYS: SortKey[] = ["name"];

export function TrendingThemesTable({ limit = 20, compact = false, category, channel, refreshToken, onUntrack, stickyHeader = false }: Props) {
  const router = useRouter();
  const [themes, setThemes] = useState<ThemeTrending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    setLoading(true);
    getTrendingThemes({ limit, category, channel })
      .then((r) => setThemes(r.themes))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [limit, category, channel, refreshToken]);

  function handleSort(key: string) {
    const k = key as SortKey;
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(STRING_KEYS.includes(k) ? "asc" : "desc");
    }
  }

  const sortedThemes = useMemo(() => {
    const sorted = [...themes].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        return String(av).localeCompare(String(bv));
      }
      return (av as number) - (bv as number);
    });
    if (sortDir === "desc") sorted.reverse();
    return sorted;
  }, [themes, sortKey, sortDir]);

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

  if (themes.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Layers className="h-8 w-8 mx-auto mb-3 opacity-25" />
        <p className="text-sm">No themes tracked yet. Add content to get started.</p>
      </div>
    );
  }

  return (
    <div className={stickyHeader ? "table-scroll" : "overflow-x-auto"}>
      <table className="w-full text-[13px] table-fixed border-collapse">
        <thead>
          <tr className={`${stickyHeader ? "dock-thead" : "[&>*]:border-b [&>*]:border-border"} bg-background text-muted-foreground text-[11px] uppercase tracking-wider`}>
            <th scope="col" className="h-8 px-2.5 text-left font-medium w-9">#</th>
            <SortableHeader label="Theme" sortKey="name" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            <SortableHeader label="Signal" sortKey="score" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[112px]" title="Narrative signal, sorted by momentum score" />
            {!compact && (
              <th scope="col" className="h-8 px-2.5 text-left font-medium w-[88px]" title="Change in signal since the last scoring run">Δ</th>
            )}
            <SortableHeader label="Sent" sortKey="avg_sentiment" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-[96px]" title="Average sentiment (-100..+100) and mention count" />
            {onUntrack && <th scope="col" className="w-8" />}
          </tr>
        </thead>
        <tbody>
          {sortedThemes.map((theme, i) => (
            <tr
              key={theme.id}
              className="border-b border-border/40 hover:bg-accent/40 cursor-pointer transition-colors"
              onClick={() => router.push(`/themes/${encodeURIComponent(theme.name)}`)}
            >
              <td className="px-2.5 py-0 h-8 text-muted-foreground/50 tnum">{i + 1}</td>
              <td className="px-2.5 py-0 h-8 max-w-0">
                <span className="font-medium text-foreground truncate block">{theme.name}</span>
              </td>
              <td className="px-2.5 py-0 h-8">
                <SignalChip label={theme.label} />
              </td>
              {!compact && (
                <td className="px-2.5 py-0 h-8">
                  <SignalDelta current={theme.label} previous={theme.previous_label} />
                </td>
              )}
              <td className="px-2.5 py-0 h-8 text-right">
                <SentimentValue
                  score={theme.avg_sentiment}
                  n={theme.mention_count}
                  confidence={theme.confidence}
                  sources={theme.unique_sources}
                />
              </td>
              {onUntrack && (
                <td className="px-2.5 py-0 h-8 text-right">
                  <button
                    type="button"
                    aria-label={`Stop tracking ${theme.name}`}
                    className="text-muted-foreground/60 hover:text-down transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      onUntrack(theme.name);
                    }}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
