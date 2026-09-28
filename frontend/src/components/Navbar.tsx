"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { MurmurLogo } from "@/components/brand/MurmurLogo";
import { cn } from "@/lib/utils";

/** The seven things you actually read. Icons are gone: at this size they added a
 *  row of near-identical glyphs that the label already disambiguated. */
const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/stocks", label: "Stocks" },
  { href: "/themes", label: "Themes" },
  { href: "/insiders", label: "Insiders" },
  { href: "/research", label: "Research" },
];

/** Setup, not analysis. These were top-level items competing with the pages you
 *  look at daily; behind one menu they stay reachable without paying for width. */
const manage = [
  { href: "/ingest", label: "Add Content" },
  { href: "/subscriptions", label: "Subscriptions" },
  { href: "/reddit", label: "Reddit Feeds" },
  { href: "/sources", label: "Sources" },
];

function ManageMenu({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = manage.some((m) => pathname === m.href);

  // Close on outside click and on Escape -- a menu that traps focus in a toolbar
  // this dense is worse than no menu.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // A route change should dismiss the menu, not leave it hanging over the new page.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className={cn(
          "flex items-center gap-1 h-full text-[13px] font-medium border-b-2 transition-colors",
          active || open
            ? "border-primary text-foreground"
            : "border-transparent text-muted-foreground hover:text-foreground"
        )}
      >
        Manage
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div
          role="menu"
          // Opaque background stated explicitly: the nav above it is
          // translucent (bg-background/85 + backdrop-blur), and a menu that
          // inherits any transparency lets the page's own controls read through
          // its items.
          style={{ backgroundColor: "hsl(var(--popover))" }}
          className="absolute right-0 top-full mt-1 w-44 rounded-sm border border-border py-1 shadow-xl z-50"
        >
          {manage.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              role="menuitem"
              className={cn(
                "block px-3 py-1.5 text-[13px] transition-colors",
                pathname === href
                  ? "text-foreground bg-accent"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
              )}
            >
              {label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function Navbar() {
  const pathname = usePathname();

  // The landing page ships its own header; the in-app nav would only offer a
  // visitor a row of tools that mean nothing until they are inside.
  if (pathname === "/") return null;

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur">
      {/* One bar: wordmark and nav share a row, so the header costs 44px instead
          of the 112px two stacked rows used to take. */}
      <div className="max-w-[1600px] mx-auto px-6 flex h-11 items-center gap-7">
        <Link href="/dashboard" className="shrink-0" aria-label="Murmur — dashboard">
          <MurmurLogo markSize={19} />
        </Link>
        <div className="flex items-center gap-5 h-full overflow-x-auto">
          {nav.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center h-full text-[13px] font-medium border-b-2 whitespace-nowrap transition-colors",
                pathname === href
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center h-full shrink-0">
          <ManageMenu pathname={pathname} />
        </div>
      </div>
    </nav>
  );
}
