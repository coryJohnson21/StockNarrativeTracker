"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, TrendingUp, Layers, Upload, Landmark, Newspaper } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/StatsCards";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import type { MediaChannel } from "@/lib/api";

const CHANNELS: { key: MediaChannel | "all"; label: string }[] = [
  { key: "all",     label: "All Media" },
  { key: "youtube", label: "YouTube" },
  { key: "podcast", label: "Podcasts" },
  { key: "news",    label: "News" },
  { key: "reddit",  label: "Reddit" },
  { key: "x",       label: "X" },
];

function FilingSection() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Landmark className="h-5 w-5 text-emerald-400" />
        <div>
          <h2 className="text-lg font-semibold leading-tight">Press Releases &amp; Earnings Transcripts</h2>
          <p className="text-xs text-muted-foreground">10-K, 10-Q, 8-K earnings releases, and earnings call transcripts</p>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-400" />
              Trending Stocks
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/stocks?category=filing" className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingStocksTable limit={10} compact category="filing" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              Trending Themes
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/themes?category=filing" className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingThemesTable limit={10} compact category="filing" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MediaSection() {
  const [activeChannel, setActiveChannel] = useState<MediaChannel | "all">("all");

  const channel = activeChannel === "all" ? undefined : activeChannel;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-blue-400" />
        <div>
          <h2 className="text-lg font-semibold leading-tight">Media Tracking</h2>
          <p className="text-xs text-muted-foreground">CNBC, Bloomberg, YouTube, podcasts, and other financial media</p>
        </div>
      </div>

      {/* Channel filter */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground whitespace-nowrap">Channel</label>
        <select
          value={activeChannel}
          onChange={(e) => setActiveChannel(e.target.value as MediaChannel | "all")}
          className="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        >
          {CHANNELS.map(({ key, label }) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Tables */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-400" />
              Trending Stocks
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/stocks?category=media" className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingStocksTable limit={10} compact category="media" channel={channel} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              Trending Themes
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/themes?category=media" className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingThemesTable limit={10} compact category="media" channel={channel} />
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

      <FilingSection />
      <MediaSection />
    </div>
  );
}
