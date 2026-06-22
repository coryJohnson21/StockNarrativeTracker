"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import { CategoryToggle } from "@/components/CategoryToggle";
import type { SourceCategory } from "@/lib/api";

function StocksPageContent() {
  const params = useSearchParams();
  const initial = params.get("category");
  const [category, setCategory] = useState<SourceCategory | undefined>(
    initial === "filing" || initial === "media" ? initial : undefined
  );

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

      <CategoryToggle value={category} onChange={setCategory} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">All Tracked Stocks</CardTitle>
          <CardDescription>
            Click any row to see the AI-generated investment summary. Momentum score: 0–100.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <TrendingStocksTable limit={100} category={category} />
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
