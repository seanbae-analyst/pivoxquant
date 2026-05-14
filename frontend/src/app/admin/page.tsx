"use client";

/**
 * /admin — Index redirect.
 *
 * The parent `admin/layout.tsx` already gates the entire `/admin/*` tree
 * via `apiFetch(API.admin.artifactsList)` (any 401/403/404 → blank 404
 * screen). By the time this page renders we know the user is an admin,
 * so we simply forward to the default admin surface.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/preview");
  }, [router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-pq-eyebrow uppercase tracking-[0.22em] text-slate-400">
        Verifying admin…
      </div>
    </div>
  );
}
