"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Lock } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";

/**
 * Admin-area layout. Gates the entire `/admin/*` tree on an allow-list
 * check performed server-side: we call an admin-only endpoint and treat any
 * 404 / 401 / 403 as "not an admin → 404".
 *
 * Spec: "일반 유저는 404". We intentionally show a blank not-found screen
 * rather than revealing the route exists.
 *
 * ⚠️ The probe used to be `/api/admin/artifacts/list`, which the 2026-08-31
 * prune deleted along with the artifact surfaces. The backend has had ZERO
 * routes matching /artifact/ ever since, so the probe returned 404, 404 is
 * read as "not an admin", and the gate denied EVERYONE — the owner included.
 * The whole `/admin/*` tree, `/admin/support` (the only customer-inquiry
 * screen) with it, was silently unreachable: it fails closed to a blank
 * not-found page, so it looks exactly like a correct denial.
 *
 * The probe is now `/api/support/admin/inquiries`, which is live and is
 * itself ADMIN_EMAILS-gated — so it answers the same question the old one
 * was meant to, and it is the endpoint this tree actually needs to work.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [gate, setGate] = useState<"checking" | "allowed" | "denied">("checking");

  useEffect(() => {
    // Not logged in → punt to /login rather than showing admin chrome.
    if (!authLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!user) return;
    let alive = true;
    apiFetch(API.support.adminInquiries)
      .then(() => alive && setGate("allowed"))
      .catch(() => {
        // Any failure — 401/403/404/network — means "not an admin".
        if (alive) setGate("denied");
      });
    return () => {
      alive = false;
    };
  }, [user, authLoading, router]);

  if (authLoading || gate === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  if (gate === "denied") {
    // Mimic the global not-found look — no hint that the route exists.
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-200 text-slate-500">
          <Lock className="h-5 w-5" />
        </div>
        <h1 className="mt-4 text-2xl font-semibold text-slate-900">404</h1>
        <p className="mt-1 text-sm text-slate-500">This page could not be found.</p>
        <Link
          href="/"
          className="mt-6 text-xs font-medium text-slate-500 underline-offset-4 hover:text-slate-900 hover:underline"
        >
          Return home
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur md:px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/mirror"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            aria-label="Back to app"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <span className="text-pq-mono-sm font-bold uppercase tracking-widest text-slate-900">
            Admin
          </span>
          <nav className="flex items-center gap-1">
            {/* "Artifact Preview" lived at /admin/preview, which the
                2026-08-31 prune deleted — the link 404'd. */}
            <Link
              href="/admin/support"
              className="rounded-md px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              고객문의
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="hidden truncate sm:inline">{user?.email}</span>
          <Link
            href="/mirror"
            className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-100"
          >
            Exit
          </Link>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
