/**
 * 섹터 이름 → 한국어 표시 (2026-10-22).
 *
 * 섹터는 시세 벤더가 영문으로 준다 ("Technology", "Consumer Cyclical" …).
 * 한국어 화면에 영문 대문자 칩으로 박혀 있던 것을 표시할 때만 옮긴다 —
 * 저장 값과 정렬 키는 그대로다. 같은 섹터의 두 표기(GICS "Consumer
 * Discretionary" / FMP "Consumer Cyclical")는 한 이름으로 모인다.
 * 모르는 이름은 받은 그대로 둔다.
 */

const KO: Record<string, string> = {
  "technology": "기술",
  "information technology": "기술",
  "consumer cyclical": "경기소비재",
  "consumer discretionary": "경기소비재",
  "consumer defensive": "필수소비재",
  "consumer staples": "필수소비재",
  "financial services": "금융",
  "financials": "금융",
  "financial": "금융",
  "healthcare": "헬스케어",
  "health care": "헬스케어",
  "communication services": "커뮤니케이션",
  "industrials": "산업재",
  "energy": "에너지",
  "basic materials": "소재",
  "materials": "소재",
  "real estate": "부동산",
  "utilities": "유틸리티",
};

export function sectorLabel(name: string | null | undefined): string {
  if (!name) return "";
  return KO[name.trim().toLowerCase()] ?? name;
}
