/** A small dot plus the label, replacing the bordered pill.
 *
 *  The pill was a 96px chip with a background, a border and a full-width center
 *  on every row -- five of them stacked read as a column of buttons. The dot
 *  carries the same categorical color in 6px, so the word stays the thing you
 *  read and the color stays available for price and sentiment.
 *
 *  Note "building" is deliberately neutral gray, not blue: it means "attention is
 *  accumulating", which is not itself bullish, and coloring it would put a third
 *  directional hue in a table that reserves green and red for direction. */
const DOT: Record<string, string> = {
  positive: "bg-up",
  building: "bg-muted-foreground",
  mixed: "bg-amber-500",
  fading: "bg-amber-600/70",
  negative: "bg-down",
};

export function SignalChip({ label, dim = false }: { label?: string; dim?: boolean }) {
  if (!label) return <span className="text-muted-foreground/40">·</span>;

  const text = label.charAt(0).toUpperCase() + label.slice(1);

  if (dim) {
    return <span className="text-xs text-muted-foreground">{text}</span>;
  }

  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span
        className={`h-1.5 w-1.5 rounded-full shrink-0 ${DOT[label] ?? "bg-muted-foreground"}`}
        aria-hidden="true"
      />
      <span className="text-foreground">{text}</span>
    </span>
  );
}
