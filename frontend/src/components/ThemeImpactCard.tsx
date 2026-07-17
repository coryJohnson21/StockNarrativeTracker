import Link from "next/link";
import { TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Globe2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ThemeImpactAnalysis, ThemeImpactEntry } from "@/types";

const LABEL_VARIANT: Record<ThemeImpactEntry["label"], "bullish" | "bearish" | "neutral"> = {
  "Positive correlation": "bullish",
  "Negative correlation": "bearish",
  Neutral: "neutral",
  "Historically correlated": "neutral",
  "Currently diverging": "neutral",
};

function ImpactRow({ entry }: { entry: ThemeImpactEntry }) {
  const DirectionIcon = entry.direction === "up" ? ArrowUpRight : ArrowDownRight;
  const directionColor = entry.direction === "up" ? "text-green-400" : "text-red-400";

  const targetContent =
    entry.target_type === "theme" ? (
      <Link href={`/themes/${encodeURIComponent(entry.target)}`} className="font-semibold hover:underline">
        {entry.target}
      </Link>
    ) : entry.target_type === "stock" ? (
      <Link href={`/stocks/${entry.target}`} className="font-semibold font-mono hover:underline">
        {entry.target}
      </Link>
    ) : (
      <span className="font-semibold inline-flex items-center gap-1">
        <Globe2 className="h-3.5 w-3.5" />
        {entry.target}
      </span>
    );

  return (
    <div className="flex items-start gap-2.5 py-2">
      <DirectionIcon className={`h-4 w-4 mt-0.5 shrink-0 ${directionColor}`} />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          {targetContent}
          <Badge variant={LABEL_VARIANT[entry.label]} className="text-[10px] px-1.5 py-0">
            {entry.label}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground leading-snug">{entry.rationale}</p>
      </div>
    </div>
  );
}

export function ThemeImpactCard({ themeName, analysis }: { themeName: string; analysis: ThemeImpactAnalysis }) {
  if (analysis.rising.length === 0 && analysis.falling.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Correlation Engine</CardTitle>
        <CardDescription>
          How other narratives tend to move if {themeName} rises or falls. AI-generated from general
          market reasoning, not statistically derived from ingested mentions.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <div className="flex items-center gap-1.5 text-sm font-medium mb-1 text-green-400">
              <TrendingUp className="h-4 w-4" />
              If {themeName} rises
            </div>
            <div className="divide-y divide-border/50">
              {analysis.rising.map((entry, i) => (
                <ImpactRow key={i} entry={entry} />
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-1.5 text-sm font-medium mb-1 text-red-400">
              <TrendingDown className="h-4 w-4" />
              If {themeName} falls
            </div>
            <div className="divide-y divide-border/50">
              {analysis.falling.map((entry, i) => (
                <ImpactRow key={i} entry={entry} />
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
