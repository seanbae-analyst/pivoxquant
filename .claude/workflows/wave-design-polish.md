---
name: wave-design-polish
description: 디자인 품질 wave — 시각/모션/브랜드보이스 병렬 점검
---

# wave-design-polish

## 목적
PivoxQuant 디자인 시스템 v3 기준 시각 일관성, 모션 스펙, 카피 톤앤매너 동시 점검.

## 실행 방법

```
3개의 Task를 동시에 띄우세요:

Task 1 — 시각 디자인 점검:
  agent: verify-design
  prompt: "~/dev/pivoxquant/frontend/src/components/ 전체를 디자인 시스템 v3 기준으로
           점검하세요.
           - raw hex (#XXXXXX) 직접 사용 → var(--token) 교체 필요 목록
           - 라임 색상 잔존 여부
           - KR 색상(▲carmine/▼indigo) 미적용 컴포넌트
           - 여백/타이포 토큰 이탈 (px 직접 지정 등)
           P0(시각 버그)/P1(토큰 이탈)/P2(개선 권고) 분류."

Task 2 — 모션 스펙 점검:
  agent: motion-designer
  prompt: "~/dev/pivoxquant/frontend/src/ 에서 transition/animation/motion 관련 코드 전수 스캔.
           - 금지 패턴(bounce/infinite spin/장식 모션) 탐지
           - duration 토큰 이탈 (임의 ms 값)
           - easing 토큰 이탈
           - 금융 앱 기준 불필요 모션 과다 여부
           수정 필요 파일·라인 목록."

Task 3 — 브랜드 보이스 점검:
  agent: brand-voice
  prompt: "~/dev/pivoxquant/frontend/src/ 의 UI 문자열(버튼/레이블/빈 상태/에러 메시지)을
           PivoxQuant 톤앤매너 기준으로 점검하세요.
           - 'stockpilot' 잔존 여부 (브랜드 오염)
           - 지나치게 캐주얼하거나 모호한 금융 표현
           - 한글/영문 혼용 일관성
           - 면책 문구 누락 위치
           수정 제안 목록."

Task 4 (완료 후) — 시각 통합 fix 우선순위:
  agent: design
  prompt: "verify-design + motion-designer + brand-voice 결과 종합.
           P0만 즉시 fix 목록으로 추출. P1은 다음 wave로 예약.
           design-token-drift CI 게이트 추가 필요 여부 판단."
```

## 예상 소요
- Task 1-3 병렬: ~15분
- Task 4: ~5분

## 완료 기준
- P0 시각 버그 0건
- raw hex / 라임 / naked ticker 회귀 0
- vitest / tsc clean
