"use client";

interface Props {
  label: string;
  sortKey: string;
  currentKey: string;
  currentDir: "asc" | "desc";
  onSort: (key: string) => void;
  align?: "left" | "right";
  className?: string;
  title?: string;
}

export function SortableHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  align = "left",
  className = "",
  title,
}: Props) {
  const active = sortKey === currentKey;
  return (
    <th
      scope="col"
      aria-sort={active ? (currentDir === "asc" ? "ascending" : "descending") : "none"}
      title={title}
      className={`h-8 px-2.5 font-medium cursor-pointer select-none transition-colors ${
        active ? "text-foreground" : "hover:text-foreground"
      } ${align === "right" ? "text-right" : "text-left"} ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span
        className={`inline-flex items-center gap-1 ${align === "right" ? "flex-row-reverse" : ""}`}
      >
        {label}
        {/* The caret always occupies its slot, visible only when active. Toggling
            it in and out shifts every header label by 9px on each sort. */}
        <span
          aria-hidden="true"
          className={`text-[9px] leading-none ${active ? "opacity-90" : "opacity-0"}`}
        >
          {currentDir === "asc" ? "▲" : "▼"}
        </span>
      </span>
    </th>
  );
}
