"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Plus, Trash2, RefreshCw, Rss } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getPodcastFeeds, addPodcastFeed, removePodcastFeed, pollPodcastFeedNow } from "@/lib/api";
import type { PodcastFeed } from "@/types";

export function PodcastFeedsTab() {
  const [feeds, setFeeds] = useState<PodcastFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [pollingId, setPollingId] = useState<string | null>(null);
  const [pollMessage, setPollMessage] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getPodcastFeeds()
      .then((r) => setFeeds(r.feeds))
      .catch((e) => setListError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || !label.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const feed = await addPodcastFeed({ url: url.trim(), label: label.trim() });
      setFeeds((prev) => [feed, ...prev]);
      setUrl("");
      setLabel("");
    } catch (err: any) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string) {
    setFeeds((prev) => prev.filter((f) => f.id !== id));
    try {
      await removePodcastFeed(id);
    } catch {
      load();
    }
  }

  async function handlePollNow(id: string) {
    setPollingId(id);
    setPollMessage(null);
    try {
      await pollPodcastFeedNow(id);
      setPollMessage("Checking for new episodes in the background — refresh in a minute to see results.");
    } catch (err: any) {
      setPollMessage(err.message);
    } finally {
      setPollingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAdd} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-medium mb-1.5 block">Label</label>
            <Input
              placeholder="CNBC — Squawk Pod"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">RSS Feed URL</label>
            <Input
              placeholder="https://feeds.example.com/show.rss"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Find the official RSS URL from the show's publisher page (Apple/Spotify links aren't RSS feeds
          themselves). New episodes are auto-downloaded, transcribed, and scored — no manual pasting. Only
          the newest few episodes are picked up at a time, not the whole archive.
        </p>
        {addError && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {addError}
          </div>
        )}
        <Button type="submit" disabled={adding || !url.trim() || !label.trim()}>
          {adding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
          Subscribe to Feed
        </Button>
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
            No podcast feeds subscribed yet. Add one above to start auto-ingesting episodes.
          </p>
        ) : (
          <ul className="space-y-2">
            {feeds.map((feed) => (
              <li
                key={feed.id}
                className="flex items-center justify-between gap-3 rounded-lg border p-3"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Rss className="h-4 w-4 text-orange-400 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{feed.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {feed.episode_count} episode{feed.episode_count === 1 ? "" : "s"} ingested
                      {feed.last_polled_at &&
                        ` · last checked ${new Date(feed.last_polled_at).toLocaleString()}`}
                    </p>
                  </div>
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
