"use client";

/**
 * /journal/import — hand the server a broker export or fill-notification
 * text, get back a list of received fills to approve one by one.
 *
 * docs/product/IMPORT_INBOX_DESIGN.md. The server receives ONLY what the user
 * uploads here: a .csv/.xlsx/.xls/.pdf file (≤2MB) or pasted text. OCR of
 * those happens on the user's own device (iOS Shortcuts "Extract Text from
 * Image", Android Lens). The image tab (<ImageImportPanel />,
 * docs/product/SCREENSHOT_IMPORT_DESIGN.md) also reads captures on the
 * device (Tesseract.js) and sends only the rows the user reviewed — the
 * server still never receives an image. Nothing parsed here reaches the
 * trade log until the user approves a row with a thesis.
 *
 *   - Opt-in consent checkbox gates the submit; remembered per user in
 *     localStorage (`pivox_import_consent:<user.id>=1`) so the second visit is
 *     one click. Keyed by user id so a shared device never pre-ticks it for
 *     someone else; without an id nothing is stored.
 *   - Upload / approve / reject also invalidate the `/pending` SWR key so the
 *     /journal inbox card is fresh on return (its dedupingInterval is 30s).
 *   - `?text=` / `?title=` prefill the text tab — the PWA `share_target`
 *     (manifest.ts) points Android's share sheet here with GET.
 *   - Results reuse <PendingTradeList /> from the /journal inbox so a row can
 *     be approved right here, or later at the top of /journal.
 *   - Phone (<md, 2026-10-09 CEO "앱처럼"): the three input methods are
 *     swipeable full-width pages (<JournalPager />) with a tab strip that
 *     tracks the swipe, page dots, and the submit pinned above the bottom nav
 *     (safe-area aware). The page in view is the submit target. At md and up
 *     the pager dissolves and the original tab buttons + single panel return.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT.
 */

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { mutate } from "swr";
import { useAuth } from "@/lib/auth";
import { useLocale, useT } from "@/lib/locale";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { PendingTradeList } from "@/components/journal/import-inbox";
import { ImageImportPanel } from "@/components/journal/image-import-panel";
import { AiTextReadPanel } from "@/components/journal/ai-text-read-panel";
import { JournalPager } from "@/components/journal/journal-pager";
import {
  RuledKicker,
  Caption,
  EditorialHead,
  FieldLabel,
  HairlineSoft,
} from "@/components/ui/editorial";
import type { ImportCreateResponse, PendingTradeDTO } from "@/lib/types";

const CONSENT_KEY_PREFIX = "pivox_import_consent";
const MAX_FILE_BYTES = 2 * 1024 * 1024;
const ACCEPT = ".csv,.xlsx,.xls,.pdf";

/** Per-user storage key; `null` when there is no signed-in id to scope it to. */
function consentKey(userId: number | null | undefined): string | null {
  return userId == null ? null : `${CONSENT_KEY_PREFIX}:${userId}`;
}

function readConsent(key: string | null): boolean {
  if (!key) return false;
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeConsent(key: string | null, on: boolean): void {
  if (!key) return;
  try {
    if (on) window.localStorage.setItem(key, "1");
    else window.localStorage.removeItem(key);
  } catch {
    /* private mode / blocked storage — the checkbox still works for this visit */
  }
}

type Tab = "file" | "text" | "image";

/** Phone page order — also the desktop tab order. */
const TABS: ReadonlyArray<Tab> = ["file", "text", "image"];

/** Tailwind's `md` is 48rem; below it is the phone layout (journal-pager.tsx). */
const PHONE_QUERY = "(max-width: 47.99rem)";

function isPhoneViewport(): boolean {
  return typeof window !== "undefined" && (window.matchMedia?.(PHONE_QUERY).matches ?? false);
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false)
  );
}

function ImportPageInner() {
  const t = useT();
  useLocale();
  const params = useSearchParams();
  const { user } = useAuth();
  const storageKey = consentKey(user?.id);

  // Share-sheet prefill: `?text=` wins, `?title=` alone is still text.
  const sharedText = params.get("text") ?? "";
  const sharedTitle = params.get("title") ?? "";
  const prefill = [sharedTitle, sharedText].filter((s) => s.trim()).join("\n");

  // `?tab=image` — the journal page's "캡처로 가져오기" button lands here
  // with the capture tab already open.
  const initialTab: Tab = prefill ? "text" : params.get("tab") === "image" ? "image" : "file";
  const [tab, setTab] = useState<Tab>(initialTab);
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState(prefill);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportCreateResponse | null>(null);
  const [rows, setRows] = useState<PendingTradeDTO[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const resultRef = useRef<HTMLElement | null>(null);

  // The phone pager reports the page in view; it becomes the submit target.
  const onPageChange = useCallback((i: number) => setTab(TABS[i] ?? "file"), []);

  // Phone: the result lands below the pager, out of sight of the pinned
  // submit — bring it into view. Desktop keeps its layout untouched.
  useEffect(() => {
    if (!result || !isPhoneViewport()) return;
    resultRef.current?.scrollIntoView({
      block: "start",
      behavior: prefersReducedMotion() ? "auto" : "smooth",
    });
  }, [result]);

  // Remembered consent — read after mount (and once the user id is known) so
  // SSR and the first client render agree.
  useEffect(() => {
    if (readConsent(storageKey)) setConsent(true);
  }, [storageKey]);

  const fileTooLarge = file != null && file.size > MAX_FILE_BYTES;
  // Broker-emailed PDF statements (Kiwoom 영웅문S# 서류발급 → 거래내역서) are
  // locked with the holder's 6-digit birth date. Sent once as `pdf_password`,
  // used for the open on the server, never stored there or here.
  const [pdfPassword, setPdfPassword] = useState("");
  const isPdf = file != null && /\.pdf$/i.test(file.name);
  const canSubmit =
    consent &&
    !submitting &&
    tab !== "image" &&
    (tab === "file" ? file != null && !fileTooLarge : text.trim().length > 0);

  function onConsentChange(next: boolean) {
    setConsent(next);
    writeConsent(storageKey, next);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      let res: ImportCreateResponse;
      if (tab === "file" && file) {
        const form = new FormData();
        form.append("file", file);
        form.append("consent", "true");
        if (isPdf && pdfPassword) form.append("pdf_password", pdfPassword);
        res = await apiFetch<ImportCreateResponse>(API.imports.create, {
          method: "POST",
          body: form,
          timeoutMs: 60_000,
        });
      } else {
        res = await apiFetch<ImportCreateResponse>(API.imports.create, {
          method: "POST",
          body: JSON.stringify({ text: text.trim(), source: "screenshot_text", consent: true }),
          timeoutMs: 60_000,
        });
      }
      setResult(res);
      setRows(res.pending.filter((p) => p.status === "pending"));
      // The /journal inbox card reads the same list — refresh its cache now.
      void mutate(API.imports.pending);
      setFile(null);
      setPdfPassword("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      setText("");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : t("journal.page.loadFailure");
      setError(msg || t("journal.page.loadFailure"));
    } finally {
      setSubmitting(false);
    }
  }

  function onImageResult(res: ImportCreateResponse) {
    setError(null);
    // Demo mode answers every POST with {ok:true} — no batch, no rows.
    if (!res || !Array.isArray(res.pending) || !res.batch) return;
    setResult(res);
    setRows(res.pending.filter((p) => p.status === "pending"));
    void mutate(API.imports.pending);
  }

  function onRowChanged(id: number, next: PendingTradeDTO | null) {
    setRows((prev) =>
      next === null ? prev.filter((r) => r.id !== id) : prev.map((r) => (r.id === id ? next : r)),
    );
    void mutate(API.imports.pending);
  }

  const tabClass = (active: boolean) =>
    `px-4 py-2 text-pq-eyebrow uppercase tracking-[0.2em] transition-colors ${
      active
        ? "bg-[rgba(245,240,232,0.10)] border border-[var(--pq-ivory)] text-[var(--pq-ivory)]"
        : "border border-[rgba(245,240,232,0.15)] text-[var(--pq-ivory-mid)] hover:border-[rgba(245,240,232,0.45)]"
    }`;

  const filePanel = (
    <div className="mt-5 max-md:mt-1">
      <FieldLabel tone="bronze">{t("journal.import.page.tabFile")}</FieldLabel>
      <Caption className="mt-1">{t("journal.import.page.fileHint")}</Caption>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          id="import-file"
          type="file"
          accept={ACCEPT}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="sr-only"
        />
        <label
          htmlFor="import-file"
          className="pq-ink-btn-ghost cursor-pointer px-4 text-pq-mono-sm uppercase tracking-[0.22em] max-md:h-12 max-md:w-full max-md:justify-center"
        >
          {t("journal.import.page.fileChoose")}
        </label>
        <span
          className="font-mono truncate max-md:w-full"
          style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}
        >
          {file ? file.name : t("journal.import.page.fileNone")}
        </span>
      </div>
      {fileTooLarge && (
        <Caption className="mt-2">
          <span style={{ color: "var(--pq-error)" }}>
            {t("journal.import.page.fileTooLarge")}
          </span>
        </Caption>
      )}
      {isPdf && (
        <div className="mt-4">
          <label htmlFor="import-pdf-password">
            <FieldLabel tone="bronze">{t("journal.import.page.pdfPasswordLabel")}</FieldLabel>
          </label>
          <input
            id="import-pdf-password"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={64}
            value={pdfPassword}
            onChange={(e) => setPdfPassword(e.target.value)}
            className="pq-input-noom-mono mt-2 block w-full max-w-xs bg-transparent px-3 py-2 font-mono outline-none"
            style={{
              color: "var(--pq-ivory)",
              border: "0.5px solid var(--pq-ivory-line)",
              borderRadius: "var(--pq-radius-cta)",
            }}
          />
          <Caption className="mt-1">{t("journal.import.page.pdfPasswordHint")}</Caption>
        </div>
      )}
    </div>
  );

  const textPanel = (
    <div className="mt-5 max-md:mt-1">
      <label htmlFor="import-text">
        <FieldLabel tone="bronze">{t("journal.import.page.textLabel")}</FieldLabel>
      </label>
      <Caption className="mt-1">{t("journal.import.page.textHint")}</Caption>
      <textarea
        id="import-text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        className="mt-3 w-full bg-transparent border border-[rgba(245,240,232,0.15)] rounded-[2px] p-3 text-pq-body-sm leading-relaxed outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)] font-mono"
        style={{ resize: "vertical" }}
      />
      {prefill && text === prefill && (
        <Caption className="mt-1">{t("journal.import.page.sharePrefilled")}</Caption>
      )}
      <div className="mt-3 space-y-1">
        <Caption>{t("journal.import.page.iosHint")}</Caption>
        <Caption>{t("journal.import.page.androidHint")}</Caption>
        <Caption>{t("journal.import.page.noImage")}</Caption>
      </div>
      {text.trim() !== "" && <AiTextReadPanel text={text} consent={consent} onResult={onImageResult} />}
    </div>
  );

  const panels: Record<Tab, { label: string; content: React.ReactNode }> = {
    file: { label: t("journal.import.page.tabFile"), content: filePanel },
    text: { label: t("journal.import.page.tabText"), content: textPanel },
    image: {
      label: t("journal.import.page.tabImage"),
      // The panel's own top margin is for the desktop tab row; under the
      // phone strip it matches the other pages.
      content: (
        <div className="max-md:*:mt-1">
          <ImageImportPanel consent={consent} onResult={onImageResult} />
        </div>
      ),
    },
  };

  // Phone: every panel is a page in the pager. Desktop: the pager dissolves
  // (md:contents) and only the selected tab's panel is shown, as before.
  // `relative` keeps each panel's absolutely-positioned bits (the sr-only file
  // inputs) inside its own page: otherwise they resolve against an ancestor
  // outside the clipped track, sit at x = page × width and widen the document,
  // which makes mobile browsers zoom the whole screen out.
  const pages = TABS.map((id) => ({
    id,
    label: panels[id].label,
    content: (
      <div className={tab === id ? "relative" : "relative md:hidden"}>{panels[id].content}</div>
    ),
  }));

  return (
    <div className="mx-auto w-full max-w-2xl px-0 pb-2 md:px-6 md:py-8">
      <header className="mb-6">
        <RuledKicker>{t("journal.import.page.kicker")}</RuledKicker>
        <EditorialHead as="h1" size={32} className="mt-3">
          {t("journal.import.page.heading")}
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">{t("journal.import.page.headingDesc")}</Caption>
        <Link
          href="/journal"
          // Phone: the app bar's ‹ carries back (top-bar.tsx subScreen).
          className="mt-3 hidden items-center gap-2 font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline md:inline-flex"
        >
          {t("journal.import.page.backToJournal")}
        </Link>
      </header>

      <form
        onSubmit={submit}
        className="rounded-[2px] md:border md:border-[var(--pq-ivory-line)] md:bg-[var(--pq-card-veil)] md:p-6"
        aria-label={t("journal.import.page.heading")}
      >
        {/* Consent — opt-in, gates the submit. Shared by every input method. */}
        <label className="flex items-start gap-3 cursor-pointer max-md:mb-4">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => onConsentChange(e.target.checked)}
            className="mt-1 h-4 w-4 shrink-0 accent-[var(--pq-bronze)]"
            aria-label={t("journal.import.page.consentLabel")}
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
            {t("journal.import.page.consentLabel")}
          </span>
        </label>

        <HairlineSoft className="my-5 max-md:hidden" />

        {/* Source tabs — desktop. The phone pager below carries its own strip. */}
        <div
          className="hidden gap-2 md:flex"
          role="tablist"
          aria-label={t("journal.import.page.heading")}
          data-testid="import-tabs-desktop"
        >
          {TABS.map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={tabClass(tab === id)}
              data-testid={id === "image" ? "import-tab-image" : undefined}
            >
              {panels[id].label}
            </button>
          ))}
        </div>

        <JournalPager
          ariaLabel={t("journal.import.page.heading")}
          requestedPage={TABS.indexOf(tab)}
          onPageChange={onPageChange}
          pages={pages}
        />

        {/* Submit — desktop: an inline row under the panel, as before. Phone:
            pinned above the bottom nav (whose own padding carries the
            home-indicator inset, hence --pq-safe-bottom in the offset); the
            bottom padding leaves room for the pager's page dots. z-[5] keeps
            it under the app bar (z-20) and the tab strip (z-10) once it
            scrolls up with the form. The capture page has its own read/send
            steps, so it shows no bar. */}
        <div
          className={
            tab === "image"
              ? undefined
              : "max-md:sticky max-md:z-[5] max-md:-mx-4 max-md:mt-6 max-md:border-t max-md:border-[var(--pq-ivory-line)] max-md:bg-[var(--pq-ink)] max-md:px-4 max-md:pt-3 max-md:pb-9"
          }
          style={{ bottom: "calc(var(--pq-bottomnav-height) + var(--pq-safe-bottom))" }}
          data-testid="import-action-bar"
        >
          <div className={`mt-5 flex items-center gap-3 max-md:mt-0${tab === "image" ? " hidden" : ""}`}>
            <button
              type="submit"
              disabled={!canSubmit}
              aria-disabled={!canSubmit}
              className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed max-md:h-12 max-md:w-full max-md:justify-center"
              data-testid="import-submit"
            >
              {submitting ? t("journal.import.page.submitting") : t("journal.import.page.submit")}
            </button>
          </div>

          {error && (
            <Caption className="mt-3 max-md:mt-2">
              <span style={{ color: "var(--pq-error)" }}>{error}</span>
            </Caption>
          )}
        </div>
      </form>

      {/* Result — factual counts + the rows, approvable in place. */}
      {result && (
        <section
          ref={resultRef}
          className="mt-8 scroll-mt-[calc(var(--pq-aux-sticky-top)+1rem)] rounded-[2px] border p-5 sm:p-6"
          style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
          aria-label={t("journal.import.page.resultKicker")}
        >
          <RuledKicker>{t("journal.import.page.resultKicker")}</RuledKicker>
          <EditorialHead as="h2" size={22} tone="ivory" className="mt-3">
            {t("journal.import.page.resultSummary")
              .replace("{parsed}", String(result.batch.parsed_count))
              .replace("{dup}", String(result.batch.duplicate_count))
              .replace("{unresolved}", String(result.batch.unresolved_count))}
          </EditorialHead>
          {result.unmapped_headers.length > 0 && (
            <Caption className="mt-2">
              {t("journal.import.page.unmappedHeaders").replace(
                "{headers}",
                result.unmapped_headers.join(", "),
              )}
            </Caption>
          )}
          {(result.skipped?.length ?? 0) > 0 && (
            <div className="mt-3" data-testid="import-skipped">
              <Caption>
                {t("journal.import.page.skippedTitle").replace(
                  "{n}",
                  String(result.skipped?.length ?? 0),
                )}
              </Caption>
              <ul className="mt-1 space-y-1">
                {(result.skipped ?? []).map((s) => (
                  <li
                    key={`${s.row}-${s.reason}`}
                    className="font-mono"
                    style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-dim)" }}
                  >
                    <span style={{ color: "var(--pq-ivory-mid)" }}>{s.row}</span>
                    {" · "}
                    {s.reason}
                    {s.snippet ? ` — ${s.snippet}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Caption className="mt-2 max-w-lg">{t("journal.import.page.resultDesc")}</Caption>

          {rows.length === 0 ? (
            <Caption className="mt-4">{t("journal.import.page.resultEmpty")}</Caption>
          ) : (
            <PendingTradeList rows={rows} onChanged={onRowChanged} />
          )}
        </section>
      )}

      {/* Automation pointer — the webhook token lives in /settings. */}
      <Link
        href="/settings#import-tokens"
        className="mt-6 inline-flex items-center gap-2 font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
      >
        {t("journal.import.page.tokensLink")}
      </Link>
    </div>
  );
}

export default function ImportPage(): React.ReactElement {
  // useSearchParams needs a Suspense boundary at the page level so the route
  // keeps a static shell (same pattern as /feedback/nps).
  return (
    <Suspense fallback={<div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6" aria-hidden />}>
      <ImportPageInner />
    </Suspense>
  );
}
