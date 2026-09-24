import type { SymbolStatus } from "@/types";

/** Why a ticker has no tradeable security behind it. Both cases look identical in
 *  the data -- a row with no price -- but mean different things, so the tooltip
 *  says which. See backend/app/services/symbols.py. */
const REASON: Record<Exclude<SymbolStatus, "ok">, string> = {
  unknown:
    "No US-listed symbol under this ticker. Usually a private company named in the transcript, or a ticker the extraction got wrong. It is still tracked for narrative, but there is no price behind it.",
  mismatch:
    "This ticker resolves to an index or quote feed rather than the company named, so any price on it would be the wrong security's. Tracked for narrative only.",
};

/** Marks a row whose ticker is not tradeable. Renders nothing for real symbols and
 *  for tickers never checked, so an unverified row is not accused of being fake. */
export function SymbolStatusBadge({
  status,
  className = "",
}: {
  status?: SymbolStatus | null;
  className?: string;
}) {
  if (!status || status === "ok") return null;
  return (
    <span
      title={REASON[status]}
      className={`inline-flex items-center whitespace-nowrap rounded border border-amber-500/30 bg-amber-500/10 px-1 py-px text-[9px] font-medium uppercase tracking-wide text-amber-500/90 cursor-help ${className}`}
    >
      Not tradeable
    </span>
  );
}
