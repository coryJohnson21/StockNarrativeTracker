import type { SourceExtractions } from "@/lib/api";

const CALL_COLORS: Record<string, string> = {
  buy:   "text-green-400",
  watch: "text-blue-400",
  hold:  "text-yellow-400",
  avoid: "text-orange-400",
  sell:  "text-red-400",
};

function sentimentLabel(score: number) {
  if (score >= 50)  return { label: "Bullish",  color: "text-green-400" };
  if (score >= 20)  return { label: "Positive", color: "text-green-300" };
  if (score <= -50) return { label: "Bearish",  color: "text-red-400" };
  if (score <= -20) return { label: "Negative", color: "text-red-300" };
  return { label: "Neutral", color: "text-muted-foreground" };
}

type Props = Pick<SourceExtractions, "calls" | "stocks" | "themes">;

export function ExtractionDetailGrid({ calls, stocks, themes }: Props) {
  if (calls.length === 0 && stocks.length === 0 && themes.length === 0) {
    return <p className="text-sm text-muted-foreground">No stocks, themes, or calls were extracted from this source.</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {calls.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Calls</p>
          <ul className="space-y-2">
            {calls.map((c, i) => (
              <li key={i} className="text-sm">
                <span className="font-medium">{c.ticker}</span>
                <span className={`ml-2 font-semibold uppercase text-xs ${CALL_COLORS[c.call] ?? ""}`}>{c.call}</span>
                {c.price_target != null && (
                  <span className="ml-2 text-xs text-muted-foreground">${c.price_target}</span>
                )}
                {c.reasoning && <p className="text-xs text-muted-foreground mt-0.5">{c.reasoning}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {stocks.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Stocks Mentioned</p>
          <ul className="space-y-2">
            {stocks.map((s, i) => {
              const { label, color } = sentimentLabel(s.sentiment);
              return (
                <li key={i} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{s.ticker}</span>
                    <span className={`text-xs ${color}`}>{label}</span>
                  </div>
                  {s.context && <p className="text-xs text-muted-foreground mt-0.5">{s.context}</p>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {themes.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Themes</p>
          <ul className="space-y-2">
            {themes.map((t, i) => {
              const { label, color } = sentimentLabel(t.sentiment);
              return (
                <li key={i} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{t.name}</span>
                    <span className={`text-xs ${color}`}>{label}</span>
                  </div>
                  {t.context && <p className="text-xs text-muted-foreground mt-0.5">{t.context}</p>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
