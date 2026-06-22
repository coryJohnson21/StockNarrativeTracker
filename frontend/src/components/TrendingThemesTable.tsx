"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Layers } from "lucide-react";
import { SentimentBadge } from "./SentimentBadge";
import { MomentumBar } from "./MomentumBadge";
import { getTrendingThemes, type SourceCategory } from "@/lib/api";
import { growthLabel, growthColor, timeAgo } from "@/lib/utils";
import type { ThemeTrending } from "@/types";

interface Props {
  limit?: number;
  compact?: boolean;
  category?: SourceCategory;
}

export function TrendingThemesTable({ limit = 20, compact = false, category }: Props) {
  const router = useRouter();
  const [themes, setThemes] = useState<ThemeTrending[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getTrendingThemes({ limit, category })
      .then((r) => setThemes(r.themes))
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
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3 w-8">#</th>
            <th className="text-left py-2 px-3">Theme</th>
            <th className="text-left py-2 px-3">Momentum</th>
            <th className="text-right py-2 px-3">Mentions</th>
            <th className="text-right py-2 px-3">7d Growth</th>
            <th className="text-left py-2 px-3">Sentiment</th>
            {!compact && <th className="text-right py-2 px-3">Sources</th>}
            {!compact && <th className="text-right py-2 px-3">Updated</th>}
          </tr>
        </thead>
        <tbody>
          {themes.map((theme, i) => (
            <tr
              key={theme.id}
              className="border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/themes/${encodeURIComponent(theme.name)}`)}
            >
              <td className="py-3 px-3 text-muted-foreground">{i + 1}</td>
              <td className="py-3 px-3">
                <span className="font-semibold text-foreground">{theme.name}</span>
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
