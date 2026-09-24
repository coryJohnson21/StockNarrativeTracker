"use client";

import Link from "next/link";
import { Flame } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SymbolStatusBadge } from "@/components/SymbolStatusBadge";
import { formatSentiment, sentimentColor } from "@/lib/utils";
import type { RedditTopTicker } from "@/types";

/** The tickers a set of Reddit posts talked about most. Used both for the whole
 *  Reddit surface (trailing week) and for a single subreddit (all time), so the
 *  heading and blurb are caller-supplied. */
export function RedditTopTickers({
  tickers,
  title = "Most mentioned",
  description,
  emptyMessage = "No tickers mentioned yet. They show up once posts have been ingested and processed.",
  rank = false,
}: {
  tickers: RedditTopTicker[];
  title?: string;
  description?: string;
  emptyMessage?: string;
  /** Show 1/2/3 position numbers — for the short "top 3" cut. */
  rank?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Flame className="h-4 w-4 text-orange-400" />
          {title}
        </CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {tickers.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          <ul className="space-y-2">
            {tickers.map((t, i) => (
              <li key={t.ticker} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  {rank && (
                    <span className="text-xs text-muted-foreground tabular-nums w-4 shrink-0">{i + 1}</span>
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Link
                        href={`/stocks/${t.ticker}`}
                        className="font-medium text-sm hover:text-primary transition-colors"
                      >
                        {t.ticker}
                      </Link>
                      <SymbolStatusBadge status={t.symbol_status} />
                    </div>
                    {t.company_name && (
                      <p className="text-xs text-muted-foreground truncate">{t.company_name}</p>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm tabular-nums">
                    {t.mention_count} mention{t.mention_count === 1 ? "" : "s"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t.avg_sentiment !== null && t.avg_sentiment !== undefined ? (
                      <span className={sentimentColor(t.avg_sentiment)}>
                        {formatSentiment(t.avg_sentiment)}
                      </span>
                    ) : (
                      "—"
                    )}
                    {" · "}
                    {t.unique_posts} post{t.unique_posts === 1 ? "" : "s"}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
