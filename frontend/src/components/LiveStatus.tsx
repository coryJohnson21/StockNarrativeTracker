"use client";

import { useEffect, useState } from "react";
import { getDashboardStats } from "@/lib/api";
import type { DashboardStats } from "@/types";

/** "Updated 10:02 · 214 tickers · 18 sources processing" — replaces the static
 *  marketing subtitle under the page title.
 *
 *  The timestamp is when this component fetched, rendered client-side only: a
 *  server-rendered clock would hydrate to the server's timezone and then jump. */
export function LiveStatus({ className = "" }: { className?: string }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [at, setAt] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getDashboardStats()
      .then((s) => {
        if (!alive) return;
        setStats(s);
        setAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      })
      .catch(() => {
        /* The status line is ambient; a failed fetch should leave the page alone
           rather than surface an error where a timestamp goes. */
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!stats || !at) {
    // Reserve the line's height so the toolbar doesn't jump when it lands.
    return <p className={`text-[12px] text-transparent select-none ${className}`}>&nbsp;</p>;
  }

  const parts = [
    `Updated ${at}`,
    `${stats.total_stocks_tracked.toLocaleString()} tickers`,
    `${stats.total_themes_tracked.toLocaleString()} themes`,
    `${stats.total_sources.toLocaleString()} sources`,
  ];
  if (stats.sources_processing > 0) {
    parts.push(`${stats.sources_processing} processing`);
  }

  return (
    <p className={`text-[12px] text-muted-foreground font-mono ${className}`}>
      {parts.join("  ·  ")}
    </p>
  );
}
