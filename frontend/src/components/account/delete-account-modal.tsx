"use client";

/**
 * <DeleteAccountModal />
 *
 * Self-service account deletion — replaces the old "mailto support" fallback
 * (GAP-J). Self-contained: owns its own API calls, loading/error state, and
 * the post-success redirect. Hosts render it conditionally and only wire
 * `onClose`:
 *
 *     {showDelete && <DeleteAccountModal onClose={() => setShowDelete(false)} />}
 *
 * Two backend paths, both already built + tested:
 *   - Default  → POST /api/auth/delete-request  (PIPA §21 30-day soft-delete;
 *     logs out, emails a self-service cancel link, pipa_purge cron hard-deletes
 *     after 30 days). Reversible — the recommended path.
 *   - Immediate → DELETE /api/auth/delete-account (irreversible hard delete).
 *     Guarded behind a type-to-confirm so it can't be a single mis-click.
 *
 * After either succeeds the server has already cleared the session cookies, so
 * we full-navigate away (window.location) rather than client-route — SWR caches
 * for the now-deleted user must not survive into the next paint.
 *
 * Legal: persona vocabulary only, no advice strings. PIPA §21 phrasing.
 */

import * as React from "react";
import { AlertTriangle, X } from "lucide-react";
import { toast } from "sonner";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

const ERROR_COLOR = "var(--pq-error, #d18888)";
const ERROR_BORDER = "rgba(209,136,136,0.30)";

/** Phrase the user must type to arm the irreversible immediate delete. */
const CONFIRM_PHRASE = "삭제";

type Phase = "form" | "done-soft" | "done-hard";

export function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  const [busy, setBusy] = React.useState(false);
  const [phase, setPhase] = React.useState<Phase>("form");
  const [showImmediate, setShowImmediate] = React.useState(false);
  const [confirmText, setConfirmText] = React.useState("");

  const armed = confirmText.trim() === CONFIRM_PHRASE;

  const errMessage = React.useCallback(
    (e: unknown, fallback: string) =>
      e instanceof ApiError && e.message ? e.message : fallback,
    [],
  );

  /** Default path — PIPA §21 30-day soft-delete (reversible). */
  const handleSoftDelete = React.useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      await apiFetch(API.auth.deleteRequest, { method: "POST" });
      setPhase("done-soft");
    } catch (e) {
      toast.error(errMessage(e, "탈퇴 요청에 실패했습니다. 다시 시도해주세요."));
      setBusy(false);
    }
  }, [busy, errMessage]);

  /** Immediate irreversible hard delete (type-to-confirm gated). */
  const handleHardDelete = React.useCallback(async () => {
    if (busy || !armed) return;
    setBusy(true);
    try {
      await apiFetch(API.auth.deleteAccount, { method: "DELETE" });
      setPhase("done-hard");
    } catch (e) {
      toast.error(errMessage(e, "계정 삭제에 실패했습니다. 다시 시도해주세요."));
      setBusy(false);
    }
  }, [busy, armed, errMessage]);

  /** Leave the app — session cookies are already cleared server-side. */
  const leave = React.useCallback((href: string) => {
    if (typeof window !== "undefined") window.location.href = href;
  }, []);

  const boxStyle: React.CSSProperties = {
    background: "var(--pq-ink, #050505)",
    border: "1px solid rgba(245,240,232,0.12)",
    padding: 24,
    borderRadius: 2,
  };

  // ── Success panels ─────────────────────────────────────────────────────
  if (phase === "done-soft") {
    return (
      <ModalShell onClose={() => leave("/")} ariaLabel="탈퇴 요청 접수">
        <div className="my-auto w-full max-w-md" style={boxStyle}>
          <h3
            className="font-display"
            style={{ fontWeight: 500, fontSize: "var(--pq-text-h4)", color: "var(--pq-ivory)", marginBottom: 12 }}
          >
            탈퇴 요청이 접수되었습니다
          </h3>
          <p
            className="font-serif"
            style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.6, color: "var(--pq-ivory-muted)", marginBottom: 12 }}
          >
            개인정보보호법 §21 에 따라 <strong>30일 후</strong> 모든 데이터가 영구
            파기됩니다. 확인 메일을 보내드렸어요 — 마음이 바뀌시면 메일의{" "}
            <strong>‘탈퇴 철회하기’</strong> 링크로 직접 되돌릴 수 있습니다.
          </p>
          <p
            className="font-serif"
            style={{ fontSize: "var(--pq-text-caption)", lineHeight: 1.5, color: "var(--pq-ivory-faint)", marginBottom: 20 }}
          >
            이 기간 동안에는 로그인이 차단됩니다.
          </p>
          <button type="button" onClick={() => leave("/")} className="pq-ink-btn-bronze" style={{ width: "100%" }}>
            확인
          </button>
        </div>
      </ModalShell>
    );
  }

  if (phase === "done-hard") {
    return (
      <ModalShell onClose={() => leave("/")} ariaLabel="계정 삭제 완료">
        <div className="my-auto w-full max-w-md" style={boxStyle}>
          <h3
            className="font-display"
            style={{ fontWeight: 500, fontSize: "var(--pq-text-h4)", color: "var(--pq-ivory)", marginBottom: 12 }}
          >
            계정이 삭제되었습니다
          </h3>
          <p
            className="font-serif"
            style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.6, color: "var(--pq-ivory-muted)", marginBottom: 20 }}
          >
            계정과 모든 데이터(보유 종목·관심목록·전달된 아티팩트 포함)가 영구
            삭제되었습니다. 이용해 주셔서 감사합니다.
          </p>
          <button type="button" onClick={() => leave("/")} className="pq-ink-btn-bronze" style={{ width: "100%" }}>
            확인
          </button>
        </div>
      </ModalShell>
    );
  }

  // ── Form ───────────────────────────────────────────────────────────────
  return (
    <ModalShell onClose={busy ? () => {} : onClose} ariaLabel="계정 삭제">
      <div className="my-auto w-full max-w-md" style={boxStyle}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle className="h-4 w-4" style={{ color: ERROR_COLOR }} />
            <h3
              className="font-display"
              style={{ fontWeight: 500, fontSize: "var(--pq-text-h4)", color: "var(--pq-ivory)" }}
            >
              계정 삭제
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="닫기"
            style={{ color: "var(--pq-ivory-dim)", background: "transparent", border: "none", cursor: busy ? "not-allowed" : "pointer" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p
          className="font-serif"
          style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.6, color: "rgba(245,240,232,0.7)", marginBottom: 20 }}
        >
          삭제하면 보유 종목, 관심목록, 전달된 아티팩트가 모두 제거됩니다.
          기본은 <strong>30일 유예</strong>로, 그 안에는 메일 링크로 직접 철회할
          수 있습니다.
        </p>

        {/* Default — 30-day soft delete (reversible) */}
        <button
          type="button"
          onClick={handleSoftDelete}
          disabled={busy}
          className="pq-ink-btn-bronze"
          style={{ width: "100%", marginBottom: 12, opacity: busy ? 0.5 : 1, cursor: busy ? "not-allowed" : "pointer" }}
        >
          {busy && !showImmediate ? "요청 중…" : "30일 후 삭제 — 철회 가능"}
        </button>

        {/* Secondary — reveal the irreversible immediate path */}
        {!showImmediate ? (
          <button
            type="button"
            onClick={() => setShowImmediate(true)}
            disabled={busy}
            className="font-mono uppercase"
            style={{
              display: "block",
              width: "100%",
              textAlign: "center",
              padding: "8px 0",
              background: "transparent",
              border: "none",
              color: "var(--pq-ivory-faint)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.16em",
              cursor: busy ? "not-allowed" : "pointer",
            }}
          >
            또는 지금 즉시 영구 삭제
          </button>
        ) : (
          <div
            style={{
              borderTop: `1px solid ${ERROR_BORDER}`,
              marginTop: 4,
              paddingTop: 16,
            }}
          >
            <p
              className="font-serif"
              style={{ fontSize: "var(--pq-text-caption)", lineHeight: 1.5, color: ERROR_COLOR, marginBottom: 12 }}
            >
              즉시 삭제는 되돌릴 수 없습니다. 계속하려면 아래에{" "}
              <strong>{CONFIRM_PHRASE}</strong> 를 입력하세요.
            </p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              disabled={busy}
              aria-label={`확인을 위해 ${CONFIRM_PHRASE} 입력`}
              placeholder={CONFIRM_PHRASE}
              className="font-mono"
              style={{
                width: "100%",
                padding: "10px 12px",
                marginBottom: 12,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(245,240,232,0.18)",
                borderRadius: 2,
                color: "var(--pq-ivory)",
                fontSize: "var(--pq-text-body)",
                outline: "none",
              }}
            />
            <button
              type="button"
              onClick={handleHardDelete}
              disabled={busy || !armed}
              className="font-mono uppercase"
              style={{
                width: "100%",
                padding: "11px 20px",
                background: armed ? ERROR_COLOR : "transparent",
                color: armed ? "var(--pq-ink, #050505)" : "rgba(245,240,232,0.4)",
                border: `1px solid ${ERROR_COLOR}`,
                borderRadius: 2,
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                cursor: busy || !armed ? "not-allowed" : "pointer",
                opacity: busy ? 0.6 : 1,
              }}
            >
              {busy && showImmediate ? "삭제 중…" : "영구 삭제"}
            </button>
          </div>
        )}
      </div>
    </ModalShell>
  );
}

export default DeleteAccountModal;
