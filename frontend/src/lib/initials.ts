/**
 * Avatar initials: at most two characters, upper-cased.
 *
 * Multi-word Latin names take one letter per word ("Sean Bae" → "SB").
 * Single-token names — Korean names ("배상현"), the guest label ("게스트") —
 * used to collapse to a single character because the word split found only
 * one word; they now take their first two characters instead ("배상", "게스").
 * Falls back to the e-mail's first two characters, then to "PQ".
 */
export function initials(name?: string | null, email?: string | null): string {
  const trimmed = name?.trim();
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
