"use client";

/**
 * 404 — one view for both places Next renders it (2026-10-09).
 *
 *   app/not-found.tsx              unmatched URLs (root). A signed-in user
 *                                  gets it inside the app shell (app bar +
 *                                  bottom nav), so a dead link in the app
 *                                  never drops them onto a bare page.
 *   app/(dashboard)/not-found.tsx  notFound() inside a dashboard route —
 *                                  already in the shell, so `inShell`.
 *
 * Korean copy; the old English "Nothing to observe here / Back to desk" read
 * like a website. Signed-in → back to 거울 (the app's home); guest → "/".
 */

import Link from "next/link";
import { Eyebrow } from "@/components/landing/eyebrow";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { EditorialHead } from "@/components/ui/editorial";
import { useAuth } from "@/lib/auth";

function Body({ signedIn }: { signedIn: boolean }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-6 py-16 text-center">
      <Eyebrow withDashLeft withDashRight>
        404
      </Eyebrow>
      <EditorialHead as="h1" size={32} className="mt-5">
        없는 화면입니다.
      </EditorialHead>
      <p
        className="mt-4 text-pq-body leading-relaxed [word-break:keep-all]"
        style={{ color: "var(--pq-ivory-mid)" }}
      >
        주소가 바뀌었거나 지워진 화면입니다. 기록은 그대로 남아 있습니다.
      </p>
      <Link
        href={signedIn ? "/mirror" : "/"}
        className="pq-ink-btn-bronze mt-8 inline-flex min-h-[44px] items-center"
        data-testid="not-found-home"
      >
        {signedIn ? "거울로 돌아가기" : "처음으로"}
      </Link>
    </div>
  );
}

export function NotFoundView({ inShell = false }: { inShell?: boolean }) {
  const { user, loading } = useAuth();
  const signedIn = !loading && !!user;

  if (inShell) return <Body signedIn />;
  if (signedIn) {
    return (
      <DashboardLayout>
        <Body signedIn />
      </DashboardLayout>
    );
  }
  return (
    <div
      className="flex min-h-[100dvh] items-center justify-center"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <Body signedIn={false} />
    </div>
  );
}
