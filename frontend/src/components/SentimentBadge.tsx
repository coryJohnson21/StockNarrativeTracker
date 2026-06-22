import { Badge } from "@/components/ui/badge";
import { formatSentiment } from "@/lib/utils";

interface Props {
  score: number;
  showNumber?: boolean;
}

export function SentimentBadge({ score, showNumber = false }: Props) {
  const variant = score >= 20 ? "bullish" : score > -20 ? "neutral" : "bearish";
  const label = showNumber
    ? `${score > 0 ? "+" : ""}${Math.round(score)}`
    : formatSentiment(score);

  return <Badge variant={variant}>{label}</Badge>;
}
