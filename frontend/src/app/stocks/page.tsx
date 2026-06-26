"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { TrendingUp, LayoutGrid, Landmark, Newspaper } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import type { SourceCategory, MediaChannel } from "@/lib/api";

const CHANNELS: { key: MediaChannel | "all"; label: string }[] = [
  { key: "all",     label: "All Media" },
  { key: "youtube", label: "YouTube" },
  { key: "podcast", label: "Podcasts" },
  { key: "news",    label: "News" },
  { key: "reddit",  label: "Reddit" },
  { key: "x",       label: "X" },
];

function StocksPageContent() {
  const params = useSearchParams();
  const initial = params.get("category");
  const [category, setCategory] = useState<SourceCategory | undefined>(
    initial === "filing" || initial === "media" ? initial : undefined
  );
  const [activeChannel, setActiveChannel] = useState<MediaChannel | "all">("all");

  const channel = category === "media" && activeChannel !== "all" ? activeChannel : undefined;

  function handleCategoryChange(next: SourceCategory | undefined) {
    setCategory(next);
    setActiveChannel("all");
  }

  const mediaActive = category === "media";
  const selectedChannelLabel = CHANNELS.find((c) => c.key === activeChannel)?.label ?? "All Media";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <TrendingUp className="h-7 w-7 text-green-400" />
          Trending Stocks
        </h1>
        <p className="text-muted-foreground mt-1">
          Stocks ranked by narrative momentum — frequency, growth rate, sentiment, and cross-source mentions.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant={category === undefined ? "default" : "outline"}
          size="sm"
          onClick={() => handleCategoryChange(undefined)}
        >
          <LayoutGrid className="h-3.5 w-3.5 mr-1.5" />
          All
        </Button>
        <Button
          variant={category === "filing" ? "default" : "outline"}
          size="sm"
          onClick={() => handleCategoryChange("filing")}
        >
          <Landmark className="h-3.5 w-3.5 mr-1.5" />
          Press Releases &amp; Earnings
        </Button>

        {/* Media Tracking — plain button when inactive, split button when active */}
        {!mediaActive ? (
          <Button variant="outline" size="sm" onClick={() => handleCategoryChange("media")}>
            <Newspaper className="h-3.5 w-3.5 mr-1.5" />
            Media Tracking
          </Button>
        ) : (
          <div className="flex items-center h-9 rounded-md overflow-hidden border border-primary text-sm font-medium">
            <button
              className="flex items-center gap-1.5 px-3 h-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              onClick={() => handleCategoryChange(undefined)}
            >
              <Newspaper className="h-3.5 w-3.5" />
              Media Tracking
            </button>
            <div className="w-px h-full bg-primary-foreground/20" />
            <select
              value={activeChannel}
              onChange={(e) => setActiveChannel(e.target.value as MediaChannel | "all")}
              className="h-full px-2 pr-6 bg-primary text-primary-foreground text-xs focus:outline-none appearance-none cursor-pointer hover:bg-primary/90 transition-colors"
            >
              {CHANNELS.map(({ key, label }) => (
                <option key={key} value={key} className="bg-background text-foreground">
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">All Tracked Stocks</CardTitle>
          <CardDescription>
            Click any row to see the AI-generated investment summary. Momentum score: 0–100.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <TrendingStocksTable limit={100} category={category} channel={channel} />
        </CardContent>
      </Card>
    </div>
  );
}

export default function StocksPage() {
  return (
    <Suspense fallback={null}>
      <StocksPageContent />
    </Suspense>
  );
}
