"use client";

import { useEffect, useState, useCallback } from "react";
import { Database, RefreshCw, Trash2, Loader2, Youtube, FileText, Landmark, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getSources, deleteSource } from "@/lib/api";
import { timeAgo, formatDuration } from "@/lib/utils";
import type { Source } from "@/types";

const statusVariant: Record<string, "default" | "secondary" | "bullish" | "bearish" | "neutral"> = {
  completed: "bullish",
  processing: "neutral",
  pending: "secondary",
  failed: "bearish",
};

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

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
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Database className="h-7 w-7 text-blue-400" />
            Sources
          </h1>
          <p className="text-muted-foreground mt-1">
            {total} ingested source{total !== 1 ? "s" : ""}
          </p>
        </div>
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
                  <tr key={source.id} className="border-b border-border/50 hover:bg-accent/20 transition-colors">
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
                          {source.url && (
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
                          )}
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
                    <td className="py-3 px-4">
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
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
