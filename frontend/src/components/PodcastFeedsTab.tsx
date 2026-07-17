"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Plus, Trash2, RefreshCw, Rss, Search, Youtube, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getPodcastFeeds,
  addPodcastFeed,
  removePodcastFeed,
  pollPodcastFeedNow,
  searchPodcasts,
  resolveYoutubeChannel,
} from "@/lib/api";
import type { PodcastFeed, PodcastSearchResult, YoutubeChannelResolution } from "@/types";

export function PodcastFeedsTab() {
  const [feeds, setFeeds] = useState<PodcastFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<PodcastSearchResult[] | null>(null);

  const [channelInput, setChannelInput] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolvedChannel, setResolvedChannel] = useState<YoutubeChannelResolution | null>(null);
  const [subscribingChannel, setSubscribingChannel] = useState(false);

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

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const { results } = await searchPodcasts(query.trim());
      setSearchResults(results);
    } catch (err: any) {
      setSearchError(err.message);
      setSearchResults(null);
    } finally {
      setSearching(false);
    }
  }

  function handleSelectResult(result: PodcastSearchResult) {
    setLabel(result.title);
    setUrl(result.feed_url);
    setSearchResults(null);
    setQuery("");
  }

  async function handleResolveChannel(e: React.FormEvent) {
    e.preventDefault();
    if (!channelInput.trim()) return;
    setResolving(true);
    setResolveError(null);
    setResolvedChannel(null);
    try {
      const result = await resolveYoutubeChannel(channelInput.trim());
      setResolvedChannel(result);
    } catch (err: any) {
      setResolveError(err.message);
    } finally {
      setResolving(false);
    }
  }

  async function handleSubscribeChannel() {
    if (!resolvedChannel) return;
    setSubscribingChannel(true);
    setResolveError(null);
    try {
      const feed = await addPodcastFeed({
        url: resolvedChannel.feed_url,
        label: resolvedChannel.title,
        source_type: "youtube",
      });
      setFeeds((prev) => [feed, ...prev]);
      setResolvedChannel(null);
      setChannelInput("");
    } catch (err: any) {
      setResolveError(err.message);
    } finally {
      setSubscribingChannel(false);
    }
  }

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
      <div className="space-y-2">
        <label className="text-sm font-medium block">Search for a podcast</label>
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <Input
            placeholder="e.g. The Compound and Friends"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" variant="outline" disabled={searching || !query.trim()}>
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </Button>
        </form>
        {searchError && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {searchError}
          </div>
        )}
        {searchResults && (
          searchResults.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No podcasts found for that search — try the exact show name, or paste its RSS URL directly below.
            </p>
          ) : (
            <ul className="space-y-1.5 border rounded-lg p-1.5">
              {searchResults.map((result) => (
                <li key={result.feed_url}>
                  <button
                    type="button"
                    onClick={() => handleSelectResult(result)}
                    className="w-full flex items-center gap-2.5 rounded-md p-1.5 text-left hover:bg-accent/50 transition-colors"
                  >
                    {result.artwork_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={result.artwork_url} alt="" className="h-9 w-9 rounded shrink-0" />
                    ) : (
                      <Rss className="h-9 w-9 p-2 rounded bg-accent text-orange-400 shrink-0" />
                    )}
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{result.title}</p>
                      {result.publisher && (
                        <p className="text-xs text-muted-foreground truncate">{result.publisher}</p>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )
        )}
      </div>

      <div className="space-y-2 border-t pt-4">
        <label className="text-sm font-medium block">Subscribe to a YouTube channel</label>
        <p className="text-xs text-muted-foreground">
          New videos are transcribed from YouTube's own captions when available — free, no Whisper
          cost — falling back to audio transcription only if a video has no caption track.
        </p>
        <form onSubmit={handleResolveChannel} className="flex items-center gap-2">
          <Input
            placeholder="Channel URL or @handle, e.g. @Fundstrat"
            value={channelInput}
            onChange={(e) => setChannelInput(e.target.value)}
          />
          <Button type="submit" variant="outline" disabled={resolving || !channelInput.trim()}>
            {resolving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </Button>
        </form>
        {resolveError && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {resolveError}
          </div>
        )}
        {resolvedChannel && (
          <div className="flex items-center justify-between gap-3 rounded-lg border p-2.5">
            <div className="flex items-center gap-2.5 min-w-0">
              <Youtube className="h-8 w-8 p-1.5 rounded bg-accent text-red-400 shrink-0" />
              <p className="text-sm font-medium truncate">{resolvedChannel.title}</p>
            </div>
            <Button type="button" size="sm" onClick={handleSubscribeChannel} disabled={subscribingChannel}>
              {subscribingChannel ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
              )}
              Subscribe
            </Button>
          </div>
        )}
      </div>

      <form onSubmit={handleAdd} className="space-y-3 border-t pt-4">
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
          Picking a search result above fills this in automatically. To add a show search didn't find,
          paste its official RSS URL directly (Apple/Spotify links aren't RSS feeds themselves). New
          episodes are auto-downloaded, transcribed, and scored — no manual pasting. Only the newest few
          episodes are picked up at a time, not the whole archive.
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
                  {feed.source_type === "youtube" ? (
                    <Youtube className="h-4 w-4 text-red-400 shrink-0" />
                  ) : (
                    <Rss className="h-4 w-4 text-orange-400 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{feed.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {feed.episode_count} {feed.source_type === "youtube" ? "video" : "episode"}
                      {feed.episode_count === 1 ? "" : "s"} ingested
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
