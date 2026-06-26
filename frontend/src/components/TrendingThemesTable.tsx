"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Layers } from "lucide-react";
import { SentimentBadge } from "./SentimentBadge";
import { MomentumBar } from "./MomentumBadge";
import { SortableHeader } from "./SortableHeader";
import { getTrendingThemes, type SourceCategory, type MediaChannel } from "@/lib/api";
import { growthLabel, growthColor, timeAgo } from "@/lib/utils";
import type { ThemeTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
  channel?: MediaChannel;
}

type SortKey =
  | "name"
  | "score"
  | "mention_count"
  | "mention_growth_rate"
  | "avg_sentiment"
  | "unique_sources"
  | "computed_at";

const STRING_KEYS: SortKey[] = ["name"];

export function TrendingThemesTable({ limit = 20, compact = false, category, channel }: Props) {
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
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-red-400 p-4">Error: {error}</p>;
  }

  if (themes.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Layers className="h-10 w-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No themes tracked yet. Add content to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm table-fixed">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3 w-8">#</th>
            <SortableHeader label="Theme" sortKey="name" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            <SortableHeader label="Momentum" sortKey="score" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-32" />
            <SortableHeader label="Mentions" sortKey="mention_count" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-16" />
            <SortableHeader label="7d Growth" sortKey="mention_growth_rate" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" className="w-20" />
            <SortableHeader label="Sentiment" sortKey="avg_sentiment" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-20" />
            {!compact && (
              <SortableHeader label="Sources" sortKey="unique_sources" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" />
            )}
            {!compact && (
              <SortableHeader label="Updated" sortKey="computed_at" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} align="right" />
            )}
          </tr>
        </thead>
        <tbody>
          {sortedThemes.map((theme, i) => (
            <tr
              key={theme.id}
              className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/themes/${encodeURIComponent(theme.name)}`)}
            >
              <td className="py-3 px-3 text-muted-foreground">{i + 1}</td>
              <td className="py-3 px-3 max-w-0">
                <span className="font-semibold text-foreground truncate block">{theme.name}</span>
              </td>
              <td className="py-3 px-3">
                <MomentumBar score={theme.score} />
              </td>
              <td className="py-3 px-3 text-right tabular-nums">{theme.mention_count}</td>
              <td className={`py-3 px-3 text-right tabular-nums font-medium ${growthColor(theme.mention_growth_rate)}`}>
                {growthLabel(theme.mention_growth_rate)}
              </td>
              <td className="py-3 px-3">
                <SentimentBadge score={theme.avg_sentiment} />
              </td>
              {!compact && (
                <td className="py-3 px-3 text-right tabular-nums text-muted-foreground">
                  {theme.unique_sources}
                </td>
              )}
              {!compact && (
                <td className="py-3 px-3 text-right text-muted-foreground text-xs">
                  {timeAgo(theme.computed_at)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
