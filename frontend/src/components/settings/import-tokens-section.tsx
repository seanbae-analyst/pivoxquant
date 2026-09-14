"use client";

/**
 * ImportTokensSection — /settings · "가져오기 토큰" (personal access tokens
 * for the import webhook). docs/product/IMPORT_INBOX_DESIGN.md §Phase 2 v3-A.
 *
 * What a token can do: place fills on the pending list. Nothing else. Rows
 * are recorded only after the user approves them with a thesis, exactly like
 * a CSV upload. The server never sees a brokerage credential; the user's
 * own tool (MacroDroid, a mail filter, cron) posts notification text.
 *
 *   1. Issue — name (1~60) + consent checkbox gate the button. At the active
 *      limit (`active_limit`, default 5) the form is disabled with a line
 *      saying so.
 *   2. Reveal — the raw token comes back ONCE in the 201 body and is shown
 *      in a box with copy (navigator.clipboard, try/catch → select-all text
 *      fallback), a one-line curl and a 3-line MacroDroid hint. Dismissed by
 *      the user; never re-fetched.
 *   3. List — name · prefix · created · last used · today's batches · revoke.
 *      Revoke asks "정말 폐기" in place, then DELETE + mutate. Revoked rows
 *      stay in the list, dimmed.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Facts only; no
 * recommendation language.
 */

import * as React from "react";
import { toast } from "sonner";

import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { parseIsoUtc } from "@/lib/format";
import { useImportTokens } from "@/lib/hooks";
import { useLocale, useT } from "@/lib/locale";
import type { ImportTokenCreateResponse, ImportTokenDTO } from "@/lib/types";
import {
  EditorialHead,
  RuledKicker,
  Caption,
  FieldLabel,
  HairlineSoft,
} from "@/components/ui/editorial";

export const TOKEN_NAME_MAX = 60;

/** 1~60 chars after trim — mirrors `IMPORT_TOKEN_NAME_INVALID` on the server. */
export function tokenNameOk(name: string): boolean {
  const n = name.trim().length;
  return n >= 1 && n <= TOKEN_NAME_MAX;
}

/** Display-only webhook address. Same origin as the app (apiFetch is relative). */
export function webhookUrl(origin: string): string {
  return `${origin}${API.imports.webhook}`;
}

export function curlExample(origin: string, token: string): string {
  return `curl -X POST ${webhookUrl(origin)} -H "Authorization: Bearer ${token}" -H "Content-Type: application/json" -d '{"text":"삼성전자 10주 매수 체결 71,200원"}'`;
}

/** KST-pinned date (optionally with time); naive backend stamps are read as UTC. */
function fmtDate(iso: string | null, locale: string, withTime = false): string {
  const d = parseIsoUtc(iso);
  if (!d) return "";
  const tag = locale === "ko" ? "ko-KR" : "en-US";
  return d.toLocaleString(tag, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: "Asia/Seoul",
  });
}

function errorKey(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.code) {
      case "IMPORT_CONSENT_REQUIRED":
        return "settingsV2.importTokens.errorConsent";
      case "IMPORT_TOKEN_NAME_INVALID":
        return "settingsV2.importTokens.errorName";
      case "IMPORT_TOKEN_LIMIT":
        return "settingsV2.importTokens.errorLimit";
      case "IMPORT_NOT_FOUND":
        return "settingsV2.importTokens.errorNotFound";
    }
  }
  return "settingsV2.importTokens.errorGeneric";
}

const cardStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.02)",
  border: "1px solid var(--pq-ivory-line)",
  borderRadius: 4,
  padding: 24,
};

const monoBox: React.CSSProperties = {
  fontSize: "var(--pq-text-mono-sm)",
  color: "var(--pq-ivory)",
  background: "rgba(0,0,0,0.35)",
  border: "1px solid var(--pq-ivory-line)",
  borderRadius: 2,
  padding: "10px 12px",
  wordBreak: "break-all",
  whiteSpace: "pre-wrap",
  userSelect: "all",
};

export function ImportTokensSection() {
  const t = useT();
  const { locale } = useLocale();
  const { tokens, activeLimit, isLoading, error, mutate } = useImportTokens();

  /* Origin for the display-only address — read after mount so SSR and the
     first client render agree. */
  const [origin, setOrigin] = React.useState("");
  React.useEffect(() => {
    if (typeof window !== "undefined") setOrigin(window.location.origin);
  }, []);

  /* ── Issue form ── */
  const [name, setName] = React.useState("");
  const [consent, setConsent] = React.useState(false);
  const [issuing, setIssuing] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  /* ── One-time reveal ── */
  const [issued, setIssued] = React.useState<ImportTokenCreateResponse | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [copyFailed, setCopyFailed] = React.useState(false);

  const activeCount = tokens.filter((tk) => !tk.revoked_at).length;
  const limitReached = activeCount >= activeLimit;
  const canIssue = tokenNameOk(name) && consent && !limitReached && !issuing;

  const issue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canIssue) return;
    setIssuing(true);
    setFormError(null);
    try {
      const res = await apiFetch<ImportTokenCreateResponse>(API.imports.tokens, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), consent: true }),
      });
      setIssued(res);
      setCopied(false);
      setCopyFailed(false);
      setName("");
      setConsent(false);
      await mutate();
    } catch (err) {
      setFormError(t(errorKey(err)));
    } finally {
      setIssuing(false);
    }
  };

  const copyToken = async () => {
    if (!issued) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(issued.token);
      setCopied(true);
      setCopyFailed(false);
    } catch {
      setCopied(false);
      setCopyFailed(true);
    }
  };

  /* ── Revoke (in-place confirm) ── */
  const [confirmId, setConfirmId] = React.useState<number | null>(null);
  const [revokingId, setRevokingId] = React.useState<number | null>(null);

  const revoke = async (tk: ImportTokenDTO) => {
    setRevokingId(tk.id);
    try {
      await apiFetch<{ ok: boolean }>(API.imports.token(tk.id), { method: "DELETE" });
      setConfirmId(null);
      if (issued && issued.id === tk.id) setIssued(null);
      await mutate();
      toast.success(t("settingsV2.importTokens.revokeDone"));
    } catch (err) {
      toast.error(t(errorKey(err)));
    } finally {
      setRevokingId(null);
    }
  };

  const address = webhookUrl(origin);

  return (
    <section
      id="import-tokens"
      style={{ scrollMarginTop: 96 }}
      aria-label="Import tokens"
      data-testid="import-tokens-section"
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            {t("settingsV2.importTokens.eyebrow")}
          </div>
          <EditorialHead size={30} as="div">
            {t("settingsV2.importTokens.heading")}{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              {t("settingsV2.importTokens.headingAccent")}
            </span>
          </EditorialHead>
        </div>
      </div>

      <div style={cardStyle}>
        <Caption className="max-w-xl">{t("settingsV2.importTokens.desc")}</Caption>

        {/* ── 2. One-time reveal ── */}
        {issued && (
          <div
            className="mt-5 rounded-[2px] border p-4"
            style={{ borderColor: "var(--pq-bronze)", background: "rgba(0,0,0,0.25)" }}
            role="region"
            aria-label={t("settingsV2.importTokens.revealKicker")}
            data-testid="import-token-reveal"
          >
            <RuledKicker>{t("settingsV2.importTokens.revealKicker")}</RuledKicker>
            <div
              className="font-serif mt-2"
              style={{
                fontSize: "var(--pq-text-body-sm)",
                lineHeight: 1.5,
                color: "var(--pq-ivory)",
                wordBreak: "keep-all",
              }}
            >
              {issued.name}
            </div>
            <Caption className="mt-1">{t("settingsV2.importTokens.revealOnce")}</Caption>

            <div className="mt-3 flex flex-wrap items-start gap-3">
              <code
                className="font-mono flex-1 min-w-0"
                style={monoBox}
                data-testid="import-token-raw"
                tabIndex={0}
              >
                {issued.token}
              </code>
              <button
                type="button"
                onClick={copyToken}
                className="pq-ink-btn-bronze inline-flex items-center px-4 py-2 text-pq-mono-sm uppercase tracking-[0.22em]"
              >
                {copied
                  ? t("settingsV2.importTokens.copied")
                  : t("settingsV2.importTokens.copy")}
              </button>
            </div>
            {copyFailed && (
              <Caption className="mt-2">
                <span style={{ color: "var(--pq-error)" }}>
                  {t("settingsV2.importTokens.copyFailed")}
                </span>
              </Caption>
            )}

            <HairlineSoft className="my-4" />

            <RuledKicker>{t("settingsV2.importTokens.usageKicker")}</RuledKicker>
            <div className="mt-3">
              <FieldLabel tone="muted">{t("settingsV2.importTokens.curlLabel")}</FieldLabel>
              <code className="font-mono block mt-1" style={monoBox}>
                {curlExample(origin, issued.token)}
              </code>
            </div>
            <div className="mt-3">
              <FieldLabel tone="muted">{t("settingsV2.importTokens.macrodroidLabel")}</FieldLabel>
              <div className="mt-1 space-y-1">
                <Caption>{t("settingsV2.importTokens.macrodroid1")}</Caption>
                <Caption>{t("settingsV2.importTokens.macrodroid2")}</Caption>
                <Caption>{t("settingsV2.importTokens.macrodroid3")}</Caption>
              </div>
              <Caption className="mt-2">
                <span className="font-mono" style={{ color: "var(--pq-ivory-mid)" }}>
                  POST {address}
                </span>
              </Caption>
            </div>

            <div className="mt-4">
              <button
                type="button"
                onClick={() => setIssued(null)}
                className="pq-ink-btn-ghost px-4 text-pq-mono-sm uppercase tracking-[0.22em]"
              >
                {t("settingsV2.importTokens.dismiss")}
              </button>
            </div>
          </div>
        )}

        <HairlineSoft className="my-5" />

        {/* ── 1. Issue form ── */}
        <form onSubmit={issue} aria-label={t("settingsV2.importTokens.issueKicker")}>
          <RuledKicker>{t("settingsV2.importTokens.issueKicker")}</RuledKicker>

          <div className="mt-3">
            <label htmlFor="import-token-name">
              <FieldLabel tone="bronze">{t("settingsV2.importTokens.nameLabel")}</FieldLabel>
            </label>
            <input
              id="import-token-name"
              type="text"
              value={name}
              maxLength={TOKEN_NAME_MAX}
              disabled={limitReached}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("settingsV2.importTokens.namePlaceholder")}
              className="mt-2 w-full max-w-md bg-transparent border border-[rgba(245,240,232,0.15)] rounded-[2px] px-3 py-2 text-pq-body-sm outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)] font-serif disabled:opacity-40"
            />
            <Caption className="mt-1">{t("settingsV2.importTokens.nameHint")}</Caption>
          </div>

          <label className="mt-4 flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              disabled={limitReached}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 accent-[var(--pq-bronze)]"
              aria-label={t("settingsV2.importTokens.consentLabel")}
            />
            <span
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body-sm)",
                lineHeight: 1.5,
                color: "var(--pq-ivory-soft)",
                wordBreak: "keep-all",
              }}
            >
              {t("settingsV2.importTokens.consentLabel")}
            </span>
          </label>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={!canIssue}
              aria-disabled={!canIssue}
              className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {issuing
                ? t("settingsV2.importTokens.issuing")
                : t("settingsV2.importTokens.issue")}
            </button>
            {limitReached && (
              <Caption>
                {t("settingsV2.importTokens.limitReached").replace(
                  "{limit}",
                  String(activeLimit),
                )}
              </Caption>
            )}
          </div>

          {formError && (
            <div role="alert" className="mt-3">
              <Caption>
                <span style={{ color: "var(--pq-error)" }}>{formError}</span>
              </Caption>
            </div>
          )}
        </form>

        <HairlineSoft className="my-5" />

        {/* ── 3. List ── */}
        <RuledKicker>{t("settingsV2.importTokens.listKicker")}</RuledKicker>

        {isLoading && tokens.length === 0 ? (
          <Caption className="mt-3">{t("settingsV2.importTokens.loading")}</Caption>
        ) : error ? (
          <Caption className="mt-3">
            <span style={{ color: "var(--pq-error)" }}>
              {t("settingsV2.importTokens.errorGeneric")}
            </span>
          </Caption>
        ) : tokens.length === 0 ? (
          <Caption className="mt-3">{t("settingsV2.importTokens.listEmpty")}</Caption>
        ) : (
          <ul className="mt-3 divide-y" style={{ borderColor: "var(--pq-ivory-line)" }}>
            {tokens.map((tk) => {
              const revoked = Boolean(tk.revoked_at);
              const confirming = confirmId === tk.id;
              const busy = revokingId === tk.id;
              return (
                <li
                  key={tk.id}
                  data-testid="import-token-row"
                  data-revoked={revoked ? "true" : "false"}
                  className="py-3 flex flex-wrap items-center gap-x-6 gap-y-2"
                  style={{
                    borderColor: "var(--pq-ivory-line)",
                    opacity: revoked ? 0.4 : 1,
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <div
                      className="font-serif truncate"
                      style={{
                        fontSize: "var(--pq-text-body-sm)",
                        color: "var(--pq-ivory)",
                      }}
                    >
                      {tk.name}
                      {revoked && (
                        <span
                          className="font-mono uppercase ml-2"
                          style={{
                            fontSize: "var(--pq-text-eyebrow)",
                            letterSpacing: "0.16em",
                            color: "var(--pq-ivory-dim)",
                          }}
                        >
                          {t("settingsV2.importTokens.revoked")}
                        </span>
                      )}
                    </div>
                    <div
                      className="font-mono mt-1 flex flex-wrap gap-x-4 gap-y-1"
                      style={{
                        fontSize: "var(--pq-text-mono-sm)",
                        color: "var(--pq-ivory-mid)",
                      }}
                    >
                      <span>
                        <FieldLabel tone="muted">{t("settingsV2.importTokens.colPrefix")}</FieldLabel>{" "}
                        {tk.prefix}…
                      </span>
                      <span>
                        <FieldLabel tone="muted">{t("settingsV2.importTokens.colCreated")}</FieldLabel>{" "}
                        {fmtDate(tk.created_at, locale)}
                      </span>
                      <span>
                        <FieldLabel tone="muted">{t("settingsV2.importTokens.colLastUsed")}</FieldLabel>{" "}
                        {tk.last_used_at
                          ? fmtDate(tk.last_used_at, locale, true)
                          : t("settingsV2.importTokens.neverUsed")}
                      </span>
                      <span>
                        <FieldLabel tone="muted">{t("settingsV2.importTokens.colToday")}</FieldLabel>{" "}
                        {t("settingsV2.importTokens.todayCount").replace(
                          "{n}",
                          String(tk.batches_today),
                        )}
                      </span>
                    </div>
                  </div>

                  {!revoked && (
                    <div className="flex items-center gap-2">
                      {confirming ? (
                        <>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => revoke(tk)}
                            className="pq-ink-btn-bronze inline-flex items-center px-4 py-1.5 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30"
                          >
                            {busy
                              ? t("settingsV2.importTokens.revoking")
                              : t("settingsV2.importTokens.revokeConfirm")}
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => setConfirmId(null)}
                            className="pq-ink-btn-ghost px-3 text-pq-mono-sm uppercase tracking-[0.22em]"
                          >
                            {t("settingsV2.importTokens.revokeCancel")}
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmId(tk.id)}
                          className="pq-ink-btn-ghost px-3 text-pq-mono-sm uppercase tracking-[0.22em]"
                        >
                          {t("settingsV2.importTokens.revoke")}
                        </button>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
