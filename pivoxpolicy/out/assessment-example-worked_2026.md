# 내부통제 평가 프로필 — 예시은행(가상) (2026)

평가자 `example` · provisional (잠정)

레벨은 **신호에서 도출**된다(직접 고르지 않음). 0 증거없음 · 1 언급 · 2 구체 · 3 검증 · `?` 미평가.
**레벨은 '공개 증거 수준' 이지 '통제 유무' 가 아니다.**

코딩된 15 차원 중 — 검증(3) **1** · 증거없음(0) **4** · 미평가 1

| 그룹 | # | 차원 | 레벨 | 발화 신호 (증거부족=↓) |
|---|---|---|---|---|
| agent_control | 1 | 에이전트 인벤토리 | **1** | mentions_ai_governance |
| agent_control | 2 | 공급자·제3자 AI | **0** |  |
| agent_control | 3 | 고유 식별자 | **0** |  |
| agent_control | 4 | 최소 권한 | **1** | mentions_least_privilege |
| agent_control | 5 | 사람 승인 | **2** | mentions_human_in_loop, specifies_risk_based_approval |
| agent_control | 6 | 감사 기록 | **1** | mentions_logging |
| agent_control | 7 | 즉시 중단 | **0** |  |
| connection | 8 | 경고 수신·전달 | **2** | acknowledged_warning, relayed_to_action |
| connection | 9 | 보고·에스컬레이션 | **?** |  |
| testing | 10 | 테스트 빈도 | **2** | mentions_periodic_test, discloses_cadence |
| testing | 11 | 테스트 범위 | **1** | mentions_core_scope; ↓includes_external_touchpoints |
| testing | 12 | 사후조치 | **1** | mentions_remediation_plan |
| testing | 13 | AI 활용·공동훈련 | **0** |  |
| response | 14 | 탐지 소요시간 | **3** | mentions_monitoring, discloses_detection_time, verified_fast_detection |
| response | 15 | 공개·신고 | **2** | mentions_notification, specifies_disclosure_timing |
| response | 16 | 재발방지 | **1** | mentions_prevention |

## 그룹별 분포

- **agent_control**: L2 1 · L1 3 · L0 3
- **connection**: L2 1 · Lunknown 1
- **testing**: L2 1 · L1 2 · L0 1
- **response**: L3 1 · L2 1 · L1 1

`↓` = 신호를 관찰했으나(observed:true) 증거가 약해(보도 등) 그 레벨로 발화하지 못함.

