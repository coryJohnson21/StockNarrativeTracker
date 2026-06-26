"use client";

import { useEffect, useState, useCallback } from "react";
import { Database, RefreshCw, Trash2, Loader2, Youtube, FileText, Landmark, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getSources, deleteSource, getSourceExtractions } from "@/lib/api";
import type { SourceExtractions } from "@/lib/api";
import { timeAgo, formatDuration } from "@/lib/utils";
import type { Source } from "@/types";
import { PodcastFeedsTab } from "@/components/PodcastFeedsTab";
import { RedditFeedsTab } from "@/components/RedditFeedsTab";

const statusVariant: Record<string, "default" | "secondary" | "bullish" | "bearish" | "neutral"> = {
  completed: "bullish",
  processing: "neutral",
  pending: "secondary",
  failed: "bearish",
};

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

function isMediaSource(type: string) {
  return ["podcast", "news", "reddit", "youtube"].includes(type);
}

function ExtractionPanel({ sourceId }: { sourceId: string }) {
  const [data, setData] = useState<SourceExtractions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSourceExtractions(sourceId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sourceId]);

  if (loading) return (
    <div className="flex items-center gap-2 py-4 px-6 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading extraction…
    </div>
  );
  if (error) return <p className="py-4 px-6 text-sm text-red-400">{error}</p>;
  if (!data) return null;

  return (
    <div className="px-6 py-4 space-y-5 bg-accent/10 border-t border-border/50">
      {/* Summary */}
      {data.summary && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Summary</p>
          <p className="text-sm leading-relaxed">{data.summary}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Calls */}
        {data.calls.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Calls</p>
            <ul className="space-y-2">
              {data.calls.map((c, i) => (
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

        {/* Stocks */}
        {data.stocks.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Stocks Mentioned</p>
            <ul className="space-y-2">
              {data.stocks.map((s, i) => {
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

        {/* Themes */}
        {data.themes.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Themes</p>
            <ul className="space-y-2">
              {data.themes.map((t, i) => {
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
    </div>
  );
}

function SourcesTable() {
  const [sources, setSources] = useState<Source[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getSources({ limit: 100 });
      setSources(r.sources);
      setTotal(r.total);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const hasActive = sources.some((s) => s.status === "pending" || s.status === "processing");
    const interval = setInterval(load, hasActive ? 5000 : 30000);
    return () => clearInterval(interval);
  }, [load, sources.length]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this source and all its extracted data?")) return;
    await deleteSource(id);
    setSources((prev) => prev.filter((s) => s.id !== id));
    if (expandedId === id) setExpandedId(null);
  }

  function toggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{total} ingested source{total !== 1 ? "s" : ""}</p>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : sources.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Database className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No sources yet. Add content to get started.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
                  <th className="text-left py-2 px-4">Source</th>
                  <th className="text-left py-2 px-4">Channel</th>
                  <th className="text-left py-2 px-4">Status</th>
                  <th className="text-right py-2 px-4">Duration</th>
                  <th className="text-right py-2 px-4">Added</th>
                  <th className="py-2 px-4"></th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <>
                    <tr
                      key={source.id}
                      className={`border-b border-border/50 transition-colors ${
                        isMediaSource(source.type) && source.status === "completed"
                          ? "cursor-pointer hover:bg-accent/20"
                          : ""
                      } ${expandedId === source.id ? "bg-accent/10" : ""}`}
                      onClick={() => {
                        if (isMediaSource(source.type) && source.status === "completed") {
                          toggleExpand(source.id);
                        }
                      }}
                    >
                      <td className="py-3 px-4 max-w-xs">
                        <div className="flex items-center gap-2">
                          {source.type === "youtube" ? (
                            <Youtube className="h-4 w-4 text-red-400 shrink-0" />
                          ) : source.type === "10-K" || source.type === "10-Q" || source.type === "8-K" ? (
                            <Landmark className="h-4 w-4 text-emerald-400 shrink-0" />
                          ) : (
                            <FileText className="h-4 w-4 text-blue-400 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <p className="font-medium truncate">{source.title || "Untitled"}</p>
                            {isMediaSource(source.type) && source.status === "completed" ? (
                              <span className="text-xs text-primary flex items-center gap-0.5 mt-0.5">
                                {expandedId === source.id
                                  ? <><ChevronUp className="h-3 w-3" /> Hide extraction</>
                                  : <><ChevronDown className="h-3 w-3" /> View extraction</>
                                }
                              </span>
                            ) : source.url ? (
                              <a
                                href={source.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-muted-foreground hover:text-primary flex items-center gap-0.5 mt-0.5"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <ExternalLink className="h-3 w-3" />
                                View original
                              </a>
                            ) : null}
                            {source.error_message && (
                              <p className="text-xs text-red-400 mt-0.5 truncate">{source.error_message}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-muted-foreground">{source.channel || "—"}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5">
                          {(source.status === "pending" || source.status === "processing") && (
                            <Loader2 className="h-3 w-3 animate-spin text-yellow-400" />
                          )}
                          <Badge variant={statusVariant[source.status] || "secondary"}>
                            {source.status}
                          </Badge>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right text-muted-foreground tabular-nums">
                        {formatDuration(source.duration_seconds)}
                      </td>
                      <td className="py-3 px-4 text-right text-muted-foreground text-xs">
                        {timeAgo(source.created_at)}
                      </td>
                      <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-red-400"
                          onClick={() => handleDelete(source.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                    {expandedId === source.id && (
                      <tr key={`${source.id}-expansion`} className="border-b border-border/50">
                        <td colSpan={6} className="p-0">
                          <ExtractionPanel sourceId={source.id} />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function SourcesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Database className="h-7 w-7 text-blue-400" />
          Sources
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage ingested content and feed subscriptions
        </p>
      </div>

      <Tabs defaultValue="sources">
        <TabsList>
          <TabsTrigger value="sources">All Sources</TabsTrigger>
          <TabsTrigger value="podcasts">Podcast Feeds</TabsTrigger>
          <TabsTrigger value="reddit">Reddit Feeds</TabsTrigger>
        </TabsList>

        <TabsContent value="sources" className="mt-4">
          <SourcesTable />
        </TabsContent>

        <TabsContent value="podcasts" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Podcast Feeds</CardTitle>
            </CardHeader>
            <CardContent>
              <PodcastFeedsTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reddit" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Reddit Feeds</CardTitle>
            </CardHeader>
            <CardContent>
              <RedditFeedsTab />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
