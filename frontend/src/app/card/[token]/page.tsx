/**
 * /card/[token] — PUBLIC OG card landing (K-factor `c` lever).
 *
 * Server component. Fetches GET /api/card/<share_token> (public, no auth) so
 * the page is crawler-friendly and `generateMetadata` can emit the brag-card
 * image as the og:image (Kakao / X / Slack unfurl).
 *
 * 404 / private cards fall through to <PublicCardNotFound /> — the backend
 * returns the same 404 for missing + private, so this surface never leaks
 * whether another user's card exists (PIPA §29 enumeration guard).
 *
 * §101: only the owner's own factual snapshot + a generic, server-generated
 * `summary_safe` line are shown. No recommendation language anywhere.
 */

import type { Metadata } from "next";

import { serverGetPublic } from "@/lib/server-api";
import { API } from "@/lib/endpoints";
import type { PublicCardResponse } from "@/lib/types";
import { PublicCardView } from "@/components/growth/public-card-view";
import { PublicCardNotFound } from "@/components/growth/public-card-not-found";
import { LandingViewTracker } from "@/components/growth/landing-view-tracker";

async function fetchCard(token: string): Promise<PublicCardResponse | null> {
  if (!token || token.length < 16 || token.length > 64) return null;
  return serverGetPublic<PublicCardResponse>(API.viral.card(token));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const card = await fetchCard(token);
  if (!card || !card.ok) {
    return {
      title: "PivoxQuant",
      robots: { index: false, follow: false },
    };
  }
  const title = `${card.owner_display_name}님의 투자 기록 · PivoxQuant`;
  const description = card.summary_safe;
  const images = card.card_image_url ? [{ url: card.card_image_url }] : [];
  return {
    title,
    description,
    alternates: { canonical: `/card/${token}` },
    openGraph: {
      title,
      description,
      type: "website",
      images,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: card.card_image_url ? [card.card_image_url] : undefined,
    },
  };
}

export default async function PublicCardPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const card = await fetchCard(token);

  if (!card || !card.ok) {
    return <PublicCardNotFound />;
  }

  return (
    <>
      <LandingViewTracker refCode={card.referral_code} channel="card_token" />
      <PublicCardView
        ownerDisplayName={card.owner_display_name}
        cardImageUrl={card.card_image_url}
        summarySafe={card.summary_safe}
        monthLabel={card.month_label}
        referralCode={card.referral_code}
      />
    </>
  );
}
