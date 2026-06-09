import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign Up",
  description:
    "Create your PivoxQuant account — AI-powered quantitative investing for US and Korean stock markets.",
  alternates: { canonical: "/signup" },
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Narrow centered form shell — moved off the shared (auth) layout 2026-06-07
  // so the onboarding pages can render full-width. Harmlessly redundant for the
  // V2 page (which self-centers); restores centering for the V1 rollback page.
  // Also wraps signup/oauth-finalize (a narrow form — correct here).
  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4">
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
