import Link from "next/link";
import type { Metadata } from "next";
import { MurmurLogo } from "@/components/brand/MurmurLogo";
import { MurmurMark } from "@/components/brand/MurmurMark";

export const metadata: Metadata = {
  title: "Murmur — Narrative intelligence for the market",
  description:
    "Murmur reads earnings calls, SEC filings, financial media and Reddit, then tells you which stocks the market is starting to talk about — and why.",
};

/** Figures quoted on the page. Hard-coded rather than fetched: this is a public
 *  marketing page that must render instantly and identically for everyone, and a
 *  live count would make the hero jump on load and break when the API is down.
 *  They are real values from the running instance -- update them when they drift. */
const CORPUS = {
  sources: "1,865",
  tickers: "1,045",
  themes: "107",
};

/** The product's five narrative stages, weakest to strongest. This ordering is
 *  the page's structural device: the stage rail below is a real sequence a stock
 *  moves through, not decorative numbering. */
const STAGES = [
  { name: "Fading", color: "var(--stage-fading)", blurb: "Coverage is drying up." },
  { name: "Emerging", color: "var(--stage-emerging)", blurb: "First mentions appear." },
  { name: "Building", color: "var(--stage-building)", blurb: "Attention is accumulating." },
  { name: "Mixed", color: "var(--stage-mixed)", blurb: "The story splits." },
  { name: "Positive", color: "var(--stage-positive)", blurb: "Consensus forms." },
];

const SOURCES = [
  { label: "SEC filings", detail: "10-K · 10-Q · 8-K · Form 4" },
  { label: "Earnings calls", detail: "Transcripts, parsed" },
  { label: "Financial media", detail: "CNBC, Bloomberg, YouTube" },
  { label: "Podcasts", detail: "Transcribed on ingest" },
  { label: "Reddit", detail: "r/stocks, r/wallstreetbets" },
  { label: "News", detail: "Wires and trade press" },
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f6f75]">
      {children}
    </div>
  );
}

/** A still fragment of the real stocks table. Not a screenshot: it is built from
 *  the same tokens and type as the product, so it stays sharp at any zoom and
 *  cannot drift visually from the app the way an exported image would. */
function ProductPreview() {
  const rows = [
    {
      ticker: "NVDA",
      name: "NVIDIA Corporation",
      stage: "Positive",
      color: "var(--stage-positive)",
      themes: "Artificial Intelligence · Semiconductors",
      why: "Advancements in AI technology continue to drive growth and investor confidence.",
      sent: "+61",
      src: "184",
    },
    {
      ticker: "INTC",
      name: "Intel Corporation",
      stage: "Building",
      color: "var(--stage-building)",
      from: "Mixed",
      themes: "Semiconductors · Interest Rates",
      why: "Intel reported a blowout quarter, significantly boosting the semiconductor sector.",
      sent: "+32",
      src: "39",
    },
    {
      ticker: "PARA",
      name: "Paramount Global",
      stage: "Mixed",
      color: "var(--stage-mixed)",
      from: "Building",
      themes: "Federal Reserve Policy · Inflation & Macro",
      why: "Paramount stock initially popped 7% on news of the lawsuit before retracing.",
      sent: "+13",
      src: "4",
    },
  ];

  return (
    <div className="overflow-hidden rounded-md border border-[#1c1c1f] bg-[#0e0e10]">
      <div className="flex items-center gap-2 border-b border-[#1c1c1f] px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-[#2a2a2f]" />
        <span className="h-2 w-2 rounded-full bg-[#2a2a2f]" />
        <span className="h-2 w-2 rounded-full bg-[#2a2a2f]" />
        <span className="ml-2 font-mono text-[11px] text-[#6f6f75]">murmur / stocks</span>
      </div>

      <div className="hidden gap-4 border-b border-[#1c1c1f] px-4 py-2 font-mono text-[10px] uppercase tracking-[0.06em] text-[#6f6f75] sm:grid sm:grid-cols-[92px_104px_minmax(0,1fr)_80px]">
        <span>Ticker</span>
        <span>Signal</span>
        <span>Themes · Why</span>
        <span className="text-right">Sent</span>
      </div>

      {rows.map((r) => (
        <div
          key={r.ticker}
          className="grid gap-4 border-b border-[#161618] px-4 py-3 last:border-b-0 sm:grid-cols-[92px_104px_minmax(0,1fr)_80px]"
        >
          <div className="min-w-0">
            <div className="font-mono text-[13px] font-semibold text-[#e8e6e3]">{r.ticker}</div>
            <div className="truncate text-[11px] text-[#7c7c82]">{r.name}</div>
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: r.color }}
              />
              <span className="text-[12px] font-medium" style={{ color: r.color }}>
                {r.stage}
              </span>
            </div>
            {r.from && (
              <div className="ml-[13px] mt-0.5 text-[10.5px] text-[#7c7c82]">↓ from {r.from}</div>
            )}
          </div>

          <div className="min-w-0">
            <div className="truncate text-[12px] text-[#cfcdc9]">{r.themes}</div>
            <div className="truncate text-[12px] text-[#7c7c82]">{r.why}</div>
          </div>

          <div className="flex items-baseline gap-1.5 font-mono text-[12px] sm:justify-end">
            <span style={{ color: "var(--up-c)" }}>{r.sent}</span>
            <span className="whitespace-nowrap text-[#6f6f75]">{r.src} src</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0b0b0c] text-[#e8e6e3]">
      {/* Marketing header. Deliberately not the app's Navbar: a visitor has no
          use for Watchlist or Insiders until they are inside the product. */}
      <header className="sticky top-0 z-50 border-b border-[#1c1c1f] bg-[#0b0b0c]">
        <div className="mx-auto flex h-14 max-w-[1120px] items-center gap-6 px-6">
          <MurmurLogo markSize={20} />
          <nav className="ml-auto flex items-center gap-6">
            <a
              href="#how"
              className="hidden text-[13px] text-[#7c7c82] transition-colors hover:text-[#e8e6e3] sm:block"
            >
              How it works
            </a>
            <a
              href="#sources"
              className="hidden text-[13px] text-[#7c7c82] transition-colors hover:text-[#e8e6e3] sm:block"
            >
              Sources
            </a>
            <Link
              href="/dashboard"
              className="rounded-sm bg-[#e8e6e3] px-3 py-1.5 text-[13px] font-medium text-[#0b0b0c] transition-colors hover:bg-white"
            >
              Open app
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero. The thesis is the product itself, so the headline is short and the
          preview carries the weight. */}
      <section className="border-b border-[#1c1c1f]">
        <div className="mx-auto grid max-w-[1120px] gap-12 px-6 py-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-start lg:py-20">
          <div>
            <Eyebrow>Narrative intelligence</Eyebrow>
            <h1 className="mt-4 text-[38px] font-semibold leading-[1.1] tracking-[-0.02em] text-balance sm:text-[46px]">
              The market talks before it moves.
            </h1>
            <p className="mt-5 max-w-[46ch] text-[15px] leading-[1.6] text-[#a9a7a3]">
              Murmur reads earnings calls, SEC filings, financial media and Reddit — then
              tells you which stocks are being talked about, what themes are driving the
              conversation, and whether the story is building or fading.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/dashboard"
                className="rounded-sm bg-[#e8e6e3] px-4 py-2.5 text-[14px] font-medium text-[#0b0b0c] transition-colors hover:bg-white"
              >
                Open app →
              </Link>
              <a
                href="#how"
                className="rounded-sm border border-[#26262a] px-4 py-2.5 text-[14px] text-[#cfcdc9] transition-colors hover:border-[#35353b] hover:text-[#e8e6e3]"
              >
                See how it works
              </a>
            </div>

            <dl className="mt-10 flex flex-wrap gap-x-10 gap-y-4 border-t border-[#1c1c1f] pt-6">
              {[
                { v: CORPUS.sources, k: "sources ingested" },
                { v: CORPUS.tickers, k: "tickers tracked" },
                { v: CORPUS.themes, k: "themes followed" },
              ].map(({ v, k }) => (
                <div key={k}>
                  <dt className="font-mono text-[20px] tabular-nums text-[#e8e6e3]">{v}</dt>
                  <dd className="mt-0.5 font-mono text-[11px] uppercase tracking-[0.08em] text-[#6f6f75]">
                    {k}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <ProductPreview />
        </div>
      </section>

      {/* The problem, stated plainly. */}
      <section className="border-b border-[#1c1c1f]">
        <div className="mx-auto max-w-[1120px] px-6 py-16">
          <div className="max-w-[62ch]">
            <Eyebrow>The problem</Eyebrow>
            <h2 className="mt-4 text-[26px] font-semibold leading-[1.25] tracking-[-0.015em] text-balance sm:text-[30px]">
              Price tells you what already happened.
            </h2>
            <p className="mt-4 text-[15px] leading-[1.65] text-[#a9a7a3]">
              By the time a move shows up on a chart, the reasoning behind it has been
              circulating for days — in an 8-K nobody read closely, on a podcast, in a
              thread. That reasoning is scattered across thousands of hours of audio and
              filings, and no one has time to read it. Murmur does, and keeps score.
            </p>
          </div>
        </div>
      </section>

      {/* How it works. Three steps, genuinely sequential, so numbering is honest. */}
      <section id="how" className="scroll-mt-16 border-b border-[#1c1c1f]">
        <div className="mx-auto max-w-[1120px] px-6 py-16">
          <Eyebrow>How it works</Eyebrow>
          <div className="mt-8 grid gap-px overflow-hidden rounded-md border border-[#1c1c1f] bg-[#1c1c1f] md:grid-cols-3">
            {[
              {
                n: "01",
                h: "Ingest",
                p: "Filings, earnings transcripts, YouTube, podcasts, news and Reddit come in continuously. Audio is transcribed on arrival.",
              },
              {
                n: "02",
                h: "Extract",
                p: "Each source is read for the tickers and themes it names, the sentiment behind each mention, and whether it says anything new or echoes what was already said.",
              },
              {
                n: "03",
                h: "Score",
                p: "Mentions roll up into a momentum score per ticker, and every stock lands in a narrative stage. Signals are backtested against forward returns.",
              },
            ].map((s) => (
              <div key={s.n} className="bg-[#0e0e10] p-6">
                <div className="font-mono text-[11px] tracking-[0.1em] text-[#6f6f75]">{s.n}</div>
                <h3 className="mt-3 text-[16px] font-semibold text-[#e8e6e3]">{s.h}</h3>
                <p className="mt-2 text-[13.5px] leading-[1.6] text-[#8a8a90]">{s.p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* The stage rail: the product's own vocabulary, and a real ordering. */}
      <section className="border-b border-[#1c1c1f]">
        <div className="mx-auto max-w-[1120px] px-6 py-16">
          <div className="max-w-[62ch]">
            <Eyebrow>The signal</Eyebrow>
            <h2 className="mt-4 text-[26px] font-semibold leading-[1.25] tracking-[-0.015em] text-balance sm:text-[30px]">
              Every stock sits somewhere on the arc.
            </h2>
            <p className="mt-4 text-[15px] leading-[1.65] text-[#a9a7a3]">
              A narrative has a shape. Murmur places each ticker on it and records the date
              it moved, so you can see a story forming rather than guessing from a price.
            </p>
          </div>

          <ol className="mt-10 grid gap-px overflow-hidden rounded-md border border-[#1c1c1f] bg-[#1c1c1f] sm:grid-cols-5">
            {STAGES.map((s) => (
              <li key={s.name} className="bg-[#0e0e10] p-5">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: s.color }}
                  />
                  <span className="text-[14px] font-medium" style={{ color: s.color }}>
                    {s.name}
                  </span>
                </div>
                <p className="mt-2 text-[12.5px] leading-[1.5] text-[#8a8a90]">{s.blurb}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Sources. Concrete and checkable, not a vague "millions of data points". */}
      <section id="sources" className="scroll-mt-16 border-b border-[#1c1c1f]">
        <div className="mx-auto max-w-[1120px] px-6 py-16">
          <div className="max-w-[62ch]">
            <Eyebrow>What it reads</Eyebrow>
            <h2 className="mt-4 text-[26px] font-semibold leading-[1.25] tracking-[-0.015em] text-balance sm:text-[30px]">
              Primary documents, not aggregated headlines.
            </h2>
          </div>

          <div className="mt-8 grid gap-px overflow-hidden rounded-md border border-[#1c1c1f] bg-[#1c1c1f] sm:grid-cols-2 lg:grid-cols-3">
            {SOURCES.map((s) => (
              <div key={s.label} className="bg-[#0e0e10] p-5">
                <div className="text-[14px] font-medium text-[#e8e6e3]">{s.label}</div>
                <div className="mt-1 font-mono text-[11.5px] text-[#6f6f75]">{s.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get: the three views, linked so a visitor can go look. */}
      <section className="border-b border-[#1c1c1f]">
        <div className="mx-auto max-w-[1120px] px-6 py-16">
          <Eyebrow>Inside</Eyebrow>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              {
                href: "/stocks",
                h: "Stocks",
                p: "Every tracked ticker with its narrative stage, the themes driving it, and one line on why it is being discussed.",
              },
              {
                href: "/themes",
                h: "Themes",
                p: "The ideas moving the market — AI, semiconductors, rate policy — each with the stocks most often named alongside them.",
              },
              {
                href: "/insiders",
                h: "Insiders",
                p: "Form 4 buys and sells from officers and directors, with scheduled 10b5-1 sales separated from real conviction.",
              },
            ].map((c) => (
              <Link
                key={c.href}
                href={c.href}
                className="group rounded-md border border-[#1c1c1f] bg-[#0e0e10] p-5 transition-colors hover:border-[#35353b]"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[15px] font-semibold text-[#e8e6e3]">{c.h}</h3>
                  <span className="text-[#6f6f75] transition-colors group-hover:text-[#e8e6e3]">
                    →
                  </span>
                </div>
                <p className="mt-2 text-[13.5px] leading-[1.6] text-[#8a8a90]">{c.p}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Closing CTA. */}
      <section className="border-b border-[#1c1c1f]">
        <div className="mx-auto flex max-w-[1120px] flex-col items-start gap-6 px-6 py-16 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-[24px] font-semibold tracking-[-0.015em] text-balance sm:text-[28px]">
              See what the market is saying today.
            </h2>
            <p className="mt-2 text-[14px] text-[#8a8a90]">
              No setup — the corpus is already loaded.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="shrink-0 rounded-sm bg-[#e8e6e3] px-5 py-2.5 text-[14px] font-medium text-[#0b0b0c] transition-colors hover:bg-white"
          >
            Open app →
          </Link>
        </div>
      </section>

      <footer className="mx-auto flex max-w-[1120px] flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-[#6f6f75]">
          <MurmurMark size={16} />
          <span className="font-mono text-[12px]">murmur</span>
        </div>
        <p className="max-w-[60ch] text-[11.5px] leading-[1.5] text-[#6f6f75]">
          Murmur is a research tool. Nothing here is investment advice, and narrative
          momentum is not a prediction of price.
        </p>
      </footer>
    </div>
  );
}
