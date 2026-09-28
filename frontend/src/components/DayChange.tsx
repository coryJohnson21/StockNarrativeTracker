/** Last completed session's percent change.
 *
 *  Named "Day" in the header but sourced from stored daily closes, so during a
 *  trading session it shows the previous close-to-close move, not an intraday
 *  one. The tooltip says so rather than letting the number imply it is live. */
export function DayChange({
  value,
  className = "",
}: {
  value?: number | null;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return (
      <span
        className={`text-muted-foreground/40 ${className}`}
        title="Not enough stored daily closes to compute a session change."
      >
        ·
      </span>
    );
  }

  // Exactly zero is a real reading, not an absence -- show it neutral rather than
  // coloring it green for being non-negative.
  const tone =
    value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted-foreground";
  const sign = value > 0 ? "+" : "";

  return (
    <span
      className={`tnum cursor-help ${tone} ${className}`}
      title="Change between the last two stored daily closes. Not intraday."
    >
      {sign}
      {value.toFixed(2)}%
    </span>
  );
}
