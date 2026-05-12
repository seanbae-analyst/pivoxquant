"use client";

/**
 * /reports/[id] — artefact viewer resolver.
 *
 * Backend `services/alert.py:alert_artifact_ready` emits notifications
 * whose link is `/reports/{artifact_id}`. Prior to 2026-05-13 the
 * matching Next.js dynamic segment did not exist, so clicking the
 * notification produced a 404 (Bug C companion, observed 2026-05-12).
 *
 * This page fetches the artefact row, then redirects to the right
 * viewer surface using the shared `getArtifactViewerUrl` mapping —
 * the same one /reports list-rows and /home Last-Brag-Card hero use.
 * That keeps the "where does Open take me" logic in one place.
 *
 * Loading state is a minimal serif placeholder so the page never
 * flashes blank on slow connections. Errors fall through to /reports
 * (archive) so the link is never broken.
 *
 * Legal: viewer routing only; no investment language.
 */

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { getArtifactViewerUrl } from "@/lib/artifact-viewer";

interface ArtifactPreview {
  ok: boolean;
  id: number;
  type: string;
  title: string;
  has_file?: boolean;
}

export default function ReportByIdPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  useEffect(() => {
    if (!id) {
      router.replace("/reports");
      return;
    }
    const numeric = Number(id);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      router.replace("/reports");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch<ArtifactPreview>(
          API.artifacts.preview(numeric),
        );
        if (cancelled) return;
        if (!data?.ok || !data.id || !data.type) {
          router.replace("/reports");
          return;
        }
        const url = getArtifactViewerUrl({
          id: data.id,
          type: data.type,
          has_file: data.has_file,
        });
        if (url.startsWith("/")) {
          router.replace(url);
        } else {
          window.location.href = url;
        }
      } catch {
        if (!cancelled) router.replace("/reports");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, router]);

  return (
    <div
      className="flex min-h-[40vh] items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <span
        className="font-serif text-[13px] uppercase"
        style={{
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
        }}
      >
        Opening artefact…
      </span>
    </div>
  );
}
