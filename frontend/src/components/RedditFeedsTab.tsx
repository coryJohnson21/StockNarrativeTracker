"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Plus, Trash2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getRedditFeeds, addRedditFeed, removeRedditFeed, pollRedditFeedNow } from "@/lib/api";
import type { RedditFeed } from "@/types";

export function RedditFeedsTab() {
  const [feeds, setFeeds] = useState<RedditFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [subreddit, setSubreddit] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [pollingId, setPollingId] = useState<string | null>(null);
  const [pollMessage, setPollMessage] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getRedditFeeds()
      .then((r) => setFeeds(r.feeds))
      .catch((e) => setListError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!subreddit.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const feed = await addRedditFeed(subreddit.trim());
      setFeeds((prev) => [feed, ...prev]);
      setSubreddit("");
    } catch (err: any) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string) {
    setFeeds((prev) => prev.filter((f) => f.id !== id));
    try { await removeRedditFeed(id); } catch { load(); }
  }

  async function handlePollNow(id: string) {
    setPollingId(id);
    setPollMessage(null);
    try {
      await pollRedditFeedNow(id);
      setPollMessage("Fetching new posts in the background — refresh in a minute to see results.");
    } catch (err: any) {
      setPollMessage(err.message);
    } finally {
      setPollingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAdd} className="space-y-3">
        <div className="flex items-end gap-3">
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
        </div>
        <p className="text-xs text-muted-foreground">
          Hot posts are fetched every 2 hours. Each post's title, body, and top comments are
          sent through GPT-4o extraction — no audio transcription needed. Up to 5 new posts
          are ingested per poll to avoid rate limits.
        </p>
        {addError && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {addError}
          </div>
        )}
      </form>

      {pollMessage && <p className="text-xs text-muted-foreground">{pollMessage}</p>}

      <div className="border-t pt-4">
        {loading ? (
          <div className="flex items-center justify-center h-20">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : listError ? (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="h-4 w-4" />
            {listError}
          </div>
        ) : feeds.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">
            No subreddits subscribed yet. Add one above to start ingesting posts.
          </p>
        ) : (
          <ul className="space-y-2">
            {feeds.map((feed) => (
              <li
                key={feed.id}
                className="flex items-center justify-between gap-3 rounded-lg border p-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">r/{feed.subreddit}</p>
                  <p className="text-xs text-muted-foreground">
                    {feed.post_count} post{feed.post_count === 1 ? "" : "s"} ingested
                    {feed.last_polled_at &&
                      ` · last checked ${new Date(feed.last_polled_at).toLocaleString()}`}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handlePollNow(feed.id)}
                    disabled={pollingId === feed.id}
                  >
                    {pollingId === feed.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => handleRemove(feed.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
