"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Layers, Plus, Loader2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import { CategoryToggle } from "@/components/CategoryToggle";
import { trackTheme, untrackTheme, type SourceCategory } from "@/lib/api";

function ThemesPageContent() {
  const params = useSearchParams();
  const initial = params.get("category");
  const [category, setCategory] = useState<SourceCategory | undefined>(
    initial === "filing" || initial === "media" ? initial : undefined
  );
  const [newTheme, setNewTheme] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTheme.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      await trackTheme(newTheme.trim());
      setNewTheme("");
      setRefreshToken((t) => t + 1);
    } catch (err: any) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleUntrack(name: string) {
    await untrackTheme(name).catch(() => {});
    setRefreshToken((t) => t + 1);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Layers className="h-7 w-7 text-purple-400" />
          Trending Themes
        </h1>
        <p className="text-muted-foreground mt-1">
          Investment themes ranked by narrative momentum across all ingested financial media.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleAdd} className="flex items-center gap-3">
            <Input
              placeholder="Add a theme to track (e.g. Quantum Computing)"
              value={newTheme}
              onChange={(e) => setNewTheme(e.target.value)}
              className="max-w-xs"
            />
            <Button type="submit" disabled={adding || !newTheme.trim()}>
              {adding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
              Add Theme
            </Button>
          </form>
          {addError && (
            <div className="flex items-center gap-2 text-sm text-red-400 mt-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {addError}
            </div>
          )}
        </CardContent>
      </Card>

      <CategoryToggle value={category} onChange={setCategory} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tracked Themes</CardTitle>
          <CardDescription>
            Click any row to see the AI summary. Use the add box above to track a new theme, or the X to stop tracking one.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <TrendingThemesTable
            limit={100}
            category={category}
            refreshToken={refreshToken}
            onUntrack={handleUntrack}
          />
        </CardContent>
      </Card>
    </div>
  );
}

export default function ThemesPage() {
  return (
    <Suspense fallback={null}>
      <ThemesPageContent />
    </Suspense>
  );
}
