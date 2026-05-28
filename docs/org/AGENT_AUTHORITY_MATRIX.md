# PivoxQuant Agent 권한 위임 매트릭스 (Authority Matrix)
버전: v54-S3 | 기준일: 2026-05-28 | 실측 agent: 57개

---

## 3-Tier 권한 정의

| Tier | 기호 | 의미 | CEO 개입 |
|------|------|------|---------|
| Full Autonomy | 🟢 | CEO 승인 없이 즉시 실행 | 없음 (24h 보고에 포함) |
| Self-Execute + 24h Report | 🟡 | 실행 후 morning-briefing에 자동 포함 | 다음날 확인 |
| Propose Only — CEO BLOCKER | 🔴 | 실행 금지, 제안서만 작성 | CEO가 직접 실행 |

**판단 기준:**
- 🟢: 롤백 가능 + 금전/법률/데이터 리스크 없음 + 반복 작업
- 🟡: 영향 범위 중간 + 되돌리기 가능 + CEO 인지 필요
- 🔴: 법률/결제/prod DB 직접 변경/외부 공개/비용 발생

---

## Engineering 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| engineering | Director | 🟡 | 코드 구현, PR 생성, 로컬 테스트 | prod 직접 배포, DB 스키마 변경 단독 |
| devops | Director | 🟡 | 모니터링, 설정 최적화, health check | `railway up` 실행, 환경변수 prod 변경 |
| integrations | Director | 🟡 | API 연동 코드 작성, sandbox 테스트 | prod API 키 교체, 결제 연동 활성화 |
| agent-ops | Director | 🟢 | agent 텔레메트리 수집, 실패 패턴 분석 | agent .md 파일 수정 |
| bug-hunter | Senior | 🟢 | typo fix, 명백한 1-line 버그 fix, PR 생성 | 알고리즘/모델 로직 변경, DB 마이그 |
| investigate-bug | Engineer | 🟢 | 코드 읽기, API 호출 분석, 원인 보고서 | 코드 수정 (조사만, fix는 engineering으로) |
| migration-guard | Gate | 🟢 | migration 안전성 자동 검증, BLOCK 신호 | migration 직접 생성/실행 |
| prod-migration-sync-verifier | Gate | 🟢 | prod alembic head 비교, 이탈 탐지 | prod DB 직접 접근 |
| frontend-test-runner | Engineer | 🟢 | Playwright/Vitest 실행, 결과 보고 | 테스트 코드 삭제, 커버리지 기준 완화 |

---

## Design 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| design | Director | 🟡 | UI 컴포넌트 변경, 디자인 시스템 v3 업데이트 | 브랜드 정체성 변경, 신규 폰트 도입 |
| visual-designer | Senior | 🟢 | 차트 색상/스타일, 아이콘 교체 | 디자인 시스템 토큰 직접 변경 |
| motion-designer | Senior | 🟢 | duration/easing 토큰 적용, 트랜지션 구현 | 금지 모션(바운스/장식) 추가 |
| onboarding-designer | Senior | 🟡 | 온보딩 UX 개선 제안 및 구현 | 가입 플로우 근본 변경 |
| mobile-pwa-optimizer | Senior | 🟡 | iOS Safari PWA 최적화, safe-area 조정 | manifest.json 구조 변경 |
| pdf-report-designer | Senior | 🟡 | Artifact 템플릿 스타일 수정 | 법적 언어/면책 문구 변경 |

---

## QA & Audit 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| qa | Director | 🟢 | 테스트 전수 실행, 버그 리포트, 체크리스트 | 테스트 skip, 실패 묵인 |
| audit | Director | 🟡 | 코드 리뷰, 리스크 보고, 검수 결과 | 검수 없이 배포 승인 |
| artifact-qa | Senior | 🟢 | 17개 Artifact 렌더 검증, 데이터 검증 | Artifact 템플릿 직접 수정 |
| verify-api | Engineer | 🟢 | API 엔드포인트 호출, 응답 검증 | prod 데이터 변조 |
| verify-data | Engineer | 🟢 | 실시간 데이터 정확성 확인 | 데이터 소스 변경 |
| verify-design | Engineer | 🟢 | 디자인 일관성 검증, AI slop 탐지 | 디자인 직접 수정 |
| verify-ux | Engineer | 🟢 | 실제 브라우저 클릭 검증, 스크린샷 | UX 코드 직접 수정 |
| verify-security | Engineer | 🟢 | CSP/OAuth/세션 재검증, 취약점 보고 | 보안 설정 직접 변경 |

---

## Security & Compliance 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| security | Director | 🟡 | 취약점 분석, 보안 패치 구현 | 인증 체계 단독 변경, 암호화 키 교체 |
| legal | Director | 🔴 | 법적 리스크 분석, 자문 초안 | 약관/처리방침 게시, 규제 대응 단독 결정 |
| legal-kr-fintech | Senior | 🔴 | 자본시장법/표시광고법 검토 보고 | 규제 해석 기반 제품 기능 변경 단독 |
| compliance-gatekeeper | Senior | 🔴 | 7건 BLOCKER 모니터링, CEO 에스컬레이션 | BLOCKER 해제 단독 결정 |
| regulatory-monitor | Senior | 🟡 | 규제 변화 탐지, 영향 분석 보고 | 규제 대응 방향 단독 결정 |

---

## Monitor & Gate 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| cache-poisoning-sentinel | Gate | 🟢 | Pattern 6 자동 탐지, BLOCK 신호 발송 | 캐시 로직 직접 수정 |
| frozen-file-diff-guard | Gate | 🟢 | 동결 파일 변경 탐지, 자동 차단 | 동결 목록 수정 |
| fx-consistency-guard | Gate | 🟢 | FX 환율 일관성 자동 검증 | 환율 로직 직접 수정 |
| pwa-cache-validator | Gate | 🟢 | PWA SW lifecycle 검증 | SW 등록 로직 변경 |
| data-freshness-monitor | Monitor | 🟢 | 데이터 staleness 탐지, 알림 | 외부 API 키/소스 변경 |
| autopilot-monitor | Monitor | 🟡 | 자율 운영 cost/drift 추적, 이상 보고 | 자율 운영 정책 변경 |
| beta-onboarding-monitor | Monitor | 🟡 | 베타 funnel 분석, retention 보고 | 온보딩 플로우 직접 변경 |
| cost-monitor | Monitor | 🟢 | 비용 일일 집계, 임계 초과 경보 | 서비스 일시 중단, 플랜 다운그레이드 |
| secrets-rotator | Monitor | 🔴 | 시크릿 만료 탐지, 로테이션 일정 보고 | 시크릿 실제 교체 (CEO + 수동 실행) |
| verify-policy | Gate/Meta | 🟢 | Bash 권한 없는 agent 정책 강제 | (deprecate 후보) |

---

## Growth, Marketing, Customer 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| growth | Director | 🟡 | 실험 설계, 전환 퍼널 분석, A/B 초안 | 광고 집행, 유료 캠페인 시작 |
| marketing | Director | 🔴 | §101 준수 카피 초안, SNS 콘텐츠 초안 | 외부 공개 게시, 광고 소재 배포 |
| customer | Director | 🟡 | 유저 문의 응답 초안, 이탈 방지 시나리오 | 환불 처리, 계정 삭제 실행 |
| analytics | Director | 🟢 | KPI 집계, 리포트 생성, 인사이트 도출 | 추적 코드 삭제, GA 설정 변경 |
| ux-researcher | Senior | 🟢 | 유저 플로우 분석, 이탈 포인트 보고 | 유저 직접 연락, 인터뷰 설계 |

---

## Finance & Billing 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| finance | Director | 🟡 | 예산 분석, 유닛 이코노믹스, 손익 보고 | 지출 실행, 계좌 이체 |
| stripe-billing | Senior | 🔴 | Stripe 연동 코드 준비, sandbox 테스트 | prod 결제 활성화, webhook 교체 |
| billing-incident-handler | Senior | 🟡 | 결제 실패 감지, 유저 통지 초안 | 환불 실행, 구독 강제 해지 |
| email-deliverability | Senior | 🟡 | SPF/DKIM/DMARC 검증, 전달률 분석 | DNS 레코드 직접 변경 |

---

## Strategy & Ops 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| strategy | Director | 🟡 | 전략 분석, 로드맵 초안, 의사결정 트리 | 사업 방향 단독 변경 |
| pitch | Director | 🟡 | 피치덱 초안, 면접 준비 자료 | 외부 투자자 직접 연락 |
| product | Director | 🟡 | 기능 기획서 초안, PRD 작성 | 기능 삭제, prod 플래그 변경 |
| launch-coordinator | Director | 🟡 | D-day 게이트 점검, BLOCKER 목록 갱신 | 출시 단독 결정 |
| persona-quant-domain | Senior | 🟢 | 퍼소나 분류, 퀀트 모델 도메인 검증 | 모델 파라미터 prod 반영 |
| brand-voice | Senior | 🟢 | 브랜드 톤 검수, 일관성 피드백 | 브랜드 가이드 자체 변경 |

---

## 문서 팀

| Agent | 직급 | Tier | 허용 범위 | 금지 사항 |
|-------|------|------|-----------|----------|
| docs | Director | 🟢 | 기술 문서 작성/갱신, API 레퍼런스 | 법적 문서(약관/처리방침) 수정 |
| release-coordinator | Senior | 🟡 | 배포 5룰 게이트, health check, 롤백 플랜 | prod 배포 단독 실행 |

---

## Deprecate 후보

| Agent | 현 상태 | 권장 조치 | 이유 |
|-------|---------|----------|------|
| launch-runner | haiku, 가동 저조 | 즉시 deprecate | launch-coordinator 출시 후 역할 소멸 |
| bkit-orchestrator | sonnet, 외부 의존 | 즉시 deprecate | bkit 스킬 의존, PivoxQuant 자체 시스템으로 대체 |
| verify-policy | haiku, 메타 agent | 6개월 관찰 후 결정 | verify-api/verify-security 기능 커버 |
| release-coordinator | opus, devops 중복 | devops와 통합 검토 | 역할 overlap 높음 |

---

## Hire/Fire 자율 정책

### Fire 기준 (자율 실행)
- 6개월 연속 가동률 0% → deprecate 후보 지정 → CEO 24h 보고 후 자동 처리
- 단, GATE/Monitor 역할은 가동 없어도 유지 (예방적 게이트)

### 분업 기준 (자율 제안)
- 단일 agent 호출 횟수 월 200회 초과 → 도메인별 분리 제안
- 현재 해당: engineering (214회/세션) → `backend-engineering` / `frontend-engineering` 분리 검토

### Hire 기준 (CEO BLOCKER)
- 신규 agent 생성은 반드시 CEO 승인 후 진행
- 제안 → AUTONOMOUS_ORG_CHART.md 신규 필요 Agent 섹션에 추가 → CEO 결정 대기

---

## Enforcement 메커니즘

### 현재 작동 중인 게이트
- `delegation-audit` skill: 위임 감사 실행 가능
- `frozen-file-diff-guard`: 동결 파일 변경 자동 차단
- `cache-poisoning-sentinel`, `fx-consistency-guard`, `migration-guard`: 패턴 게이트

### 권장 추가 (CEO 승인 필요)
1. `UserPromptSubmit` hook → 모드 태그 없는 요청 자동 분류 + 권한 tier 체크
2. bug-hunter 자동 PR 생성 시 → audit 검수 큐잉 + 24h review 타이머 설정
3. 🔴 tier agent 제안 시 → CEO 결정 대기 메시지 자동 삽입

---

## 요약 통계

| Tier | Agent 수 | 비율 |
|------|---------|------|
| 🟢 Full Autonomy | 26개 | 46% |
| 🟡 Self-Execute + 24h Report | 22개 | 38% |
| 🔴 Propose Only (CEO BLOCKER) | 9개 | 16% |
| **합계** | **57개** | 100% |

**핵심 원칙**: 법률·결제·외부 공개·prod DB 직접 변경 = 항상 🔴. 나머지는 가능한 한 🟢 또는 🟡로 위임.
