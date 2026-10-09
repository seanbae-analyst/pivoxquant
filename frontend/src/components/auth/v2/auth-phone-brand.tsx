/**
 * <AuthPhoneBrand />
 *
 * The PIVOXQUANT wordmark block at the top of the PHONE auth entry
 * (/login, /signup). 2026-10-09, CEO: "폰 그리고 시작하기 들어가서 나오는
 * 로그인 부분 너무 이상함" — the installed app opens on AppCover
 * (components/pwa/app-welcome.tsx): PIVOXQUANT alone on Vantablack. Tapping
 * 시작하기 used to drop the user onto a web-style editorial split page with no
 * wordmark at all. This block repeats AppCover's wordmark — same class, same
 * size, same 0.22em tracking — so cover → cards → sign-in reads as one app.
 *
 * Pure presentational. Visibility (phone only) is the caller's job — the
 * desktop split layout stays as it was.
 */

interface AuthPhoneBrandProps {
  /** Small line under the wordmark (e.g. "멈춤 · 기록 · 거울"). */
  tagline?: string;
  /**
   * "cover" (default) — AppCover's size, for the sign-in screen.
   * "compact" — a small header mark for the steps after it
   * (signup/oauth-finalize), where the form needs the room.
   */
  size?: "cover" | "compact";
}

export function AuthPhoneBrand({ tagline, size = "cover" }: AuthPhoneBrandProps) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center"
      style={{ gap: 18 }}
      data-testid="auth-phone-brand"
    >
      {/* Same treatment as AppCover: `pq-splash-wordmark` (display face +
          ivory text-shadow), uppercase, 0.22em tracking, min(display, 10vw).
          The cover's slow "breath" is switched off here: this is a working
          screen, not a splash. */}
      <span
        className="pq-splash-wordmark font-serif"
        style={{
          fontSize:
            size === "compact"
              ? "var(--pq-text-h5)"
              : "min(var(--pq-text-display), 10vw)",
          letterSpacing: "0.22em",
          // Tracking adds trailing space after the last letter; pull it back
          // so the word sits optically centred, as on the cover.
          marginRight: "-0.22em",
          lineHeight: 1,
          fontWeight: 500,
          textTransform: "uppercase",
          color: "var(--pq-ivory)",
          animation: "none",
        }}
      >
        PIVOXQUANT
      </span>
      {tagline ? (
        <span
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-caption)",
            letterSpacing: "0.24em",
            marginRight: "-0.24em",
            color: "rgba(var(--pq-bronze-rgb), 0.80)",
          }}
        >
          {tagline}
        </span>
      ) : null}
    </div>
  );
}

export default AuthPhoneBrand;
