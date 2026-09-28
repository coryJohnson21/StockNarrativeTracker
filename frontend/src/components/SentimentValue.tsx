import type { Confidence } from "@/types";

/** Sentiment as a signed number plus its sample size, replacing the "Bullish"
 *  pill. The pill spent a full-width chip and a border to say what +42 says in
 *  four characters, and it colored a third of every row green for a reason
 *  unrelated to price.
 *
 *  Scale is -100..+100 (see backend/app/services/momentum.py), NOT -1..+1. */
export function SentimentValue({
  score,
  n,
  confidence,
  sources,
  className = "",
}: {
  score: number;
  n: number;
  confidence?: Confidence;
  sources?: number;
  className?: string;
}) {
  const tone =
    score >= 20 ? "text-up" : score <= -20 ? "text-down" : "text-muted-foreground";
  const sign = score > 0 ? "+" : "";

  return (
    <span className={`inline-flex items-baseline gap-1.5 ${className}`}>
      <span
        className={`tnum cursor-help ${tone}`}
        title={`Average sentiment ${sign}${Math.round(score)} on a -100..+100 scale.`}
      >
        {sign}
        {Math.round(score)}
      </span>
      <span
        className={`text-[11px] tnum cursor-help ${
          confidence === "low" ? "text-amber-500/80" : "text-muted-foreground/60"
        }`}
        title={`${n} mention${n === 1 ? "" : "s"}${
          sources != null ? ` across ${sources} source${sources === 1 ? "" : "s"}` : ""
        } — ${confidence ?? "unknown"} confidence`}
      >
        {n}
      </span>
    </span>
  );
}
