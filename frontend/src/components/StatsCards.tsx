"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, BarChart2, Layers, Loader2 } from "lucide-react";
import { getDashboardStats } from "@/lib/api";
import type { DashboardStats } from "@/types";

export function StatsCards() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .finally(() => setLoading(false));

    const interval = setInterval(() => {
      getDashboardStats().then(setStats);
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4 flex items-center justify-center h-20">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: "Sources Ingested",
      value: stats?.total_sources ?? 0,
      sub: stats?.sources_processing ? `${stats.sources_processing} processing` : "all complete",
      icon: BarChart2,
      color: "text-blue-400",
    },
    {
      label: "Stocks Tracked",
      value: stats?.total_stocks_tracked ?? 0,
      sub: stats?.top_stock ? `#1 ${stats.top_stock}` : "none yet",
      icon: TrendingUp,
      color: "text-green-400",
    },
    {
      label: "Themes Tracked",
      value: stats?.total_themes_tracked ?? 0,
      sub: stats?.top_theme ? `#1 ${stats.top_theme}` : "none yet",
      icon: Layers,
      color: "text-purple-400",
    },
    {
      label: "Top Momentum",
      value: stats?.top_stock ?? stats?.top_theme ?? "—",
      sub: "highest score right now",
      icon: TrendingUp,
      color: "text-yellow-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map(({ label, value, sub, icon: Icon, color }) => (
        <Card key={label}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
                <p className="text-2xl font-bold mt-1">{value}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
              </div>
              <Icon className={`h-5 w-5 ${color}`} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
