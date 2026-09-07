"use client";

/**
 * /admin — Index redirect.
 *
 * The parent `admin/layout.tsx` already gates the entire `/admin/*` tree
 * (any 401/403/404 → blank 404 screen). By the time this page renders we
 * know the user is an admin, so we forward to the default admin surface.
 *
 * That forward used to target /admin/preview, which the 2026-08-31 prune
 * deleted — measured 2026-09-07, prod returns 404 for it. So the admin index
 * rendered "Verifying admin…" and then threw the owner at a not-found page.
 * /admin/support is the only admin screen left standing.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/support");
  }, [router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-pq-eyebrow uppercase tracking-[0.22em] text-slate-400">
        Verifying admin…
      </div>
    </div>
  );
}
