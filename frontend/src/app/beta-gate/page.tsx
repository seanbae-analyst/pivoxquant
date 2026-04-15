import type { Metadata } from "next";
import { Suspense } from "react";
import BetaGateForm from "./beta-gate-form";

export const metadata: Metadata = {
  title: "Private Beta · PivoxQuant",
  description: "PivoxQuant is currently in private beta.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function BetaGatePage() {
  return (
    <main className="relative min-h-[100dvh] w-full overflow-hidden bg-background">
      {/* Ambient gradient backdrop */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,_rgba(139,92,246,0.22),_transparent_60%)] blur-3xl" />
        <div className="absolute bottom-[-10%] left-[-10%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle,_rgba(59,130,246,0.18),_transparent_60%)] blur-3xl" />
        <div className="absolute bottom-[-5%] right-[-10%] h-[360px] w-[360px] rounded-full bg-[radial-gradient(circle,_rgba(236,72,153,0.16),_transparent_60%)] blur-3xl" />
      </div>

      <div className="mx-auto flex min-h-[100dvh] max-w-md items-center justify-center px-5 py-10">
        <Suspense fallback={null}>
          <BetaGateForm />
        </Suspense>
      </div>
    </main>
  );
}
