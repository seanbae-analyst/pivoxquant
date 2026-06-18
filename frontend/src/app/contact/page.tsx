import Link from "next/link";
import { Mail, MessageSquare, FileText } from "lucide-react";

export const metadata = {
  title: "Contact",
  description: "How to reach the PivoxQuant desk.",
  alternates: { canonical: "/contact" },
};

const CHANNELS = [
  {
    icon: Mail,
    title: "General",
    address: "hello@pivoxquant.com",
    helper:
      "Product questions, beta access, partnership conversations.",
  },
  {
    icon: MessageSquare,
    title: "Support",
    address: "support@pivoxquant.com",
    helper:
      "Account, billing, broker connection, missing artifacts. We reply within one business day.",
  },
];

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)] px-6 md:px-10 py-12">
      <div className="max-w-3xl mx-auto">
        <header className="mb-12">
          <div className="pq-ink-kicker mb-2">Contact</div>
          <h1 className="font-serif text-4xl md:text-5xl mb-4">
            How to reach the desk.
          </h1>
          <p className="text-pq-body text-[rgba(245,240,232,0.7)] max-w-xl">
            We do not staff a phone line. Email is the primary channel — pick
            the address that fits your question and we will reply.
          </p>
        </header>

        <div className="space-y-6">
          {CHANNELS.map((c) => {
            const Icon = c.icon;
            return (
              <section
                key={c.title}
                className="rounded-sm p-6"
                style={{
                  backgroundColor: "rgba(245,240,232,0.03)",
                  border: "0.5px solid var(--pq-ivory-line)",
                }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <Icon className="h-4 w-4 text-[var(--pq-bronze)]" />
                  <h2 className="font-serif text-xl">{c.title}</h2>
                </div>
                <a
                  href={`mailto:${c.address}`}
                  className="font-mono text-pq-body text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)] tracking-wide block mb-2"
                >
                  {c.address}
                </a>
                <p className="text-pq-body-sm text-[rgba(245,240,232,0.65)] leading-relaxed">
                  {c.helper}
                </p>
              </section>
            );
          })}
        </div>

        <section className="mt-12 pt-10 border-t border-[var(--pq-ivory-line)]">
          <h2 className="font-serif text-xl mb-4">Before you write</h2>
          <p className="text-pq-body-sm text-[rgba(245,240,232,0.65)] leading-relaxed mb-3">
            Most product questions are answered in our docs.
          </p>
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 text-pq-caption uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
          >
            <FileText className="h-3.5 w-3.5" />
            Read the docs
          </Link>
        </section>

        <footer className="mt-16 pt-8 border-t border-[var(--pq-ivory-line)] text-center">
          <div className="pq-fleuron inline-flex mb-3" aria-hidden="true">❦</div>
          <p className="pq-caption">
            PivoxQuant · operated from Seoul
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
