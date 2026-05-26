"use client";

/**
 * Share Card Modal — K-factor `i` lever (one-tap sharing of a brag card).
 *
 * Three share affordances, ordered by friction:
 *   1. 카카오톡 공유 — Kakao JS SDK (free). Hidden when NEXT_PUBLIC_KAKAO_KEY
 *      is unset so the build never breaks (CEO action TODO in kakao-share.ts).
 *   2. 이미지 저장 — navigator.share() on mobile (sheet incl. save), PNG
 *      download fallback on desktop.
 *   3. 링크 복사 — navigator.clipboard, with a document.execCommand fallback.
 *
 * Every share dispatches a `share_clicked` funnel event (channel in meta).
 *
 * §101 / compliance: the prefilled caption is the user's own factual record
 * + a generic product mention. No ticker recommendation, no return/profit
 * guarantee, no buy/sell/추천 language. The shared link points at the public
 * OG landing (/r/<referral_code> or /card/<share_token>).
 */

import { useCallback, useMemo, useState } from "react";
import { motion } from "motion/react";
import { Copy, Download, Share2, Check, X } from "lucide-react";
import { toast } from "sonner";

import { PQ_EASE, PQ_DUR_BASE } from "@/lib/motion";
import { track } from "@/lib/track";
import { isKakaoAvailable, shareToKakao } from "@/lib/kakao-share";
import { ModalShell } from "@/components/ui/modal-shell";

/** §101-safe default caption — factual + generic, no recommendation. */
const DEFAULT_CAPTION = "나의 이번 달 투자 기록 📈 by PivoxQuant";

export interface ShareCardModalProps {
  /** Owner-facing close handler. */
  onClose: () => void;
  /**
   * The share link the social card points at. Caller passes the public OG
   * landing URL (e.g. `${origin}/r/<referral_code>`); a relative path is
   * resolved against `window.location.origin`.
   */
  shareUrl: string;
  /**
   * Card image for the social unfurl + PNG download. Either an
   * `image/png;base64` data URL (from the preview `png_base64`) or an
   * absolute public image URL (the backend share image-serve route).
   */
  imageSrc: string | null;
  /** Title surfaced on the Kakao feed card. */
  title?: string;
  /** Pre-filled caption the user can copy alongside the link. */
  caption?: string;
}

/** Resolve a possibly-relative URL to an absolute one (browser only). */
function absolute(url: string): string {
  if (typeof window === "undefined") return url;
  try {
    return new URL(url, window.location.origin).toString();
  } catch {
    return url;
  }
}

export function ShareCardModal({
  onClose,
  shareUrl,
  imageSrc,
  title = "이번 달 투자 기록",
  caption = DEFAULT_CAPTION,
}: ShareCardModalProps) {
  const [copied, setCopied] = useState(false);
  const absUrl = useMemo(() => absolute(shareUrl), [shareUrl]);
  // Caption with the link appended — what the user pastes into a post.
  const fullCaption = useMemo(
    () => `${caption}\n${absUrl}`,
    [caption, absUrl],
  );
  const kakaoOn = isKakaoAvailable();

  const handleKakao = useCallback(async () => {
    void track("share_clicked", { channel: "kakao", meta: { surface: "card" } });
    const ok = await shareToKakao({
      title,
      description: caption,
      imageUrl: imageSrc && /^https?:/.test(imageSrc) ? imageSrc : absUrl,
      linkUrl: absUrl,
    });
    if (!ok) {
      toast.error("카카오 공유를 사용할 수 없어요. 링크 복사를 이용해 주세요.");
    }
  }, [title, caption, imageSrc, absUrl]);

  const handleSaveImage = useCallback(async () => {
    void track("share_clicked", { channel: "image", meta: { surface: "card" } });
    if (!imageSrc) {
      toast.error("이미지를 준비하지 못했어요.");
      return;
    }
    // Mobile: native share sheet (includes "이미지 저장"). Prefer sharing the
    // file when possible so the image itself (not just a link) is shared.
    try {
      const blob = await (await fetch(imageSrc)).blob();
      const file = new File([blob], "pivoxquant-brag-card.png", {
        type: "image/png",
      });
      const nav = navigator as Navigator & {
        canShare?: (data: ShareData) => boolean;
      };
      if (
        typeof navigator.share === "function" &&
        nav.canShare?.({ files: [file] })
      ) {
        await navigator.share({ files: [file], text: fullCaption, title });
        return;
      }
      // Desktop fallback: trigger a PNG download.
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = "pivoxquant-brag-card.png";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success("이미지를 저장했어요.");
    } catch (err) {
      // AbortError = user dismissed the native sheet; not a failure.
      if (err instanceof DOMException && err.name === "AbortError") return;
      toast.error("이미지 저장에 실패했어요.");
    }
  }, [imageSrc, fullCaption, title]);

  const handleCopyLink = useCallback(async () => {
    void track("share_clicked", { channel: "link", meta: { surface: "card" } });
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(fullCaption);
      } else {
        // Legacy fallback for non-secure contexts.
        const ta = document.createElement("textarea");
        ta.value = fullCaption;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      setCopied(true);
      toast.success("링크를 복사했어요.");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("복사에 실패했어요.");
    }
  }, [fullCaption]);

  return (
    <ModalShell onClose={onClose} ariaLabel="카드 공유">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: PQ_DUR_BASE, ease: PQ_EASE }}
        onClick={(e) => e.stopPropagation()}
        // Lift the bottom sheet clear of the mobile BottomNav (md:hidden, z-50,
        // h-16 + safe-area) so the share / save actions never sit behind it.
        // --pq-bottomnav-clearance is the single source of truth (globals.css).
        // Cleared at sm+ where the dialog is centered and the nav hides.
        className="mb-[var(--pq-bottomnav-clearance)] w-full max-w-md overflow-hidden sm:mb-0"
        style={{
          background: "var(--pq-ink)",
          border: "1px solid var(--pq-border)",
          borderRadius: "var(--pq-radius-card)",
          color: "var(--pq-ivory)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between gap-3 px-5 py-4"
          style={{ borderBottom: "1px solid var(--pq-border)" }}
        >
          <div>
            <div
              className="text-xs font-semibold uppercase font-mono"
              style={{ color: "var(--pq-bronze)", letterSpacing: "0.2em" }}
            >
              Share
            </div>
            <div className="mt-0.5 text-lg font-display">카드 공유하기</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-md transition-colors"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-col gap-3 px-5 py-5">
          <p
            className="text-sm leading-relaxed"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.7)" }}
          >
            내 투자 기록을 친구에게 공유해 보세요. 받는 분은 가입 없이
            카드를 볼 수 있어요.
          </p>

          {kakaoOn && (
            <ShareButton
              icon={<Share2 className="h-4 w-4" />}
              label="카카오톡 공유"
              onClick={handleKakao}
            />
          )}
          <ShareButton
            icon={<Download className="h-4 w-4" />}
            label="이미지 저장"
            onClick={handleSaveImage}
          />
          <ShareButton
            icon={
              copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />
            }
            label={copied ? "링크 복사됨" : "링크 복사"}
            onClick={handleCopyLink}
          />

          {/* §101 micro-note */}
          <p
            className="mt-1 text-xs leading-relaxed"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
          >
            정보 제공 목적이며 투자 권유가 아닙니다.
          </p>
        </div>
      </motion.div>
    </ModalShell>
  );
}

function ShareButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.98 }}
      className="flex w-full items-center gap-3 px-4 py-3.5 text-left text-sm font-medium transition-colors"
      style={{
        border: "1px solid rgba(245,240,232,0.12)",
        borderRadius: "var(--pq-radius-cta)",
        background: "var(--pq-ivory-line-ghost)",
        color: "var(--pq-ivory)",
      }}
    >
      <span style={{ color: "var(--pq-bronze)" }}>{icon}</span>
      {label}
    </motion.button>
  );
}
