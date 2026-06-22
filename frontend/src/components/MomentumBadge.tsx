import { cn } from "@/lib/utils";

interface Props {
  score: number;
  size?: "sm" | "lg";
}

export function MomentumScore({ score, size = "sm" }: Props) {
  const color =
    score >= 70
      ? "text-green-400"
      : score >= 40
      ? "text-yellow-400"
      : "text-muted-foreground";

  return (
    <span className={cn("font-bold tabular-nums", color, size === "lg" ? "text-2xl" : "text-sm")}>
      {score.toFixed(1)}
    </span>
  );
}

export function MomentumBar({ score }: { score: number }) {
  const pct = Math.round(score);
  const color =
    score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-muted-foreground/40";

  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <MomentumScore score={score} />
    </div>
  );
}
