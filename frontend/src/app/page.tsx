import Link from "next/link";
import { ArrowRight, TrendingUp, Layers, Upload, Landmark, Newspaper } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/StatsCards";
import { TrendingStocksTable } from "@/components/TrendingStocksTable";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";

function CategorySection({
  title,
  description,
  icon,
  category,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  category: "filing" | "media";
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {icon}
        <div>
          <h2 className="text-lg font-semibold leading-tight">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
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
              <Link href={`/stocks?category=${category}`} className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingStocksTable limit={10} compact category={category} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              Trending Themes
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href={`/themes?category=${category}`} className="text-xs text-muted-foreground gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <TrendingThemesTable limit={10} compact category={category} />
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

      <CategorySection
        title="Press Releases & Earnings Transcripts"
        description="10-K, 10-Q, 8-K earnings releases, and earnings call transcripts"
        icon={<Landmark className="h-5 w-5 text-emerald-400" />}
        category="filing"
      />

      <CategorySection
        title="Media Tracking"
        description="CNBC, Bloomberg, YouTube, podcasts, and other financial media"
        icon={<Newspaper className="h-5 w-5 text-blue-400" />}
        category="media"
      />
    </div>
  );
}
