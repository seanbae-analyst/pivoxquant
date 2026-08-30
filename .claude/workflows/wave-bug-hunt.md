---
name: wave-bug-hunt
description: 버그헌팅 wave — bug-hunter 3도메인 병렬 + audit-code 크로스체크
---

# wave-bug-hunt

## 목적
PivoxQuant 코드베이스를 도메인별로 병렬 헌팅한 뒤 audit-code로 교차 검수.

## 실행 방법 (Claude Code에서 직접 호출)

```
3개의 Task를 동시에 띄우세요:

Task 1 — 백엔드 버그헌팅:
  agent: bug-hunter
  prompt: " 디렉토리 전체를 헌팅하세요.
           집중 도메인: 퀀트 수식(Sharpe/Sortino/FX), 보안(auth/tier bypass),
           법규(§101/PIPA). P0/P1/P2 분류해 보고."

Task 2 — 프론트엔드 버그헌팅:
  agent: bug-hunter
  prompt: "frontend/src/ 전체를 헌팅하세요.
           집중 도메인: SWR 캐시 누수, 티커 표시(naked ticker), 색상 반전,
           모바일 safe-area. P0/P1/P2 분류해 보고."

Task 3 — 데이터/API 검증:
  agent: verify-data
  prompt: "services/ 의 데이터 파이프라인을 검증하세요.
           FX 변환 일관성, 퀀트 수식 입력값 null 처리, 캐시 cross-user 누수."

Task 4 (Task 1-3 완료 후) — 교차 감사:
  agent: qa
  prompt: "bug-hunter 3개 결과를 종합해 중복 제거하고 우선순위 최종 확정.
           P0(SHIP-BLOCKER)만 즉시 fix 목록으로 추출."
```

## 예상 소요
- Task 1-3 병렬: ~15분
- Task 4 감사: ~5분

## 완료 기준
- P0 목록 확정 + fix 커밋 또는 DEFERRED 사유 명시
- pytest / vitest 회귀 0
