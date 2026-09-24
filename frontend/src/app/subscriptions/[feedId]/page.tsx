"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Rss, Youtube, Loader2, AlertCircle, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getPodcastFeedDetail, getSourceExtractions, pollPodcastFeedNow } from "@/lib/api";
import type { SourceExtractions } from "@/lib/api";
import { timeAgo, formatDuration } from "@/lib/utils";
import type { PodcastFeedDetail, PodcastEpisode } from "@/types";
import { ExtractionDetailGrid } from "@/components/ExtractionDetailGrid";
import { TrackRecordPanel } from "@/components/TrackRecordPanel";

const statusVariant: Record<string, "default" | "secondary" | "bullish" | "bearish" | "neutral"> = {
  completed: "bullish",
  processing: "neutral",
  pending: "secondary",
  failed: "bearish",
};

function EpisodeDetail({ sourceId }: { sourceId: string }) {
  const [data, setData] = useState<SourceExtractions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSourceExtractions(sourceId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sourceId]);

  if (loading) return (
    <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading breakdown…
    </div>
  );
  if (error) return <p className="py-4 text-sm text-red-400">{error}</p>;
  if (!data) return null;

  return (
    <div className="pt-4">
      <ExtractionDetailGrid calls={data.calls} stocks={data.stocks} themes={data.themes} />
    </div>
  );
}

function EpisodeRow({ episode }: { episode: PodcastEpisode }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = episode.status === "completed";

  return (
    <Card>
      <CardContent className="p-4">
        <div
          className={`flex items-start justify-between gap-4 ${canExpand ? "cursor-pointer" : ""}`}
          onClick={() => canExpand && setExpanded((v) => !v)}
        >
          <div className="min-w-0 flex-1">
            <p className="font-medium">{episode.title || "Untitled"}</p>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              {episode.published_at && <span>{new Date(episode.published_at).toLocaleDateString()}</span>}
              {episode.duration_seconds != null && <span>· {formatDuration(episode.duration_seconds)}</span>}
              <Badge variant={statusVariant[episode.status] || "secondary"} className="w-24 justify-center">{episode.status}</Badge>
            </div>
            {episode.error_message && (
              <p className="text-xs text-red-400 mt-1">{episode.error_message}</p>
            )}
            {episode.summary && (
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{episode.summary}</p>
            )}
          </div>
          {canExpand && (
            <button
              type="button"
              className="text-xs text-primary flex items-center gap-0.5 shrink-0 mt-0.5"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded((v) => !v);
              }}
            >
              {expanded ? (
                <>Hide details <ChevronUp className="h-3 w-3" /></>
              ) : (
                <>View details <ChevronDown className="h-3 w-3" /></>
              )}
            </button>
          )}
        </div>
        {expanded && <EpisodeDetail sourceId={episode.id} />}
      </CardContent>
    </Card>
  );
}

export default function SubscriptionDetailPage() {
  const params = useParams();
  const feedId = params.feedId as string;

  const [feed, setFeed] = useState<PodcastFeedDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!feedId) return;
    getPodcastFeedDetail(feedId)
      .then(setFeed)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [feedId]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await pollPodcastFeedNow(feedId);
      // Newly-found episodes are created (as "pending") before ingestion runs in the
      // background, so a short delay is enough for them to show up in the list.
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setFeed(await getPodcastFeedDetail(feedId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh feed");
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !feed) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-400">
        <AlertCircle className="h-4 w-4" />
        {error || "Feed not found"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/subscriptions" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1 mb-3">
            <ArrowLeft className="h-3.5 w-3.5" />
            Subscriptions
          </Link>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            {feed.source_type === "youtube" ? (
              <Youtube className="h-7 w-7 text-red-400" />
            ) : (
              <Rss className="h-7 w-7 text-orange-400" />
            )}
            {feed.label}
          </h1>
          <p className="text-muted-foreground mt-1">
            {feed.episode_count} {feed.source_type === "youtube" ? "video" : "episode"}
            {feed.episode_count === 1 ? "" : "s"}
            {feed.last_polled_at && ` · last checked ${timeAgo(feed.last_polled_at)}`}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing} className="shrink-0 mt-8">
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <TrackRecordPanel feedId={feedId} label={feed.label} />

      {feed.episodes.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12 text-muted-foreground">
            <p className="text-sm">No episodes ingested yet.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {feed.episodes.map((episode) => (
            <EpisodeRow key={episode.id} episode={episode} />
          ))}
        </div>
      )}
    </div>
  );
}
