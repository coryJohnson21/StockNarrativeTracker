"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, TrendingUp, Layers, Upload, Landmark, Newspaper, UserRoundCheck, LayoutGrid, MessagesSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/StatsCards";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import { RecentInsiderTrades } from "@/components/RecentInsiderTrades";
import type { MediaChannel, SourceCategory } from "@/lib/api";

const CHANNELS: { key: MediaChannel | "all"; label: string }[] = [
  { key: "all",     label: "All Media" },
  { key: "youtube", label: "YouTube" },
  { key: "podcast", label: "Podcasts" },
  { key: "news",    label: "News" },
  { key: "reddit",  label: "Reddit" },
  { key: "x",       label: "X" },
];

/** Category + channel picker, matching the one on /stocks so the two pages behave
 *  the same way. Media Tracking expands into a split button carrying the channel
 *  dropdown once it is the active category. */
function NarrativeFilter({
  category,
  channel,
  onCategoryChange,
  onChannelChange,
}: {
  category: SourceCategory | undefined;
  channel: MediaChannel | "all";
  onCategoryChange: (next: SourceCategory | undefined) => void;
  onChannelChange: (next: MediaChannel | "all") => void;
}) {
  const mediaActive = category === "media";
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button variant={category === undefined ? "default" : "outline"} size="sm" onClick={() => onCategoryChange(undefined)}>
        <LayoutGrid className="h-3.5 w-3.5 mr-1.5" />
        All
      </Button>
      <Button variant={category === "filing" ? "default" : "outline"} size="sm" onClick={() => onCategoryChange("filing")}>
        <Landmark className="h-3.5 w-3.5 mr-1.5" />
        Press Releases &amp; Earnings
      </Button>
      {!mediaActive ? (
        <Button variant="outline" size="sm" onClick={() => onCategoryChange("media")}>
          <Newspaper className="h-3.5 w-3.5 mr-1.5" />
          Media Tracking
        </Button>
      ) : (
        <div className="flex items-center h-9 rounded-md overflow-hidden border border-primary text-sm font-medium">
          <button
            className="flex items-center gap-1.5 px-3 h-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            onClick={() => onCategoryChange(undefined)}
          >
            <Newspaper className="h-3.5 w-3.5" />
            Media Tracking
          </button>
          <div className="w-px h-full bg-primary-foreground/20" />
          <select
            value={channel}
            onChange={(e) => onChannelChange(e.target.value as MediaChannel | "all")}
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
  );
}

const CATEGORY_BLURB: Record<string, string> = {
  all: "Everything ingested — filings and media together.",
  filing: "10-K, 10-Q, 8-K earnings releases, and earnings call transcripts.",
  media: "CNBC, Bloomberg, YouTube, podcasts, and other financial media.",
};

/** One pair of tables over whichever slice the filter selects, replacing the two
 *  fixed Filing/Media sections that used to render the same two tables twice. */
function NarrativeSection() {
  const [category, setCategory] = useState<SourceCategory | undefined>(undefined);
  const [activeChannel, setActiveChannel] = useState<MediaChannel | "all">("all");

  const channel = category === "media" && activeChannel !== "all" ? activeChannel : undefined;
  const href = (base: string) => (category ? `${base}?category=${category}` : base);

  function handleCategoryChange(next: SourceCategory | undefined) {
    setCategory(next);
    setActiveChannel("all");
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5 text-blue-400" />
          <div>
            <h2 className="text-lg font-semibold leading-tight">What is being talked about</h2>
            <p className="text-xs text-muted-foreground">{CATEGORY_BLURB[category ?? "all"]}</p>
          </div>
        </div>
        <NarrativeFilter
          category={category}
          channel={activeChannel}
          onCategoryChange={handleCategoryChange}
          onChannelChange={setActiveChannel}
        />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-400" />
              Trending Stocks
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href={href("/stocks")} className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingStocksTable limit={10} compact category={category} channel={channel} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              Trending Themes
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href={href("/themes")} className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingThemesTable limit={10} compact category={category} channel={channel} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}


const INSIDER_WINDOW_DAYS = 30;

function InsiderSection() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <UserRoundCheck className="h-5 w-5 text-amber-400" />
        <div className="flex-1">
          <h2 className="text-lg font-semibold leading-tight">Insider Activity</h2>
          <p className="text-xs text-muted-foreground">
            Largest open-market buys and sells by officers, directors, and 10% holders (Form 4), last {INSIDER_WINDOW_DAYS} days.
            Buys and sells are ranked separately — a routine sale at a mega-cap dwarfs almost any purchase.
          </p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/insiders" className="text-xs text-muted-foreground gap-1 shrink-0">
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </Button>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-400">
                Buys
              </span>
              Biggest Insider Purchases
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <RecentInsiderTrades side="buys" days={INSIDER_WINDOW_DAYS} limit={10} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-400">
                Sells
              </span>
              Biggest Insider Sales
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <RecentInsiderTrades side="sells" days={INSIDER_WINDOW_DAYS} limit={10} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            What is Wall Street talking about right now?
          </p>
        </div>
        <Button asChild>
          <Link href="/ingest">
            <Upload className="h-4 w-4 mr-2" />
            Add Content
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <StatsCards />

      <NarrativeSection />
      <InsiderSection />
    </div>
  );
}
