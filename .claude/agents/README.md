# 🏢 AI 조직도 — 17개 부서 Agent System

> 1인 창업자가 17개 부서를 운영하는 AI 네이티브 조직

---

## 조직 구조

```
                        ┌─────────────┐
                        │   CEO (나)   │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────┴──────┐  ┌─────┴─────┐  ┌──────┴──────┐
       │  전략 그룹   │  │ 제품 그룹  │  │  지원 그룹   │
       └──────┬──────┘  └─────┬─────┘  └──────┬──────┘
              │               │                │
     ┌────────┤        ┌──────┤         ┌──────┤
     │        │        │      │         │      │
 strategy  finance  product  design  legal  security
 growth   analytics  eng.    QA     docs   devops
 marketing customer  integ.         pitch
```

---

## 부서별 요약

### 전략 그룹 (Strategy Group)
| 부서 | 파일 | 모델 | 벤치마크 | 스킬 수 |
|------|------|------|----------|---------|
| 기획부 | `strategy.md` | opus | McKinsey Partner | 4 |
| 재무부 | `finance.md` | opus | Sequoia CFO | 4 |
| 그로스부 | `growth.md` | opus | Airbnb Growth | 4 |
| 마케팅부 | `marketing.md` | opus | Ogilvy Creative | 4 |
| 데이터부 | `analytics.md` | opus | Google Analytics | 4 |

### 제품 그룹 (Product Group)
| 부서 | 파일 | 모델 | 벤치마크 | 스킬 수 |
|------|------|------|----------|---------|
| 프로덕트부 | `product.md` | opus | Stripe PM | 5 |
| 디자인부 | `design.md` | opus | Apple × Bloomberg | 5 |
| 개발부 | `engineering.md` | opus | Google Staff Eng | 6 |
| QA부 | `qa.md` | opus | NASA JPL | 5 |
| 연동부 | `integrations.md` | opus | Stripe Integration | 4 |

### 지원 그룹 (Support Group)
| 부서 | 파일 | 모델 | 벤치마크 | 스킬 수 |
|------|------|------|----------|---------|
| 법무부 | `legal.md` | opus | Kim & Chang | 4 |
| 보안부 | `security.md` | opus | NSA Red Team | 5 |
| 인프라부 | `devops.md` | opus | Netflix SRE | 5 |
| 문서부 | `docs.md` | sonnet | Stripe Docs | 4 |
| 고객부 | `customer.md` | opus | Zappos | 4 |
| 피칭부 | `pitch.md` | opus | YC Demo Day | 4 |

### 감사 (Audit)
| 부서 | 파일 | 모델 | 벤치마크 | 스킬 수 |
|------|------|------|----------|---------|
| **검수부** | `audit.md` | **opus** | **Goldman Sachs** | **8** |

---

## 총계
- **17개 부서** / **76개 스킬**
- 모델: opus 16 / sonnet 1
- 모든 에이전트: 세계 최고 수준 벤치마크 적용

---

## 사용법

Claude Code에서:
```
@engineering "이 컴포넌트 리팩토링해줘"
@qa "이 코드 버그 있는지 검사해줘"  
@audit "출시 전 전체 검수해줘"
@legal "이 기능 규제 문제 없는지 확인해줘"
```

---

## 폴더 구조
```
.claude/agents/
├── README.md              ← 이 파일
├── audit.md               + audit/skills/SKILL.md
├── engineering.md          + engineering/skills/SKILL.md
├── qa.md                   + qa/skills/SKILL.md
├── design.md               + design/skills/SKILL.md
├── devops.md               + devops/skills/SKILL.md
├── strategy.md             + strategy/skills/SKILL.md
├── product.md              + product/skills/SKILL.md
├── growth.md               + growth/skills/SKILL.md
├── marketing.md            + marketing/skills/SKILL.md
├── security.md             + security/skills/SKILL.md
├── legal.md                + legal/skills/SKILL.md
├── analytics.md            + analytics/skills/SKILL.md
├── finance.md              + finance/skills/SKILL.md
├── integrations.md         + integrations/skills/SKILL.md
├── customer.md             + customer/skills/SKILL.md
├── pitch.md                + pitch/skills/SKILL.md
└── docs.md                 + docs/skills/SKILL.md
```
