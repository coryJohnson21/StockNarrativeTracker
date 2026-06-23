"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Star, Plus, Loader2, AlertCircle, X, Youtube, Newspaper, MessagesSquare, Landmark } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SentimentBadge } from "@/components/SentimentBadge";
import { MomentumBar } from "@/components/MomentumBadge";
import { getWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/api";
import type { WatchlistItem, BasketBreakdown } from "@/types";

const BASKETS: { key: keyof WatchlistItem["baskets"]; label: string; icon: typeof Youtube }[] = [
  { key: "youtube", label: "YouTube", icon: Youtube },
  { key: "news", label: "News (CNBC, Bloomberg)", icon: Newspaper },
  { key: "reddit", label: "Reddit & Forums", icon: MessagesSquare },
  { key: "filing", label: "SEC Filings", icon: Landmark },
];

function BasketTile({ label, icon: Icon, basket }: { label: string; icon: typeof Youtube; basket: BasketBreakdown }) {
  return (
    <div className="rounded-lg border p-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="text-lg font-bold tabular-nums">
        {basket.mention_count}{" "}
        <span className="text-xs font-normal text-muted-foreground">mentions</span>
      </p>
      {basket.mention_count > 0 ? (
        <SentimentBadge score={basket.avg_sentiment} showNumber />
      ) : (
        <span className="text-xs text-muted-foreground">No data yet</span>
      )}
    </div>
  );
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getWatchlist()
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTicker.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const item = await addToWatchlist(newTicker.trim().toUpperCase());
      setItems((prev) => [item, ...prev]);
      setNewTicker("");
    } catch (err: any) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(ticker: string) {
    setItems((prev) => prev.filter((i) => i.ticker !== ticker));
    try {
      await removeFromWatchlist(ticker);
    } catch {
      load();
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Star className="h-7 w-7 text-yellow-400" />
          Watchlist
        </h1>
        <p className="text-muted-foreground mt-1">
          Track specific tickers across YouTube, news, Reddit &amp; forums, and SEC filings.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleAdd} className="flex items-center gap-3">
            <Input
              placeholder="Add a ticker (e.g. NVDA)"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
              className="max-w-xs"
            />
            <Button type="submit" disabled={adding || !newTicker.trim()}>
              {adding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
              Add
            </Button>
          </form>
          {addError && (
            <div className="flex items-center gap-2 text-sm text-red-400 mt-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {addError}
            </div>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-muted-foreground py-16">
          No tickers on your watchlist yet. Add one above to start tracking it.
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <Card key={item.ticker}>
              <CardHeader className="pb-2 flex flex-row items-start justify-between">
                <div>
                  <CardTitle className="text-lg font-mono flex items-center gap-2">
                    <Link href={`/stocks/${item.ticker}`} className="hover:underline">
                      {item.ticker}
                    </Link>
                  </CardTitle>
                  {item.company_name && <CardDescription>{item.company_name}</CardDescription>}
                </div>
                <div className="flex items-center gap-3">
                  {item.momentum_score !== undefined && item.momentum_score !== null && (
                    <MomentumBar score={item.momentum_score} />
                  )}
                  <Button variant="ghost" size="sm" onClick={() => handleRemove(item.ticker)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {BASKETS.map(({ key, label, icon }) => (
                    <BasketTile key={key} label={label} icon={icon} basket={item.baskets[key]} />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
