"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Youtube, FileText, CheckCircle, AlertCircle, Landmark } from "lucide-react";
import { ingestYouTube, ingestTranscript, scanSecTicker } from "@/lib/api";
import type { Source } from "@/types";

interface Result {
  source?: Source;
  count?: number;
  type: "youtube" | "transcript" | "sec";
}

export function IngestForm() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  // YouTube tab state
  const [ytUrl, setYtUrl] = useState("");

  // Transcript tab state
  const [txTitle, setTxTitle] = useState("");
  const [txChannel, setTxChannel] = useState("");
  const [txContent, setTxContent] = useState("");

  // SEC tab state
  const [secTicker, setSecTicker] = useState("");

  function reset() {
    setResult(null);
    setError(null);
  }

  async function handleYouTube(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const source = await ingestYouTube(ytUrl);
      setResult({ source, type: "youtube" });
      setYtUrl("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleTranscript(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const source = await ingestTranscript({
        title: txTitle,
        content: txContent,
        channel: txChannel || undefined,
      });
      setResult({ source, type: "transcript" });
      setTxTitle("");
      setTxChannel("");
      setTxContent("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSec(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await scanSecTicker(secTicker.toUpperCase());
      setResult({ count: res.count, type: "sec" });
      setSecTicker("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add Financial Content</CardTitle>
        <CardDescription>
          Paste a YouTube URL, upload a transcript, or pull SEC filings for an S&amp;P 500 ticker. AI will extract
          stocks, themes, and sentiment automatically.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {result ? (
          <div className="text-center py-8">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h3 className="font-semibold text-lg mb-1">
              {result.type === "sec" ? "SEC filings queued for processing" : "Content queued for processing"}
            </h3>
            <p className="text-muted-foreground text-sm mb-2">
              {result.type === "sec"
                ? `${result.count} new filing${result.count === 1 ? "" : "s"} found and being processed in the background.`
                : `${result.source?.title || "Source"} is being processed in the background.`}
            </p>
            <p className="text-xs text-muted-foreground mb-6">
              {result.type === "sec"
                ? "Extraction will complete in 1–3 minutes per filing. Check the Sources tab for progress."
                : "Transcription and AI extraction will complete in 1–3 minutes. Check the Sources tab for progress."}
            </p>
            <Button onClick={reset}>Add More Content</Button>
          </div>
        ) : (
          <Tabs defaultValue="youtube">
            <TabsList className="mb-6">
              <TabsTrigger value="youtube" className="gap-2">
                <Youtube className="h-4 w-4" />
                YouTube URL
              </TabsTrigger>
              <TabsTrigger value="transcript" className="gap-2">
                <FileText className="h-4 w-4" />
                Paste Transcript
              </TabsTrigger>
              <TabsTrigger value="sec" className="gap-2">
                <Landmark className="h-4 w-4" />
                SEC Filings
              </TabsTrigger>
            </TabsList>

            <TabsContent value="youtube">
              <form onSubmit={handleYouTube} className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-1.5 block">YouTube URL</label>
                  <Input
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={ytUrl}
                    onChange={(e) => setYtUrl(e.target.value)}
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Works with CNBC, Bloomberg, earnings call recordings, finance channels. Max ~25 min for best results.
                  </p>
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-sm text-red-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}
                <Button type="submit" disabled={loading || !ytUrl} className="w-full">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Youtube className="h-4 w-4 mr-2" />
                      Ingest Video
                    </>
                  )}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="transcript">
              <form onSubmit={handleTranscript} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">Title *</label>
                    <Input
                      placeholder="Q4 Earnings Call — NVDA"
                      value={txTitle}
                      onChange={(e) => setTxTitle(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">Source / Channel</label>
                    <Input
                      placeholder="CNBC, Bloomberg, etc."
                      value={txChannel}
                      onChange={(e) => setTxChannel(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">Transcript *</label>
                  <Textarea
                    placeholder="Paste earnings call transcript, interview, or any financial media text..."
                    value={txContent}
                    onChange={(e) => setTxContent(e.target.value)}
                    rows={10}
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Minimum ~200 words for meaningful extraction.
                  </p>
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-sm text-red-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}
                <Button type="submit" disabled={loading || !txTitle || !txContent} className="w-full">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <FileText className="h-4 w-4 mr-2" />
                      Process Transcript
                    </>
                  )}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="sec">
              <form onSubmit={handleSec} className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-1.5 block">Ticker</label>
                  <Input
                    placeholder="AAPL, MSFT, NVDA..."
                    value={secTicker}
                    onChange={(e) => setSecTicker(e.target.value)}
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Fetches the latest 10-K, 10-Q, and 8-K earnings press release from SEC EDGAR for any S&amp;P 500
                    company. All ~500 companies are also scanned automatically in the background.
                  </p>
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-sm text-red-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}
                <Button type="submit" disabled={loading || !secTicker} className="w-full">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Fetching...
                    </>
                  ) : (
                    <>
                      <Landmark className="h-4 w-4 mr-2" />
                      Fetch SEC Filings
                    </>
                  )}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
