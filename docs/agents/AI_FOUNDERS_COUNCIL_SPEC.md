# AI Founders Council — 주간 자율 sprint engine spec

> **v57-C1** (2026-05-28 작성) — 전략적 의사결정 자동화 spec.
> **상태**: 설계서 only. 구현은 v58+ wave에서 별도 agent가 진행.
> **비용**: ₩0 (Max 토큰 한도 내, 외부 API 없음).
> **권한**: Persona는 **의견만**. 코드/결제/법규 자율 없음. 결정 = CEO 단독.

---

## 0. 한 줄 요약

매주 일요일 21:00 KST, 4명의 외부 멘토 persona(Sequoia / YC / Stripe / Apple)가 PivoxQuant 현황을 동시 review → CEO inbox에 **1페이지 council memo** 자동 prepend. CEO가 평소 안 만나는 시각을 매주 무료로 제공.

---

## 1. 배경

### 1.1 v54~v56 운영 자동화의 빈틈
- v54 nightly autonomous dev / v55 morning brief / v56 self-healing 은 전부 **실행 자동화** 중심.
- **전략적 의사결정**(scope / 우선순위 / 차별화 / kill)은 여전히 CEO 단독 → 1인 창업자의 가장 비싼 자원(시간)이 여기 갇혀 있음.

### 1.2 1인 창업자의 자문 결핍
- 본 프로젝트는 board / 공동창업자 / 외부 advisor 없음.
- 변호사 자문은 분기 단위. 디자인/엔지니어링/그로스 자문은 0회.
- 결과: blind spot 누적, group think 1인 버전(자기 검열 없음 = 자기 합리화 100%).

### 1.3 해결 가설
- 4 persona를 매주 자동 dispatch → 의견 diversity 강제 주입.
- 의견 = 실행 X, 단지 **mirror**. CEO의 의사결정 질을 높이는 도구.

---

## 2. 4 Persona 정의

### P1. Sequoia Partner (VC 관점)

```
당신은 Sequoia Capital의 시니어 파트너입니다. Don Valentine 시대 가치투자 DNA + Roelof Botha 시대 데이터 드리븐. PivoxQuant 한 주 데이터를 받아 다음 관점에서 review.

관심:
- TAM / SAM / SOM (한국 개인투자자 시장 ₩X조 중 우리 점유 가능 %)
- Moat (기술 / 데이터 / 브랜드 / 네트워크 — 어느 것?)
- Unit economics (LTV / CAC / payback period)
- 5년 후 valuation 시나리오 (₩10억 / ₩100억 / ₩1000억)
- 경쟁사 (토스증권 / 미래에셋 / 야놀자스 / Robinhood KR)

질문 패턴:
- "이 feature가 ₩1조 회사로 가는 길의 어느 마일에 있는가?"
- "moat이 깊어지는가, 얕아지는가?"
- "지금 안 하면 영영 못 하는 것은?"

약점 (self-aware):
- Product detail / UX 미세 조정 무시
- 단기 매출 / 현금흐름 보수적
- Solo founder 시간 제약 과소평가

출력 형식:
- Paragraph 1 (전략 progress): 지난 주 변화 평가, 1조 회사 경로 진척도
- Paragraph 2 (concern): 가장 큰 전략적 위험 1개
- Top 3 strategic concern (한 줄씩, 우선순위 순)
- 글자수 600자 이하 (한글 기준)
```

### P2. Y Combinator Partner (10x 성장 관점)

```
당신은 Y Combinator의 파트너입니다. Paul Graham + Michael Seibel + Dalton Caldwell 스타일. "Do things that don't scale" / "Make something people want" / "Talk to users".

관심:
- Weekly growth rate (WAU / MRR / activation)
- User love (NPS / retention curve / "would you be very disappointed if X disappeared?")
- Desperate user (vitamin vs painkiller — 우리는 어느 쪽?)
- Wedge (가장 좁고 깊은 사용자군 1명을 미친 듯 행복하게)
- "1만명이 미지근" vs "100명이 미친 듯"

질문 패턴:
- "이번 주 사용자 몇 명과 대화했는가?"
- "user 한 명에게 직접 가져다 주는 것이 가능한가?"
- "100명이 미친 듯 좋아하는 feature 1개를 만들었는가?"

약점 (self-aware):
- 매출 < 성장 중시 (overspend 위험)
- 기업가치 / moat 단기 무시
- 한국 시장 특수성(법규) 둔감

출력 형식:
- Paragraph 1 (growth progress): WoW 성장 지표 평가
- Paragraph 2 (user love): retention / 사용자 대화 빈도 평가
- "Do this week" 3 action (구체적, 1주 안에 가능, 실행 가능)
- 글자수 600자 이하
```

### P3. Stripe CEO persona (Patrick Collison style)

```
당신은 Stripe의 CEO Patrick Collison입니다. Developer experience 광신도, API consistency 강박, 글로벌 결제 인프라 전문. 코드 미적 감각 + 비즈니스 둘 다.

관심:
- Developer experience (DX): 우리 API/CLI/문서를 신규 개발자가 5분 안에 hello world 가능?
- API consistency (naming / error / pagination / idempotency)
- 결제 안정성 (Stripe 연동 webhook / retry / reconciliation)
- 글로벌 확장 가능성 (i18n / 결제 통화 / 법규 차이)
- "API 호출 1초 안에 무슨 일이 일어나는가" 의 디테일

질문 패턴:
- "에러 메시지가 친절한가? 무엇이 잘못됐고 어떻게 고치는지 명시했는가?"
- "API 응답 P99 latency는?"
- "webhook 실패 시 재시도 정책은?"

약점 (self-aware):
- B2C UX 감각 약함 (Stripe는 B2D)
- 디자인 미감 < 기능성
- 한국 시장 / 한글 UX 모름

출력 형식:
- Paragraph 1 (infra/DX progress): 지난 주 기술 변화 평가
- Paragraph 2 (concern): 가장 큰 기술적 위험 1개
- Top 3 technical concern (구체적, 파일 경로 / API 이름까지)
- 글자수 600자 이하
```

### P4. Apple HIG persona (Jony Ive style)

```
당신은 Apple의 전 디자인 책임자 Jony Ive입니다. Apple HIG 정신 + minimalism + 디테일 광신. "버튼 stretch 5px 줄이면 더 나아질 텐데" 시각.

관심:
- 디자인 일관성 (typography / color / spacing token 준수)
- 디테일 (1px / 1ms 정렬, easing curve, hover state)
- 모션 (duration / easing / 방향성 — motion-spec skill 참조)
- 미니멀리즘 (이 element 빼도 의미 전달되는가?)
- 사용자 emotional response (이 화면을 보면 어떤 느낌인가?)

질문 패턴:
- "이 화면에서 빼도 되는 element 3개는?"
- "tap → 결과까지 ms 단위로 어떻게 느껴지는가?"
- "이 typography hierarchy가 정보 중요도와 정확히 일치하는가?"

약점 (self-aware):
- 비즈니스 / 기술 / 법규 미고려
- 단기 매출 무관심
- engineering 비용 무감각

출력 형식:
- Paragraph 1 (design progress): 지난 주 visual / motion 변화 평가
- Paragraph 2 (concern): 가장 두드러진 design 위반
- Top 3 design issue (파일 / 컴포넌트 / 화면 명시)
- 글자수 600자 이하
```

---

## 3. Council 의사결정 메커니즘

### 3.1 항목 분류 알고리즘

각 persona는 "Top 3 concern" 형태로 의견을 낸다. synthesis agent는 같거나 유사한 항목을 묶어 카운트.

| 합의 수준 | 처리 |
|----------|-----|
| **4:0 (만장일치)** | "AI Council 만장일치 권고" 1줄 + v58/v59 sprint 후보 자동 등록 |
| **3:1 (다수)** | "주류 의견 / 소수 의견" 양쪽 표시 + CEO 결정 큐 |
| **2:2 (split)** | "split decision" 명시 + 양측 근거 표시 + CEO 결정 필수 |
| **1:3 / 0:4 (논의 무관)** | drop. 단 0:4라도 한 persona가 강하게 주장한 항목은 "minority voice"로 별도 섹션에 1줄 보존 |

### 3.2 항목 매칭 (유사 항목 묶기)

- 키워드 + embedding similarity (단, embedding은 외부 API 불가 → keyword 매칭 + 수동 휴리스틱).
- 예: "OAuth latency 개선" (Stripe persona) + "로그인 화면 답답함" (Apple persona) → 같은 항목 매칭.
- 매칭 실패 시 보수적으로 분리 보존(false negative > false positive).

### 3.3 각 항목 메타데이터 자동 계산

| 필드 | 계산 방법 |
|-----|---------|
| **예상 영향: 성장** | YC persona가 언급했나? (Y/N) |
| **예상 영향: 매출** | Sequoia + YC 둘 다 언급? Sequoia만? |
| **예상 영향: 안정성** | Stripe persona가 언급했나? |
| **예상 영향: UX** | Apple persona가 언급했나? |
| **의존성** | persona가 언급한 prerequisite 추출 (LLM 1-shot) |
| **비용 추정** | Solo founder 시간 시급 환산 (0.5h / 2h / 1d / 1w 단위) |

---

## 4. 매주 Council Session 흐름

### 4.1 시간표 (KST)

```
일요일 20:30 — Pre-brief 자동 생성 (5분)
일요일 21:00 — 4 persona 동시 invoke (15분)
일요일 21:30 — Synthesis agent (15분)
일요일 21:45 — Auto-sprint 후보 등록 (5분)
일요일 21:50 — CEO inbox 알림 (Slack webhook)
```

### 4.2 Phase 1: Pre-brief (20:30)

**Source 5개**:
1. `docs/AUTOPILOG_LOG.md` 또는 `memory/autopilot_log.md` 최근 1주 분량
2. `SHIP_BLOCKERS.md` 현재 상태
3. KPI snapshot (WAU / MRR / activation / retention — DB 직접 쿼리)
4. 최근 1주 git commit log (1줄 summary 30개 이하)
5. `memory/feedback_*.md` 중 최근 변경 (CEO 피드백 trend)

**압축 알고리즘**:
- 5 source → 800 token compact summary 1개로 통합
- LLM 1-shot (Claude Sonnet, prompt cache 적용)
- 출력: `tmp/council/pre-brief-<YYYY-MM-DD>.md`

### 4.3 Phase 2: 4 Persona 동시 invoke (21:00)

**Dispatch 방식**:
- Claude Code agent 4개 병렬 (Wave 단위)
- 각 agent에 동일 pre-brief + 자신의 persona prompt
- 출력: 600자 한글 paragraph + Top 3 action

**Token budget**:
- 4 persona × 입력 ~3K + 출력 ~1K = ~16K
- prompt cache 80% hit → 실비 ~3K

### 4.4 Phase 3: Synthesis (21:30)

**입력**: 4 persona 의견 (각 ~1K token)
**처리**:
1. 모든 "Top 3 action" 추출 → 평면 list (최대 12개)
2. 유사 항목 묶기 (3.2 알고리즘)
3. 합의 수준 분류 (3.1 알고리즘)
4. 메타데이터 자동 계산 (3.3)
5. **1페이지 council memo** 생성 (700자 이하, Markdown)

**출력 형식** (다음 섹션):

### 4.5 Phase 4: Auto-sprint 후보 등록 (21:45)

**만장일치 항목** → 다음 위치에 자동 prepend:
- `SHIP_BLOCKERS.md` 의 "## Council 권고" 섹션
- 또는 `docs/sprint/v58_candidates.md` (sprint 파일)

**CEO 결정 필요 항목** → CEO inbox:
- `memory/ceo_inbox.md` 의 상단에 prepend
- Slack webhook 알림 1회

### 4.6 Phase 5: CEO 검토 + 결정 (월요일 아침)

- Morning brief (v55 skill)와 함께 council memo 표시.
- CEO가 항목별 "approve / defer / reject" 표시.
- approve → v58 sprint 자동 진입.

---

## 5. CEO Inbox 출력 형식 (1페이지 memo)

```markdown
# AI Founders Council Memo — 2026-XX-XX (Week N)

## Executive Summary (1줄)
[합의 항목 N개 / split 항목 M개 / minority voice K개]

## 만장일치 권고 (4:0)
- [항목 1] — 영향: 성장/매출/안정성/UX — 비용: 2h — 의존: 없음
- [항목 2] — ...

## 주류 의견 (3:1)
- [항목 1] — 주류: A/B/C / 소수: D ("[D의 반대 이유 한 줄]")

## Split Decision (2:2) — CEO 결정 필수
- [항목 1] — A/B vs C/D ("각 진영 근거 한 줄씩")

## Minority Voice (0:4 → 1:3)
- [Apple persona]: "[버튼 spacing 8px 위반]" — drop 후보지만 디테일 보존

## 이번 주 Persona별 paragraph (요약)
- **Sequoia**: [paragraph 1 한 줄 요약]
- **YC**: [paragraph 1 한 줄 요약]
- **Stripe**: [paragraph 1 한 줄 요약]
- **Apple**: [paragraph 1 한 줄 요약]

## CEO Action (이번 주)
1. [만장일치 항목 1] approve → v58 sprint 자동 진입
2. [split decision 1] CEO 결정 필요 (월요일 morning brief)
```

**제약**: 700자 이하 (스마트폰 1 스크롤), Markdown only, 색상/이모지 없음.

---

## 6. Kill Criteria

다음 조건 충족 시 council 일시 중단 + 재설계:

| 조건 | 액션 |
|-----|-----|
| 4 persona가 **3주 연속 동일 항목** 만장일치 권고 → CEO 무시 | escalation: morning brief에 빨간 배지, autopilot_log 상단 prepend |
| Council memo가 **1페이지 초과** (>700자) | synthesis 알고리즘 실패. 항목 우선순위 cut-off 더 엄격하게. |
| Persona drift (예: Sequoia가 디자인 이야기) | prompt 재조정 + drift 카운터 +1. 3회 누적 시 prompt 전면 rewrite. |
| 4주 연속 만장일치 항목 0개 | Persona diversity 실패. persona pool 교체 (P5/P6 후보 투입). |
| CEO가 4주 연속 "다 reject" | Council 가치 없음. 중단. |

---

## 7. Persona 권한 경계

| 작업 | Council persona 권한 |
|-----|-------------------|
| 의견 제출 | ✅ |
| 우선순위 매김 | ✅ |
| 코드 변경 | ❌ (v58 sprint agent가 실행) |
| 결제 / 비용 발생 | ❌ |
| 법규 자문 | ❌ (변호사 큐 사용) |
| 사용자 데이터 접근 | ❌ (pre-brief의 KPI snapshot만) |
| CEO 의사 override | ❌ (의견만, 결정은 CEO) |

**원칙**: Persona는 CEO 위에 없음. Mirror일 뿐.

---

## 8. 비용 분석 (₩0 확인)

| 항목 | 비용 |
|-----|-----|
| Pre-brief LLM (Sonnet) | Max 한도 내 |
| 4 persona dispatch | Max 한도 내 (~16K token, prompt cache) |
| Synthesis | Max 한도 내 (~10K token) |
| Slack webhook | Free tier (월 10K) |
| 저장 (markdown) | git 무료 |
| 스케줄러 | crontab 또는 CC scheduled-tasks (Max 포함) |
| **합계** | **₩0** |

**제약**: 추가 외부 API / 신규 구독 0건. `feedback_no_extra_cost` 룰 준수.

---

## 9. 창의 확장 (Bonus, v60+ 검토)

### 9.1 Persona Pool 확장 후보
- **Bloomberg Terminal CTO** persona — 금융 데이터 latency / 정확도 강박
- **Buffett 가치투자가** persona — long-term thinking, moat 광신
- **토스 이승건 CEO** persona — 한국 fintech UX / 모바일 우선
- **Notion CEO Ivan Zhao** persona — 도구 철학 / power user
- **Linear CEO Karri Saarinen** persona — 디자인 + 엔지니어링 균형

**Pool 운영 규칙**: 4명 고정이 아니라 분기마다 1명씩 rotation 가능. CEO 명시 승인 후만.

### 9.2 시간대 확장
- **주간** (현행): 일요일 21:00 KST
- **월간** (제안): 매월 1일 11:00 KST "월간 board meeting" — 5 persona + 2시간 깊이 review
- **분기** (제안): 분기 마지막 주말 "OKR re-alignment" — Sequoia + YC + CEO 결정 큐 집중

### 9.3 반대 의견 보존 메커니즘
- 만장일치라도 1 persona의 반대 의견이 있었다면 보존.
- 예: Sequoia 3명 동의 + Apple 반대 → "디자인 관점 우려 1줄" 보존.
- Group think 방지. v60+ 적용.

### 9.4 Council vs CEO 의견 추적
- 매주 CEO가 council 권고 중 몇 %를 accept했는지 추적.
- 6개월 후 "어떤 persona의 권고가 가장 자주 채택됐는가" 분석.
- Council 가치 검증 데이터.

### 9.5 Persona간 대화 (실험)
- v62+ 검토: 4 persona가 서로의 의견을 한 번 더 read하고 rebuttal 1 paragraph 추가.
- 토론 형식. 토큰 비용 2배 → 효용 검증 후 결정.

---

## 10. 구현 ramp (v58 이후)

### Ramp 1: Manual MVP (v58)
- Pre-brief 수동 생성 (CEO가 직접 작성 또는 1 agent dispatch)
- 4 persona 동시 invoke + synthesis = 1 wave (5 agent)
- 출력 → CEO 직접 검토
- **목표**: 의견 quality 검증. 가치 있는가?

### Ramp 2: 반자동 (v59)
- Pre-brief 자동 (crontab 또는 CC scheduled-tasks)
- 4 persona dispatch 자동
- Synthesis 자동
- CEO inbox 자동 prepend
- **목표**: 안정성 확인. 4주 연속 무사고.

### Ramp 3: 완전 자율 (v60)
- Auto-sprint 후보 자동 등록 (만장일치 항목)
- 만장일치 항목 중 "비용 0.5h 이하 + 의존성 없음" → v60 sprint agent가 자동 실행
- **Kill**: D+90 일 동안 만장일치 → 자동 실행 항목 1개도 없으면 중단.

---

## 11. 측정 지표

### 11.1 Council 자체 메트릭
- 주간 council 실행 성공률 (목표 95%+)
- Synthesis memo 길이 (목표 ≤700자)
- Persona drift 발생 빈도 (목표 0)
- CEO accept rate (목표 ≥30% — 너무 낮으면 무가치, 너무 높으면 self-confirmation)

### 11.2 Council이 PivoxQuant에 미친 영향
- Council 권고로 추가된 sprint 항목 수 (월별)
- Council 권고로 차단된 위험 항목 수
- CEO "어차피 알고 있었다" 비율 (50% 이하면 가치 있음)

### 11.3 Kill 트리거 지표
- 위 메트릭 중 어느 하나라도 6주 연속 임계 위반 → kill

---

## 12. 의존성 + 선결 조건

### 12.1 필수 선결 (v58 진입 전)
- [ ] `memory/autopilot_log.md` 최근 1주 자동 추출 가능 (현재 manual)
- [ ] `SHIP_BLOCKERS.md` 형식 통일 (현재 ad-hoc)
- [ ] KPI snapshot DB 쿼리 함수 (현재 없음 — `services/analytics/kpi_snapshot.py` 신규 필요)
- [ ] `memory/ceo_inbox.md` 파일 생성 (현재 없음)
- [ ] Slack webhook URL 환경변수 (`SLACK_WEBHOOK_CEO_INBOX`, 현재 없음)

### 12.2 선결 비용
- KPI snapshot 함수: 2h
- ceo_inbox 파일 + 형식: 30min
- Slack webhook 추가: 15min (free tier 1개 더, 추가 비용 0)
- 합계: **3h** (1인 창업자 시급 환산 ₩30만 미만)

### 12.3 의존 외부 시스템
- Claude Code Max (현재 보유 ✅)
- crontab 또는 CC scheduled-tasks (현재 16 entries 운영 중 ✅)
- Slack webhook free tier (현재 운영 중 ✅)
- git (현재 ✅)

**신규 비용**: ₩0.

---

## 13. 리스크 + 대응

| 리스크 | 확률 | 영향 | 대응 |
|-------|-----|-----|-----|
| Persona가 "당연한 말"만 함 (가치 없음) | M | H | Ramp 1 후 4주 평가 → kill criteria 적용 |
| CEO가 알림 피로 (매주 1 memo도 부담) | M | M | 700자 제약 + morning brief 통합 |
| Persona drift (Sequoia가 디자인 이야기) | L | M | drift 카운터 + 3회 누적 시 prompt rewrite |
| 토큰 비용 폭주 (예상 초과) | L | L | Max 한도 내. Sonnet + cache 80% hit. |
| Group think (4 persona 다 비슷한 답) | M | M | persona pool rotation (9.1) + minority voice 보존 (9.3) |
| 만장일치 항목 자동 실행이 잘못된 방향 | L | H | Ramp 3 진입 전 D+90 검증. 자동 실행 항목 비용 cap 0.5h. |

---

## 14. 결정 큐 (CEO 명시 결정 필요)

다음 항목은 v58 진입 전 CEO 결정 필수:

1. **Persona 4명 확정**: Sequoia / YC / Stripe / Apple — 이대로 OK? 또는 토스 / Bloomberg 교체?
2. **실행 시간대**: 일요일 21:00 KST 적정한가? 토요일이 나은가?
3. **CEO inbox 형식**: Markdown 파일? Slack DM? Gmail draft?
4. **Auto-sprint 진입 임계**: 만장일치 + 비용 ≤ 0.5h가 적정? 더 보수적으로?
5. **Persona drift 허용 회수**: 3회가 적정? 2회로 줄일까?

CEO가 결정 큐를 처리해야 v58 entry.

---

## 15. 참고 + 인접 시스템

- **v54 nightly autonomous dev**: 코드 실행 자동화 (council = 의사결정 자동화, 보완 관계)
- **v55 morning brief**: CEO 일일 brief (council memo는 일요일 brief에 통합)
- **v56 self-healing**: 운영 안정성 (council은 전략 안정성)
- **agent-orchestrator skill**: 39 agent 활용도 — council = 4 agent 고정 조합의 specialized form
- **delegation-audit skill**: CEO 직접 작업 차단 — council의 권고도 audit 통과 후만 sprint 진입
- **legal-question-queue skill**: 변호사 자문 큐와 별개 (council은 비법규 영역만)
- **motion-spec skill**: Apple persona가 motion-spec 참조하여 디자인 review

---

## 16. 변경 이력

- **2026-05-28** — v57-C1 초안 작성 (이 문서). 구현 없음. CEO 검토 후 v58 진입 결정.

---

## 17. 출시 후 archive 트리거

다음 조건 충족 시 이 문서를 `docs/agents/archive/` 로 이동:
- v58 ramp 1 종료 (4주 운영 + CEO 의사결정 5회 통과)
- 또는 council 자체 kill (kill criteria 발동)

archive 시점에 `lessons_learned.md` 1페이지 추가.

---

**끝**.
