/** Wilder's RSI-14 on daily closes. Shared by the stocks table and the stock
 *  landing page so one ticker never shows two different readings.
 *
 *  Colour marks the conventional 30/70 zones, but deliberately stays muted in the
 *  50-70 middle: in a sustained trend RSI can sit above 70 for weeks, so a high
 *  reading is context, not a sell signal. The tooltip says as much. */

const OVERBOUGHT = 70;
const OVERSOLD = 30;

export function rsiZone(value: number): "overbought" | "oversold" | "neutral" {
  if (value >= OVERBOUGHT) return "overbought";
  if (value <= OVERSOLD) return "oversold";
  return "neutral";
}

const ZONE_CLASS: Record<ReturnType<typeof rsiZone>, string> = {
  overbought: "text-orange-400",
  oversold: "text-sky-400",
  neutral: "text-muted-foreground",
};

export function rsiHint(value: number): string {
  const zone = rsiZone(value);
  const base = `RSI-14 ${value.toFixed(1)} (Wilder, daily closes).`;
  if (zone === "overbought") {
    return `${base} Above ${OVERBOUGHT} is conventionally "overbought", but RSI can stay pinned there through a strong uptrend — read it as stretched, not as a signal to sell.`;
  }
  if (zone === "oversold") {
    return `${base} Below ${OVERSOLD} is conventionally "oversold". In a downtrend it can stay there, so it marks weakness rather than a floor.`;
  }
  return `${base} Between ${OVERSOLD} and ${OVERBOUGHT} is the neutral band; 50 divides net-up from net-down momentum.`;
}

export function RsiValue({
  value,
  className = "",
}: {
  value?: number | null;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return (
      <span
        className={`text-muted-foreground ${className}`}
        title="Not enough daily closes stored yet to compute a 14-period RSI."
      >
        —
      </span>
    );
  }
  return (
    <span className={`tabular-nums cursor-help ${ZONE_CLASS[rsiZone(value)]} ${className}`} title={rsiHint(value)}>
      {value.toFixed(1)}
    </span>
  );
}
