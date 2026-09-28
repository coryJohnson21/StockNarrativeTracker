/** What changed since the last scoring run, replacing the old "Previous" column.
 *
 *  That column repeated a full second signal chip to say something that is only
 *  interesting when it differs from the current one -- on most rows it was the
 *  same word twice. Here an unchanged signal collapses to a dot.
 *
 *  Note this is a *label* transition (Building -> Positive), not a rank move:
 *  the momentum table stores previous_label, and no previous rank, so an arrow
 *  with a number beside it would be inventing a figure the API never sent. */

const ORDER = ["negative", "fading", "mixed", "building", "positive"];

export function SignalDelta({
  current,
  previous,
  className = "",
}: {
  current?: string;
  previous?: string;
  className?: string;
}) {
  if (!previous || !current || previous === current) {
    return (
      <span
        className={`text-muted-foreground/40 ${className}`}
        title={previous ? "Unchanged since the last scoring run." : "No prior reading."}
      >
        ·
      </span>
    );
  }

  const from = ORDER.indexOf(previous);
  const to = ORDER.indexOf(current);
  const known = from !== -1 && to !== -1;
  const improved = known && to > from;

  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] whitespace-nowrap cursor-help ${
        !known ? "text-muted-foreground" : improved ? "text-up" : "text-down"
      } ${className}`}
      title={`Signal moved from ${cap(previous)} to ${cap(current)} since the last scoring run.`}
    >
      {known && <span aria-hidden="true">{improved ? "↑" : "↓"}</span>}
      <span className="text-muted-foreground/80">{cap(previous)}</span>
    </span>
  );
}
