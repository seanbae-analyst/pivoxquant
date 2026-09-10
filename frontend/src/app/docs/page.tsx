import Link from "next/link";
import { Book, NotebookPen, Contrast, Shield } from "lucide-react";

export const metadata = {
  title: "Docs",
  description: "Product documentation and help.",
  alternates: { canonical: "/docs" },
};

const SECTIONS = [
  {
    icon: Book,
    title: "Getting Started",
    items: [
      {
        q: "What is PivoxQuant?",
        a: "A record you keep about your own investing, and a mirror it holds up. Stop before you buy and write down why; weeks later the same record shows how you actually behaved. Observational only — not investment advice.",
      },
      {
        q: "Do you execute real trades?",
        a: "No. PivoxQuant has no order path to any broker — it never routes, places, or suggests an order. It only reads the record you keep.",
      },
      {
        q: "Can I connect my brokerage account?",
        a: "Not in this beta. Positions are entered by hand in Portfolio, and every surface works on what you enter. Account linking is not offered.",
      },
    ],
  },
  {
    icon: NotebookPen,
    title: "The record",
    items: [
      {
        q: "What is Pre-Trade?",
        a: "Seven questions you answer before a position change — ticker, side, and a written thesis, then your own cross-examination. Nothing is submitted to a broker; the point is the pause and the written reason.",
      },
      {
        q: "Where do my entries go?",
        a: "Journal keeps every pre-trade entry alongside the trades you recorded, so a decision and what followed sit next to each other.",
      },
      {
        q: "Do I need to connect a broker?",
        a: "No — and there is nothing to connect. Positions are entered by hand and every surface works the same.",
      },
    ],
  },
  {
    icon: Contrast,
    title: "The mirror",
    items: [
      {
        q: "What does the Mirror show?",
        a: "What you said about your own habits in the five onboarding questions, next to what your last 30 days of trades actually show, across nine axes — holding period, turnover, sector spread, and so on.",
      },
      {
        q: "Is the mirror scoring me?",
        a: "No. It counts what is in your record and shows it back. There is no grade, no ranking, and no suggestion about what to do next.",
      },
      {
        q: "Why is my mirror empty?",
        a: "It fills from your own trades. Until a few are recorded there is nothing to reflect, and the surface says so rather than inventing a reading.",
      },
    ],
  },
  {
    icon: Shield,
    title: "Legal & Compliance",
    items: [
      {
        q: "Does PivoxQuant provide regulated guidance?",
        a: "No. PivoxQuant is not a licensed investment advisor and does not provide investment advice. All content is observational and informational only.",
      },
      {
        q: "How is my data protected?",
        a: "See our Privacy Policy. Data encrypted in transit and at rest. No broker credentials are collected.",
      },
      {
        q: "How do I delete my account?",
        a: "Settings → Danger Zone → Delete Account. Per PIPA, all data is purged within 30 days.",
      },
    ],
  },
];

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)] px-6 md:px-10 py-12">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12">
          <div className="pq-ink-kicker mb-2">Documentation</div>
          <h1 className="font-serif text-4xl md:text-5xl mb-4">
            How PivoxQuant works.
          </h1>
          <p className="text-pq-body text-[rgba(245,240,232,0.7)] max-w-2xl">
            How the record works, what the mirror reads from it, and what this
            tool does not do.
          </p>
        </header>

        <div className="space-y-12">
          {SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <section key={section.title}>
                <div className="flex items-center gap-3 mb-6 pb-3 border-b border-[var(--pq-ivory-line)]">
                  <Icon className="h-4 w-4 text-[var(--pq-bronze)]" />
                  <h2 className="font-serif text-xl">{section.title}</h2>
                </div>
                <dl className="space-y-5">
                  {section.items.map((item) => (
                    <div key={item.q}>
                      <dt className="text-pq-body text-[var(--pq-ivory)] mb-1.5">
                        {item.q}
                      </dt>
                      <dd className="text-pq-body-sm text-[var(--pq-ivory-mid)] leading-relaxed">
                        {item.a}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            );
          })}
        </div>

        <footer className="mt-16 pt-8 border-t border-[var(--pq-ivory-line)] text-center">
          <div className="pq-fleuron inline-flex mb-3" aria-hidden="true">❦</div>
          <p className="pq-caption">
            More questions? Email us · hello@pivoxquant.com
          </p>
          <div className="flex items-center justify-center gap-4 mt-4 flex-wrap">
            <Link
              href="/terms"
              className="text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
            >
              Terms
            </Link>
            <span className="text-[rgba(245,240,232,0.3)]">·</span>
            <Link
              href="/privacy"
              className="text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
            >
              Privacy
            </Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
