"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, BarChart2, Layers, Upload, Database } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: BarChart2 },
  { href: "/stocks", label: "Stocks", icon: TrendingUp },
  { href: "/themes", label: "Themes", icon: Layers },
  { href: "/ingest", label: "Add Content", icon: Upload },
  { href: "/sources", label: "Sources", icon: Database },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 flex h-14 items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-bold text-foreground mr-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          <span>NarrativeTracker</span>
        </Link>
        <div className="flex items-center gap-1">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                pathname === href
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
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
