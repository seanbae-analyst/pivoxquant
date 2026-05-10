import Link from "next/link";
import { Book, HelpCircle, MessageSquare, FileText, Shield } from "lucide-react";

export const metadata = {
  title: "Docs",
  description: "Product documentation and help.",
};

const SECTIONS = [
  {
    icon: Book,
    title: "Getting Started",
    items: [
      {
        q: "What is PivoxQuant?",
        a: "A quiet operating system for private capital — observational research, not investment advice.",
      },
      {
        q: "Do you execute real trades?",
        a: "No. Korean brokers (KIS) are connected read-only. PivoxQuant never routes orders.",
      },
      {
        q: "How do I connect my account?",
        a: "Settings → Brokers → Connect KIS (read-only). Additional brokers are on the roadmap.",
      },
    ],
  },
  {
    icon: FileText,
    title: "Reports & Artifacts",
    items: [
      {
        q: "How often are reports generated?",
        a: "Weekly Memo arrives Monday 07:00 KST. Morning Brief daily. Monthly/Quarterly reports on calendar.",
      },
      {
        q: "What tier gets which reports?",
        a: "Free: Weekly Memo preview. Pro: 12 artifacts. Premium: All + priority + concierge notes.",
      },
      {
        q: "Can I download PDFs?",
        a: "Yes — via Reports page or email delivery.",
      },
    ],
  },
  {
    icon: HelpCircle,
    title: "Signals & Risk",
    items: [
      {
        q: "What do POSITIVE / NEGATIVE / NEUTRAL mean?",
        a: "Observation labels based on a 4-pillar quant score. Not recommendations to buy or sell.",
      },
      {
        q: "How is risk measured?",
        a: "VaR, ES, max drawdown, correlation, VIX regime, tail ratio, cash buffer — 7 independent observations.",
      },
      {
        q: "What is the Risk Board demo?",
        a: "If you have not added positions, the Risk Board shows sample observations so you can see the format.",
      },
    ],
  },
  {
    icon: MessageSquare,
    title: "AI Chat",
    items: [
      {
        q: "What can I ask?",
        a: "Anything about your portfolio observations, market context, or historical patterns. Responses are informational only.",
      },
      {
        q: "Is it real Claude?",
        a: "Yes. Claude-augmented synthesis via Anthropic API. Each response is scrubbed through our legal filter.",
      },
      {
        q: "Does it remember my portfolio?",
        a: "Yes — it reads your observation state on each turn.",
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
        a: "See our Privacy Policy. Data encrypted in transit and at rest. Broker credentials encrypted per-user.",
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
          <h1 className="font-serif italic text-4xl md:text-5xl mb-4">
            How PivoxQuant works.
          </h1>
          <p className="text-[14px] text-[rgba(245,240,232,0.7)] max-w-2xl">
            Everything you need to observe your book, read the weekly memo, and
            understand what the engine does — and what it does not.
          </p>
        </header>

        <div className="space-y-12">
          {SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <section key={section.title}>
                <div className="flex items-center gap-3 mb-6 pb-3 border-b border-[var(--pq-ivory-line)]">
                  <Icon className="h-4 w-4 text-[var(--pq-bronze)]" />
                  <h2 className="font-serif italic text-xl">{section.title}</h2>
                </div>
                <dl className="space-y-5">
                  {section.items.map((item) => (
                    <div key={item.q}>
                      <dt className="text-[14px] text-[var(--pq-ivory)] mb-1.5">
                        {item.q}
                      </dt>
                      <dd className="text-[13px] text-[rgba(245,240,232,0.65)] leading-relaxed">
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
            <a
              href="https://github.com/seanbae-analyst/pivoxquant"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
            >
              GitHub
            </a>
            <span className="text-[rgba(245,240,232,0.3)]">·</span>
            <Link
              href="/terms"
              className="text-[11px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
            >
              Terms
            </Link>
            <span className="text-[rgba(245,240,232,0.3)]">·</span>
            <Link
              href="/privacy"
              className="text-[11px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
            >
              Privacy
            </Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
