import type { Stage } from "@/types";

/** The five narrative stages, weakest to strongest.
 *
 *  Building and Mixed are deliberately equal rank (index 2 and 2): "attention is
 *  accumulating" and "opinion is split" are different situations, not one better
 *  than the other, so moving between them is not an upgrade or a downgrade. The
 *  spec's ordering is Fading < Emerging < Building = Mixed < Positive. */
const RANK: Record<Stage, number> = {
  fading: 0,
  emerging: 1,
  building: 2,
  mixed: 2,
  positive: 3,
};

/** Display order for the filter pills: strongest first, so the most actionable
 *  stages sit where the eye lands. */
export const STAGES: Stage[] = ["positive", "building", "mixed", "emerging", "fading"];

export const STAGE_COLOR: Record<Stage, string> = {
  positive: "var(--stage-positive)",
  building: "var(--stage-building)",
  mixed: "var(--stage-mixed)",
  emerging: "var(--stage-emerging)",
  fading: "var(--stage-fading)",
};

export function isStage(v?: string | null): v is Stage {
  return !!v && v in RANK;
}

export function stageLabel(s: Stage): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function stageColor(s?: string | null): string {
  return isStage(s) ? STAGE_COLOR[s] : "hsl(var(--muted-foreground))";
}

/** "up" | "down" | null for a transition. Null when either stage is unknown or
 *  the two rank equally -- an equal-rank move is a change of character, not a
 *  promotion, and drawing an arrow on it would assert something false. */
export function stageDirection(from?: string | null, to?: string | null): "up" | "down" | null {
  if (!isStage(from) || !isStage(to)) return null;
  if (RANK[to] === RANK[from]) return null;
  return RANK[to] > RANK[from] ? "up" : "down";
}
