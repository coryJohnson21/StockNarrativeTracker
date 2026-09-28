"use client";

import { cn } from "@/lib/utils";
import type { SourceCategory, MediaChannel } from "@/lib/api";

export const CHANNELS: { key: MediaChannel | "all"; label: string }[] = [
  { key: "all", label: "All Media" },
  { key: "youtube", label: "YouTube" },
  { key: "podcast", label: "Podcasts" },
  { key: "news", label: "News" },
  { key: "reddit", label: "Reddit" },
  { key: "x", label: "X" },
];

const SEGMENTS: { key: SourceCategory | undefined; label: string }[] = [
  { key: undefined, label: "All" },
  { key: "filing", label: "Filings" },
  { key: "media", label: "Media" },
];

/** Compact segmented control replacing three icon buttons that together ran wider
 *  than the table's first four columns. Icons are gone, the labels are shortened,
 *  and the whole thing is one bordered group so it reads as a single control. */
export function CategoryToggle({
  value,
  onChange,
  channel,
  onChannelChange,
  className = "",
}: {
  value: SourceCategory | undefined;
  onChange: (value: SourceCategory | undefined) => void;
  channel?: MediaChannel | "all";
  onChannelChange?: (next: MediaChannel | "all") => void;
  className?: string;
}) {
  const showChannels = value === "media" && onChannelChange != null;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="inline-flex items-center rounded-sm border border-border overflow-hidden h-7">
        {SEGMENTS.map(({ key, label }, i) => (
          <button
            key={label}
            onClick={() => onChange(key)}
            className={cn(
              "px-2.5 h-full text-[12px] font-medium transition-colors",
              i > 0 && "border-l border-border",
              value === key
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {showChannels && (
        <select
          value={channel}
          onChange={(e) => onChannelChange!(e.target.value as MediaChannel | "all")}
          className="h-7 rounded-sm border border-border bg-background px-2 text-[12px] text-muted-foreground hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer"
        >
          {CHANNELS.map(({ key, label }) => (
            <option key={key} value={key} className="bg-background text-foreground">
              {label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
