import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { AppShell } from "@/components/AppShell";

/** Plex rather than Inter/system: it has actual character at small sizes, and its
 *  mono companion shares the same skeleton, so tickers and prices sit naturally
 *  beside the prose. Exposed as CSS vars that tailwind.config maps to font-sans
 *  and font-mono, so `font-mono` anywhere means Plex Mono. */
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Murmur — Financial Media Intelligence",
  description: "Track trending stocks, investment themes, and narrative momentum from financial media",
  icons: { icon: "/brand/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${sans.variable} ${mono.variable} font-sans min-h-screen bg-background antialiased`}>
        <Navbar />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
