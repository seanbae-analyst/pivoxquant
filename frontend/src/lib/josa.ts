/**
 * 한국어 조사 고르기 — "섹터 분산이(가)" 처럼 괄호로 둘 다 적던 자리를
 * 앞 말의 받침에 맞는 하나로 바꾼다 (2026-10-22).
 *
 * 마지막 글자가 한글 음절이 아니면(영문·숫자·기호) 받침을 알 수 없어
 * 받침 없는 쪽을 쓴다 — "AAPL가" 보다 어색한 경우가 드물다.
 */

const HANGUL_FIRST = 0xac00;
const HANGUL_LAST = 0xd7a3;
const RIEUL_JONG = 8; // ㄹ 받침 (종성 인덱스)

function jong(word: string): number | null {
  const ch = word.trim().slice(-1);
  if (!ch) return null;
  const code = ch.charCodeAt(0);
  if (code < HANGUL_FIRST || code > HANGUL_LAST) return null;
  return (code - HANGUL_FIRST) % 28;
}

type Pair = "이/가" | "을/를" | "은/는" | "과/와" | "으로/로";

/** ``word`` + the particle that fits it: josa("섹터 분산", "이/가") → "섹터 분산이". */
export function josa(word: string, pair: Pair): string {
  const j = jong(word);
  const [withJong, withoutJong] = pair.split("/");
  if (pair === "으로/로") {
    // ㄹ 받침은 "로": 거울로, 연필로.
    return word + (j !== null && j !== 0 && j !== RIEUL_JONG ? withJong : withoutJong);
  }
  return word + (j !== null && j !== 0 ? withJong : withoutJong);
}
