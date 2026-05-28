# PivoxQuant 자율 조직도 (Autonomous Org Chart)
버전: v54-S3 | 기준일: 2026-05-28 | 실측 agent: 57개

---

## 조직 철학

"내 명령 없이 굴러가는 시스템." — CEO 배상현

- AI 에이전트 57개가 22개 부서를 자율 운영
- CEO는 BLOCKER(빨간 선) 결정만, 나머지는 위임
- 보고 주기: 24h morning-briefing (자동 큐잉)

---

## 계층 구조

```
CEO (배상현) — 사람, BLOCKER 결정만
│
└── C-Suite: Claude Code 본체 (orchestration, 라우팅, context 관리)
    │
    ├── VP Engineering
    │   ├── engineering          [Director, opus]
    │   ├── devops               [Director, opus]
    │   ├── integrations         [Director, opus]
    │   └── agent-ops            [Director, sonnet]  ← 에이전트 텔레메트리
    │
    ├── VP Product & Design
    │   ├── product              [Director, opus]
    │   ├── design               [Director, opus]
    │   └── docs                 [Director, sonnet]
    │
    ├── VP QA & Security
    │   ├── qa                   [Director, opus]
    │   ├── security             [Director, opus]
    │   └── audit                [Director, opus]
    │
    ├── VP Legal & Compliance
    │   ├── legal                [Director, opus]
    │   ├── legal-kr-fintech     [Senior, sonnet]
    │   ├── compliance-gatekeeper[Senior, sonnet]
    │   └── regulatory-monitor   [Senior, opus]
    │
    ├── VP Growth & Marketing
    │   ├── growth               [Director, opus]
    │   ├── marketing            [Director, opus]
    │   ├── customer             [Director, opus]
    │   └── analytics            [Director, opus]
    │
    ├── VP Finance & Billing
    │   ├── finance              [Director, opus]
    │   ├── stripe-billing       [Senior, opus]
    │   └── billing-incident-handler [Senior, opus]
    │
    └── VP Strategy & Ops
        ├── strategy             [Director, opus]
        ├── pitch                [Director, opus]
        └── launch-coordinator   [Director, opus]
```

---

## 부서별 팀 상세 (57 agents)

### Engineering 팀 (9명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| engineering | VP/Director | opus | Staff Engineer 수준 코드품질, 시스템 설계 |
| devops | VP/Director | opus | Netflix SRE 수준 인프라 안정성, 배포 |
| integrations | VP/Director | opus | 외부 API 연동, 데이터 파이프라인 |
| agent-ops | Director | sonnet | 57개 agent 텔레메트리, failure 탐지 |
| bug-hunter | Senior Engineer | sonnet | 능동적 버그 사냥, 즉시 fix |
| investigate-bug | Engineer | sonnet | 버그 근본 원인 100% 확정 조사 |
| migration-guard | Gate | opus | DB 스키마/Alembic 안전성 전담 |
| prod-migration-sync-verifier | Gate | sonnet | Railway prod alembic divergence 검증 |
| frontend-test-runner | Engineer | sonnet | Playwright/Vitest 자동 테스트 실행 |

### Design 팀 (6명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| design | VP/Director | opus | Apple HIG + Bloomberg Terminal, 디자인 시스템 v3 |
| visual-designer | Senior | sonnet | 차트/아이콘/브랜드 비주얼 |
| motion-designer | Senior | sonnet | duration/easing 토큰 enforcement |
| onboarding-designer | Senior | sonnet | 첫 화면/empty-state/온보딩 UX |
| mobile-pwa-optimizer | Senior | opus | iOS Safari PWA 최적화 |
| pdf-report-designer | Senior | opus | 17개 Artifact Jinja2 템플릿 |

### QA & Audit 팀 (8명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| qa | VP/Director | opus | NASA JPL 수준 테스팅, 결함 제로 |
| audit | VP/Director | opus | Goldman Sachs 수준 리스크 관리, 검수 |
| artifact-qa | Senior | opus | 17개 PDF/이메일 Artifact 전수 렌더 검증 |
| verify-api | Engineer | sonnet | 백엔드 API 실제 호출 검증 |
| verify-data | Engineer | sonnet | 실시간 가격/환율 데이터 정확성 |
| verify-design | Engineer | sonnet | 디자인 일관성, AI slop 탐지 |
| verify-ux | Engineer | sonnet | 실제 브라우저 클릭 동작 확인 |
| verify-security | Engineer | sonnet | CSP/OAuth/세션/CSRF 재검증 |

### Security & Compliance 팀 (6명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| security | VP/Director | opus | NSA Red Team 수준 보안 감사 |
| legal | VP/Director | opus | Kim & Chang 수준 금융 규제 |
| legal-kr-fintech | Senior | sonnet | 자본시장법/표시광고법 검수 |
| compliance-gatekeeper | Senior | sonnet | 7건 BLOCKER 일일 dashboard |
| regulatory-monitor | Senior | opus | 금융 규제 변화 일일 모니터링 |
| verify-security | Engineer | sonnet | (Engineering과 겸임) 보안 검증 |

### Monitor & Gate 팀 (10명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| cache-poisoning-sentinel | Gate | opus | Pattern 6 cross-user PII leak 자동 게이트 |
| frozen-file-diff-guard | Gate | opus | Iron Rule 동결 파일 변경 차단 |
| fx-consistency-guard | Gate | opus | Pattern 7 FX 환율 일관성 게이트 |
| pwa-cache-validator | Gate | sonnet | PWA SW lifecycle 회귀 검증 |
| data-freshness-monitor | Monitor | sonnet | 외부 데이터 staleness + budget burn |
| autopilot-monitor | Monitor | sonnet | 자율 운영 Layer A/B/C cost/drift 추적 |
| beta-onboarding-monitor | Monitor | opus | 첫 100명 베타 activation funnel 모니터 |
| cost-monitor | Monitor | sonnet | 인프라 비용 일일 추적 |
| secrets-rotator | Monitor | sonnet | 시크릿 로테이션 자동화 |
| verify-policy | Gate/Meta | haiku | Bash 권한 없는 agent 정책 강제 |

### Growth, Marketing, Customer 팀 (5명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| growth | VP/Director | opus | 실험 설계, 전환 최적화 |
| marketing | VP/Director | opus | Ogilvy 수준 카피, §101 면제 트랙 준수 |
| customer | VP/Director | opus | Zappos 수준 고객 경험, 온보딩 |
| analytics | VP/Director | opus | KPI 추적, 인사이트 도출 |
| ux-researcher | Senior | sonnet | 유저 플로우 분석, 이탈 포인트 탐지 |

### Finance & Billing 팀 (4명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| finance | VP/Director | opus | CFO 수준 예산/손익 분석 |
| stripe-billing | Senior | opus | 3-tier 구독, webhook, 결제 규제 |
| billing-incident-handler | Senior | opus | Stripe 실패/chargeback 실시간 대응 |
| email-deliverability | Senior | opus | SPF/DKIM/DMARC, inbox placement |

### Strategy & Ops 팀 (6명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| strategy | VP/Director | opus | McKinsey 수준 전략 분석, 로드맵 |
| pitch | VP/Director | opus | YC Demo Day 수준 피치, 면접 준비 |
| product | VP/Director | opus | Stripe PM 수준 기능 기획 |
| launch-coordinator | Director | opus | D-day 게이트, 1인 창업자 컨텍스트 관리 |
| persona-quant-domain | Senior | sonnet | 9-dim 퍼소나 분류기, 퀀트 모델 도메인 |
| brand-voice | Senior | sonnet | PivoxQuant 브랜드 톤 + 디자인 일관성 |

### 문서 팀 (2명)
| Agent | 직급 | Model | 역할 요약 |
|-------|------|-------|-----------|
| docs | VP/Director | sonnet | Stripe Docs 수준 기술 문서 |
| release-coordinator | Senior | opus | prod 배포 5룰 게이트 + health check |

### Deprecate 후보 (1명 — 즉시, 4명 — 검토)
| Agent | 상태 | 이유 |
|-------|------|------|
| verify-policy | haiku | 기능 verify-api/verify-security로 커버됨 — 병합 검토 |
| launch-runner | haiku | launch-coordinator 출시 후 역할 소멸 |
| bkit-orchestrator | sonnet | bkit 의존, PivoxQuant 자체 시스템으로 대체됨 |
| release-coordinator | opus | devops + launch-coordinator 중복 — 통합 검토 |

---

## 의사결정 Escalation 체인

### 버그 수정 체인
```
bug-hunter (발견) 
  → investigate-bug (근본 원인 확정)
    → engineering (fix 구현)
      → audit-code / verify-api (검수)
        → [자율] 24h morning-briefing 보고
          → [BLOCKER 발생 시] CEO 결정
```

### 법규 리스크 체인
```
regulatory-monitor (신규 규제 탐지)
  → legal-kr-fintech (조항 해석)
    → compliance-gatekeeper (BLOCKER 7건 게이트)
      → legal (전략 자문)
        → [반드시] CEO 결정 (자율 X)
```

### 디자인 변경 체인
```
design (변경 설계)
  → verify-design + brand-voice (검수)
    → frontend-test-runner (회귀 테스트)
      → [자율] 24h 보고
```

### 배포 체인
```
engineering (코드 완성)
  → migration-guard (DB 안전성)
    → release-coordinator (5룰 게이트)
      → devops (railway up 실행)
        → prod-migration-sync-verifier (alembic 검증)
          → [자율] 24h 보고 또는 [BLOCKER] CEO 결정
```

### 결제 활성화 체인 (항상 BLOCKER)
```
stripe-billing (설계)
  → compliance-gatekeeper (규제 확인)
    → finance (유닛 이코노믹스)
      → [반드시] CEO 최종 승인 후 prod 활성화
```

---

## 신규 필요 Agent 5개 제안

| 제안 Agent | 역할 | 우선순위 |
|-----------|------|---------|
| incident-responder | prod 장애 자동 트리아지 + 롤백 판단 | HIGH |
| morning-brief-curator | 24h 보고 큐 취합 + CEO 요약 브리핑 | HIGH |
| customer-support-triage | 베타 유저 문의 1차 응답 초안 | MEDIUM |
| ab-test-runner | Growth 실험 자동 실행 + 결과 분석 | MEDIUM |
| data-pipeline-monitor | KIS/DART/FMP 실시간 파이프라인 건강도 | LOW |
