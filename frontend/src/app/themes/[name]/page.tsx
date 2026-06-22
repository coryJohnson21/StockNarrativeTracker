"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, Landmark, Newspaper, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SentimentBadge } from "@/components/SentimentBadge";
import { MomentumBar } from "@/components/MomentumBadge";
import { getThemeProfile } from "@/lib/api";
import type { ThemeProfile } from "@/types";

export default function ThemeDetailPage() {
  const params = useParams();
  const name = decodeURIComponent((params.name as string) || "");

  const [profile, setProfile] = useState<ThemeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    getThemeProfile(name)
      .then(setProfile)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [name]);

  return (
    <div className="space-y-6">
      <Link href="/themes" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
        <ArrowLeft className="h-4 w-4" />
        Back to Trending Themes
      </Link>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : profile ? (
        <>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                <Layers className="h-7 w-7 text-purple-400" />
                {profile.name}
              </h1>
            </div>
            {profile.momentum_score !== undefined && profile.momentum_score !== null && (
              <div className="text-right">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Momentum Score</p>
                <MomentumBar score={profile.momentum_score} />
              </div>
            )}
          </div>

          {profile.description && (
            <Card>
              <CardContent className="pt-6 text-sm leading-relaxed text-muted-foreground">
                {profile.description}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Narrative Momentum</CardTitle>
              <CardDescription>Where mentions are coming from and what the sentiment looks like.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Landmark className="h-4 w-4 text-emerald-400" />
                    Press Releases & Earnings
                  </div>
                  <p className="text-2xl font-bold tabular-nums">
                    {profile.mention_breakdown.filing.mention_count}{" "}
                    <span className="text-sm font-normal text-muted-foreground">mentions</span>
                  </p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{profile.mention_breakdown.filing.unique_sources} source(s)</span>
                    <SentimentBadge score={profile.mention_breakdown.filing.avg_sentiment} showNumber />
                  </div>
                </div>

                <div className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Newspaper className="h-4 w-4 text-blue-400" />
                    Media Tracking
                  </div>
                  <p className="text-2xl font-bold tabular-nums">
                    {profile.mention_breakdown.media.mention_count}{" "}
                    <span className="text-sm font-normal text-muted-foreground">mentions</span>
                  </p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{profile.mention_breakdown.media.unique_sources} source(s)</span>
                    <SentimentBadge score={profile.mention_breakdown.media.avg_sentiment} showNumber />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {profile.top_stocks.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Most Associated Stocks</CardTitle>
                <CardDescription>Stocks most often mentioned alongside this theme.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <tbody>
                    {profile.top_stocks.map((stock) => (
                      <tr key={stock.ticker} className="border-b border-border/50 last:border-0">
                        <td className="py-2.5 px-6">
                          <Link href={`/stocks/${stock.ticker}`} className="font-bold font-mono hover:text-primary hover:underline">
                            {stock.ticker}
                          </Link>
                          <span className="text-muted-foreground ml-2 text-xs">{stock.company_name}</span>
                        </td>
                        <td className="py-2.5 px-6 text-right text-muted-foreground tabular-nums">
                          {stock.co_mentions} co-mention{stock.co_mentions === 1 ? "" : "s"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
