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
    <main className="relative min-h-[100dvh] w-full overflow-hidden bg-[#050505]">
      {/* Vantablack canvas — no decorative blobs (matches landing tone) */}
      <div className="mx-auto flex min-h-[100dvh] max-w-md items-center justify-center px-5 py-10">
        <Suspense fallback={null}>
          <BetaGateForm />
        </Suspense>
      </div>
    </main>
  );
}
