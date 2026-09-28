"use client";

import type { Stage } from "@/types";
import { STAGES, STAGE_COLOR, stageLabel } from "@/lib/stages";

/** One pill per stage with its count. Clicking filters to that stage; clicking
 *  the active pill clears the filter.
 *
 *  Counts are passed in from the unfiltered dataset, never recomputed from the
 *  filtered rows -- otherwise selecting "Positive" would drop every other count
 *  to zero and the pills would stop being a summary of the whole list. */
export function SignalFilterPills({
  counts,
  active,
  onChange,
}: {
  counts: Record<string, number>;
  active: Stage | null;
  onChange: (next: Stage | null) => void;
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {STAGES.map((stage) => {
        const count = counts[stage] ?? 0;
        const isActive = active === stage;
        return (
          <button
            key={stage}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(isActive ? null : stage)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-[11px] py-[5px] text-[13px] transition-colors ${
              isActive
                ? "border-transparent bg-[#1f1f23] text-white"
                : "border-[#26262a] text-foreground/80 hover:text-foreground hover:border-[#35353b]"
            }`}
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full shrink-0"
              style={{ background: STAGE_COLOR[stage] }}
            />
            {stageLabel(stage)}
            <span className="font-mono text-[12px] text-muted-foreground">{count}</span>
          </button>
        );
      })}
    </div>
  );
}
