"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getStockPriceHistory, type PriceRange } from "@/lib/api";

const RANGES: { value: PriceRange; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "5y", label: "5Y" },
];

export function StockPriceChart({ ticker, currency }: { ticker: string; currency?: string }) {
  const [range, setRange] = useState<PriceRange>("6mo");
  const [points, setPoints] = useState<{ date: string; close: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStockPriceHistory(ticker, range)
      .then((r) => setPoints(r.points))
      .catch(() => setPoints([]))
      .finally(() => setLoading(false));
  }, [ticker, range]);

  const first = points[0]?.close;
  const last = points[points.length - 1]?.close;
  const up = first !== undefined && last !== undefined && last >= first;

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
            No price history available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor={up ? "#34d399" : "#f87171"}
                    stopOpacity={0.35}
                  />
                  <stop
                    offset="95%"
                    stopColor={up ? "#34d399" : "#f87171"}
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.5 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.5 }}
                tickLine={false}
                axisLine={false}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => [`${currency || "$"}${Number(value ?? 0).toFixed(2)}`, "Close"]}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={up ? "#34d399" : "#f87171"}
                strokeWidth={2}
                fill="url(#priceFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
