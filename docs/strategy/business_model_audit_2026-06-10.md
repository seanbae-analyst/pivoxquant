# 사업모델 감사 — 깨지는 부분 전수 (2026-06-10)

> 작성: 기획부(Strategy) · 대상: 배상현(CEO) · **정직 보고 모드 / 아첨 금지**
> CEO 야간 지시: "사업모델 감사 돌려서 깨지는 부분 다 확인."
> 모든 근거 = Read/Grep 실측 (file:line). 코드 미수정. 기억·추측 인용 없음.

---

## Executive Summary

사업모델은 **세 군데에서 구조적으로 깨져 있다.** 하나는 법적(수익모델 자체가
면제 트랙과 충돌), 하나는 계약적(가격표가 파는 것 ≠ 코드가 주는 것), 하나는
유닛이코노믹스(전역 AI 예산 캡이 유저 수와 함께 깨짐). 셋 다 출시 전에 풀어야
하고, 그중 **두 개는 코드 수정만으로 즉시 해결 가능**하다(변호사 불필요).

**Top 5 BREAKS (severity 순):**

| # | 깨지는 부분 | Severity | 수선 주체 |
|---|---|---|---|
| B1 | **§101 면제 ② "매월 청구 없음" vs 월 구독** — 수익모델 자체가 면제 요건과 충돌 | 🔴 CRITICAL | 변호사 (Q7/Q-S3) + 약관 |
| B2 | **가격표 Pro가 파는 6개 아티팩트를 백엔드는 Premium에만 배송** — 표시광고 불일치 | 🔴 CRITICAL | 코드 OR 가격표 (즉시) |
| B3 | **AI 예산 캡이 전역(global) 카운터** — 유저 200명 넘으면 Pro 유저가 주간 메모 못 받음 | 🟠 HIGH | 코드 (per-user 전환) |
| B4 | **KIS 시세 재배포 갭(R7)** — 유료화 시 무라이선스 상업 재배포 성립 | 🟠 HIGH | 변호사 + 데이터 소스 교체 |
| B5 | **free→pro 전환로 막다른 길** — 업그레이드 CTA가 503 게이트로 항상 실패 | 🟡 MED | 시퀀스 (출시 후 자동 해소) |

---

## 1. 깨지는 부분 (BREAKS) — 상세

### B1 — 🔴 수익모델 ≠ 면제 트랙: §101 ② "매월 청구 없음" vs 월 구독

**증거 (코드의 자기 법무 문서):**
`docs/legal-attachments/section-101-exemption-decision.md:29`
> ② **매월 청구 없음** | ⚠️ Pro ₩9,900/월 + Premium ₩19,900/월 = 월 구독 →
> 변호사 자문 Q7

같은 문서 `:76`, `:98-101`: §101 면제 4요건 중 ②③④가 **전부 회색지대**이며,
CASE C(VIOLATION)면 "즉시 해당 surface 제거 + 유사투자자문업 신고 트랙 전환
(5년 갱신/자본금 신규 요건)"이라고 코드 저장소가 스스로 적어놨다.

**왜 #1 리스크인가:** B2~B5는 *제품의 일부*가 깨지는 거지만, B1은 **수익을
만드는 행위(월 구독료 청구) 자체**가 회사의 법적 포지셔닝(§101 면제 = 유사투자
자문업 미신고)을 깨뜨릴 수 있다. 즉 "돈을 받는 방식"과 "법을 피하는 방식"이
정면충돌한다. 면제가 깨지면 자본금·5년 갱신 요건이 새로 생기고, 1인 100만원
예산으로는 감당 불가 → **회사 모델 전체가 무효화**될 수 있는 단일 실패점.

- **확률**: 중 (변호사가 "구독료 = 자문 대가 아님" 약관 명시로 면제 유지 가능
  하다는 의견이면 해소. 그러나 2024-08-14 시행 신규 규제 ②(양방향 채널 금지)와
  겹쳐 불확실 — `docs/legal-attachments/regulatory-impact-2026-05.md` HIGH ②).
- **영향**: 치명 (모델 전체)
- **수선 방향**: **변호사 (코드 아님).** Q7/Q-S3 의견서가 단일 BLOCKER.
  - CASE B 대비: 약관 §6.1에 "구독료는 자문 대가가 아니다" 직설 명시 (이미
    `:94`에 fix 경로 문서화됨) + `services/ai/service.py:306-314` rec_shares
    구체 수량 출력 완화.
  - **Kill 기준**: 변호사가 CASE C(면제 깨짐) 사인 → 월 구독 모델 폐기,
    1회성 결제(아티팩트 단건 판매) 또는 유사투자자문업 신고로 피벗 검토.
    이건 출시 전에 알아야 하는 단 하나의 답이다.

---

### B2 — 🔴 가격표가 파는 것 ≠ 코드가 주는 것 (Pro 6종이 실제로 Premium 전용)

**이건 버그가 아니라 표시광고법(§3) + 계약 불일치다.** Pro(₩9,900) 구독자가
가격표에서 약속받은 아티팩트를 **백엔드가 Premium(₩19,900) 유저에게만 배송**한다.

**증거 — 가격표 Pro 카드 feature 리스트 (`frontend/src/app/pricing/page.tsx:97`):**
> "Pro artifacts — Morning Brief Plus, Earnings Pre-Brief, DD Checklist,
> **Insider Mirror, Risk Board, Dividend Income, Quarterly Self-Report,
> ... Self-Audit, Portfolio Segment**, AI Assistant, Weekly Memo (full)"

추가로 `:99` — "Risk Board — 7-layer observation" 을 Pro 전용 줄로 한 번 더 명시.

**증거 — 백엔드 실제 게이트 (`services/artifacts/*_service.py` 의 `_tiers` import):**

| 아티팩트 | 가격표 표기 | 백엔드 실제 게이트 (file) | 불일치 |
|---|---|---|---|
| Risk Board | **Pro** (`:97`,`:99`) | **PREMIUM** `risk_board_service.py:59` | ❌ |
| Insider Mirror | **Pro** (`:97`) | **PREMIUM** `insider_mirror_service.py:51` | ❌ |
| Dividend Income | **Pro** (`:97`) | **PREMIUM** `dividend_income_service.py:63` | ❌ |
| Quarterly Self-Report | **Pro** (`:97`) | **PREMIUM** `quarterly_self_report_service.py:75` | ❌ |
| Self-Audit | **Pro** (`:97`) | **PREMIUM** `self_audit_service.py:46` | ❌ |
| Portfolio Segment | **Pro** (`:97`) | **PREMIUM** `portfolio_segment_service.py:51` | ❌ |
| Morning Brief Plus | Pro | (확인) — weekly memo / brief 계열 PRO | ✅ |
| Earnings Pre-Brief | Pro | PRO `earnings_prebrief_service.py:65` | ✅ |
| DD Checklist | Pro | PRO `dd_checklist_service.py:47` | ✅ |
| Weekly Memo (full) | Pro | PRO `weekly_memo_service.py:77` | ✅ |
| AI Assistant | Pro | PRO `routes/ai.py:92` `@require_tier("pro")` | ✅ |

→ 가격표 Pro 카드 12개 항목 중 **6개가 실제로는 Premium 전용.** Pro 결제자는
₩9,900을 내고 광고된 기능의 절반을 못 받는다. 동시에 Premium 카드(`:114`)는
이 6개를 "Premium artifacts"로 다시 파는 게 아니라 *다른* 7종(Capital Allocation,
Credit Rating, Burn Rate, Monthly Finance, KPI Dashboard, Year-End Letter,
Brag Card)을 판다 — 즉 6개는 **어느 카드에서도 정직하게 매칭되지 않는다.**

> 참고: Brag Card는 가격표에서 Premium으로 팔지만 백엔드
> `brag_card_service.py`는 `_tiers` import이 없어(전 유저/Free) — 또 다른 방향의
> 불일치. Credit Rating/Burn Rate/KPI Dashboard는 가격표 Premium인데 백엔드는
> **PRO** (`PAID_TIERS_PRO_AND_UP`) — 즉 Premium에 판 걸 Pro가 받는 역방향
> 누수까지 존재.

- **확률**: 확정 (이미 코드에 존재. 결제 켜는 순간 100% 발현)
- **영향**: 큼 (Pro 구독자 환불·민원·표시광고 신고 + Premium 가치 희석)
- **수선 방향**: **코드 OR 가격표 — 둘 중 하나로 SoT 통일 (변호사 불필요).**
  - 권고: **가격표를 백엔드에 맞춘다**(코드가 검증된 SoT, `_tiers.py`가 단일
    근원). Risk Board/Insider Mirror/Dividend/Quarterly/Self-Audit/Portfolio
    Segment 6종을 가격표 Premium 카드로 이동, Credit Rating/Burn Rate/KPI를
    Pro로 내림. = `pricing/page.tsx` TIERS 배열 + 랜딩 Pricing 섹션 +
    `terms-ko.md §8.1`(가격표 SoT 주석 `:67`) 동시 수정.
  - **이게 더 중요한 이유**: 가격표 SoT가 `terms-ko.md`라고 코드 주석이
    선언(`:67`)하는데, 약관과 백엔드 게이트가 다르면 **약관 위반을 약관이
    증명**하는 꼴. 출시 전 무조건 일치시켜야 함.

---

### B3 — 🟠 AI 예산 캡이 전역 카운터 (유저 수와 함께 깨지는 유닛이코노믹스)

**증거:** `services/artifacts/weekly_memo_service.py:163-184`
```
_WEEKLY_AI_LIMIT = 200
_ai_usage = {"day": None, "count": 0}   # ← 모듈 전역, per-user 아님
```
`services/cache_service.py:33,85` — `EARNINGS_TONE_DAILY_LIMIT = 50` 도 동일하게
모듈 전역 `_earnings_tone_usage` 카운터. earnings_prebrief `_AI_LIMIT = 100`
(`earnings_prebrief_service.py:164`) 도 "per UTC day" 전역.

**무엇이 깨지나:** 이 캡들은 **비용 폭주를 막는 안전장치로는 옳지만**, *전역*
이라서 **유저 수가 늘면 서비스 품질이 깨진다.**
- 주간 메모: Pro 유저 1명당 일요일 1콜(`:1038` "~1 call per Pro user per
  Sunday"). 전역 캡 200 → **Pro 유저 201명째부터 주간 메모를 못 받는다.**
  유저가 ₩9,900 내고 핵심 산출물을 "오늘 예산 소진"으로 못 받음 = retention
  파괴 + 환불 사유. 캡이 곧 **유료 유저 상한선 200명**이 되어버린다.
- earnings_tone 50/day 전역도 동일 — 50명 넘으면 51번째 유저 429.

**유닛이코노믹스 (실측 기반 추정):**
- 모델 = `claude-haiku-4-5`(`weekly_memo:1344`, `earnings_prebrief:507`,
  `ai/service.py:141`, `ai/models.py:17`) — 가장 싼 티어. **이건 잘한 결정.**
- Haiku 1콜 비용은 입력/출력 토큰에 따라 대략 $0.001~0.01 수준(아티팩트당).
  Pro 유저 1명 월간 변동비 추정: 주간메모 4콜 + earnings/AI assistant 산발 →
  **월 수십 원~수백 원 수준.** ₩9,900 가격 대비 **변동비는 무시 가능** =
  마진 구조 자체는 건강.
- **진짜 비용 리스크는 토큰비가 아니라**: (a) 전역 캡이 깨지면 *유료 유저를
  못 받는* 기회비용, (b) FMP 상업 플랜(B4와 연동) — 고정비. 데이터 벤더가
  Anthropic보다 비싸다.

- **확률**: 높음 (유저 200명은 출시 후 곧 도달 목표치)
- **영향**: 큼 (유료 유저 상한 = 200명에 묶임)
- **수선 방향**: **코드.** 캡을 (1) per-user 로 전환하거나 (2) 전역 캡을
  유저 수 비례로 동적 산정. 단기: 캡 상향 + 모니터링 알림(소진 80%). 비용
  방어는 유지하되 "유료 유저를 거절"하지 않도록 per-tier 분리.

---

### B4 — 🟠 KIS 시세 재배포 갭 (유료화 시 무라이선스 상업 재배포)

**증거:** `docs/legal/R7_kis_market_data_options_2026-06-09.md`
- `routes/market.py:1201-1207` — KOSPI/KOSDAQ 지수가 KIS 경유. KIS 앱키 =
  **본인 계좌 조회용**, 상업 재배포 권한 아님.
- `services/data/fetcher.py:1211` — `.KS`/`.KQ` → KIS 1순위, FMP fallback.
- 유료결제 활성화 = 상업 재배포 성립 → KRX/KOSCOM 정보이용계약 필요.

**비즈니스 의미:** B1과 마찬가지로 **수익화 행위가 법적 갭을 발현시킨다.** 단
R7 문서 `:30`의 판단대로 "유료화는 R3(통신판매업)+R4(Stripe)로 이중 차단 →
R7은 유료화 전까지 실질 우선도 낮음." 즉 **B1 다음 순번**. 무료 베타 동안엔
회색지대지만, 결제 켜기 전에 KR 데이터 소스를 정리해야 한다.

- **확률**: 중 (KR 유저가 매출의 큰 비중이면 높음)
- **영향**: 큼 (KRX/KOSCOM 분쟁 + KR 화면 전면 중단 리스크)
- **수선 방향**: **변호사 사인 + 데이터 소스 교체.** R7 추천 = 옵션2(금융위
  공공데이터 T+1, cc-zero 확정 시 비용 0) + 단기 브릿지 옵션4
  (`KR_INDEX_KIS_ENABLED=0` env 토글, `routes/market.py:1201` 게이트 이미 존재).
  본인계좌 read-only(표면1)는 KIS 약관 허용 → 유지 OK.

---

### B5 — 🟡 free→pro 전환로가 막다른 길 (현재 시퀀스 한정)

**증거:** `routes/billing.py:56-90` — `BUSINESS_REGISTRATION_NUMBER` +
`TELESELLER_REGISTRATION_NUMBER` 둘 다 설정 전까지 **모든 결제 endpoint 503
`BUSINESS_REGISTRATION_PENDING`.** 가격표 CTA(`pricing/page.tsx:826`
`handleCheckout`)는 consent 모달 → `proceedToCheckout`(`:479`) → 503 → toast
"구독 가입 준비 중입니다"(`:517`)로 끝난다.

**평가 (정직):** 이건 **의도된 게이트라 "깨졌다"기보단 "막혔다".** 그리고
실제로 **잘 처리돼 있다** — 옛날엔 503을 삼키고 /home으로 튕겼는데(`:503-508`
주석), 지금은 명확한 toast로 사용자에게 알린다. 전환로 UX 자체는 graceful.

**그러나 남는 break:** 무료 유저가 TierGate(`tier-gate.tsx`)에 막혀 /pricing
으로 유도되지만, /pricing 끝은 항상 503이다. 즉 **현재 시퀀스에선 free→pro
전환이 구조적으로 0%** — 결제가 켜지기 전까지 *어떤 무료 유저도 유료로 못
간다.* record-as-spine 전략 메모(`record-as-spine_2026-06-09.md:230-233`)가
정확히 이걸 인지: "결제가 막힌 동안 무료로 할 수 있는 최선은 retention(척추)
투자." → 옳다.

- **확률**: 확정 (게이트 ON인 동안 100%)
- **영향**: 중 (출시=결제 ON 시 자동 해소. 단 베타 기간 매출 0 확정)
- **수선 방향**: **시퀀스 (코드 아님).** B1(변호사) + 통신판매업 신고 +
  Stripe env 설정이 풀리면 자동 해소. 그 전까지 전환 시도 금지, retention에
  집중(척추 메모와 정합).

---

## 2. 3-tier 구조 자체에 대한 비판적 평가

**현 구조:** Free(0) / Pro(₩9,900) / Premium(₩19,900), 차이 = 아티팩트 개수
(Free 3종 universal / Pro 6 / Premium 9, CLAUDE.md 기준).

**비판 1 — 티어 컷이 "기능 가치"가 아니라 "아티팩트 개수"로 그어졌다.**
B2가 증명하듯 어떤 게 Pro고 어떤 게 Premium인지에 **일관된 논리가 없다.** Risk
Board(7-layer 리스크)는 가격표가 Pro라고 부르지만 백엔드는 Premium이고, 정작
Credit Rating/Burn Rate는 가격표 Premium인데 백엔드 Pro다. = **티어 배분이
우연적**이다. 사용자가 "왜 이건 Pro고 저건 Premium이지?"에 답을 못 한다.

**비판 2 — 척추 전략과 가격 구조가 어긋난다.** record-as-spine 메모는 제품의
영혼을 **기록(Journal/Pre-Trade/Behavior Mirror)**으로 본다. 그런데 가격표 3티어
는 전부 **아티팩트(출력물)**로만 나뉜다. 즉 **차별화 자산(기록)은 무료고, 파는
건 출력물이다.** 메모 `:244`도 인정: "척추는 유료 전환 사유가 아니라 retention
엔진. 지불 의향은 아티팩트(year-end 등 Premium)에서 검증." → 전략은 맞지만,
**그러면 Pro와 Premium의 진짜 경계는 "year-end letter 같은 연/분기 단위 깊은
산출물"이어야** 하고, 지금처럼 6종이 어느 카드에도 안 맞는 상태는 그 경계를
흐린다.

**데이터가 말하는 것 — 무엇이 티어를 옮겨야 하나:**
- **Risk Board를 Pro로 내려라 (가격표 약속대로).** 7-layer 리스크는 record-as
  -spine의 "관측 입력단"이고, Pro의 핵심 약속(`:99`)이다. Premium에 가두면 Pro의
  매력이 비고, B2 불일치도 가격표 쪽 손질로 해결되는 게 아니라 **백엔드를 가격표
  에 맞추는** 방향(Risk Board만큼은)이 제품적으로 옳다.
- **Year-End Letter / Quarterly / Self-Audit = Premium 유지.** 이건 "1년 기록의
  요약본"(척추의 출력단, 메모 §3)이라 *누적 가치*가 크고 지불 의향 검증 포인트.
  명확히 Premium이어야 한다.
- **Brag Card 백엔드 게이트 부재** → Free에 노출 중. 바이럴(공유 OG) 자산이니
  Free 유지가 acquisition에 맞다 — 단 가격표에서 Premium으로 파는 표기는 제거.

**근본 권고:** 3-tier 자체는 SaaS 표준이라 유지하되, **티어 경계의 논리를
재정의**하라:
- **Free** = 관측 + 기록 척추(Journal/Pre-Trade) + 주간 메모 축약 → retention.
- **Pro(₩9,900)** = "매주 쓰는 데스크" = 주간/이벤트성 산출물(Weekly full,
  Earnings Pre-Brief, DD, **Risk Board**, AI Assistant).
- **Premium(₩19,900)** = "분기·연 단위 깊은 리포트" = Year-End Letter,
  Quarterly Self-Report, Self-Audit, Capital Allocation, Credit Rating.

즉 **시간 지평(주간 vs 분기/연)**으로 컷을 다시 그으면 사용자에게 설명 가능한
논리가 생긴다. 지금의 "개수 컷"은 B2를 낳은 근본 원인이다.

---

## 3. 출시 시퀀스 리스크 (billing flips on: 무엇이 먼저 깨지나)

period_end는 이미 fix됨(commit 93c0d946). 결제 ON 시 **순서대로 발현될 잠재
break:**

| 순번 | 결제 ON 시 즉시 깨지는 것 | 근거 | 출시 전 차단법 |
|---|---|---|---|
| 1 | **B2 — Pro 구독자가 광고된 6개 아티팩트 미수신** | 첫 Pro 결제자 일요일 메모/리스크보드 누락 | 가격표↔백엔드 일치 (코드) — **출시 BLOCKER로 격상 권고** |
| 2 | **B1 — §101 면제 ② 발현** (월 청구 시작) | 청구 발생 = 면제 요건 충돌 활성화 | 변호사 Q7 사인 (이미 BLOCKER) |
| 3 | **B4 — KIS 재배포 갭 발현** (상업 재배포 성립) | R7 `:9` | `KR_INDEX_KIS_ENABLED=0` 브릿지 OR 옵션2 |
| 4 | **B3 — 유료 유저 200명 캡** | 전역 카운터 | 출시 직후엔 안 터짐, but 성장 시 | 
| 5 | 환불 흐름 §17 (consent 모달 `:376`은 표기만, 부분환불 미구현) | CLAUDE.md "부분환불 §17 deferred" | 변호사 + 코드 |

**가장 위험한 건 #1(B2).** B1/B4는 이미 BLOCKER로 인지돼 있어 결제가 *안* 켜질
거지만, B2는 **아무도 BLOCKER로 안 잡고 있다** — 결제만 켜지면 첫 Pro 유저부터
조용히 깨진다. 표시광고 불일치는 환불·민원·신고로 직결되므로 **결제 ON 전
반드시 가격표↔`_tiers.py` 정합성 테스트를 추가**해야 한다(현재 그런 회귀
테스트 없음 — `tests/`에 가격표-게이트 일치 검증 부재).

---

## 부록 — 실측 출처 인덱스

- 가격표 SoT: `frontend/src/app/pricing/page.tsx:70-122` (TIERS), `:97`(Pro), `:114`(Premium), `:67`(terms-ko.md §8.1 = 선언된 SoT)
- 백엔드 티어 게이트: `services/artifacts/_tiers.py:42-48`, 각 `*_service.py`의 `_PAID_TIERS` import (file:line 표 §B2)
- TierGate FE: `frontend/src/components/ui/tier-gate.tsx:30-43`
- require_tier BE: `routes/decorators.py:96,108-130`; `routes/ai.py:92`
- 결제 게이트: `routes/billing.py:39-90`(503), `:248`(price id), `:496,629-632`(webhook tier sync)
- AI 예산 캡(전역): `weekly_memo_service.py:163-184`, `cache_service.py:33,85`, `earnings_prebrief_service.py:164`
- 모델(비용): `claude-haiku-4-5` — `weekly_memo:1344`, `ai/service.py:141`, `ai/models.py:17`
- §101: `docs/legal-attachments/section-101-exemption-decision.md:29,76,98-101`
- KIS R7: `docs/legal/R7_kis_market_data_options_2026-06-09.md`, `routes/market.py:1201`, `services/data/fetcher.py:1211`
- 척추 정합: `docs/strategy/record-as-spine_2026-06-09.md:230-244`
- rec_shares 회색지대: `services/ai/service.py:306-314`

> 한 줄 요약: **수익모델(B1)·가격표(B2)·확장성(B3)이 동시에 깨져 있다. B2는
> 코드로 오늘 고칠 수 있고 BLOCKER로 격상해야 한다. B1은 변호사 단일 BLOCKER다.**
