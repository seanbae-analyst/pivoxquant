/**
 * PivoxQuant 로고 글자 — "Pivox" 는 주변 글자색(아이보리), "Quant" 는 브론즈.
 * PivoxMap · PivoxData 와 한 가족의 규칙이다 (2026-10-25). 크기 · 굵기는 쓰는 쪽이 정한다.
 * `upper` 는 표지의 대문자 워드마크(PIVOXQUANT) — textContent 가 대문자여야 하는 테스트가 있다.
 */
export function QuantMark({ upper = false }: { upper?: boolean }) {
  return (
    <>
      {upper ? "PIVOX" : "Pivox"}
      <span style={{ color: "var(--pq-bronze)" }}>{upper ? "QUANT" : "Quant"}</span>
    </>
  );
}
