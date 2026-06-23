"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Bar, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getStockMentionHistory, type PriceRange, type MentionHistoryPoint } from "@/lib/api";

const RANGES: { value: PriceRange; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "5y", label: "5Y" },
];

export function MomentumHistoryChart({ ticker }: { ticker: string }) {
  const [range, setRange] = useState<PriceRange>("6mo");
  const [points, setPoints] = useState<MentionHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStockMentionHistory(ticker, range)
      .then((r) => setPoints(r.points))
      .catch(() => setPoints([]))
      .finally(() => setLoading(false));
  }, [ticker, range]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-1">
        {RANGES.map((r) => (
          <button
            key={r.value}
            onClick={() => setRange(r.value)}
            className={`text-xs px-2 py-1 rounded-md transition-colors ${
              range === r.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent/50"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="h-56">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : points.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            No mention history available yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.5 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
              />
              <YAxis
                yAxisId="mentions"
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.5 }}
                tickLine={false}
                axisLine={false}
                width={32}
                allowDecimals={false}
              />
              <YAxis
                yAxisId="sentiment"
                orientation="right"
                domain={[-100, 100]}
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.5 }}
                tickLine={false}
                axisLine={false}
                width={36}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value, name) =>
                  name === "avg_sentiment"
                    ? [Number(value ?? 0).toFixed(0), "Sentiment"]
                    : [value, "Mentions"]
                }
              />
              <Bar yAxisId="mentions" dataKey="mention_count" fill="#818cf8" radius={[3, 3, 0, 0]} />
              <Line
                yAxisId="sentiment"
                type="monotone"
                dataKey="avg_sentiment"
                stroke="#facc15"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-[#818cf8]" /> Mentions
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 bg-[#facc15]" /> Avg. sentiment
        </span>
      </div>
    </div>
  );
}
