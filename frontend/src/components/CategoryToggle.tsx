"use client";

import { Landmark, Newspaper, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SourceCategory } from "@/lib/api";

interface Props {
  value: SourceCategory | undefined;
  onChange: (value: SourceCategory | undefined) => void;
}

export function CategoryToggle({ value, onChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant={value === undefined ? "default" : "outline"}
        size="sm"
        onClick={() => onChange(undefined)}
      >
        <LayoutGrid className="h-3.5 w-3.5 mr-1.5" />
        All
      </Button>
      <Button
        variant={value === "filing" ? "default" : "outline"}
        size="sm"
        onClick={() => onChange("filing")}
      >
        <Landmark className="h-3.5 w-3.5 mr-1.5" />
        Press Releases & Earnings
      </Button>
      <Button
        variant={value === "media" ? "default" : "outline"}
        size="sm"
        onClick={() => onChange("media")}
      >
        <Newspaper className="h-3.5 w-3.5 mr-1.5" />
        Media Tracking
      </Button>
    </div>
  );
}
