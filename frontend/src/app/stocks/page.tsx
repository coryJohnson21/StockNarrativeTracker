"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CategoryToggle } from "@/components/CategoryToggle";
import { NarrativeStocksList } from "@/components/stocks/NarrativeStocksList";
import { StockSearch } from "@/components/StockSearch";
import { LiveStatus } from "@/components/LiveStatus";
import type { SourceCategory, MediaChannel } from "@/lib/api";

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

  return (
    <div>
      {/* Source filter, status and search, docked under the nav. The page title
          now lives in the list header beside the signal pills, where it sits
          with the "N changed signal today" count. */}
      <div className="dock-toolbar flex items-center gap-4 flex-wrap py-2.5">
        <CategoryToggle
          value={category}
          onChange={handleCategoryChange}
          channel={activeChannel}
          onChannelChange={setActiveChannel}
        />
        <LiveStatus className="hidden xl:block" />
        <div className="ml-auto">
          <StockSearch />
        </div>
      </div>

      {/* Full-bleed: the negative margin cancels main's px-6 so the two-column
          split and its divider run the whole width of the page. */}
      <div className="-mx-6 border-t border-[#1c1c1f]">
        <NarrativeStocksList limit={100} category={category} channel={channel} />
      </div>
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
