"use client";

/**
 * Onboarding · 체결 자동 기록 — between holdings (step 0) and the five
 * questions.
 *
 * 2026-10-07, CEO: "아이폰 안드로이드 세팅 기능들도 최초 로그인 때 포지션
 * 올리는 것처럼 바로 하게끔". The phone automation (MacroDroid / iOS
 * Shortcuts → import webhook → pending inbox → fill_memo push) used to live
 * only in /settings, where a new user would never find it. Here it is one
 * screen, right after the holdings, for the phone the user is holding.
 *
 * Optional: "나중에" goes on to the questions, and the same setup stays in
 * /settings. Issuing a token needs the consent tick — the server refuses it
 * otherwise (IMPORT_CONSENT_REQUIRED). The raw token is shown once, exactly
 * as in ImportTokensSection, and the copy fields / steps are the same i18n
 * keys, so the two places cannot drift apart.
 *
 * 2026-10-10, CEO: "증권사별로 아니면 폰 별로 해당 가능한 기능들 세팅하게끔".
 * Phone → broker → (iPhone) SMS or app notification, then one line on what
 * that combination needs, then only its steps. The rules live in
 * lib/fill-setup.ts. Picking a broker is optional; without one the iPhone
 * opens on SMS, as before.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useImportTokens, usePortfolioPositions } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import { currentLocationPath, loginHref } from "@/lib/login-redirect";
import { detectPhone, type PhoneKind } from "@/lib/phone";
import {
  FILL_BROKERS,
  brokerHintKey,
  defaultIosRoute,
  fillRoute,
  kickerKey,
  statusKey,
  stepKeys,
  type FillBroker,
  type IosRoute,
} from "@/lib/fill-setup";
import type { ImportTokenCreateResponse } from "@/lib/types";
import {
  MACRODROID_BODY,
  CopyField,
  authHeaderValue,
  errorKey,
  webhookUrl,
} from "@/components/settings/import-tokens-section";

const TOKEN_NAME: Record<PhoneKind, string> = {
  android: "안드로이드 폰",
  ios: "아이폰",
};

export default function OnboardingFillsPage() {
  const router = useRouter();
  const t = useT();
  const { user, loading: authLoading } = useAuth();
  const { tokens, isLoading: tokensLoading, mutate } = useImportTokens();
  const { data: posData } = usePortfolioPositions<{ positions?: unknown[] }>();

  const [phone, setPhone] = useState<PhoneKind>("android");
  const [broker, setBroker] = useState<FillBroker | null>(null);
  const [iosRoute, setIosRoute] = useState<IosRoute>("sms");
  const [origin, setOrigin] = useState("");
  const [consent, setConsent] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<ImportTokenCreateResponse | null>(null);

  useEffect(() => {
    setPhone(detectPhone(window.navigator.userAgent));
    setOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace(loginHref(currentLocationPath()));
      return;
    }
    if (!authLoading && user?.onboarding_completed === true) router.replace("/mirror");
  }, [authLoading, user, router]);

  // Holdings come first, same rule as the questions page.
  useEffect(() => {
    if (!user || user.onboarding_completed === true || posData === undefined) return;
    if ((posData.positions ?? []).length === 0) router.replace("/onboarding/broker");
  }, [user, posData, router]);

  const hasActiveToken = tokens.some((tk) => !tk.revoked_at);

  const issue = async () => {
    if (!consent || issuing) return;
    setIssuing(true);
    setError(null);
    try {
      const res = await apiFetch<ImportTokenCreateResponse>(API.imports.tokens, {
        method: "POST",
        body: JSON.stringify({ name: TOKEN_NAME[phone], consent: true }),
      });
      setIssued(res);
      await mutate();
    } catch (err) {
      setError(t(errorKey(err)));
    } finally {
      setIssuing(false);
    }
  };

  const next = () => router.push("/onboarding");

  const pickBroker = (b: FillBroker) => {
    setBroker(b);
    setIosRoute(defaultIosRoute(b));
  };

  if (authLoading || !user || user.onboarding_completed === true) return null;

  const route = fillRoute(phone, iosRoute);

  return (
    <div className="flex min-h-[100dvh] flex-col bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      <header className="sticky top-0 z-20 border-b border-[var(--pq-ivory-line)] bg-[rgba(10,10,10,0.9)] px-4 py-3 backdrop-blur-xl sm:px-6">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <span className="font-serif text-base">PivoxQuant</span>
          <span className="text-pq-mono-sm text-[var(--pq-ivory-faint)]">{t("fillsOnboarding.stepLabel")}</span>
        </div>
      </header>

      <main className="flex-1 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl py-8">
          <h1 className="font-serif text-[28px] leading-[1.3] [word-break:keep-all] sm:text-4xl">
            {t("fillsOnboarding.title")}
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]">
            {t("fillsOnboarding.subtitle")}
          </p>

          {/* Phone switch — preselected from the user agent. */}
          <div role="tablist" aria-label={t("fillsOnboarding.phoneLabel")} className="mt-6 flex border-b border-[var(--pq-ivory-line)]">
            {(["android", "ios"] as const).map((k) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={phone === k}
                onClick={() => setPhone(k)}
                className="relative flex-1 py-3 text-[15px]"
                style={{ color: phone === k ? "var(--pq-ivory)" : "var(--pq-ivory-dim)" }}
                data-testid={`fills-phone-${k}`}
              >
                {t(`fillsOnboarding.phone.${k}`)}
                {phone === k && (
                  <span aria-hidden className="absolute inset-x-8 bottom-0 h-[2px]" style={{ background: "var(--pq-bronze)" }} />
                )}
              </button>
            ))}
          </div>

          {/* Broker — optional; it picks the iPhone route and adds one sourced hint. */}
          <section className="mt-6" aria-labelledby="fills-broker-label">
            <div id="fills-broker-label" className="text-[13px] tracking-[0.16em] text-[var(--pq-bronze)]">
              {t("fillsOnboarding.brokerLabel")}
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-[var(--pq-ivory-faint)] [word-break:keep-all]">
              {t("fillsOnboarding.brokerPrompt")}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {FILL_BROKERS.map((b) => (
                <button
                  key={b}
                  type="button"
                  aria-pressed={broker === b}
                  onClick={() => pickBroker(b)}
                  className="min-h-[44px] rounded-[2px] border px-3 text-[14px]"
                  style={{
                    borderColor: broker === b ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
                    color: broker === b ? "var(--pq-ivory)" : "var(--pq-ivory-dim)",
                  }}
                  data-testid={`fills-broker-${b}`}
                >
                  {t(`fillsOnboarding.broker.${b}`)}
                </button>
              ))}
            </div>
            {broker && (
              <p className="mt-3 text-[14px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]" data-testid="fills-broker-hint">
                {t(brokerHintKey(broker))}
              </p>
            )}
          </section>

          {/* iPhone — SMS works on any iOS; an app's push needs iOS 27. */}
          {phone === "ios" && (
            <div
              role="radiogroup"
              aria-label={t("fillsOnboarding.iosRouteLabel")}
              className="mt-5 grid grid-cols-2 gap-2"
            >
              {(["sms", "app"] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  role="radio"
                  aria-checked={iosRoute === r}
                  onClick={() => setIosRoute(r)}
                  className="min-h-[44px] rounded-[2px] border px-2 text-[14px] [word-break:keep-all]"
                  style={{
                    borderColor: iosRoute === r ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
                    color: iosRoute === r ? "var(--pq-ivory)" : "var(--pq-ivory-dim)",
                  }}
                  data-testid={`fills-ios-route-${r}`}
                >
                  {t(`fillsOnboarding.iosRoute.${r}`)}
                </button>
              ))}
            </div>
          )}

          <p className="mt-4 text-[14px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]" data-testid="fills-need">
            {t(statusKey(route))}
          </p>

          {/* 1 — the key. */}
          <section className="mt-6 rounded-[2px] border border-[var(--pq-ivory-line)] p-4">
            <div className="text-[13px] tracking-[0.16em] text-[var(--pq-bronze)]">{t("fillsOnboarding.keyKicker")}</div>

            {issued ? (
              <div data-testid="fills-issued">
                <p className="mt-2 text-[14px] text-[var(--pq-ivory-mid)]">{t("settingsV2.importTokens.revealOnce")}</p>
                <CopyField label={t("settingsV2.importTokens.urlLabel")} value={webhookUrl(origin)} testId="fills-url" />
                <CopyField label={t("settingsV2.importTokens.headerLabel")} value={authHeaderValue(issued.token)} testId="fills-header" />
                {phone === "android" && (
                  <CopyField label={t("settingsV2.importTokens.bodyLabel")} value={MACRODROID_BODY} testId="fills-body" />
                )}
              </div>
            ) : tokensLoading ? (
              // Until the key list arrives, `tokens` is [] — rendering the
              // issue form here flashes it at a user who already has a key.
              <div
                className="pq-skeleton-dark mt-3 h-[88px] w-full rounded-[2px]"
                role="status"
                aria-busy="true"
                data-testid="fills-token-loading"
              />
            ) : hasActiveToken ? (
              <p className="mt-2 text-[14px] leading-relaxed text-[var(--pq-ivory-mid)]" data-testid="fills-has-token">
                {t("fillsOnboarding.hasToken")}
              </p>
            ) : (
              <>
                <label className="mt-3 flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-1 h-4 w-4 shrink-0 accent-[var(--pq-bronze)]"
                    data-testid="fills-consent"
                  />
                  <span className="text-[14px] leading-relaxed text-[var(--pq-ivory-soft)] [word-break:keep-all]">
                    {t("settingsV2.importTokens.consentLabel")}
                  </span>
                </label>
                <button
                  type="button"
                  onClick={issue}
                  disabled={!consent || issuing}
                  className="pq-ink-btn-bronze mt-4 flex min-h-[48px] w-full items-center justify-center text-[15px] disabled:cursor-not-allowed disabled:opacity-30"
                  data-testid="fills-issue"
                >
                  {issuing ? t("settingsV2.importTokens.issuing") : t("fillsOnboarding.issue")}
                </button>
                {error && (
                  <p role="alert" className="mt-2 text-[14px]" style={{ color: "var(--pq-error)" }}>
                    {error}
                  </p>
                )}
              </>
            )}
          </section>

          {/* 2 — the phone side. */}
          <section className="mt-6" data-testid={`fills-steps-${phone}`} data-route={route}>
            <div className="text-[13px] tracking-[0.16em] text-[var(--pq-bronze)]">
              {t(kickerKey(route))}
            </div>
            {route === "ios-app" && (
              <p className="mt-2 text-[14px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]" data-testid="fills-ios-app-caveat">
                {t("settingsV2.importTokens.iosAppCaveat")}
              </p>
            )}
            <ol className="mt-3 space-y-2">
              {stepKeys(route).map((k) => (
                <li key={k} className="text-[14px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]">
                  {t(k)}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-[14px] leading-relaxed text-[var(--pq-ivory-mid)] [word-break:keep-all]">
              {t("settingsV2.importTokens.guideMemo")}
            </p>
          </section>

          <p className="mt-6 text-[13px] leading-relaxed text-[var(--pq-ivory-faint)] [word-break:keep-all]">
            {t("fillsOnboarding.later")}
          </p>
        </div>
      </main>

      <footer
        className="sticky bottom-0 z-20 border-t border-[var(--pq-ivory-line)] bg-[rgba(10,10,10,0.9)] px-4 py-4 backdrop-blur-xl sm:px-6"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom, 0px))" }}
      >
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <button
            type="button"
            onClick={next}
            className="min-h-[44px] px-2 text-[15px] text-[var(--pq-ivory-dim)]"
            data-testid="fills-skip"
          >
            {t("fillsOnboarding.skip")}
          </button>
          <button
            type="button"
            onClick={next}
            className="pq-ink-btn-bronze inline-flex min-h-[44px] items-center gap-1"
            data-testid="fills-next"
          >
            {t("brokerOnboarding.nextStep")}
            <ChevronRight size={14} />
          </button>
        </div>
      </footer>
    </div>
  );
}
