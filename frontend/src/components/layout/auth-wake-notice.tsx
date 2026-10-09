"use client";

/**
 * <AuthWakeNotice /> — the one line the (dashboard) shell shows while the
 * auth state is UNKNOWN (useAuth().waking): the backend has not answered
 * `/api/auth/me` yet, almost always because the free-plan Render service is
 * still booting (~44 s cold, keep-warm.yml).
 *
 * Before 2026-10-09 the shell treated that as "signed out" and sent the user
 * to /login, where a signed-in person was asked to sign in again and then
 * bounced back once the server woke. Now the shell holds its skeleton with
 * this line; past the wake deadline it says so and offers a retry.
 * Renders nothing outside the unknown state.
 */

import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/locale";

export function AuthWakeNotice() {
  const { waking, wakeFailed, retryAuth } = useAuth();
  const t = useT();
  if (!waking) return null;
  return (
    <div
      data-testid="auth-wake-notice"
      className="mb-4 flex flex-wrap items-center gap-3 text-[12.5px]"
      style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)", lineHeight: 1.5 }}
    >
      <p role={wakeFailed ? "alert" : "status"} aria-live="polite" className="m-0">
        {wakeFailed ? t("auth.login.wakeFailed") : t("auth.login.waking")}
      </p>
      {wakeFailed ? (
        <button
          type="button"
          onClick={retryAuth}
          className="min-h-[44px] rounded-[2px] border px-4"
          style={{
            borderColor: "rgba(var(--pq-bronze-rgb), 0.45)",
            color: "var(--pq-bronze)",
            background: "transparent",
          }}
        >
          {t("auth.login.wakeRetry")}
        </button>
      ) : null}
    </div>
  );
}
