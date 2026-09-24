"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Target, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getPodcastFeedTrackRecord } from "@/lib/api";
import type { ChannelTrackRecord, ScoredCall } from "@/types";

const HORIZONS = [5, 20, 60];
const COLLAPSED_CALLS = 8;

const CALL_COLORS: Record<string, string> = {
  buy: "text-green-400",
  watch: "text-blue-400",
  hold: "text-yellow-400",
  avoid: "text-orange-400",
  sell: "text-red-400",
};

/** "an episode" / "a post" -- the noun is caller-supplied, so pick the article. */
function article(noun: string): string {
  return /^[aeiou]/i.test(noun) ? "an" : "a";
}

function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** The hover behind the since-return: how long it has run, and to when.
 *  The as-of date matters because prices can lag today by days. */
function sinceHint(call: ScoredCall): string | undefined {
  if (call.return_since_pct === null || call.return_since_pct === undefined) return undefined;
  const called = new Date(call.called_at).toLocaleDateString();
  const asOf = call.since_as_of ? new Date(`${call.since_as_of}T00:00:00`).toLocaleDateString() : null;
  const days = call.since_trading_days;
  const span =
    days === null || days === undefined
      ? "Since the call"
      : days === 0
        ? "Same trading day as the call"
        : `${days} trading day${days === 1 ? "" : "s"} since the call`;
  return `${span} — ${called}${asOf ? ` to the last close on ${asOf}` : ""}. Keeps moving as prices arrive, so it is shown but not scored.`;
}

function signClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-muted-foreground";
  return v >= 0 ? "text-green-400" : "text-red-400";
}

/** What the weight actually means for this channel's pull on the momentum score. */
function weightVerdict(r: ChannelTrackRecord): { text: string; className: string } {
  if (r.n_scored === 0) return { text: "no judged calls yet — counted as a coin flip", className: "text-muted-foreground" };
  if (r.weight >= 1.1) return { text: "mentions count for more than a neutral source", className: "text-green-400" };
  if (r.weight <= 0.9) return { text: "mentions are discounted below a neutral source", className: "text-red-400" };
  return { text: "close enough to a coin flip to count as neutral", className: "text-muted-foreground" };
}

function Stat({ label, value, className, hint }: { label: string; value: string; className?: string; hint?: string }) {
  return (
    <div title={hint}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-xl font-semibold tabular-nums mt-0.5 ${className ?? ""}`}>{value}</p>
    </div>
  );
}

function OutcomeCell({ call }: { call: ScoredCall }) {
  if (!call.directional) {
    return <span className="text-muted-foreground" title="Hold and watch take no side, so they can't be scored">not a bet</span>;
  }
  if (call.correct === null || call.correct === undefined) {
    return <span className="text-muted-foreground" title="Made too recently to have a realized return over the window">pending</span>;
  }
  return call.correct
    ? <span className="text-green-400">right</span>
    : <span className="text-red-400">wrong</span>;
}

function CallRow({ call, benchmark }: { call: ScoredCall; benchmark: string | null }) {
  return (
    <tr className="border-b border-border/50 align-top">
      <td className="py-2 pr-2">
        <Link href={`/stocks/${call.ticker}`} className="font-medium hover:text-primary">{call.ticker}</Link>
        <div className="text-muted-foreground mt-0.5">{new Date(call.called_at).toLocaleDateString()}</div>
      </td>
      <td className="py-2 pr-2">
        <span className={`font-semibold uppercase ${CALL_COLORS[call.call] ?? ""}`}>{call.call}</span>
        {call.price_target != null && <div className="text-muted-foreground mt-0.5">${call.price_target}</div>}
      </td>
      <td className="py-2 pr-2 max-w-md">
        {call.source_url ? (
          <a href={call.source_url} target="_blank" rel="noreferrer" className="hover:text-primary">{call.source_title || "Untitled"}</a>
        ) : (
          <span>{call.source_title || "Untitled"}</span>
        )}
        {call.reasoning && <p className="text-muted-foreground mt-0.5 leading-relaxed">{call.reasoning}</p>}
      </td>
      <td className={`py-2 pr-2 text-right tabular-nums ${signClass(call.return_pct)}`}>{pct(call.return_pct)}</td>
      <td className="py-2 pr-2 text-right tabular-nums text-muted-foreground" title={benchmark ? `${benchmark} over the same window` : undefined}>
        {pct(call.benchmark_return_pct)}
      </td>
      <td className={`py-2 pr-2 text-right tabular-nums font-medium ${signClass(call.alpha_pct)}`} title="Excess return in the direction the call bet on">
        {pct(call.alpha_pct)}
      </td>
      <td className={`py-2 pr-2 text-right tabular-nums ${signClass(call.return_since_pct)}`}>
        <span title={sinceHint(call)} className={call.return_since_pct != null ? "cursor-help border-b border-dotted border-muted-foreground/40" : undefined}>
          {pct(call.return_since_pct)}
        </span>
      </td>
      <td className="py-2 text-right"><OutcomeCell call={call} /></td>
    </tr>
  );
}

export function TrackRecordPanel({
  feedId,
  label,
  fetchTrackRecord = getPodcastFeedTrackRecord,
  /** What one scored item is called here -- "episode" for podcasts, "post" for Reddit. */
  itemNoun = "episode",
}: {
  feedId: string;
  label: string;
  fetchTrackRecord?: (id: string, horizon: number) => Promise<ChannelTrackRecord>;
  itemNoun?: string;
}) {
  const [horizon, setHorizon] = useState(20);
  const [record, setRecord] = useState<ChannelTrackRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchTrackRecord(feedId, horizon)
      .then((r) => !cancelled && setRecord(r))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load track record"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [feedId, horizon, fetchTrackRecord]);

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (loading && !record) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Scoring this feed&apos;s calls…
        </CardContent>
      </Card>
    );
  }
  if (!record) return null;

  const verdict = weightVerdict(record);
  const pending = record.calls.filter((c) => c.directional && (c.correct === null || c.correct === undefined)).length;
  const visible = showAll ? record.calls : record.calls.slice(0, COLLAPSED_CALLS);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="h-4 w-4 text-violet-400" />
              Track record
            </CardTitle>
            <CardDescription>
              Every explicit buy/sell/avoid call {label} made, judged against{" "}
              {record.benchmark ?? "its own raw return"} over the next {record.horizon} trading days. Hold and watch
              calls take no side, so they are listed but not scored. <span className="text-foreground">Since call</span>{" "}
              tracks each one to the latest close for context — it keeps moving, so the verdict stays on the fixed window.
            </CardDescription>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-xs text-muted-foreground mr-1">Window</span>
            {HORIZONS.map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${horizon === h ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent/50"}`}
              >
                {h}d
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {record.n_calls === 0 ? (
          <p className="text-sm text-muted-foreground">
            No explicit calls extracted from this feed yet. Calls are picked up when {article(itemNoun)} {itemNoun} names a
            ticker and takes a clear position on it.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 pb-4 border-b border-border">
              <Stat label="Calls made" value={String(record.n_calls)} />
              <Stat
                label="Judged"
                value={String(record.n_scored)}
                hint={`Directional calls old enough to have a realized ${record.horizon}-day return`}
              />
              <Stat
                label="Hit rate"
                value={record.hit_rate === null ? "—" : `${(record.hit_rate * 100).toFixed(0)}%`}
                className={record.hit_rate === null ? "text-muted-foreground" : record.hit_rate >= 0.5 ? "text-green-400" : "text-red-400"}
                hint={record.wilson_lower === null ? undefined : `At least ${(record.wilson_lower * 100).toFixed(0)}% with 95% confidence`}
              />
              <Stat
                label="Mean alpha"
                value={pct(record.mean_alpha_pct, 2)}
                className={signClass(record.mean_alpha_pct)}
                hint="Average excess return in the direction each call bet on"
              />
              <Stat label="Momentum weight" value={`${record.weight.toFixed(2)}×`} className={verdict.className} />
            </div>

            <p className={`text-xs mt-3 ${verdict.className}`}>
              {verdict.text}
              {record.n_scored > 0 && record.n_scored < 10 ? (
                <span className="text-muted-foreground">
                  {" "}— only {record.n_scored} judged call{record.n_scored === 1 ? "" : "s"}, so the weight stays shrunk toward 1.0.
                </span>
              ) : (
                "."
              )}
              {pending > 0 && (
                <span className="text-muted-foreground">
                  {" "}{pending} more {pending === 1 ? "is" : "are"} waiting on prices.
                </span>
              )}
            </p>

            <div className="overflow-x-auto mt-4">
              <table className="w-full text-xs">
                <thead className="text-muted-foreground uppercase tracking-wide">
                  <tr className="border-b border-border">
                    <th className="text-left py-1.5 pr-2">Ticker</th>
                    <th className="text-left py-1.5 pr-2">Call</th>
                    <th className="text-left py-1.5 pr-2 capitalize">{itemNoun}</th>
                    <th className="text-right py-1.5 pr-2" title={`Return over the ${record.horizon} trading days after the call — the fixed window the outcome is judged on`}>
                      {record.horizon}d return
                    </th>
                    <th className="text-right py-1.5 pr-2">{record.benchmark ?? "Bench"}</th>
                    <th className="text-right py-1.5 pr-2">Alpha</th>
                    <th className="text-right py-1.5 pr-2" title="Return from the call to the most recent close — hover a value for the elapsed span. Not scored.">
                      Since call
                    </th>
                    <th className="text-right py-1.5">Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((c) => (
                    <CallRow key={`${c.source_id}-${c.ticker}`} call={c} benchmark={record.benchmark} />
                  ))}
                </tbody>
              </table>
            </div>

            {record.calls.length > COLLAPSED_CALLS && (
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="text-xs text-primary flex items-center gap-0.5 mt-3"
              >
                {showAll ? (
                  <>Show fewer <ChevronUp className="h-3 w-3" /></>
                ) : (
                  <>Show all {record.calls.length} calls <ChevronDown className="h-3 w-3" /></>
                )}
              </button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
