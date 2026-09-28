/** Seven days of mention counts as a bare polyline, with the window's TOTAL
 *  beside it. No axes, no grid: at 56x16 the shape is the whole message -- is
 *  attention building or fading -- and anything else is noise at this size.
 *
 *  The number is the 7-day sum, not the last day's count: a lone trailing digit
 *  next to a week-long line reads as the week's volume, so showing "1" for a
 *  stock with 40 mentions this week actively misleads.
 *
 *  Drawn as inline SVG rather than through the charting library because a table
 *  renders 100 of these; Recharts would mount 100 ResponsiveContainers and their
 *  resize observers for what is ultimately six line segments. */

const W = 56;
const H = 16;
const PAD = 1.5; // keeps the 1.5px stroke from clipping at the box edges

export function MentionSparkline({
  data,
  className = "",
}: {
  data?: number[] | null;
  className?: string;
}) {
  if (!data || data.length < 2) {
    return <span className={`text-muted-foreground/40 ${className}`}>·</span>;
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min;
  const total = data.reduce((a, b) => a + b, 0);

  const stepX = (W - PAD * 2) / (data.length - 1);
  const points = data
    .map((v, i) => {
      const x = PAD + i * stepX;
      // A flat series has no range to normalize against; draw it down the middle
      // rather than dividing by zero and collapsing it onto the top edge.
      const t = span === 0 ? 0.5 : (v - min) / span;
      const y = H - PAD - t * (H - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  // Direction over the window, compared against the midpoint rather than the
  // previous day so a single quiet day doesn't flip a clearly rising week.
  const half = Math.floor(data.length / 2);
  const early = data.slice(0, half).reduce((a, b) => a + b, 0);
  const late = data.slice(half).reduce((a, b) => a + b, 0);
  const stroke =
    late > early ? "hsl(var(--up))" : late < early ? "hsl(var(--muted-foreground))" : "hsl(var(--muted-foreground))";

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        className="overflow-visible shrink-0"
        aria-hidden="true"
      >
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth="1.25"
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity="0.85"
        />
      </svg>
      <span
        className="text-[11px] text-muted-foreground tnum cursor-help"
        title={`${total} mention${total === 1 ? "" : "s"} over the last 7 days (${data.join(", ")}).`}
      >
        {total}
      </span>
    </span>
  );
}
