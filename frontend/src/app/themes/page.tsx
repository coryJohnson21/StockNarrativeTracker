"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import { CategoryToggle } from "@/components/CategoryToggle";
import type { SourceCategory } from "@/lib/api";

function ThemesPageContent() {
  const params = useSearchParams();
  const initial = params.get("category");
  const [category, setCategory] = useState<SourceCategory | undefined>(
    initial === "filing" || initial === "media" ? initial : undefined
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Layers className="h-7 w-7 text-purple-400" />
          Trending Themes
        </h1>
        <p className="text-muted-foreground mt-1">
          Investment themes ranked by narrative momentum across all ingested financial media.
        </p>
      </div>

      <CategoryToggle value={category} onChange={setCategory} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">All Tracked Themes</CardTitle>
          <CardDescription>
            Click any row to see the AI summary. Includes AI, Nuclear, Cybersecurity, and 20+ categories.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <TrendingThemesTable limit={100} category={category} />
        </CardContent>
      </Card>
    </div>
  );
}

export default function ThemesPage() {
  return (
    <Suspense fallback={null}>
      <ThemesPageContent />
    </Suspense>
  );
}
