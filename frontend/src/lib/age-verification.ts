/**
 * lib/age-verification.ts — PIPA §22 ⑥ defense-in-depth helper.
 *
 * 개인정보 보호법 §22 ⑥ — 만 14세 미만 아동의 개인정보 수집 시 법정대리인의
 * 동의를 받아야 함. PivoxQuant 출시 시점에는 법정대리인 동의 절차가
 * 구축되어 있지 않으므로 만 14세 미만은 회원가입을 fail-fast 한다.
 *
 * 본 헬퍼는 회원가입 컴포넌트(legal-consent-modal / signup _v1 / _v2) 가
 * 동일한 만나이 계산 로직을 공유하기 위함이다.
 */

export const MIN_AGE_YEARS = 14;

export const BIRTHDATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Returns true when `birthdate` (yyyy-mm-dd) parses as a real date.
 * Empty string returns false; future dates return false.
 */
export function isValidBirthdate(birthdate: string): boolean {
  if (!BIRTHDATE_REGEX.test(birthdate)) return false;
  const [yStr, mStr, dStr] = birthdate.split("-");
  const y = Number(yStr);
  const m = Number(mStr);
  const d = Number(dStr);
  if (Number.isNaN(y) || Number.isNaN(m) || Number.isNaN(d)) return false;
  if (m < 1 || m > 12) return false;
  if (d < 1 || d > 31) return false;
  // Reject future dates and obviously invalid years (< 1900).
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (
    dt.getUTCFullYear() !== y ||
    dt.getUTCMonth() !== m - 1 ||
    dt.getUTCDate() !== d
  ) {
    return false;
  }
  if (y < 1900) return false;
  if (dt.getTime() > Date.now()) return false;
  return true;
}

/**
 * Computes the age in completed years given a `yyyy-mm-dd` birthdate.
 * Returns -1 when the birthdate is invalid (caller treats as "not eligible").
 *
 * `now` is injectable so tests can pin the clock.
 */
export function computeAgeYears(birthdate: string, now: Date = new Date()): number {
  if (!isValidBirthdate(birthdate)) return -1;
  const [yStr, mStr, dStr] = birthdate.split("-");
  const y = Number(yStr);
  const m = Number(mStr);
  const d = Number(dStr);
  let age = now.getFullYear() - y;
  const beforeBirthdayThisYear =
    now.getMonth() + 1 < m ||
    (now.getMonth() + 1 === m && now.getDate() < d);
  if (beforeBirthdayThisYear) age -= 1;
  return age;
}

export function isAtLeastMinAge(birthdate: string, now: Date = new Date()): boolean {
  return computeAgeYears(birthdate, now) >= MIN_AGE_YEARS;
}

export const UNDER_AGE_KO =
  "만 14세 미만은 법정대리인 동의가 필요합니다. 출시 후 별도 절차로 안내드립니다.";
export const UNDER_AGE_EN =
  "Users under 14 require legal guardian consent. We will reach out after launch with a dedicated flow.";
export const BIRTHDATE_LABEL_KO = "생년월일 (PIPA §22 ⑥)";
export const BIRTHDATE_LABEL_EN = "Date of birth";
