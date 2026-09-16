"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Rss, Youtube, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getPodcastFeeds, pollPodcastFeedNow, pollAllPodcastFeedsNow } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { PodcastFeed } from "@/types";

export default function SubscriptionsPage() {
  const [feeds, setFeeds] = useState<PodcastFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [refreshingAll, setRefreshingAll] = useState(false);

  useEffect(() => {
    getPodcastFeeds()
      .then((r) => setFeeds(r.feeds))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleRefresh(id: string) {
    setRefreshingId(id);
    try {
      await pollPodcastFeedNow(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh feed");
    } finally {
      setRefreshingId(null);
    }
  }

  async function handleRefreshAll() {
    setRefreshingAll(true);
    try {
      await pollAllPodcastFeedsNow();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh feeds");
    } finally {
      setRefreshingAll(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Rss className="h-7 w-7 text-orange-400" />
            Subscriptions
          </h1>
          <p className="text-muted-foreground mt-1">
            Podcast feeds and YouTube channels being auto-ingested
          </p>
        </div>
        {feeds.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            disabled={refreshingAll}
            className="shrink-0"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshingAll ? "animate-spin" : ""}`} />
            Refresh all
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : feeds.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12 text-muted-foreground">
            <Rss className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No subscriptions yet. Add a podcast feed or YouTube channel from Sources.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {feeds.map((feed) => (
            <Link key={feed.id} href={`/subscriptions/${feed.id}`}>
              <Card className="hover:bg-accent/20 transition-colors cursor-pointer h-full">
                <CardContent className="p-4 flex items-center gap-3">
                  {feed.source_type === "youtube" ? (
                    <Youtube className="h-8 w-8 p-1.5 rounded bg-accent text-red-400 shrink-0" />
                  ) : (
                    <Rss className="h-8 w-8 p-1.5 rounded bg-accent text-orange-400 shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-medium truncate">{feed.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {feed.latest_episode_at ? `Last upload ${timeAgo(feed.latest_episode_at)}` : "No episodes yet"}
                    </p>
                  </div>
                  <button
                    type="button"
                    title="Check for new episodes now"
                    className="shrink-0 p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground disabled:opacity-50"
                    disabled={refreshingId === feed.id}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleRefresh(feed.id);
                    }}
                  >
                    <RefreshCw className={`h-4 w-4 ${refreshingId === feed.id ? "animate-spin" : ""}`} />
                  </button>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
