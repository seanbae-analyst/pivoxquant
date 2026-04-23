"use client";

/**
 * /settings/profile — Profile-only surface.
 *
 * Split out of /settings so the profile dropdown can link to a dedicated
 * page. Contains: identity card (avatar initials, name, email, tier),
 * investor-assessment link, name edit, language, delete-account deeplink.
 */

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useInvestmentProfile } from "@/lib/hooks";
import { useLocale } from "@/lib/locale";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ModalShell } from "@/components/ui/modal-shell";
import { cn } from "@/lib/utils";
import {
  ChevronRight,
  Loader2,
  AlertTriangle,
  X,
  Trash2,
  ArrowLeft,
} from "lucide-react";

/* ── Investor labels ── */

const INVESTOR_TYPE_LABELS: Record<string, string> = {
  passive_index_hugger: "Passive index",
  steady_accumulator: "Steady accumulator",
  value_hunter: "Value hunter",
  risk_managed_growth: "Risk-managed growth",
  swing_trader: "Swing trader",
  momentum_rider: "Momentum rider",
  macro_rotator: "Macro rotator",
  aggressive_scalper: "Aggressive scalper",
};

function initials(name?: string | null, email?: string | null): string {
  if (name) {
    return name
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }
  if (email) return email.slice(0, 2).toUpperCase();
  return "PQ";
}

/* ── Section shell ── */

function Section({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header>
        <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          {kicker}
        </div>
        <h2 className="mt-1 font-serif text-2xl text-[var(--pq-ivory)]">
          {title}
        </h2>
      </header>
      {children}
    </section>
  );
}

/* ── Delete modal ── */

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div className="my-auto w-full max-w-md bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] p-6 rounded-[2px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              Delete account
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-[rgba(245,240,232,0.6)] mb-6">
          Deletion is permanent and removes all positions, watchlists, and
          delivered artifacts. Per PIPA, all data is purged within 30 days.
        </p>
        <div className="flex items-center gap-3">
          <a
            href="mailto:seanbae1521@gmail.com?subject=Account%20Deletion%20Request"
            className="flex-1 pq-ink-btn-bronze text-center"
          >
            Contact support
          </a>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 pq-ink-btn-ghost"
          >
            Cancel
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── Page ── */

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading: authLoading, refresh } = useAuth();
  const { data: profileData, isLoading: profileLoading } = useInvestmentProfile();
  const investorType = profileData?.profile?.profile_type ?? null;
  const { locale, setLocale } = useLocale();

  const [nameInput, setNameInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user?.name) setNameInput(user.name);
  }, [user]);

  const tier = (user?.subscription_tier ?? "observer").toLowerCase();
  const tierLabel =
    tier === "pro" || tier === "operator"
      ? "Operator"
      : tier === "premium" || tier === "partner"
        ? "Partner"
        : "Observer";

  const handleSaveName = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = nameInput.trim();
      if (!trimmed) {
        toast.error("Name cannot be empty.");
        return;
      }
      if (trimmed === user?.name) return;
      setSaving(true);
      try {
        await apiFetch(API.profile.update, {
          method: "PATCH",
          body: JSON.stringify({ name: trimmed }),
        });
        await refresh();
        toast.success("Name updated.");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Update failed.");
      } finally {
        setSaving(false);
      }
    },
    [nameInput, user, refresh],
  );

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--pq-bronze)]" />
      </div>
    );
  }

  const init = initials(user.name, user.email);

  return (
    <ErrorBoundary>
      <div className="space-y-10">
        {/* ── Header ── */}
        <header>
          <Link
            href="/settings"
            className="inline-flex items-center gap-1.5 text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)] transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to settings
          </Link>
          <h1 className="mt-3 font-serif text-2xl md:text-3xl text-[var(--pq-ivory)]">
            My Profile
          </h1>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.5)]">
            Identity, assessment, and personal preferences.
          </p>
        </header>

        {/* ── Identity card ── */}
        <Section kicker="01 · Identity" title="Who you are">
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-6 rounded-[2px]">
            <div className="flex items-center gap-5">
              <span
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full font-mono text-lg font-semibold"
                style={{
                  background: "transparent",
                  border: "0.5px solid var(--pq-bronze)",
                  color: "var(--pq-bronze)",
                  letterSpacing: "0.04em",
                }}
              >
                {init}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-serif text-xl text-[var(--pq-ivory)] truncate">
                  {user.name || "Unnamed"}
                </div>
                <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)] truncate">
                  {user.email}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono"
                    style={{
                      border: "0.5px solid var(--pq-bronze)",
                      color: "var(--pq-bronze)",
                      letterSpacing: "0.2em",
                      textTransform: "uppercase",
                    }}
                  >
                    {tierLabel}
                  </span>
                  {user.oauth_provider && (
                    <span className="text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
                      via {user.oauth_provider === "kakao" ? "Kakao" : user.oauth_provider}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Section>

        {/* ── Name ── */}
        <Section kicker="02 · Display" title="Name">
          <form
            onSubmit={handleSaveName}
            className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px] space-y-3"
          >
            <label
              htmlFor="profile-name"
              className="block text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)]"
            >
              Display name
            </label>
            <input
              id="profile-name"
              type="text"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              maxLength={50}
              className="pq-ink-input w-full"
              placeholder="Your name"
            />
            <div className="flex items-center gap-3">
              <span className="text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
                Email is read-only
              </span>
              <button
                type="submit"
                disabled={saving || nameInput.trim() === user.name}
                className="pq-ink-btn-bronze ml-auto flex items-center gap-1.5 disabled:opacity-50"
              >
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </Section>

        {/* ── Investor Assessment ── */}
        <Section kicker="03 · Calibration" title="Investor assessment">
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
            <div className="flex items-center justify-between gap-4 mb-4">
              <span className="text-sm text-[rgba(245,240,232,0.6)]">
                Investor type
              </span>
              <span className="text-sm text-[var(--pq-ivory)]">
                {profileLoading ? (
                  <span className="text-[rgba(245,240,232,0.3)]">Loading…</span>
                ) : investorType ? (
                  INVESTOR_TYPE_LABELS[investorType] ?? investorType
                ) : (
                  <span className="text-[rgba(245,240,232,0.3)]">Not set</span>
                )}
              </span>
            </div>
            <Link
              href="/onboarding"
              className="flex items-center justify-between border border-[rgba(245,240,232,0.08)] px-4 py-3 rounded-[2px] hover:border-[var(--pq-bronze)] transition-colors group"
            >
              <div>
                <div className="font-serif text-base text-[var(--pq-ivory)]">
                  {investorType ? "Retake assessment" : "Take investor assessment"}
                </div>
                <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
                  20-question questionnaire — calibrates every analytical surface.
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-[var(--pq-bronze)] transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </Section>

        {/* ── Language ── */}
        <Section kicker="04 · Locale" title="Language">
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
            <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-3">
              Interface language
            </div>
            <div className="flex gap-2">
              {(["ko", "en"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => {
                    setLocale(l);
                    toast.success("Language updated.");
                  }}
                  className={cn(
                    locale === l ? "pq-ink-btn-bronze" : "pq-ink-btn-ghost",
                  )}
                >
                  {l === "ko" ? "한국어" : "English"}
                </button>
              ))}
            </div>
          </div>
        </Section>

        {/* ── Danger zone ── */}
        <section className="pt-8 border-t border-[rgba(245,240,232,0.08)]">
          <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
            Danger zone
          </div>
          <p className="mt-2 text-xs text-[rgba(245,240,232,0.5)]">
            Deletion is permanent and purges all positions, watchlists, and
            artifacts within 30 days (PIPA).
          </p>
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 border border-red-500/30 text-red-400 text-xs tracking-[0.18em] uppercase hover:bg-red-500/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete account
            </button>
          </div>
        </section>
      </div>

      {showDelete && <DeleteAccountModal onClose={() => setShowDelete(false)} />}
    </ErrorBoundary>
  );
}
