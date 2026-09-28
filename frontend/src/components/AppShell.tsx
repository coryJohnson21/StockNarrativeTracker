"use client";

import { usePathname } from "next/navigation";

/** The app's page frame: a centred, padded column under the nav.
 *
 *  The landing page opts out. It is full-bleed by design -- section backgrounds
 *  run edge to edge and each section sets its own inner width -- so wrapping it
 *  in the app's max-width and padding would box it into a column and defeat the
 *  layout. Every other route keeps the frame. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/") return <>{children}</>;

  return <main className="max-w-[1600px] mx-auto px-6 py-5">{children}</main>;
}
