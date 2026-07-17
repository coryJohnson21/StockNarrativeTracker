"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Layers, X } from "lucide-react";
import { SentimentBadge } from "./SentimentBadge";
import { SignalChip } from "./SignalChip";
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
}

type SortKey = "name" | "score" | "avg_sentiment";

const STRING_KEYS: SortKey[] = ["name"];

export function TrendingThemesTable({ limit = 20, compact = false, category, channel, refreshToken, onUntrack }: Props) {
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
            <th className="text-left py-2 px-3 w-28">Signal</th>
            {!compact && (
              <th className="text-left py-2 px-3 w-24 text-muted-foreground">Previous</th>
            )}
            <SortableHeader label="Sentiment" sortKey="avg_sentiment" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-32" />
            {onUntrack && <th className="w-8" />}
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
                <SignalChip label={theme.label} />
              </td>
              {!compact && (
                <td className="py-3 px-3">
                  <SignalChip label={theme.previous_label} dim />
                </td>
              )}
              <td className="py-3 px-3">
                <SentimentBadge score={theme.avg_sentiment} />
              </td>
              {onUntrack && (
                <td className="py-3 px-3 text-right">
                  <button
                    type="button"
                    aria-label={`Stop tracking ${theme.name}`}
                    className="text-muted-foreground hover:text-red-400 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      onUntrack(theme.name);
                    }}
                  >
                    <X className="h-4 w-4" />
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
