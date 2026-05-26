/**
 * Kakao JS SDK loader + share helper (free tier — no paid service).
 *
 * The SDK is loaded lazily from the CDN only when a Kakao share is first
 * attempted, and only when `NEXT_PUBLIC_KAKAO_KEY` is configured. When the
 * key is absent (e.g. local dev or before the CEO provisions a Kakao
 * developer app) `isKakaoAvailable()` returns false and the caller hides the
 * Kakao button entirely — nothing throws, the build is unaffected.
 *
 * CEO ACTION TODO: create a Kakao Developers application (free) and set
 *   NEXT_PUBLIC_KAKAO_KEY = <JavaScript key>
 * in Vercel env. Register the production domain (pivoxquant.com) under the
 * app's "Web platform" + "Kakao Link" allowed domains. Until then the
 * Kakao share button is gracefully hidden.
 */

const KAKAO_SDK_SRC =
  "https://t1.kakaocdn.net/kakao_js_sdk/2.7.2/kakao.min.js";
const KAKAO_SDK_INTEGRITY =
  "sha384-TiCUE00h649CAMonG018J2ujOgDKW/kVWlChEuu4jK2vxfAAD0eZxzCKakxg55G4";

interface KakaoShareLink {
  webUrl: string;
  mobileWebUrl: string;
}

interface KakaoFeedTemplate {
  objectType: "feed";
  content: {
    title: string;
    description: string;
    imageUrl: string;
    link: KakaoShareLink;
  };
  buttons?: { title: string; link: KakaoShareLink }[];
}

interface KakaoSDK {
  isInitialized: () => boolean;
  init: (key: string) => void;
  Share: {
    sendDefault: (settings: KakaoFeedTemplate) => void;
  };
}

declare global {
  interface Window {
    Kakao?: KakaoSDK;
  }
}

/** True when a Kakao JS key is configured at build time. */
export function isKakaoAvailable(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_KAKAO_KEY);
}

let loadPromise: Promise<KakaoSDK | null> | null = null;

/**
 * Load + initialise the Kakao SDK once. Resolves to the initialised SDK or
 * null when the key is missing / the script fails to load. Never rejects.
 */
function loadKakao(): Promise<KakaoSDK | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  const key = process.env.NEXT_PUBLIC_KAKAO_KEY;
  if (!key) return Promise.resolve(null);

  if (loadPromise) return loadPromise;

  loadPromise = new Promise<KakaoSDK | null>((resolve) => {
    const finishInit = () => {
      const sdk = window.Kakao;
      if (!sdk) {
        resolve(null);
        return;
      }
      try {
        if (!sdk.isInitialized()) sdk.init(key);
        resolve(sdk);
      } catch {
        resolve(null);
      }
    };

    if (window.Kakao) {
      finishInit();
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${KAKAO_SDK_SRC}"]`,
    );
    if (existing) {
      existing.addEventListener("load", finishInit, { once: true });
      existing.addEventListener("error", () => resolve(null), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = KAKAO_SDK_SRC;
    script.async = true;
    script.integrity = KAKAO_SDK_INTEGRITY;
    script.crossOrigin = "anonymous";
    script.addEventListener("load", finishInit, { once: true });
    script.addEventListener("error", () => resolve(null), { once: true });
    document.head.appendChild(script);
  });

  return loadPromise;
}

/**
 * Open the Kakao share sheet for a brag card. Returns true when the share
 * was dispatched, false when Kakao is unavailable (caller should fall back).
 * Never throws.
 */
export async function shareToKakao(args: {
  title: string;
  description: string;
  imageUrl: string;
  linkUrl: string;
}): Promise<boolean> {
  const sdk = await loadKakao();
  if (!sdk) return false;
  const link: KakaoShareLink = {
    webUrl: args.linkUrl,
    mobileWebUrl: args.linkUrl,
  };
  try {
    sdk.Share.sendDefault({
      objectType: "feed",
      content: {
        title: args.title,
        description: args.description,
        imageUrl: args.imageUrl,
        link,
      },
      buttons: [{ title: "카드 보러가기", link }],
    });
    return true;
  } catch {
    return false;
  }
}
