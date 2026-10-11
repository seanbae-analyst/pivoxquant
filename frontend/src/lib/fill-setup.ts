import type { PhoneKind } from "./phone";

/**
 * Which phone automation can carry a broker's fill notice to the import
 * webhook — onboarding (`/onboarding/fills`) and the settings token reveal.
 *
 * 2026-10-10 CEO: "증권사별로 아니면 폰 별로 해당 가능한 기능들 세팅하게끔".
 * Only what each broker's own pages say goes in here; everything else falls
 * to the generic "check your broker's alert settings" line.
 *
 *  - Android: MacroDroid reads any app's push or a KakaoTalk 알림톡, so every
 *    broker takes the same route.
 *  - iPhone, SMS: the Shortcuts Message trigger, any iOS version.
 *  - iPhone, app notification: the Shortcuts Notification trigger, iOS 27+
 *    (2026-09-14). Apple's list of automations that run without asking
 *    (support.apple.com/guide/shortcuts/apdfbdbd7123/10.0/ios/27) has Message
 *    but not Notification, and no broker's push wording has been checked
 *    against our parser — so this route is shown as a trial.
 */

export const FILL_BROKERS = ["toss", "kis", "kiwoom", "kb", "mirae", "samsung", "nh", "other"] as const;
export type FillBroker = (typeof FILL_BROKERS)[number];

export type IosRoute = "sms" | "app";
export type FillRoute = "android" | "ios-sms" | "ios-app";

/**
 * Brokers whose fill notice is an app push, with SMS only as a fallback.
 * 토스증권 국내주식 거래설명서 (2026-09-14): "주요내용 통지는 App Push로
 * 발송됩니다. ※ 단, App Push 알림이 불가할 경우 알림톡(카카오톡) > SMS 순".
 * The push comes from the Toss app (support.toss.im/faq/3335).
 */
const APP_PUSH_FIRST: ReadonlySet<FillBroker> = new Set<FillBroker>(["toss"]);

/**
 * Brokers with a sourced one-line hint (fillsOnboarding.hint.<id>):
 *  - toss — above.
 *  - kis — 한국투자 거래결과통보 안내: phone notice 발생 즉시, email 발생일 익일 오전.
 *  - kiwoom — 영웅문S# App Store listing: 알림은 SMS · 카카오톡 · PUSH.
 *  - kb — kbsec.com SMS 서비스: 주문체결통보 by SMS (무료) or PUSH.
 * Mirae / Samsung / NH / other: not confirmed → the generic hint.
 */
const HINTED: ReadonlySet<FillBroker> = new Set<FillBroker>(["toss", "kis", "kiwoom", "kb"]);

export function brokerHintKey(broker: FillBroker): string {
  return HINTED.has(broker) ? `fillsOnboarding.hint.${broker}` : "fillsOnboarding.hint.check";
}

/** The iPhone route to open first: app notification for push-first brokers, SMS otherwise. */
export function defaultIosRoute(broker: FillBroker | null): IosRoute {
  return broker !== null && APP_PUSH_FIRST.has(broker) ? "app" : "sms";
}

export function fillRoute(phone: PhoneKind, iosRoute: IosRoute): FillRoute {
  if (phone === "android") return "android";
  return iosRoute === "app" ? "ios-app" : "ios-sms";
}

const K = "settingsV2.importTokens";

export const ANDROID_STEP_KEYS = [1, 2, 3, 4, 5, 6, 7].map((n) => `${K}.android${n}`);
export const IOS_SMS_STEP_KEYS = [1, 2, 3, 4, 5, 6, 7].map((n) => `${K}.ios${n}`);
/** Steps 3, 4 and 7 (the web request and the reason-box link) are the SMS route's own. */
export const IOS_APP_STEP_KEYS = [
  `${K}.iosApp1`,
  `${K}.iosApp2`,
  `${K}.ios3`,
  `${K}.ios4`,
  `${K}.iosApp5`,
  `${K}.iosApp6`,
  `${K}.ios7`,
];

export function stepKeys(route: FillRoute): readonly string[] {
  if (route === "android") return ANDROID_STEP_KEYS;
  return route === "ios-app" ? IOS_APP_STEP_KEYS : IOS_SMS_STEP_KEYS;
}

export function kickerKey(route: FillRoute): string {
  if (route === "android") return `${K}.androidKicker`;
  return route === "ios-app" ? `${K}.iosAppKicker` : `${K}.iosKicker`;
}

/** One line on what this phone × route needs and whether it works today. */
export function statusKey(route: FillRoute): string {
  if (route === "android") return "fillsOnboarding.status.android";
  return route === "ios-app" ? "fillsOnboarding.status.iosApp" : "fillsOnboarding.status.iosSms";
}
