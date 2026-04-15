import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Investor Profile",
  description:
    "Set up your PivoxQuant investor profile — risk tolerance, time horizon, and investment style.",
  alternates: { canonical: "/onboarding" },
  robots: { index: false, follow: false },
};

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
