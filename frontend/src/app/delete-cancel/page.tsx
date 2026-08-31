"use client";

/**
 * /delete-cancel — landing page for the "탈퇴 철회하기" link emailed by the
 * PIPA §21 30-day deletion-request flow (routes/auth.py:_send_deletion_request_email).
 *
 * The recipient is LOGGED OUT (login is refused during the grace window), so
 * the page authenticates with the signed token from the URL — never a session.
 * It POSTs the token to /api/auth/delete-cancel, which clears
 * deletion_requested_at + deleted_at and restores the account to active. The
 * user then signs in normally.
 *
 * Must be reachable without the beta password — see middleware.ts
 * BETA_BYPASS_PREFIXES (the email lands days later, possibly on another device).
 *
 * useSearchParams() requires a Suspense boundary in the App Router.
 */

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

type Status = "idle" | "submitting" | "restored" | "already" | "error";

const PAGE_STYLE: React.CSSProperties = {
  minHeight: "100dvh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--pq-ink, #050505)",
  padding: 24,
};

const CARD_STYLE: React.CSSProperties = {
  width: "100%",
  maxWidth: 460,
  background: "rgba(255,255,255,0.02)",
  border: "1px solid var(--pq-ivory-line, rgba(245,240,232,0.12))",
  borderRadius: 4,
  padding: 32,
};

function DeleteCancelInner() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [status, setStatus] = React.useState<Status>("idle");
  const [errMsg, setErrMsg] = React.useState("");

  const submit = React.useCallback(async () => {
    if (!token) {
      setStatus("error");
      setErrMsg("철회 링크가 올바르지 않습니다. 이메일의 링크를 다시 확인해주세요.");
      return;
    }
    setStatus("submitting");
    try {
      const res = await apiFetch<{ ok: boolean; restored?: boolean; already_active?: boolean }>(
        API.auth.deleteCancel,
        { method: "POST", body: JSON.stringify({ token }) },
      );
      setStatus(res.already_active ? "already" : "restored");
    } catch (e) {
      setStatus("error");
      setErrMsg(
        e instanceof ApiError && e.message
          ? e.message
          : "철회 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
      );
    }
  }, [token]);

  const eyebrow = (
    <p
      className="font-mono uppercase"
      style={{
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.22em",
        color: "var(--pq-bronze)",
        marginBottom: 16,
      }}
    >
      PivoxQuant · 탈퇴 철회
    </p>
  );

  const heading = (text: string) => (
    <h1
      className="font-display"
      style={{
        fontWeight: 500,
        fontSize: "var(--pq-text-quote)",
        lineHeight: 1.25,
        letterSpacing: "-0.02em",
        color: "var(--pq-ivory)",
        marginBottom: 12,
      }}
    >
      {text}
    </h1>
  );

  const body = (text: React.ReactNode) => (
    <p
      className="font-serif"
      style={{
        fontSize: "var(--pq-text-body)",
        lineHeight: 1.6,
        color: "rgba(245,240,232,0.75)",
        marginBottom: 24,
      }}
    >
      {text}
    </p>
  );

  if (status === "restored" || status === "already") {
    return (
      <main style={PAGE_STYLE}>
        <div style={CARD_STYLE}>
          {eyebrow}
          {heading(
            status === "restored" ? "탈퇴가 철회되었습니다" : "이미 활성 계정입니다",
          )}
          {body(
            status === "restored"
              ? "계정이 다시 활성화되었습니다. 데이터는 그대로 보존되어 있어요. 아래에서 다시 로그인해 주세요."
              : "이 계정은 탈퇴 대기 상태가 아닙니다. 이미 철회되었거나 정상 이용 중인 계정입니다.",
          )}
          <Link href="/login" className="pq-ink-btn-bronze" style={{ display: "inline-block" }}>
            로그인하기
          </Link>
        </div>
      </main>
    );
  }

  if (status === "error") {
    return (
      <main style={PAGE_STYLE}>
        <div style={CARD_STYLE}>
          {eyebrow}
          {heading("철회할 수 없습니다")}
          {body(errMsg)}
          <Link
            href="/"
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "var(--pq-bronze)",
              textDecoration: "none",
              borderBottom: "1px solid rgba(184,149,106,0.4)",
              paddingBottom: 2,
            }}
          >
            홈으로
          </Link>
        </div>
      </main>
    );
  }

  // idle / submitting
  return (
    <main style={PAGE_STYLE}>
      <div style={CARD_STYLE}>
        {eyebrow}
        {heading("탈퇴를 철회하시겠어요?")}
        {body(
          "철회하면 30일 후 예정된 데이터 파기가 취소되고 계정이 다시 활성화됩니다. 보유 종목·거래 기록·사전 기록이 그대로 보존됩니다.",
        )}
        <button
          type="button"
          onClick={submit}
          disabled={status === "submitting"}
          className="pq-ink-btn-bronze"
          style={{
            width: "100%",
            opacity: status === "submitting" ? 0.6 : 1,
            cursor: status === "submitting" ? "not-allowed" : "pointer",
          }}
        >
          {status === "submitting" ? "처리 중…" : "탈퇴 철회하기"}
        </button>
      </div>
    </main>
  );
}

export default function DeleteCancelPage() {
  return (
    <React.Suspense fallback={<main style={PAGE_STYLE} />}>
      <DeleteCancelInner />
    </React.Suspense>
  );
}
