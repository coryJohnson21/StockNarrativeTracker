"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  MessageSquare,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getRedditFeedDetail, getSourceExtractions, getRedditFeedTrackRecord, pollRedditFeedNow } from "@/lib/api";
import type { SourceExtractions } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { RedditFeedDetail, RedditPost } from "@/types";
import { ExtractionDetailGrid } from "@/components/ExtractionDetailGrid";
import { TrackRecordPanel } from "@/components/TrackRecordPanel";
import { RedditTopTickers } from "@/components/RedditTopTickers";

const statusVariant: Record<string, "default" | "secondary" | "bullish" | "bearish" | "neutral"> = {
  completed: "bullish",
  processing: "neutral",
  pending: "secondary",
  failed: "bearish",
};

function PostDetail({ sourceId }: { sourceId: string }) {
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

function PostRow({ post }: { post: RedditPost }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = post.status === "completed";
  const posted = post.published_at || post.created_at;

  return (
    <Card>
      <CardContent className="p-4">
        <div
          className={`flex items-start justify-between gap-4 ${canExpand ? "cursor-pointer" : ""}`}
          onClick={() => canExpand && setExpanded((v) => !v)}
        >
          <div className="min-w-0 flex-1">
            <p className="font-medium">{post.title || "Untitled"}</p>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              {posted && <span>{timeAgo(posted)}</span>}
              <Badge variant={statusVariant[post.status] || "secondary"} className="w-24 justify-center">
                {post.status}
              </Badge>
              {post.url && (
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-0.5 hover:text-primary"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="h-3 w-3" />
                  View on Reddit
                </a>
              )}
            </div>
            {post.error_message && <p className="text-xs text-red-400 mt-1">{post.error_message}</p>}
            {post.summary && (
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{post.summary}</p>
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
        {expanded && <PostDetail sourceId={post.id} />}
      </CardContent>
    </Card>
  );
}

export default function RedditFeedDetailPage() {
  const params = useParams();
  const feedId = params.feedId as string;

  const [feed, setFeed] = useState<RedditFeedDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [pollMessage, setPollMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!feedId) return;
    getRedditFeedDetail(feedId)
      .then(setFeed)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [feedId]);

  async function handleRefresh() {
    setRefreshing(true);
    setPollMessage(null);
    try {
      await pollRedditFeedNow(feedId);
      setPollMessage("Fetching new posts in the background — reload in a minute to see them.");
    } catch (e) {
      setPollMessage(e instanceof Error ? e.message : "Poll failed");
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
      <div className="space-y-4">
        <Link href="/reddit" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" /> Back to Reddit
        </Link>
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error || "Feed not found"}
        </div>
      </div>
    );
  }

  const completed = feed.posts.filter((p) => p.status === "completed").length;

  return (
    <div className="space-y-6">
      <Link href="/reddit" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
        <ArrowLeft className="h-4 w-4" /> Back to Reddit
      </Link>

      {/* 1 — feed overview header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <MessageSquare className="h-7 w-7 text-orange-400" />
            r/{feed.subreddit}
          </h1>
          <p className="text-muted-foreground mt-1">
            {feed.post_count} post{feed.post_count === 1 ? "" : "s"} ingested
            {completed !== feed.post_count && ` · ${completed} processed`}
            {feed.last_polled_at && ` · last checked ${timeAgo(feed.last_polled_at)}`}
            {" · polled automatically every 2 hours"}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a
            href={`https://www.reddit.com/r/${feed.subreddit}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="outline" size="sm">
              <ExternalLink className="h-4 w-4 mr-2" />
              Open on Reddit
            </Button>
          </a>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Poll now
          </Button>
        </div>
      </div>
      {pollMessage && <p className="text-xs text-muted-foreground">{pollMessage}</p>}

      {/* 4 — what this subreddit talks about */}
      <RedditTopTickers
        tickers={feed.top_tickers}
        title={`Most mentioned in r/${feed.subreddit}`}
        description="Tickers named across every post ingested from this subreddit, with the average sentiment of those mentions."
      />

      {/* 3 — is the crowd here actually right */}
      <TrackRecordPanel
        feedId={feedId}
        label={`r/${feed.subreddit}`}
        fetchTrackRecord={getRedditFeedTrackRecord}
        itemNoun="post"
      />

      {/* 2 — the posts themselves */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Posts</h2>
        {feed.posts.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No posts ingested yet. Hit “Poll now” to fetch this subreddit&apos;s hot posts.
            </CardContent>
          </Card>
        ) : (
          feed.posts.map((post) => <PostRow key={post.id} post={post} />)
        )}
      </div>
    </div>
  );
}
