export type PhoneKind = "android" | "ios";

/**
 * Which phone setup guide to open first — a best guess from the user agent
 * (the user can switch). Anything that is not an iPhone/iPad gets Android:
 * desktop users are setting up whichever phone they hold, and Android's
 * guide is the one that covers app pushes too.
 */
export function detectPhone(ua: string): PhoneKind {
  return /iPhone|iPad|iPod/i.test(ua) ? "ios" : "android";
}
