/**
 * /r/[code] — retired referral landing.
 *
 * Same reasoning as /card/[token]: the codes are already out there, referral
 * attribution went with the growth backend, and a 404 on a shared link is the
 * worse of the two failures.
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

export default function RetiredReferralPage() {
  return <RetiredLinkNotice />;
}
