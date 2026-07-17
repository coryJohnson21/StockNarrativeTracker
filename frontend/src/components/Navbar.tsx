"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, BarChart2, Layers, Upload, Database, Star, Rss } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: BarChart2 },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/stocks", label: "Stocks", icon: TrendingUp },
  { href: "/themes", label: "Themes", icon: Layers },
  { href: "/subscriptions", label: "Subscriptions", icon: Rss },
  { href: "/ingest", label: "Add Content", icon: Upload },
  { href: "/sources", label: "Sources", icon: Database },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="bg-card/50 backdrop-blur sticky top-0 z-50 border-b border-border">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex h-16 items-center border-b border-border/50">
          <Link href="/" className="flex items-center gap-2 font-bold text-foreground text-xl">
            <TrendingUp className="h-6 w-6 text-primary" />
            <span>NarrativeTracker</span>
          </Link>
        </div>
        <div className="flex items-center justify-end gap-7 h-12">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 h-full text-sm font-medium border-b-2 transition-colors",
                pathname === href
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
