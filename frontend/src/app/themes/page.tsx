"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TrendingThemesTable } from "@/components/TrendingThemesTable";
import { CategoryToggle } from "@/components/CategoryToggle";
import { LiveStatus } from "@/components/LiveStatus";
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
    <div>
      {/* Same shape as /stocks: no H1 (the nav says Themes), the add box and the
          filter share one docked toolbar, and the table runs full width. */}
      <div className="dock-toolbar flex items-center gap-3 flex-wrap py-2.5">
        <CategoryToggle value={category} onChange={setCategory} />
        <LiveStatus className="hidden xl:block" />
        <form onSubmit={handleAdd} className="ml-auto flex items-center gap-2">
          <Input
            placeholder="Track a theme…"
            value={newTheme}
            onChange={(e) => setNewTheme(e.target.value)}
            className="h-7 w-[220px] text-[12px] rounded-sm"
          />
          <Button
            type="submit"
            size="sm"
            variant="outline"
            disabled={adding || !newTheme.trim()}
            className="h-7 text-[12px] shrink-0"
          >
            {adding ? <Loader2 className="h-3 w-3 animate-spin mr-1.5" /> : <Plus className="h-3 w-3 mr-1.5" />}
            Add
          </Button>
        </form>
      </div>

      {addError && (
        <div className="flex items-center gap-2 text-[12px] text-down pb-2">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {addError}
        </div>
      )}

      <div className="border-t border-border">
        <TrendingThemesTable
          limit={100}
          category={category}
          refreshToken={refreshToken}
          onUntrack={handleUntrack}
          stickyHeader
        />
      </div>
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
