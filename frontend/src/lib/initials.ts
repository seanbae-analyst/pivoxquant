/**
 * Avatar initials: at most two characters, upper-cased — except a 2–3
 * syllable Korean name, which is shown whole ("배상현").
 *
 * Multi-word Latin names take one letter per word ("Sean Bae" → "SB").
 * Single-token names — Korean names ("배상현"), the guest label ("게스트") —
 * used to collapse to a single character because the word split found only
 * one word; they now take their first two characters instead. Korean names of
 * 2–3 syllables are shown whole ("배상현", "게스트").
 * Falls back to the e-mail's first two characters, then to "PQ".
 */
const HANGUL_NAME = /^[\uAC00-\uD7A3]{2,3}$/;

export function initials(name?: string | null, email?: string | null): string {
  const trimmed = name?.trim();
  // A Korean name of two or three syllables is shown whole — "배상현", not
  // "배상" (CEO 2026-10-22). Cutting a 3-syllable name to its first two
  // leaves the family name plus half the given name.
  if (trimmed && HANGUL_NAME.test(trimmed)) return trimmed;
  if (trimmed) {
    const fromWords = trimmed
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("");
    const picked = fromWords.length >= 2 ? fromWords : trimmed.replace(/\s+/g, "");
    return picked.slice(0, 2).toUpperCase();
  }
  const mail = email?.trim();
  if (mail) return mail.slice(0, 2).toUpperCase();
  return "PQ";
}
