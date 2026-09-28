"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CategoryToggle } from "@/components/CategoryToggle";
import { LiveStatus } from "@/components/LiveStatus";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import { RecentInsiderTrades } from "@/components/RecentInsiderTrades";
import type { MediaChannel, SourceCategory } from "@/lib/api";

const CATEGORY_BLURB: Record<string, string> = {
  all: "Everything ingested — filings and media together.",
  filing: "10-K, 10-Q, 8-K earnings releases, and earnings call transcripts.",
  media: "CNBC, Bloomberg, YouTube, podcasts, and other financial media.",
};

/** A section label and a "view all" link over a full-width table, replacing the
 *  Card + CardHeader + CardTitle stack. Same information, one hairline. */
function SectionHead({ title, blurb, href }: { title: string; blurb?: string; href: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 pb-1.5">
      <div className="flex items-baseline gap-2.5 min-w-0">
        <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
        {blurb && <p className="text-[11px] text-muted-foreground truncate">{blurb}</p>}
      </div>
      <Link
        href={href}
        className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 shrink-0 transition-colors"
      >
        View all <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

/** One pair of tables over whichever slice the filter selects. */
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
    <section>
      <div className="flex items-center gap-4 flex-wrap pb-2.5">
        <h2 className="text-[13px] font-semibold tracking-tight">What is being talked about</h2>
        <CategoryToggle
          value={category}
          onChange={handleCategoryChange}
          channel={activeChannel}
          onChannelChange={setActiveChannel}
        />
        <p className="text-[11px] text-muted-foreground hidden xl:block">
          {CATEGORY_BLURB[category ?? "all"]}
        </p>
      </div>
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-x-8 gap-y-5">
        <div>
          <SectionHead title="Trending Stocks" href={href("/stocks")} />
          <div className="border-t border-border">
            <TrendingStocksTable limit={10} compact category={category} channel={channel} />
          </div>
        </div>
        <div>
          <SectionHead title="Trending Themes" href={href("/themes")} />
          <div className="border-t border-border">
            <TrendingThemesTable limit={10} compact category={category} channel={channel} />
          </div>
        </div>
      </div>
    </section>
  );
}


const INSIDER_WINDOW_DAYS = 30;

function InsiderSection() {
  return (
    <section>
      <div className="flex items-baseline gap-2.5 flex-wrap pb-2.5">
        <h2 className="text-[13px] font-semibold tracking-tight">Insider Activity</h2>
        <p className="text-[11px] text-muted-foreground">
          Open-market Form 4 buys and sells, last {INSIDER_WINDOW_DAYS} days. Ranked separately —
          a routine sale at a mega-cap dwarfs almost any purchase.
        </p>
      </div>
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-x-8 gap-y-5">
        <div>
          <SectionHead title="Biggest Purchases" href="/insiders" />
          <div className="border-t border-border">
            <RecentInsiderTrades side="buys" days={INSIDER_WINDOW_DAYS} limit={10} />
          </div>
        </div>
        <div>
          <SectionHead title="Biggest Sales" href="/insiders" />
          <div className="border-t border-border">
            <RecentInsiderTrades side="sells" days={INSIDER_WINDOW_DAYS} limit={10} />
          </div>
        </div>
      </div>
    </section>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* The H1 is replaced by live status text: the nav already says Dashboard,
          and "What is Wall Street talking about right now?" told you nothing the
          page itself doesn't. */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <LiveStatus />
        <Button asChild size="sm" variant="outline" className="h-7 text-[12px]">
          <Link href="/ingest">Add Content</Link>
        </Button>
      </div>

      <NarrativeSection />
      <InsiderSection />
    </div>
  );
}
