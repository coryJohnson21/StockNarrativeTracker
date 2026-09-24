"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  RefreshCw,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getRedditOverview, addRedditFeed, removeRedditFeed, pollRedditFeedNow } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { RedditOverview } from "@/types";
import { RedditTopTickers } from "@/components/RedditTopTickers";

export default function RedditPage() {
  const [data, setData] = useState<RedditOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [subreddit, setSubreddit] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [pollingId, setPollingId] = useState<string | null>(null);
  const [pollMessage, setPollMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    getRedditOverview()
      .then((r) => {
        setData(r);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!subreddit.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      await addRedditFeed(subreddit.trim());
      setSubreddit("");
      load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Could not subscribe");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string, sub: string) {
    if (!confirm(`Unsubscribe from r/${sub}? Already-ingested posts are kept.`)) return;
    try {
      await removeRedditFeed(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not unsubscribe");
    }
  }

  async function handlePollNow(id: string) {
    setPollingId(id);
    setPollMessage(null);
    try {
      await pollRedditFeedNow(id);
      setPollMessage("Fetching new posts in the background — refresh in a minute to see results.");
    } catch (err) {
      setPollMessage(err instanceof Error ? err.message : "Poll failed");
    } finally {
      setPollingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <MessageSquare className="h-7 w-7 text-orange-400" />
          Reddit
        </h1>
        <p className="text-muted-foreground mt-1">
          Subscribed subreddits and what the crowd has been talking about
          {data ? ` · ${data.total_posts} post${data.total_posts === 1 ? "" : "s"} ingested` : ""}
        </p>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : data ? (
        <>
          {/* Top 3 tickers across all subreddits, trailing week */}
          <RedditTopTickers
            tickers={data.top_tickers_7d}
            rank
            title={`Top tickers · last ${data.trailing_days} days`}
            description="The three tickers mentioned most across every subscribed subreddit over the past week."
            emptyMessage={`No tickers mentioned in the last ${data.trailing_days} days. Poll a subreddit below to pull in fresh posts.`}
          />

          {/* Subscribe */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Subscribe to a subreddit</CardTitle>
              <CardDescription>
                Hot posts are fetched every 2 hours. Each post&apos;s title, body, and top comments run through
                extraction — no audio transcription needed. Up to 5 new posts per poll, to stay under rate limits.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAdd} className="flex items-end gap-3">
                <div className="flex-1">
                  <label className="text-sm font-medium mb-1.5 block">Subreddit</label>
                  <div className="flex items-center">
                    <span className="inline-flex items-center px-2.5 h-9 rounded-l-md border border-r-0 border-input bg-muted text-muted-foreground text-sm">
                      r/
                    </span>
                    <Input
                      className="rounded-l-none"
                      placeholder="stocks"
                      value={subreddit}
                      onChange={(e) => setSubreddit(e.target.value.replace(/^r?\/?/, ""))}
                      required
                    />
                  </div>
                </div>
                <Button type="submit" disabled={adding || !subreddit.trim()}>
                  {adding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                  Subscribe
                </Button>
              </form>
              {addError && (
                <div className="flex items-center gap-2 text-sm text-red-400 mt-3">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {addError}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Feed cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                Subscribed{data.feeds.length > 0 ? ` (${data.feeds.length})` : ""}
              </h2>
              <Button variant="outline" size="sm" onClick={load}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
            {pollMessage && <p className="text-xs text-muted-foreground">{pollMessage}</p>}

            {data.feeds.length === 0 ? (
              <Card>
                <CardContent className="py-10 text-center text-sm text-muted-foreground">
                  No subreddits subscribed yet. Add one above to start ingesting posts.
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {data.feeds.map((feed) => (
                  <Card key={feed.id} className="transition-colors hover:border-primary/40">
                    <CardContent className="p-4 flex items-start justify-between gap-3">
                      <Link href={`/reddit/${feed.id}`} className="min-w-0 flex-1 group">
                        <p className="font-medium flex items-center gap-1 group-hover:text-primary transition-colors">
                          r/{feed.subreddit}
                          <ChevronRight className="h-4 w-4 opacity-50" />
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {feed.post_count} post{feed.post_count === 1 ? "" : "s"} ingested
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {feed.last_polled_at
                            ? `Last checked ${timeAgo(feed.last_polled_at)}`
                            : "Not polled yet"}
                        </p>
                      </Link>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          title="Poll now"
                          onClick={() => handlePollNow(feed.id)}
                          disabled={pollingId === feed.id}
                        >
                          {pollingId === feed.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="h-3.5 w-3.5" />
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          title="Unsubscribe"
                          onClick={() => handleRemove(feed.id, feed.subreddit)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
