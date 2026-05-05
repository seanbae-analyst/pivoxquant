"use client";

/**
 * <RealtimeStatusBanner /> — Surface SSE connection state to the user.
 *
 * Mounts inside the (dashboard) layout so every authenticated page picks
 * it up automatically. Only renders when the realtime stream is unhealthy,
 * so the happy path stays invisible.
 *
 * State → variant:
 *   - !streamActive                       → null (idle by design — no user / no positions / hidden tab)
 *   - streamActive && failed              → red banner ("실시간 데이터 연결 실패")
 *   - streamActive && !connected          → yellow banner ("재연결 중")
 *   - streamActive && connected           → null (happy path)
 *
 * Why this exists:
 *   Before this component, `RealtimeProvider` tracked `connected` and
 *   `failed` but no UI consumed them. When the SSE stream dropped (server
 *   restart, network hiccup, MAX_RETRIES exceeded) the cached price kept
 *   showing without any visual indication that it had gone stale. Users
 *   could read a 5-minute-old quote as "fresh" and act on it. This banner
 *   makes the stale state explicit.
 *
 *   The streamActive gate prevents a known regression where the yellow
 *   "재연결 중" banner stayed up forever for users with zero positions —
 *   the provider intentionally does not open SSE in that state, but the
 *   default `connected: false` made the banner think it was reconnecting.
 *
 * Law / neutrality:
 *   - "실시간 데이터" / "재연결" only — no advice / guarantee language.
 *   - No BUY/SELL/HOLD framing; this is purely a transport-layer status.
 *
 * Design v3:
 *   - rounded-sm (4px), Vantablack base, KR-tone accents.
 *   - Uses --pq-error (#d18888) for the failed state to stay consistent
 *     with the loss color reserved for KR convention.
 */

import { useRealtimeStatus } from "@/lib/realtime";

export function RealtimeStatusBanner() {
  const { connected, failed, streamActive } = useRealtimeStatus();

  // Stream is intentionally idle (no user, no positions, hidden tab) —
  // hide the banner entirely. Without this guard, the default `connected:
  // false` would render a permanent yellow "재연결 중" for users with
  // zero positions.
  if (!streamActive) return null;

  // Happy path — hide.
  if (connected && !failed) return null;

  // MAX_RETRIES exceeded — SSE gave up entirely. Highest urgency.
  if (failed) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="mx-4 mt-3 rounded-sm border px-3 py-2 md:mx-10"
        style={{
          borderColor: "rgba(209, 136, 136, 0.45)",
          backgroundColor: "rgba(209, 136, 136, 0.08)",
        }}
      >
        <div className="flex items-start gap-2.5">
          <span
            className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: "var(--pq-error)" }}
            aria-hidden
          />
          <div className="flex-1 min-w-0">
            <p
              className="font-mono text-[10.5px] uppercase tracking-[0.22em]"
              style={{ color: "var(--pq-error)" }}
            >
              실시간 데이터 연결 실패
            </p>
            <p
              className="mt-1 text-[12px] leading-relaxed"
              style={{ color: "rgba(245, 240, 232, 0.72)" }}
            >
              표시된 가격은 최신이 아닐 수 있습니다. 페이지를 새로고침하여 다시 시도해 주세요.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              if (typeof window !== "undefined") window.location.reload();
            }}
            className="shrink-0 rounded-sm border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors hover:bg-white/5"
            style={{
              borderColor: "rgba(209, 136, 136, 0.45)",
              color: "var(--pq-error)",
            }}
          >
            새로고침
          </button>
        </div>
      </div>
    );
  }

  // Disconnected but still retrying — softer warning.
  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-4 mt-3 rounded-sm border px-3 py-2 md:mx-10"
      style={{
        borderColor: "rgba(234, 179, 8, 0.35)",
        backgroundColor: "rgba(234, 179, 8, 0.06)",
      }}
    >
      <div className="flex items-start gap-2.5">
        <span
          className="mt-1 inline-block h-1.5 w-1.5 shrink-0 animate-pulse rounded-full"
          style={{ backgroundColor: "rgba(234, 179, 8, 0.85)" }}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <p
            className="font-mono text-[10.5px] uppercase tracking-[0.22em]"
            style={{ color: "rgba(234, 179, 8, 0.85)" }}
          >
            재연결 중
          </p>
          <p
            className="mt-1 text-[12px] leading-relaxed"
            style={{ color: "rgba(245, 240, 232, 0.65)" }}
          >
            실시간 가격 스트림이 일시적으로 끊겼습니다. 표시된 가격은 최신이 아닐 수 있습니다.
          </p>
        </div>
      </div>
    </div>
  );
}
