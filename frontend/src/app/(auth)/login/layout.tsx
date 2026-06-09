import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In",
  description:
    "Sign in to PivoxQuant — AI Quant Research Tool for US and Korean equities. Continue with Google or Kakao.",
  alternates: { canonical: "/login" },
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Narrow centered form shell — moved off the shared (auth) layout 2026-06-07
  // so the onboarding pages can render full-width. Harmlessly redundant for the
  // V2 page (which self-centers); restores centering for the V1 rollback page.
  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4">
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
