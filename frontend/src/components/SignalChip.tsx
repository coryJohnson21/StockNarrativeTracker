const LABEL_STYLES: Record<string, string> = {
  positive: "bg-green-500/10 text-green-400 border border-green-500/20",
  building: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  mixed: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  fading: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
  negative: "bg-red-500/10 text-red-400 border border-red-500/20",
};

export function SignalChip({ label, dim = false }: { label?: string; dim?: boolean }) {
  if (!label) return <span className="text-muted-foreground">—</span>;
  const style = dim
    ? "text-muted-foreground text-xs"
    : `inline-flex w-24 items-center justify-center rounded-full px-2 py-0.5 text-xs font-medium text-center ${LABEL_STYLES[label] ?? "bg-muted text-muted-foreground"}`;
  return <span className={style}>{label.charAt(0).toUpperCase() + label.slice(1)}</span>;
}
