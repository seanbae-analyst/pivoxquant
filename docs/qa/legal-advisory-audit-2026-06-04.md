# 법적 전수검수 + 최신 규제 fresh research — 2026-06-04

**작성일** 2026-06-04 · **방법** legal 4-agent 병렬(legal-kr-fintech / legal / compliance-gatekeeper / regulatory-monitor) + 메인 grep/Read 실측 검증
**대상** 약관/처리방침/면책 법문 + 18 아티팩트(23 PDF/이메일) + AI 런타임 + 어제(06-03) H1~H4 fix 착지 + 2026 외부 규제 델타(1개월 공백 메움)
**성격** 내부 참고용 — 법률자문 아님. CEO 지시 "약관/PDF 싹다 검수 + legal agent 싹다 + 최신규율 직접 research".

---

## 0. TL;DR

- **무료 Stage-0 출시 = ✅ GO (코드측 신규 하드 BLOCKER 0).** 4-agent 합의 + 메인 실측. 진짜 출시 게이트 = **외부 변호사 의견서(누적 89건) + 통신판매업 신고** 뿐 — 둘 다 유료 Stage-1 전환의 BLOCKER이지 무료 출시와 무관.
- **🔴 최우선 발견 — STALE 폐기본 trap**: `docs/legal/terms-of-service.md`·`privacy-policy.md`·`disclaimer.md` 는 **2026-04-09 폐기 초안**으로 자동매매·Alpaca·Supabase·AI채팅·이메일가입 등 **위법/허위 문구 12건 잔존**. 라이브 SoT 는 `frontend/src/content/terms-ko.md`·`privacy-ko.md`(v2.0-draft, 0건). **변호사에게 docs/legal/ 을 제출하면 틀린 자문을 받는다.** (실측: 폐기본 12 hit vs 라이브 0 hit / `/terms`·`/privacy` page.tsx 가 frontend/content 렌더 확인)
- **어제 H1~H4 fix 전부 착지 확정**(grep 실측): H1 Alpaca 출처 제거 ✅ / H2 "적중률" 0건 ✅ / H4 "월스트리트 애널리스트" 페르소나 제거 ✅.
- **최신 규제 fresh scan(1개월 공백 메움)**: 확정 델타 4건. 임박 시행 🔴 **D-47 전상법 §17(7-21)**. §101 면제 트랙 직접 위협 NO.
- **변호사 없이 가능한 잔여 코드 위생**: N1/N4 "Action Points" 제목(이미 부제로 중화·MED) / 처리방침 시행일 기입(베타게이트 해제 전) / STALE 폐기본 워터마킹.

심각도: 🔴 BLOCKER / 🟠 HIGH(확정 결함·강한 해석위험) / 🟡 MED(문구·해석 의존) / 🟢 LOW(완화됨)

---

## 1. 어제(06-03) H1~H4 fix 착지 검증 (메인 grep 실측)

| 항목 | 착지 | 증거 (file:line) |
|------|:---:|------|
| H1 earnings Alpaca 데이터출처 폴백 제거 | ✅ | `earnings_prebrief_service.py:1204,1212` `return "FMP · SEC EDGAR"`. Alpaca 문자열은 `_has_active_alpaca(user_id)` 게이트(723-731)만 잔존 = 정상 |
| H2 "적중률"(자사 forbidden 등록어) 정적 PDF 노출 | ✅ | `grep -rn "적중률" services/artifacts/` → **0건** (템플릿 3곳 + forbidden_terms + _i18n 전부 "일치율/Consistency") |
| H3 earnings Scenario "Action"→"Note"·"권장"→"대조 시점" | ✅ | 06-03 회귀 298 pass(어제 검증). 잔여 = Q-EP1(변호사) |
| H4 earnings AI "월스트리트 시니어 애널리스트" 페르소나 | ✅ | `grep "월스트리트\|애널리스트\|analyst"` earnings_prebrief_service.py → **0건** (중립 정보요약 도구로 교체 + `_is_compliant_question` canonical SoT 통일) |

→ **어제 작업 회귀 없음. 4건 전부 prod-safe 상태 유지.**

---

## 2. 신규 발견 (오늘)

### 2-1. 🔴 STALE 폐기본 trap — `docs/legal/*.md` (최우선)

- **위치** `docs/legal/terms-of-service.md`(2026-04-09, 초안) / `privacy-policy.md` / `disclaimer.md`
- **증거** terms-of-service.md: §4-1(바) "자동매매 주문 실행 도구" / §6 Premium "자동매매" / §9 "자동매매 서비스 특약 … Alpaca, KIS" / §13 위탁표 "Alpaca/Supabase" / §5 "이메일 주소 및 비밀번호 등록". **Alpaca·자동매매·Supabase grep = 12 hit.** 라이브 `frontend/src/content/terms-ko.md` = **0 hit.**
- **문제** 자동매매(2026-05-05 물리삭제, 투자일임업 회피)·Alpaca(2026-05-27 제거)·Supabase(미사용)·이메일가입(OAuth-only)·AI채팅(기본 OFF)이 전부 폐기된 사항인데 이 초안에 살아있음. **변호사 제출 또는 실수 게시 시: ① 존재하지 않는 기능을 유료로 약속(표시광고법 §3①) ② 자동매매 특약이 투자일임업 회피 결정과 정면 충돌 ③ 변호사가 틀린 전제로 자문.**
- **라이브 SoT 확정** `frontend/src/app/terms/page.tsx:39` = `src/content/terms-ko.md` ("single source of truth") / `privacy/page.tsx:37` = `privacy-ko.md`. docs/legal/ 은 **유저 비노출**(렌더 경로 아님) → 즉시 법규 위반은 아니나 **내부/변호사 혼동 trap**.
- **수정** docs/legal/*.md 3개 상단에 `> ⛔ DEPRECATED (2026-04-09 초안). 현행 = frontend/src/content/{terms,privacy}-ko.md` 헤더. 변호사 제출 시 라이브 frontend/content 원본만. (변호사 불요·코드 위생. legal agent 가 spawn_task 칩 발행함)

### 2-2. 🟡 N1/N4 — "Action Points" 제목 (이미 부제로 중화)

- **위치** `burn_rate.html:138`, `capital_allocation.html:173` — `<h2>Action Points · {persona}</h2>` (EN/KR 모두 "Action Points")
- **맥락 실측** burn_rate.html:140 부제 = "비용 관찰 항목입니다. 정보 제공 목적이며 거래 권유가 아닙니다 / not a solicitation to buy or sell" + governance "자기 거래 데이터 한정" + 내용 = 본인 거래비용/burn 관찰(증권 권유 아님). → **제목 어감만 directive, 내용·부제는 관찰형으로 이미 중화.**
- **법규** 자본시장법 §17/§101④ (어제 G2와 동일선상, MED GRAY)
- **수정** 제목을 부제와 일치("관찰 항목 / Observation Points")시키면 깔끔. 안전한 선택적 rename. **비차단.** (+ 사소 i18n: KR locale 분기도 "Action Points" 영문 출력 = 한글화 누락)

### 2-3. 🟡 처리방침 시행일 미확정 (PIPA §30)

- **위치** 라이브 `frontend/src/content/privacy-ko.md` — 시행일 "변호사 검토 후 확정" 상태 + DRAFT 워터마크
- **문제** PIPA §30 은 처리방침에 시행일 명시 요구. 현재 베타 게이트(307)로 유저 접근 제한이라 즉시 위반 아니나 **베타게이트 해제 = 유저 실접속 전 시행일·DPO 실명·DRAFT 제거 필수.**
- **수정** (변호사 형식 사인 후) 시행일 기입 + DRAFT 워터마크 제거 + terms §13 실주소/등록번호. → 베타 해제 직전 체크리스트.

### 2-4. 🟡 N3 insider_mirror "Mirror Backtest" KPI / Brevo §28-8 (기존 큐 매핑)

- N3 insider_mirror hit_rate 백테스트 라벨 = **Q-EP3** 기존(이미 "참고용·미래보장 아님" 고지, MED 잔존).
- Brevo(프랑스 사업자) §28-8 국외이전 GDPR 동등성 경로 + Sentry 조건부활성 사전고지 = **Q6 보강** 권고(신규 에스컬레이션 아님).

→ **신규 변호사 큐 에스컬레이션 0건** (전부 기존 Q6/Q7/Q11/Q15/Q-EP3 매핑 또는 코드 위생).

---

## 3. 최신 규제 fresh research (2026-05-10 ~ 06-04, 1개월 공백 메움)

> WebSearch/WebFetch 1차출처 + 날짜 실측. 훈련데이터 미인용. **§101 면제 트랙 직접 위협 NO.**
> 메모리: `regulatory_changes_2026-06.md`(05 승계). ⚠️ regulatory-monitor **cron INACTIVE**(미등록=공백 원인) → 재등록 권고.

### 확정 신규/변동 4건

| # | 규제 | 공포/시행 | 1차출처 | §101 | PivoxQuant 영향 |
|---|------|----------|---------|:---:|------|
| 1 | 정통망법 §50의9 매출 6% 과징금 | 공포 **3-31** / 시행 **2026-09-30** | [lawtimes 219136](https://www.lawtimes.co.kr/news/articleView.html?idxno=219136) · 217999 | NO | Pro/Premium 마케팅메일 직접대상. 매출0시 20억↓. 정기평가 2027-03-31 |
| 2 | PIPA 시행령 입법예고 (본법 10% 과징금) | 본법 시행 **9-11** / 입법예고 **6-01~7-13** | [hankyung](https://www.hankyung.com/article/2026060114091) · dataeconomy 35464 | NO | §28-8 국외이전(US 4사) 고지형식. 감경 ≤40%. 7-13 후 확정본 → privacy-ko 갱신 |
| 3 | 전상법 §17 가분 디지털콘텐츠 청약철회 | 시행 **2026-07-21 (D-47)** | [korea.kr 156641602](https://www2.korea.kr/briefing/pressReleaseView.do?newsId=156641602) · law.go.kr 009318 | NO | Pro/Premium 월구독 미사용분 환불 의무 가능. terms-ko §17 갱신(Stripe Live 전) |
| 4 | 금감원 AI 24h 핀플루언서 감시 가동 | 보도 **2026-04-28** | [newsis](https://www.newsis.com/view/NISX20260428_0003609045) · asiae | 간접 | 음성·자막 추출→위법/의심/정상 분류, 특사경. 양방향 단속 risk↑. AI_CHAT OFF 유지 |

### 임박 시행 D-day
- 🔴 **D-47 · 7-21** 전상법 §17 — 결제 OFF(503)라 즉시 BLOCKER 아니나 **Stripe Live 전 terms-ko §17 환불조항 갱신 필수**. (큐 Q-R1/Q15)
- 🟡 **D-99 · 9-11** PIPA 10% — 시행령 입법예고 7-13 종료 후 확정본 재스캔.
- 🟡 **D-118 · 9-30** 정통망법 §50의9 — 시행령 산정기준 추적.
- AI기본법 §31 = 시행 2026-01-22, **계도 1년+(2027-01-22까지 과태료 유예)** 확정. §31②(결과물표시)=구현 / §31①(사전고지)=Q-AI10 갭.

### 확인 불가 (OPEN — 추측 금지)
1. 자본시장법 시행령 36288호(시행 4-28) **§101 면제 요건 직접 변경 여부** (개정이유서 원문 미확보).
2. 정통망법 §50의9 시행령 **과징금 산정기준** 입법예고 일정.
3. 전상법 §17 **가분콘텐츠 환불 세부 시행령** 확정본.

### 변동 없음
자본시장법 §101 본문 개정 없음 · 신용정보법 §2 9의2 마이데이터 유권해석 변동 없음(KIS 단일계좌 NO) · 금소법 6대 판매원칙 변동 없음.

---

## 4. 컴플라이언스 BLOCKER 대시보드 (오늘 실측)

| # | 항목 | Status | 막는 주체 | 증거 |
|---|------|:---:|------|------|
| B-1 | 변호사 큐 89건 | 🔴 RED | 외부(CEO 미팅 미예약) | `legal_question_queue.md` status pending |
| B-2 | 통신판매업 신고 | 🔴 RED | 외부(CEO, ~45,000원) | `business_registration.md` 미신고. **무료=신고 불필요**(대가성 판매 아님), 유료 Stage-1 전 |
| B-3 | 정통망법 §50 opt-out 인프라 | 🟢 GREEN | 코드 완비 | migration 021 + email_opt_out/unsubscribe 54 hit |
| B-4 | AI 생성물 표시(DisclaimerBanner+AI라벨) | 🟢 GREEN | 코드 완비(§31① AMBER→Q-AI10) | `(dashboard)/layout.tsx:209` 전 대시보드 마운트 |
| B-5 | PIPA §28-8 마케팅 동의(cross_border) | 🟢 GREEN | 코드 완비 | migration 024 + LegalConsentModal |
| B-6 | 전상법 §17 청약철회 | 🟡 AMBER | 코드(무료 유예 명시)/변호사(유료) | `terms-ko.md` "유료 도입 시 신설" 명시. D-47 7-21 갱신 |
| B-7 | 금소법 §19 광고규제 어휘 | 🟢 GREEN | 0건 | "수익보장/전문가추천" 실질 true-positive 0 |

**Stripe kill-switch 무결성** ✅: `billing.py:68-124` `_stripe_enabled()` + `@billing_bp.before_request` 가 **모든** billing 라우트(webhook 포함) 503 차단. EXEMPT = `/subscription`(read-only)·`/availability` 2개. prod `/api/billing/availability`→available:false. ⚠️ **AMBER**: Railway `STRIPE_ENABLED=0` env 명시 설정 여부는 콘솔 직접 확인만 가능(grep 불가) — 단 미설정이어도 `TELESELLER_REGISTRATION_NUMBER` 없어 폴백도 차단.

**SHIP_BLOCKERS reconcile** ✅: 어제 M2(dd_checklist_email/brag_card_email 면책 누락) → A12(BLOCKED)/A13(PENDING) 정상 추적 등록.

---

## 5. 무료 Stage-0 출시 최종 판정

**GO** — 코드가 막는 BLOCKER 0. 약관 법문(legal)·PDF 아티팩트(legal-kr-fintech)·BLOCKER 대시보드(compliance-gatekeeper)·외부 규제(regulatory-monitor) 4-agent 전원 + 메인 grep 실측 합의. 어제 "코드 GO, 변호사만 남음" 결론이 오늘 약관 법리·신규 규제 관점에서도 유지·재확인됨.

남은 것 = **외부 의존만**: ① 변호사 의견서(89건, 유료 전환 BLOCKER) ② 통신판매업 신고(유료 전환 전) ③ 베타게이트 해제 전 처리방침 시행일·DRAFT 제거(변호사 형식 사인).

---

## 6. CEO 액션 (우선순위)

1. **⚠️ 변호사 미팅 시 `docs/legal/*.md` 제출 금지** — 라이브 `frontend/src/content/terms-ko.md`·`privacy-ko.md` 만. (docs/legal/ 워터마킹 칩 발행됨 / 원하면 즉시 적용 가능)
2. **regulatory-monitor cron 재등록** — INACTIVE 확인됨(1개월 공백 원인). `docs/REGULATORY_MONITOR_ACTIVATION.md`. 재발방지.
3. **Railway `STRIPE_ENABLED=0` 콘솔 명시 확인** (AMBER 해소).
4. **(Stripe Live 전) terms-ko §17 환불조항 갱신** — 전상법 §17 D-47(7-21). 무료 출시엔 무관.
5. **(베타 해제 전) 처리방침 시행일·DPO 실명·DRAFT 제거** — PIPA §30.
6. 변호사 큐 89건 + 통신판매업 신고 = 유료 Stage-1 전환 선결.

---

## 7. 변호사 큐 변동
- **신규 1건**: Q-R1(전상법 §17 가분콘텐츠 D-47 = Q15 우선순위 상향). 누적 **88→89건**.
- **라벨 정정**: 06-03 audit §7 권고 "Q-R1 양방향채팅"·"Q-R2 §31①" 은 별도 추가 안 됨(각각 Q13·Q-AI10 흡수). 오늘 Q-R1 = 전상법(중복 아님) — 큐에 메모.
- Q6 보강 권고(Brevo 프랑스 §28-8 / Sentry 조건부 사전고지).

---

## 8. agent telemetry
- legal-kr-fintech(130k tok, 문서·PDF 전수 + H1~H4 검증 + N1~N6) · legal(123k, 약관 법문 + STALE trap 확정) · compliance-gatekeeper(59k, 7-BLOCKER 대시보드 + Stripe 게이트) · regulatory-monitor(82k, fresh 규제 4델타 + cron INACTIVE)
- 메인 실측 검증: H1/H2/H4 grep 착지 · 라이브 SoT 스왑 · 폐기본 12vs0 hit · N1 맥락 · 큐 편집 정리.
- **내부 참고용 · 법률자문 아님.** 🔴/🟠 항목은 변호사 사인 또는 코드 수정 후 재감사.
