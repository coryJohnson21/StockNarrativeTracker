"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { searchStocks } from "@/lib/api";
import type { StockSearchResult } from "@/types";

export function StockSearch() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const handle = setTimeout(() => {
      searchStocks(q)
        .then((r) => {
          setResults(r.stocks);
          setHighlighted(0);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /** "/" focuses search, the convention this kind of tool is expected to follow.
   *  Ignored while the user is already typing somewhere -- otherwise a "/" in the
   *  ingest textarea would yank focus out of it mid-sentence. */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      e.preventDefault();
      inputRef.current?.focus();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function goToTicker(ticker: string) {
    setOpen(false);
    setQuery("");
    setResults([]);
    router.push(`/stocks/${ticker}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      goToTicker(results[highlighted].ticker);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown = open && query.trim().length > 0;

  return (
    <div ref={containerRef} className="relative w-full max-w-[220px]">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search"
          className="pl-7 pr-8 h-7 text-[12px] rounded-sm"
        />
        {loading ? (
          <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : (
          !query && (
            <kbd className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none select-none rounded-[3px] border border-border px-1 font-mono text-[10px] leading-[14px] text-muted-foreground/70">
              /
            </kbd>
          )
        )}
      </div>

      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full rounded-sm border bg-popover text-popover-foreground shadow-md overflow-hidden">
          {results.length === 0 && !loading ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">No tracked stocks match &quot;{query}&quot;</div>
          ) : (
            <ul className="max-h-72 overflow-y-auto py-1">
              {results.map((stock, i) => (
                <li key={stock.ticker}>
                  <button
                    type="button"
                    className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors ${
                      i === highlighted ? "bg-accent text-accent-foreground" : "hover:bg-accent hover:text-accent-foreground"
                    }`}
                    onMouseEnter={() => setHighlighted(i)}
                    onClick={() => goToTicker(stock.ticker)}
                  >
                    <span className="font-medium">{stock.ticker}</span>
                    <span className="text-muted-foreground truncate">{stock.company_name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
