/**
 * /card/[token] — retired public brag-card landing.
 *
 * Kept as a static route on purpose: the tokens were minted into links that
 * other people still hold. See <RetiredLinkNotice /> for why this does not
 * fetch, does not 404, and does not blame expiry.
 *
 * noindex: there is nothing here worth a search result, and the old pages
 * should fall out of the index rather than rank on a dead surface.
 */
import type { Metadata } from "next";

import { RetiredLinkNotice } from "@/components/share/retired-link-notice";

export const metadata: Metadata = {
  title: "PivoxQuant",
  description: "이 공유 링크는 더 이상 열람할 수 없습니다.",
  robots: { index: false, follow: false },
  openGraph: {
    title: "PivoxQuant",
    description: "이 공유 링크는 더 이상 열람할 수 없습니다.",
    type: "website",
  },
  twitter: { card: "summary", title: "PivoxQuant" },
};

export default function RetiredCardPage() {
  return <RetiredLinkNotice />;
}
