export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Full-screen ink base only. The narrow centered form shell (max-w-sm) now
  // lives in login/ and signup/ layouts — NOT here — because the onboarding
  // pages (/onboarding wizard + /onboarding/broker) render their OWN full-width
  // app-shells (sticky header/footer, max-w-3xl / max-w-lg content) and were
  // being strangled to 384px by the shared max-w-sm wrapper (2026-06-07 fix).
  return (
    <div
      className="min-h-[100dvh]"
      style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      {children}
    </div>
  );
}
