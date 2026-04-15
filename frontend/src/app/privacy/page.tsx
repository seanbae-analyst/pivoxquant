import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy - PivoxQuant",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-[100dvh] bg-white">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:py-20">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors mb-8"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </Link>

        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Last updated: April 13, 2026
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-slate-600">
          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              1. Information We Collect
            </h2>
            <p className="mt-3">
              When you sign up via Google or Kakao OAuth, we receive your name,
              email address, and profile photo from the provider. We also collect
              usage data such as pages visited, features used, and interaction
              patterns to improve the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              2. How We Use Your Information
            </h2>
            <p className="mt-3">
              We use your information to provide and improve the Service,
              personalize your experience, send important notifications about
              your account, and generate anonymized analytics. We do not sell
              your personal information to third parties.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              3. Data Storage
            </h2>
            <p className="mt-3">
              Your data is stored securely using industry-standard encryption.
              Portfolio data, watchlists, and preferences are stored in our
              database. We retain your data for as long as your account is
              active.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              4. Third-Party Services
            </h2>
            <p className="mt-3">
              We use third-party services for authentication (Google, Kakao),
              market data (Financial Modeling Prep), AI analysis (Anthropic
              Claude), and payment processing. Each provider has their own
              privacy policy governing their use of your data.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              5. Cookies and Sessions
            </h2>
            <p className="mt-3">
              We use session cookies to maintain your login state. These cookies
              are essential for the Service to function and expire after 24 hours
              of inactivity.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              6. Your Rights
            </h2>
            <p className="mt-3">
              You have the right to access, update, or delete your personal
              data. You can request data deletion by contacting us. Upon account
              deletion, all associated data will be permanently removed within 30
              days.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              7. Security
            </h2>
            <p className="mt-3">
              We implement appropriate technical and organizational measures to
              protect your personal data. This includes HTTPS encryption, CSRF
              protection, rate limiting, and secure session management.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">
              8. Contact
            </h2>
            <p className="mt-3">
              For privacy-related inquiries, contact us at{" "}
              <a
                href="mailto:seanbae1521@gmail.com"
                className="text-[var(--sp-accent)] hover:underline"
              >
                seanbae1521@gmail.com
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
