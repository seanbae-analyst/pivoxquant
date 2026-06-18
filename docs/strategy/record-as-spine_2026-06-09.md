# 전략 메모: 기록(Record-of-Reasoning)을 제품의 척추로

> 작성: 2026-06-09 · 기획부(Strategy) · 대상: 배상현(CEO) · **정직 보고 모드**
> CEO 야간 지시: "기능이 너무 많고 따로 논다. 기록(투자 저널)에 더 FOCUS 하자.
> 더 깊이 생각해라." — 이 메모는 그 지시를 코드 실측 위에서 검증하고, 채택/반려
> 권고와 실행 로드맵을 제시한다. 코드는 수정하지 않았다. (사실 근거 = Read/Grep 실측)

---

## Executive Summary

CEO의 직관은 **옳다, 그리고 데이터가 뒷받침한다.** 현재 22개 대시보드 라우트가
"Artifacts / Portfolio / Research / System" 4개 그룹으로 나뉘어 있는데
(`terminal-sidebar.tsx`), 정작 제품의 영혼인 **기록(Journal · Pre-Trade
Deposition · Behavior Mirrors)** 은 전부 맨 아래 **"System" 그룹 — Settings 옆에**
파묻혀 있다. 즉 브랜드 카피("거래 전 거울", "Record of Reasoning", "compounding
memory")는 이미 기록 중심인데 **정보 구조(IA)는 기록을 부속품으로 취급한다.** 이
괴리가 "기능이 따로 논다"의 정체다.

권고: **기록을 척추로 승격**한다. 단, "저널 앱으로 피벗"이 아니라 **모든 기능이
기록에 쓰고(write) 기록에서 읽는(read) 단일 루프**로 재배선한다. 이미 존재하는
배관(Pre-Trade → /journal 자동 적재, Behavior Mirrors, 18종 아티팩트)을 레버리지
하면 1인 창업자가 출시 전에 감당 가능하다. 새로 만드는 것보다 **연결·승격·정리**가
일의 80%다.

**핵심 3대 결정 (ICE 순):**
1. **IA 재편** — Journal을 nav 최상단으로, 기록 그룹 신설 (ICE 9×8×9 = 648)
2. **Pre-Trade에 persona 컨텍스트 배선** — `GET /api/profile/persona` 이미 존재,
   pre-trade가 소비만 안 함 (ICE 7×8×7 = 392)
3. **홈을 "기록 리뷰 피드"로 전환** — 현재 V2는 아티팩트 갤러리 (ICE 8×6×5 = 240)

**반려/강등 권고:** AI Chat(`/ai-chat`)·Discover·Market은 이미 nav에서 `hidden:true`
처리됨 — 옳다. Companion(`/companion`, Premium Plus 챗봇)은 척추에 안 붙으면
지금처럼 격리 베타로 두는 게 맞다(아래 §3).

---

## 1. HONEST DIAGNOSIS — CEO가 옳은가?

### 1.1 실측한 라우트 인벤토리 (22개)
`frontend/src/app/(dashboard)/`: home, market, signals, discover, watchlist,
detail/[ticker], alerts, ai, ai-chat, risk, **journal**, **pre-trade**, reports,
**companion**, **growth**, portfolio, profile, settings, support + (layout).

### 1.2 현재 IA — 기록이 어디에 있나 (`terminal-sidebar.tsx` 실측)
```
TOP (ungrouped):  Home
그룹 "Artifacts":  Reports · Signals · AI Analysis
그룹 "Portfolio":  Portfolio · Watchlist(hidden) · Risk Board
그룹 "Research":   Market(hidden) · Discover(hidden) · AI Chat(hidden) · AI Analysis
그룹 "System":     Alerts · Companion · ★Journal · Routine(=growth) · Profile · Settings
```
**진단:** 제품에서 가장 차별화된 자산 세 개 —
- **Journal**(`/journal`, pre-trade reflection feed + 5개 Behavior Mirror),
- **Pre-Trade Deposition**(7문항 거울, `pre-trade-questions.ts` + `friction.py`),
- **Behavior Mirrors**(disposition/concentration/turnover/averaging-down,
  `services/behavior/`)

— 이게 전부 **"System" 그룹, Settings·Profile과 한 묶음**이다. 사용자 인식상
"기록"은 *설정 같은 관리 메뉴* 수준으로 취급된다. 척추가 맹장 자리에 있다.

### 1.3 "따로 논다"는 구체적으로 어디서 보이나
- **Pre-Trade는 persona를 모른다.** `pre-trade-questions.ts`는 7문항이 전 사용자
  동일 카피. `GET /api/profile/persona`(`routes/profile.py:814`)가 declared+observed
  persona를 이미 반환하는데 **deposition 컴포넌트가 이걸 안 읽는다.** Beginner와
  Quant가 똑같은 톤의 질문을 받는다 → 개인화 단절.
- **아티팩트(18종)는 기록을 "재료"가 아니라 "별도 산출물"로 취급.** year-end letter,
  self-audit, quarterly self-report는 본질적으로 *사용자의 1년 기록 요약*인데,
  nav에서 "Artifacts" 그룹으로 Journal과 **분리**되어 있다. 같은 뿌리인데 다른 방.
- **Signals / Risk Board / Quant engine은 기록에 한 줄도 안 쓴다.** 사용자가 본
  POSITIVE/NEGATIVE 관측이나 7-layer 리스크 경고가 *그 시점 그 종목에 대한 기록*으로
  저널에 남지 않는다 → "내가 그때 뭘 보고 들어갔나"의 절반이 비어 있다.
- **홈(V2)은 아티팩트 갤러리**(`home/_v2/page-v2.tsx`)다. 로그인 후 첫 화면이
  "리포트 진열장"이지 "내 기록 리뷰"가 아니다.

### 1.4 Verdict
**CEO가 옳다.** 스캐터는 기능 *개수*의 문제가 아니라 **공통 척추의 부재**다. 22개가
각자의 페이지로 존재하지만, 그 사이를 흐르는 단일 데이터(=사용자의 기록)가 없다.
브랜드는 기록을 외치는데 IA·데이터플로우는 기록을 무시한다. 이건 피벗할 문제가
아니라 **이미 가진 것을 한 줄로 꿰는** 문제다. (← 이게 좋은 소식이다)

---

## 2. THE THESIS — 왜 기록이 척추여야 하는가

### 2.1 한 문장
**모든 기능이 먹이는 한 개의 습관, 그리고 모든 기능을 더 똑똑하게 만드는 한 개의
저장소 — 그게 기록이다.** 척추는 "또 하나의 페이지"가 아니라 *나머지 21개가 쓰고
읽는 단일 진실원(SoT)* 이다.

### 2.2 증거 (브랜드가 이미 베팅한 학술 근거)
- **Barber & Odean (2000), "Trading Is Hazardous to Your Wealth"** — 가장 많이
  거래한 가구는 연 11.4% vs 시장 17.9%. 과신에 의한 과잉매매가 수익을 파괴한다.
  이미 `pre-trade-questions.ts` 주석에 인용되어 있다. **기록의 적은 망각이 아니라
  과잉행동**이고, deposition은 "진입 직전"이라는 단 하나의 결정적 순간에 마찰을 건다.
- **Disposition effect (Shefrin & Statman; Odean 1998)** — 오른 건 너무 빨리 팔고
  내린 건 너무 오래 쥔다. `services/behavior/profit_loss_mirror.py`가 이미 이걸
  거울로 비춘다. 기록 없이는 자기 disposition을 못 본다.
- **Premortem / 사전 부검 (Klein; Annie Duke, *Thinking in Bets*)** — "이미 실패했다
  상상하라"가 결정 품질을 올린다. pre-trade 질문 6번이 정확히 이것("내일 손절에
  닿았다 상상하라").
- **결정 저널링** — 결정과 결과를 *분리해 기록*하면 결과 편향(outcome bias)을
  교정하고 사후 합리화를 막는다. 저널이 없으면 "내가 왜 들어갔는지"는 손익이 덮어쓴다.

### 2.3 왜 PivoxQuant에 특히 맞나 (법적 해자)
자본시장법 §17/§101 때문에 우리는 **"사라"고 말할 수 없다.** 추천·조언·BUY/SELL 금지.
경쟁사가 "AI가 종목 추천"으로 갈 때 우리는 못 간다. **그런데 기록은 §17의 제약을
정확히 자산으로 뒤집는다** — "관측 자료, 투자 권유 아님 / 채점도 추천도 없이." 우리가
법적으로 *할 수 있는 단 하나의 강한 것*이 바로 "사용자가 자기 결정을 직접 심문하고
기록하게 만드는 것"이다. 척추를 기록으로 두는 건 컴플라이언스와 차별화가 **같은
방향**을 가리키는 희귀한 경우다. 제약이 곧 포지셔닝이다.

### 2.4 The Core Loop
```
   관측(Observe) ──▶ 성찰·기록(Reflect & Record) ──▶ 리뷰(Review) ──▶ 복리(Compound)
        │                      │                          │                │
   signals/risk/        pre-trade 7문항 +          journal feed +     아티팩트(year-end,
   detail/market        rationale(암호화)          behavior mirrors   self-audit) +
                                                                      persona 진화
        ▲──────────────────────────────────────────────────────────────────┘
                  기록이 쌓일수록 관측·성찰이 더 개인화된다
```

---

## 3. EACH FEATURE AS A TRIBUTARY (지류)

각 기능을 두 방향으로 평가: **FEEDS the record**(기록에 쓴다) /
**FED BY the record**(기록이 그것을 똑똑하게 한다). 척추에 안 붙는 건 정직하게 강등.

| 기능 | FEEDS 기록 (write) | FED BY 기록 (read) | 판정 |
|---|---|---|---|
| **Pre-Trade Deposition** (`friction.py`, `pre-trade-questions.ts`) | 이미 핵심. rationale+7문항이 `/journal`에 적재됨 | **누락**: persona·과거 유사진입 결과를 안 읽음 (Q7 "지난번 비슷한 진입 어떻게 끝났나"가 수동) | **척추 본체** |
| **Journal** (`journal/page.tsx`) | feed 자체 | Behavior Mirror 5종 이미 read | **척추 본체** |
| **Behavior Mirrors** (`services/behavior/`) | disposition/concentration/turnover/avg-down 계산 | 거래·기록 히스토리에서 read | **척추 본체** |
| **Quant Engine / Signals** (`services/quant/`) | **누락**: 관측 시점 스냅샷을 기록에 안 남김 | 사용자가 과거에 본 시그널 ↔ 실제 진입 대조 가능해야 | **지류 — 배선 필요** |
| **Risk 7-Layer** (`risk_defense.py`, `/risk`) | **누락**: 진입 시점 리스크 경고가 기록에 안 박힘 | 사용자의 반복 리스크 패턴 학습 | **지류 — 배선 필요** |
| **Artifacts 18종** (`services/artifacts/`) | year-end·self-audit·quarterly가 곧 기록의 *요약본* | persona_resolver로 이미 개인화 | **지류 — 척추의 출력단. nav 통합 필요** |
| **Personas** (`persona-showcase.tsx`, `/api/profile/persona`) | observed persona가 행동에서 갱신됨 | deposition·아티팩트 톤을 결정해야 (아티팩트만 함) | **지류 — pre-trade 배선 필요** |
| **Watchlist / Alerts** | 관심·알림이 "왜 봤나"를 기록에 안 남김 | — | **약한 지류 — hidden 유지 OK** |
| **AI Assistant** (`/ai`, SWOT/sector/earnings-tone) | **누락**: 분석 결과가 기록에 안 붙음 | 기록을 컨텍스트로 주면 개인화 (현재 안 함) | **지류 — 선택적 배선** |
| **Twin** (`services/twin/`) | weekly report 생성 | 거래·기록에서 read | **지류 — 백그라운드 OK** |
| **AI Chat** (`/ai-chat`) | 기록에 안 씀, 일회성 대화 | 기록 컨텍스트 없음 | **강등 (이미 hidden) — 유지** |
| **Discover / Market** | 척추 무관 | 무관 | **강등 (이미 hidden) — 유지** |
| **Companion** (`/companion`, Premium Plus 챗봇) | 기록을 컨텍스트로 *쓸 수 있으나* 현재 격리 챗봇 | 잠재적으로 기록 위에서 대화 | **격리 베타 유지. 척추 붙이면 살리고, 아니면 출시 후로 demote** |

### 정직한 컷/강등 권고
- **AI Chat / Discover / Market**: 이미 `hidden:true`. 잘했다. 척추에 안 붙는다.
  출시 전 노동을 여기 쓰지 마라. (기회비용: 이걸 손대면 척추 배선을 못 한다)
- **Companion**: Premium Plus gated 챗봇은 매력적이지만 **척추가 아니다.** 척추를
  먼저 세운 뒤 "내 기록 위에서 대화하는 동반자"로 재정의하면 살아난다. 지금은
  closed beta 격리가 정답 — 출시 BLOCKER 아님.
- **Growth/Routine**(`/growth`): 습관 트래커. 척추(기록 습관)와 *같은 의도*이므로
  **별도 페이지로 두지 말고 Journal 안의 streak/루틴 위젯으로 흡수** 검토.

---

## 4. CONCRETE REORGANIZATION

### 4.1 새 IA — 기록 중심
```
TOP (ungrouped):
  ▸ Journal           ← 최상단으로 승격 (홈 다음 첫 시선). "내 기록"
  ▸ Home              ← "오늘의 리뷰" 피드로 성격 전환 (§4.3)

그룹 "기록 / Record":          ← 신설. 척추 본체를 한 방에 모은다
  ▸ Journal (feed + mirrors)
  ▸ Pre-Trade (거울)          ← deposition 직접 진입점 (현재 modal-only 보완)
  ▸ Routine (growth 흡수 검토)

그룹 "리포트 / Artifacts":
  ▸ Reports  ▸ Year-End / Self-Audit (기록의 요약본임을 카피로 명시)

그룹 "관측 / Observe":          ← 기존 Research 개명. 기록에 먹이를 주는 입력단
  ▸ Signals  ▸ Risk Board  ▸ AI Analysis  ▸ Portfolio  ▸ (Watchlist/Market/Discover hidden 유지)

그룹 "System":
  ▸ Alerts  ▸ Profile · Persona  ▸ Settings  ▸ (Companion: beta)
```
핵심 변화: **Journal이 Settings 옆 "System"에서 → nav 최상단 + 전용 "기록" 그룹의
머리로.** 척추가 척추 자리로 온다. (코드상 `terminal-sidebar.tsx`/`bottom-nav.tsx`의
배열 재배치 + GroupHeader 라벨 변경 = 저위험 작업)

### 4.2 The Core Loop (재확인)
관측 → 성찰·기록 → 리뷰 → 복리. §2.4 다이어그램. 모든 진입은 deposition을 거쳐
journal에 남고(이미 trade-modal-v2/add-position-modal-v2에 mount됨), behavior
mirror가 패턴을 비추고, 아티팩트가 분기/연 단위로 요약하며, 그 누적이 persona를
진화시켜 다음 관측·deposition을 더 개인화한다.

### 4.3 홈 화면의 변신
**현재**: V2 = 아티팩트 갤러리. **권고**: "오늘의 리뷰(Today's Review)" 피드.
- 최상단: *최근 미결(open) deposition* — "이 진입, 24시간 전 무슨 생각이었나" 회상
- 그 아래: Behavior Mirror 한 줄 요약 (예: "이번 달 회전율 ↑, disposition 경고")
- 그 아래: 관측 입력단(오늘의 Signals/Risk 변화) — *기록에 먹일 후보*로 프레이밍
- 하단: 다가오는 아티팩트(주간 메모 등)
- **법적 카피 유지**: "관측 자료 · 투자 권유 아님 / 채점도 추천도 없습니다"
(주의: V2/V1 플래그 구조 — `NEXT_PUBLIC_HOME_V2`. 새 홈은 V3로 가거나 V2 내부
교체. 함부로 V1 삭제 금지 — `frontend/CLAUDE.md` 롤백 보험 경고.)

---

## 5. ROADMAP — 1인 창업자 / 출시 전 현실판

**원칙(70-20-10):** 70% = 이미 있는 걸 연결·재배치(저위험), 20% = persona 배선,
10% = 홈 재설계. **새 백엔드 모델 신설 최소화** — `PreTradeReflection`,
behavior mirror, persona API가 이미 다 있다.

### Phase 0 — IA 재배치 (0.5~1일, 코드 거의 무위험)
- `terminal-sidebar.tsx` / `bottom-nav.tsx` 배열 재정렬: Journal 최상단 + "기록" 그룹 신설.
- GroupHeader 라벨 변경(Artifacts→리포트, Research→관측).
- **성공 기준**: 로그인 후 3초 안에 "내 기록"이 보인다. nav 클릭으로 기록 그룹 도달 ≤1.
- **이미 있어 레버리지**: 모든 페이지 존재. 배선만.

### Phase 1 — Pre-Trade에 persona 배선 (1~2일)
- `pre-trade-friction-core.tsx`에서 `GET /api/profile/persona`(SWR `useProfile`
  패턴) 호출 → persona별 톤 적용(§7 부록). 데이터·엔드포인트 이미 존재.
- **성공 기준**: Beginner와 Quant가 톤이 다른 7문항을 본다. §17 카피 안전성 통과
  (`tests/test_no_hardcoded_samples.py` + legal-guard CI green).
- **Kill 기준**: persona 응답이 비결정적이거나 fallback이 잦으면 → 톤 분기 보류,
  Beginner/그 외 2단계로 축소.

### Phase 2 — 관측→기록 배선 (2~3일)
- 진입 시점 Signal/Risk 스냅샷을 `PreTradeReflection`에 동봉(메타 필드). "그때 본
  관측"을 journal 카드에 표시. **새 모델 없이 기존 row에 컨텍스트 첨부** 우선.
- **성공 기준**: journal 카드에서 "진입 시점 관측" 1줄 확인 가능.

### Phase 3 — 홈 = 오늘의 리뷰 (2~3일, 출시 후 가능)
- §4.3. V2 내부 교체 또는 V3 플래그. 롤백 보험 유지.

### 출시 BLOCKER와의 관계 (정직)
척추 작업은 **유료결제·법무(Q1-Q15)·통신판매업 BLOCKER와 독립**이다. 즉 결제가
막힌 동안 **무료로 할 수 있는 최선의 활성화 투자가 바로 이것** — 클로즈드 베타
사용자에게 "왜 머무는가"의 답을 주는 게 척추다. 기회비용 관점에서 지금이 적기다.

---

## 6. RISKS & COUNTERARGUMENTS (정직 — 이게 틀릴 수 있는 지점)

| 리스크 | 확률 | 영향 | 대응 |
|---|---|---|---|
| **저널은 retention이 약하다** — 일기 앱의 무덤. 사람들은 기록을 안 한다 | 높음 | 치명 | 기록을 *별도 행위*로 만들지 말 것. deposition은 **진입 흐름에 끼워** 자동 적재(이미 그렇게 설계됨). "따로 일기 쓰기" 절대 강요 금지 |
| **활성화 장벽** — 거래가 없으면 기록도 없다(빈 journal) | 중 | 큼 | EmptyState가 이미 portfolio로 유도. 관측(signals/risk)만으로도 "관측 기록"이 쌓이게 §4.3 홈에서 프레이밍 |
| **§17 역설** — 기록에 "과거 유사진입 결과"를 보여주면 *암묵적 추천*으로 읽힐 위험 | 중 | 법적 치명 | Q7은 **사용자 자신의 과거**를 비추는 거울(자기성찰)이지 "이번에 사라/팔라"가 아님. 카피는 2인칭 self-interrogation·결과 중립(채점 금지) 엄수. legal-guard CI + `tests/test_no_hardcoded_samples.py` 게이트 |
| **차별화 ≠ 시장 수요** — "기록이 멋지다"와 "₩9,900 낼 만하다"는 다르다 | 중 | 큼 | 척추는 *유료 전환 사유*가 아니라 *retention 엔진*. 결제 BLOCKER 풀릴 때까지는 머무름을 만드는 게 목표. 지불 의향은 아티팩트(year-end 등 Premium)에서 검증 |
| **홈 재설계가 V1/V2 플래그를 깨뜨림** | 중 | 중 | Phase 3로 미룸. 출시 전엔 nav 재배치(Phase 0)만으로도 80% 효과. V1 삭제 금지 |
| **persona observed가 부정확** | 중 | 중 | declared persona를 1차로, observed는 보조. fallback=balanced(이미 그렇게 설계) |

### 이 가설을 falsify 하는 것
- 클로즈드 베타에서 **deposition 완료율이 진입의 30% 미만**으로 지속 → 마찰이
  너무 크거나 가치를 못 느낌 → 척추 가설 약화. (계측 필요)
- journal **재방문율이 7일 내 한 자릿수%** → "리뷰" 행위가 안 일어남 → 복리 루프
  단절 → 척추 재고.
- persona 톤 분기 후에도 **사용자 인지된 개인화 차이 없음** → Phase 1 ROI 부정.

### 무엇을 희생하나 (정직)
척추에 집중하면 **AI Chat·Discover·Market 같은 "탐색형" 기능 투자를 포기**한다.
경쟁사가 "AI가 종목 찾아줌"으로 갈 때 우리는 그 길을 *법적으로* 못 가므로 어차피
포기할 수밖에 없는 길이다 — 즉 희생의 기회비용이 낮다. 진짜 희생은 **Companion
챗봇의 출시 전 완성**을 미루는 것. 이건 감수할 가치가 있다.

---

## 7. APPENDIX — Persona별 Pre-Trade Deposition 톤 제안

### 7.1 현 상태 (실측)
- 7문항 SoT = `frontend/src/data/pre-trade-questions.ts` (`PRE_TRADE_QUESTIONS`).
  랜딩 teaser(`deposition-teaser.tsx`)와 in-product core
  (`pre-trade-friction-core.tsx`)가 둘 다 여기서 import → drift 방지 구조.
- **persona 컨텍스트가 배선 안 됨.** deposition 컴포넌트는 persona를 모른다.
- persona 데이터는 **이미 존재**: `GET /api/profile/persona`
  (`routes/profile.py:814`, declared+observed 반환). 프론트는 `useProfile` SWR
  패턴(`hooks.ts:134`, `API.profile.get`) 또는 신규 `usePersona` 훅으로 소비 가능.
- persona 셋: growth / value / balanced / income / quant / beginner
  (`persona-showcase.tsx`) — 백엔드는 +speculator/daytrader (`persona_resolver.py`).

### 7.2 배선 방법 (스케치, 코드 미수정)
1. `pre-trade-friction-core.tsx`에서 `usePersona()`(신규, `/api/profile/persona`
   래핑) 또는 기존 profile SWR로 persona 코드 취득.
2. 7문항은 **질문 자체는 동일**(SoT 1개 유지) — persona별로 **보조 마이크로카피
   (subhint)** 1줄만 분기. 질문의 의미·번호·순서는 절대 불변 → drift·법무 리스크 최소.
3. fallback = balanced(중립 톤). persona 미해결 시 현재 카피 그대로.
4. 모든 카피 §17-safe: 2인칭 self-reflection, 방향·가격·목표 제시 금지,
   추천/조언/BUY/SELL 금지. legal-guard CI + pytest 게이트 통과 필수.

### 7.3 Persona별 톤 (보조 마이크로카피 — 질문 7개에 얹는 1줄)
질문은 §pre-trade-questions.ts 원문 유지. 아래는 *톤 가이드 + 예시 subhint*(번호는
원 질문 번호).

**Beginner — 더 부드럽고 설명적·격려적**
- 전체 톤: "틀려도 괜찮아요. 이건 시험이 아니라 연습입니다."
- Q1: "어렵게 쓰지 마세요 — '왜 지금, 이 종목인가'를 친구에게 말하듯 한 줄로."
- Q2: "손절선이 낯설다면: 어디까지 내려가면 '내 생각이 틀렸다'고 인정할 가격인가요?"
- Q6: "숫자가 무섭게 느껴지면, 그게 신호예요. 잃어도 잠들 수 있는 금액인가요?"
- (격려 마감: "여기까지 적은 것만으로 대부분의 사람보다 신중합니다.")

**Quant — 간결·수치 중심·군더더기 제거**
- 전체 톤: 형용사 제거. 숫자만.
- Q2: "stop = 구조적 레벨? (swing low 등) Y/N + 가격."
- Q3: "R:R ≥ 1:2 ? 목표−현재 / 현재−stop = ?"
- Q6: "사이즈 = 평소 σ 내? max loss(원) 명시."
- (마감 없음 — terse.)

**Value — 인내·내재가치·시간지평**
- 전체 톤: "서두를 이유가 있나요? 좋은 기업은 기다려 줍니다."
- Q1: "이건 가격에 대한 베팅인가, 기업에 대한 판단인가?"
- Q3: "목표가 1년 뒤라면, 오늘의 마찰은 중요하지 않습니다 — 논지가 시간을 견디나요?"
- Q7: "비슷하게 '싸 보여서' 들어갔던 지난번, 인내가 보상받았나요?"

**Income — 인내 + 현금흐름 관점**
- 전체 톤: "주가 변동보다 배당·현금흐름의 지속성에 시선을."
- Q1: "이 진입의 목적이 가격 차익인가, 현금흐름인가? 섞이지 않았나요?"
- Q3: "총수익에 배당을 포함해도 R:R 논지가 성립하나요?"
- Q4: "수익률(yield)에 끌린 감정인가, 차분한 판단인가?"

**Growth — 확신(conviction) 시험·논지 압박**
- 전체 톤: "확신은 좋습니다 — 단, 그 확신이 시장에 이미 가격에 반영됐나요?"
- Q1: "시장이 *아직* 못 본 게 뭔가요? 이미 모두가 아는 성장 스토리는 edge가 아닙니다."
- Q4: "이 흥분이 논지 때문인가, 가격이 오르는 걸 봐서인가? (FOMO 점검)"
- Q5: "직전 매매가 수익이었어도 같은 크기로 들어갈 건가요?"

**Balanced (default / fallback) — 중립**
- 현재 원문 톤 그대로. persona 미해결 시 안전 fallback.

**(Speculator / Daytrader — 백엔드 존재, FE 미노출)**: 노출 시 톤 = 극도 간결 +
tilt/revenge 강조(Q5·Q6). 단 출시 전 FE persona 셋(6종)에 없으므로 **이번 범위 밖**.
배선 시 balanced로 흡수.

---

## 부록 B — 근거 파일 인덱스 (실측 출처)
- IA/nav: `frontend/src/components/layout/terminal-sidebar.tsx`,
  `frontend/src/components/layout/bottom-nav.tsx`
- 기록 본체: `frontend/src/app/(dashboard)/journal/page.tsx`,
  `frontend/src/components/journal/*` (5 mirror + storage-proof)
- Deposition: `frontend/src/data/pre-trade-questions.ts`,
  `frontend/src/components/pre-trade/pre-trade-friction-core.tsx`,
  `services/pre_trade/friction.py`, `models/pre_trade_reflection.py`
- Deposition mount(자동적재): `frontend/src/components/portfolio/v2/trade-modal-v2.tsx`,
  `add-position-modal-v2.tsx`
- Behavior: `services/behavior/{profit_loss,concentration,turnover,averaging_down}_mirror.py`
- Persona: `frontend/src/components/landing/persona-showcase.tsx`,
  `routes/profile.py:814` (`/api/profile/persona`),
  `services/artifacts/persona_resolver.py`
- Artifacts: `services/artifacts/{year_end_letter,self_audit,quarterly_self_report}_service.py`
- 홈: `frontend/src/app/(dashboard)/home/page.tsx` (V1/V2 flag)
- 법적: CLAUDE.md(§17·POSITIVE/NEGATIVE·DisclaimerBanner), `.github/workflows/legal-guard.yml`,
  `tests/test_no_hardcoded_samples.py`

> 한 줄 요약: 피벗하지 마라. **이미 가진 척추를 척추 자리에 놓아라.**
