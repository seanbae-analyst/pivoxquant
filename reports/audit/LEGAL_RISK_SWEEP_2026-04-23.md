# LEGAL RISK SWEEP — 2026-04-23

**Auditor**: Legal Agent (김앤장 기준 법률 검토 시뮬레이션)
**Scope**: 이번 세션 13 commits 반영 후 전 방위 법적 리스크 + 사실 오류
**Status**: READ-ONLY audit. Fix 금지. Push 금지.
**Disclaimer**: 본 문서는 변호사 자문이 아닌 내부 사전 검토. 외부 공개 전 로펌 확인 필수.

---

## 1. Executive Summary

이번 세션에서 Living CFO 4-Layer + Journal Companion + 8 페르소나 PDF 분기 + 랜딩 V2 + Hero v4 cinematic + Dashboard Layer 4 가 대거 투입됐고, 법적 방어선(legal_filter 89 + legal_gate 20 + triple disclaimer + audit log)은 이전 세션 대비 **강화된 구조**로 자리 잡았다. 대부분의 신규 카피는 "observational", "not advice" framing 을 유지했다.

그러나 아래 **Critical 3건 + High 6건** 이 존재한다:

| 구분 | 건수 | 요약 |
|------|------|------|
| 🔴 Critical | **3** | dd_checklist AAPL 하드코딩 / Feature 페이지 13개 중 disclaimer 0건 / legal-guard YML 허점 |
| 🟠 High | **6** | daytrader partial 內 "매수" 단어 / legal_filter 89 regex 누락 한글 패턴 / data_bridge 주석-실제 불일치 / Privacy draft 미적용 / DRAFT_TERMS draft 상태 프로덕션 미반영 / persona partial 단위 legal_filter 미통과 검증 부재 |
| 🟡 Medium | 4 | Cookie consent companion 갱신 / /companion page 내 Closed Beta 라벨 가시성 / waitlist 테이블 schema 미확인 / 한글본 우선 선언 terms/page.tsx 실제 반영 여부 |
| ✅ OK | 다수 | Journal Companion HARD rules / audit_logger sha256 / legal_gate 20 advice regex / 페르소나 8 overlay .md 본문 / broker 안전장치(Alpaca paper=True, KIS read-only) |

**최악 시나리오**: dd_checklist 가 NVDA/삼성전자 유저에게 "AAPL $94.9B 매출" 숫자를 그대로 담은 PDF 를 발송하는 경우 — 자본시장법 §55(설명의무) 위반 + 자본시장법 §178(부정거래 금지·허위표시) 저촉 + 공정위 전자상거래법 §21(기만적 표시) 3중 리스크.

---

## 2. 카테고리별 발견 사항

### 2.1. 자본시장법 리스크 (legal_filter 89 regex + 실전 카피)

**✅ OK 사항**
- `services/legal_filter.py` 89 패턴 (Group 1~9) — 정교한 surgical 치환 설계. `Suggest`/`Optimize`/`Should`/`Must` 단독 패턴에 lookahead 로 방어 부정 문맥 제외 로직까지 적용.
- `services/agents/legal_gate.py` 20 advice-pattern + 재사용 89 regex 로 이중 필터 구조.
- `frontend/src/components/ui/disclaimer-banner.tsx` 3종(signal/ai/analysis) 한글 disclaimer 포함 — "매수 또는 매도를 권유하는 것이 아닙니다" 명시.
- `/pricing/page.tsx:101-102` "do not solicit or recommend the purchase or sale" 선언.

**🟠 High — 한글 자문성 패턴 누락**

`services/agents/legal_gate.py` ADVICE_PATTERNS 의 한글 버전 검토 결과:
- 포함: 매수, 매도, 매입, 익절, 손절, 진입, 청산, 추천, 권장, 권유, 조언, 유망, 좋은, 나쁜
- **누락**: `가능성이 높은`, `가능성 높은`, `주목할`, `지켜볼`, `눈여겨볼`, `기대되는`, `매력적인`, `저평가`, `고평가`, `매도세`, `매수세`, `bullish`(단독 — 이미 legal_filter 에는 있음), `promising`, `worth a look`, `worth watching`, `attractive`(단독)

→ legal_filter 에는 bullish/promising 일부 있지만 legal_gate.py 고유 검사에는 없음. 이중 검사(legal_filter + legal_gate) 구조이므로 legal_filter 만 커버하면 OK 인지 아키텍처 재확인 필요. `legal_gate.py:207` 에서 `detect_prohibited` 호출로 재사용은 하지만, `detect_prohibited` 는 **_PROHIBITED_PATTERNS 6건만** 검사(목표가/예상수익률 등 숫자). 89 regex 치환은 호출하지 않음. **즉, legal_gate.py 는 _PROHIBITED_PATTERNS 6 + ADVICE_PATTERNS 20 = 26 건만 검사 중**.

증거:
- `services/legal_filter.py:153-160` — `_PROHIBITED_PATTERNS` 6건
- `services/legal_filter.py:202-210` — `detect_prohibited` 는 `_PROHIBITED_PATTERNS` 만 iterate
- `services/agents/legal_gate.py:207` — gate 에서 호출하는 건 `detect_prohibited`, 전체 89 regex 가 아님

**리스크**: Journal Companion 이 "이 종목은 유망해 보여요" / "지켜볼 만합니다" 출력 시 **두 레이어 다 통과**. T5 refusal 가드는 작동하지만 LLM 이 예상치 못한 응답 생성 시 방어선 뚫림.

**권고**: `legal_gate.py:207` 을 `detect_prohibited + scrub_text_has_changed` 이중 검사로 변경 (scrub 전후 비교하여 변경 있으면 deny).

---

### 2.2. dd_checklist AAPL 치명 하드코딩 (Critical #1)

**증거** — `services/artifacts/templates/dd_checklist.html`:

| Line | 하드코딩된 값 | 영향 |
|------|--------------|------|
| 382 | `{% set _kpi_ticker = ticker \| default('AAPL') %}` | ticker param 없으면 모든 유저가 AAPL 카드 수신 |
| 465 | `Operating Margin · 0.88 · '30.2% · TTM'` | 업종 불문 AAPL 숫자 |
| 466 | `Return on Equity · 0.92 · '154% · TTM'` | AAPL 154% ROE 고정 |
| 467 | `FCF Yield · 0.62 · '3.4% · TTM'` | AAPL 고정 |
| 657 | `'5Y revenue CAGR 6.1%. Positive in 4 of 5 years.'` | 체크리스트 답변 하드코딩 |
| 660 | `'TTM op. margin 30.2% vs sector median 22.4%.'` | 사실과 다르게 표시 가능 |
| 740 | `quarterly_label \| default('$94.9B · Q4 FY25')` | AAPL 분기 매출 $94.9B |
| 762 | `margin_label \| default('46.2% · 30.2% · 24.4%')` | AAPL 마진 |
| 794 | `fcf_label \| default('$99.8B · FY25')` | AAPL FCF |
| 795 | `fcf_history \| default([73.4, 80.2, 92.9, 96.4, 99.8])` | AAPL 5Y FCF 시계열 |
| 819 | `peer_label \| default('28.4 · 32.1 · 24.8 · 26.2')` | AAPL·MSFT·GOOG·META P/E |
| 821-824 | `peer_bars` 하드 | 4 종목 |

**Renderer 동작 시나리오 (최악)**:
1. 유저 A (NVDA 관심) → NVDA 로 dd_checklist 생성
2. Backend renderer 가 FMP 에서 NVDA 펀더멘털 fetch 실패 → `ticker` 는 전달되지만 axes/quarterly_revenue/fcf_history/peer_bars 등 미전달
3. Jinja `| default(...)` fallback → **AAPL 숫자 그대로 렌더**
4. PDF 표지엔 "NVDA DD Checklist" 라 찍혀있지만 내부 숫자는 전부 AAPL
5. 유저가 이 데이터 근거로 NVDA 매매 판정 → 손실

**법령 저촉**:
- 자본시장법 §55 (설명의무 위반) — 정보 제공 서비스라도 "허위/오인 소지" 표시는 위반
- 자본시장법 §178 (부정거래행위 금지) — "중요한 사항에 관하여 거짓의 기재 또는 표시" 포함
- 공정거래법 §3조 표시광고법 §3 (기만적 표시·광고)
- 민법 §750 (불법행위) — 손해배상 청구 근거

**권고 (즉시 fix)**:
- **Phase 1 (≤1일)**: 모든 `| default(...)` 에서 샘플 데이터 **제거**. context 미전달 시 `—` (emdash) 표시 + "데이터 미제공" 배너 렌더.
- **Phase 2 (≤1주)**: `edgar_service.py` + `fmp_service.py` 로부터 ticker 별 동적 fetch 주입. 최소 14개 필수 필드(완성도/redflags/review_date/axes 5개/quarterly_revenue 8Q/margin 3종/fcf 5Y/peers 최소 3 종목) 계약화.
- **Phase 3**: 필수 필드 누락 시 PDF 생성 거부 + 404 반환.

**우선순위**: 🔴 **최우선** — 다음 세션 Line 382, 463-469, 655-686, 740, 762, 794-795, 819-824 전부 수정.

---

### 2.3. Journal Companion 법적 경계 (재검증)

**✅ OK — 설계 매우 견고**
- `services/agents/prompts/companion_system.md` HARD rules 완전 — 28개 금지어 명시(L30-33), T1-T6 템플릿 한정 어휘, footer 강제(L37-38).
- "When in doubt → T5" iron rule 명시(L154).
- `services/agents/legal_gate.py` T5 refusal fallback 안전 기본값, `AGENT_ENABLED=0` kill switch.
- `services/agents/audit_logger.py` sha256 해시만 저장 — 원문 미저장. 2년 retention + purge_after 인덱싱.

**🟠 High — legal_gate.py ADVICE_PATTERNS 누락**

재검토 결과 20 패턴 중 누락 고위험:
1. 영문 "worth a look" / "promising" / "attractive" — 4.7행에는 없음 (legal_filter Group 7 에는 일부 있음, 하지만 gate 는 재사용 안 함)
2. 한글 `수익률이 좋을`, `전망이 밝은`, `반등 시`, `돌파 시`, `눈여겨볼`, `지켜볼`, `흐름이 좋은`
3. 영문 `look(s) attractive`, `looks strong`, `looks weak` (evaluation 형이지만 thesis-evaluation 패턴은 `good/bad/weak/strong X` 조합만 잡음)

**✅ OK — 페르소나 overlay 8개**
- `services/agents/prompts/persona/*.md` 8 파일 grep 결과 — "유망/추천/조언/권유" 0건. 모든 파일 하단에 footer 재강제 문구 있음.
- 단, `balanced.md:22` "리밸런싱 임계치", `income.md:23` "배당 커버리지" 등은 **factual term** 으로 사용되므로 문제 없음.

**🟠 High — 페르소나 PDF partials**

`services/artifacts/templates/partials/daytrader/data_focus.html:17`:
```
<span class="pq-signal-val">상위 3 종목 매수 방향 우세 관찰</span>
```

"매수 방향 우세 관찰" — 표현상 "관찰" 이 붙어 있어 directive 가 아니지만:
- `legal_gate.py:48` 의 패턴 `(매수|매도|매입|익절|손절|진입|청산)(하|하세|하시|할)` 는 매치 X (뒤에 "하" 안 붙음 → 통과)
- `legal_filter.py` Group 2 의 `매수\s*(권고|권장|추천)` 도 매치 X (권고/권장/추천 안 붙음 → 통과)

→ **이중 필터 둘 다 통과하는 회색 영역**. 유저에게 "매수 방향" 이 표시되면 자문성 해석 여지 있음.

**권고**: 해당 라인을 `"상위 3 종목 주문 흐름 방향성 관찰"` 또는 `"상위 3 종목 ask→bid 흐름 우세 관찰"` 로 변경.

---

### 2.4. 페르소나 PDF 분기 법적 경계

**검증 결과** — `services/artifacts/templates/partials/{growth,value,balanced,income,quant,speculator,daytrader,beginner}/` 각 3파일(opener/data_focus/risk_block) 총 24개 fragment:

**🟢 OK**
- `balanced/risk_block.html` "Rebalance Thresholds" — legal_filter Group 8 `리밸런싱` 은 매치하지만 `services/legal_filter.py:117` 의 lookahead `(?!하지\s*않|하지\s*맙)` 통과 → 치환 대상. 하지만 partial 은 렌더 시점이 아니라 **문자열 템플릿 시점**이므로 legal_filter 가 작동하지 않을 가능성.
- `_persona_macros.html:171/173` "비교 지수" — benchmark 리스트 factual.

**🟠 High — legal_filter 커버리지 체인 확인 필요**

`services/legal_filter.py` 의 scrub 함수는 **AI 생성 텍스트의 응답 boundary** 에 호출되도록 설계 (docstring L14-18). 그런데 페르소나 partials 는 Jinja 가 서버에서 렌더링하는 **정적 템플릿**. 그 출력물이 PDF 되기 전 legal_filter 통과하는지 확인되지 않음.

현재 상태: **legal-guard.yml** 은 템플릿 파일을 `services/` 에 포함시켜 grep 하지만, YML 은 "매수하세요|매도하세요|추천합니다|조언드립니다" 4 phrases 만 검사. "매수 방향 우세" 류 통과. CI 가 이 문제를 잡지 못함.

**권고**:
- pre-render hook 에서 Jinja 출력물을 `safe_scrub()` 통과 → 다음 PDF 빌드 파이프라인에 주입
- legal-guard.yml 에 templates/ 디렉터리 대상 추가 grep 규칙 (`매수\s+(방향|우세|흐름)`, `매도\s+(방향|우세|흐름)`) 추가

---

### 2.5. 개인정보 리스크 (PIPA)

**✅ OK**
- `services/agents/audit_logger.py` — sha256 해시 only, raw 메시지 저장 X. length prefix 로 collision 방어. (L28-42)
- `services/agents/data_bridge.py` docstring L8-15 — "Ticker symbols NEVER leave this module. Sectors only." 선언.
- Sector bucket 5 종 + amount bin 4 종 coarse 화 (L170-218). KRW 환산에 `1400` 고정 fallback 사용.
- PIPA §16 데이터 최소화 원칙 충족 구조.
- `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.1-9.11` — PIPA §15/§16/§17/§18/§21/§23/§26/§28-8/§29/§30/§35-37/§39-8 상세 매핑. 구조적으로 견고.

**🟠 High — 주석과 실제 구현 불일치 (data_bridge.py)**

docstring (L12) "Ticker symbols NEVER leave this module" 선언했지만:
- `load_journal_entries` (L70-123) — 일지 원문(2000 자까지) 그대로 payload 에 포함. docstring L17 "Raw journal text IS included verbatim" 로 **정반대 기술**.
- `_journaled_tickers_for` (L363-394) — journal 원문에서 2~5자 대문자 토큰 → 티커로 추정.

**법적 해석**: 이용자가 자발적으로 일지에 "NVDA 를 500주 샀다. 평균단가 100달러" 썼다면, 그 원문이 **Anthropic API 로 그대로 전송**. `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.4` 에 위탁 공개 명시했지만, "가명화된 payload (실명/이메일/계좌번호 제외)" 문구와 **일지 원문에 이용자 스스로 기재한 티커/가격** 은 모순되지 않음 — 단, 이용자 원문 동의 vs. 시스템 가명화 invariant 간 logical tension 존재. 로펌에 **명확화 질의** 필요.

**권고**:
- data_bridge.py docstring L12 "Ticker symbols NEVER leave this module" → "**System**-generated ticker references never leave. User-authored text IS forwarded (user-generated content, covered by separate consent §9.4)" 로 정정
- 이용자가 티커를 일지에 쓰는 행위에 대한 warning 팝업 — 프론트 `/journal` UI 추가 권고

**🟡 Medium — localStorage Companion history**

`frontend/src/lib/cfo/useCompanion.ts:77-115`:
- `LS_KEY_HISTORY` 로 대화 원문 localStorage 저장.
- 유저 자발적, server 미전송.

PIPA 관점: 이용자 단말 저장은 PIPA 적용 대상 아님 (§2조 "처리" 정의가 "개인정보파일" 전제). 그러나 `DRAFT_PRIVACY_POLICY §9.5` 에 "단말 로컬 저장(localStorage)을 이용한 이용자 편의 기능" 언급 없음 — **고지 의무 충족** 권고.

---

### 2.6. 신규 페이지 disclaimer 커버리지 (Critical #2)

**🔴 Critical — 13개 features 페이지 중 disclaimer 0건 확인**

`/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/features/` 하위 디렉터리:
```
ai-assistant  canslim  dashboard  engine  explorer  global-desk
paper-trading  personas  pre-trade  profiles  quant-scoring  reports
risk-defense
```

Grep 결과:
- `advice` 문자열: **0건** (ai-assistant, profiles, paper-trading, quant-scoring 포함 전부 0)
- `disclaimer|DisclaimerBanner|FootSignature|Observational`: 13 건 (5 파일) — 대부분 metadata description 에 산재
- 실제 하단 면책 배너 컴포넌트 렌더: **0건 추정** (grep 결과 없음)

**CLAUDE.md L51 선언**: "DisclaimerBanner — 모든 분석/시그널 페이지에 면책 배너 필수"
**legal-guard.yml L80-93**: dashboard 하위 페이지에만 DisclaimerBanner 검사 — features/ 미커버.

**법령 저촉**:
- 자본시장법 §57 (투자광고 규제) — 특정 상품을 "Quant Scoring", "CANSLIM Screener" 로 홍보하면서 면책 고지 미표시 → **투자광고 규칙 위반 가능**
- 금융투자협회 투자광고 규정 §4 (면책 문구 의무 표시)

**권고 (즉시)**:
1. 13개 features 페이지 전부 하단에 `<FootSignature note="..."/>` or `<DisclaimerBanner/>` 추가
2. `legal-guard.yml` Disclaimer coverage check 범위 확장: `frontend/src/app/features/*/page.tsx` 추가

---

### 2.7. 외주/위탁 법적 구조

**✅ OK**
- Anthropic Claude API 위탁 — `DRAFT_PRIVACY_POLICY §9.4` PIPA §26/§28-8 매핑 완료.
- DPA(Data Processing Agreement) 필수 조항 4종 명시(보안 수준 / 재위탁 금지 / 침해 72시간 / 모델 학습 금지).

**🟡 Medium — 실제 Anthropic DPA 체결 상태 미확인**
draft 에는 "DPA 링크 별도" 언급되나 실제 계약서 첨부/링크 없음.

**권고**: Anthropic Enterprise/API DPA 체결 → 문서 링크 삽입. 무료 API tier 는 DPA 별도 요청 필요 — 로펌 검토 대상.

**✅ OK — 외부 API 개인정보 미포함**
- FMP / Alpaca / KIS / Alpha Vantage / Naver: ticker/price/volume 만 요청 — PIPA 적용 대상 아님 (개인정보 X)
- Google / Kakao OAuth: 최소 scope (email/name only) 가정 — **확인 필요**

---

### 2.8. 약관/방침 DRAFT 최종 점검

**✅ OK**
- `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md` §9.1~9.11 PIPA §30 필수 항목 11종 충족:
  1. 수집 항목 ✓ 2. 목적 ✓ 3. 보유기간 ✓ 4. 제3자 처리위탁 ✓ 5. 민감정보 ✓
  6. 이용자 권리 ✓ 7. DPO(권고) ✓ 8. 안전성 조치 ✓ 9. 자동수집장치(cookies) ✓
  10. 침해 신고 ✓ 11. 변경 고지 ✓
- `DRAFT_TERMS_AI_CLAUSE §7-§14` — 자본시장법 §6/§9/§11/§101, 약관규제법 §7, 민법 §393/§750 근거 매핑.

**🟠 High — Draft 실제 프로덕션 미반영**

`frontend/src/app/terms/page.tsx` / `frontend/src/app/privacy/page.tsx` 가 draft 반영했는지 확인 필요. draft 헤더에 "프로덕션 반영 금지" 명시 → 현재 프로덕션 terms/privacy 는 **Journal Companion 조항 없는 구버전** 가능성.

**권고**:
- 로펌 검토 후 terms/page.tsx 에 §7-§14 신규 조항 삽입 필요
- 삽입 완료 전까지 `/companion` 페이지 Closed Beta 플래그(AGENT_ENABLED=0) 유지

**🟡 Medium — Severability + Governing Language**
- draft `§14 Governing Language` 한글본 우선 선언 → 기존 terms/page.tsx 가 영문 단일이라면 inconsistent. 기존 것도 한글 병기로 확장 권고.

---

### 2.9. GitHub Actions legal-guard.yml 검증

**✅ OK 한 부분**
- `en_hits` regex: `\b(should\s+(buy|sell)|recommend(ed|ing|s)?|give[s]?\s+investment\s+advice)\b` 와 방어 부정 exclude.
- `disclaimer` 파일 / `signup` / `pricing` consent 는 exclude.
- dashboard 페이지 DisclaimerBanner 검사.
- Broker safety: KIS_READ_ONLY, Alpaca paper=True 검사.
- Signal literal BUY/SELL/HOLD 리터럴 검사 (routes/services python).

**🔴 Critical #3 — 범위 + 패턴 허점**

| 허점 | 영향 |
|------|------|
| `frontend/src/app/features/*/page.tsx` DisclaimerBanner 검사 누락 | Critical #2 와 직결 — 13 신규 페이지 미커버 |
| kr_hits 패턴이 `매수하세요\|매도하세요\|추천합니다\|조언드립니다\|이\s*종목을\s*사세요` 5 phrases 에 국한 | "매수 방향", "매수세 강함", "매수 타이밍" 등 미커버 (legal_filter 에는 있지만 CI guard 는 이들 없음) |
| `services/artifacts/templates/**/*.html` grep 범위 미포함 (`--include='*.py' --include='*.tsx' --include='*.ts' --include='*.md'`) | daytrader partial 의 "매수 방향" 통과 |
| `services/agents/prompts/persona/**/*.md` 는 md 이므로 일부 커버되나 en_hits 에 md 미포함 (tsx/ts/py 만) | 페르소나 overlay 영문 누락 어휘 미검출 |
| legal_gate.py 의 20 패턴은 CI 가 **호출 검증** 안 함. 런타임에만 검사. | Journal Companion deploy 시점 정적 검사 부재 |

**권고**:
1. legal-guard.yml `grep --include` 에 `*.html` 추가 (templates/ partials 커버)
2. kr_hits 에 `(매수|매도)\s*(방향|우세|타이밍|세|구간)` 추가
3. features/ 페이지 DisclaimerBanner 검사 확장
4. Python unit test 를 CI 에 추가하여 `legal_gate.run_gate()` 와 샘플 prompts 회귀 검증

---

## 3. Top 10 즉시 Fix 항목

| # | 우선순위 | 항목 | 파일 | 예상 공수 |
|---|---------|------|------|----------|
| 1 | 🔴 Critical | dd_checklist AAPL 하드코딩 제거 (Phase 1) | `services/artifacts/templates/dd_checklist.html` L382, 463-469, 655-686, 740, 762, 794-795, 819-824 | 2h |
| 2 | 🔴 Critical | 13 features 페이지 DisclaimerBanner 추가 | `frontend/src/app/features/{canslim,dashboard,engine,explorer,global-desk,pre-trade,personas,reports,risk-defense,ai-assistant,profiles,paper-trading,quant-scoring}/page.tsx` | 3h |
| 3 | 🔴 Critical | legal-guard.yml features/ 범위 확장 + html/md 포함 + kr 패턴 추가 | `.github/workflows/legal-guard.yml` | 1h |
| 4 | 🟠 High | legal_gate.py detect_prohibited → scrub_text 전후 비교로 전환 (89 regex 전수 검사) | `services/agents/legal_gate.py:207` | 2h |
| 5 | 🟠 High | daytrader data_focus "매수 방향 우세" → "주문 흐름 방향" | `services/artifacts/templates/partials/daytrader/data_focus.html:17` | 10min |
| 6 | 🟠 High | data_bridge.py docstring 정정 (user-generated content 명시) | `services/agents/data_bridge.py:8-18` | 15min |
| 7 | 🟠 High | DRAFT_TERMS §7-§14 프로덕션 terms/page.tsx 반영 (로펌 승인 후) | `frontend/src/app/terms/page.tsx` | 로펌 의존 |
| 8 | 🟠 High | DRAFT_PRIVACY §9.1-§9.11 프로덕션 privacy/page.tsx 반영 (로펌 승인 후) | `frontend/src/app/privacy/page.tsx` | 로펌 의존 |
| 9 | 🟡 Medium | Cookie Consent 정책에 Journal Companion audit 로그 추가 | (구현 파일 미탐색 — 검증 필요) | 1h |
| 10 | 🟡 Medium | legal_gate.py ADVICE_PATTERNS 한글/영문 누락 어휘 확장 (`유망/가능성/지켜볼/promising/attractive`) | `services/agents/legal_gate.py:38-107` | 1h |

---

## 4. 로펌 제출 시 반드시 포함할 추가 자료

1. **dd_checklist.html 현재 코드 + Phase 1 fix 커밋** — 허위 정보 제공 리스크 실체 증명.
2. **legal_gate.py detect_prohibited 6 regex 전체 목록** + `shared-legal-filter` 호출 체인 설명.
3. **Journal Companion 샘플 출력물 200건** — T1~T6 각 분류별 25건 씩, gate verdict 포함.
4. **Anthropic DPA 초안 또는 체결본** — PIPA §28-8 국외이전 근거.
5. **Transfer Impact Assessment (TIA) 문서** — Anthropic PBC 미국(California) 이전의 적정성 평가.
6. **persona partial 24 파일 전체 snapshot** (legal 리뷰 sign-off 대상).
7. **legal_filter.py 89 regex 전수 테스트 케이스** — 각 패턴별 True Positive / False Positive 예시 3건.
8. **audit_logger sha256 저장 구조 DB 스키마** — `user_agent_audit` 테이블 DDL + 인덱스.
9. **localStorage 사용 범위 + 이용자 고지 방식** — `useCompanion.ts` LS_KEY_HISTORY / LS_KEY_DISCLAIMER_ACK 설명.
10. **유사투자자무업 신고번호** (획득 전이면 "신청 진행 중" 상태 공문).
11. **Kill switch(`AGENT_ENABLED=0`) 운영 가이드** — 장애/위반 감지 시 1-click 차단 절차.

---

## 5. GitHub Actions 자동 검증 Gap (수동 추가 필요)

| 항목 | 현재 | 필요 |
|------|------|------|
| features/ DisclaimerBanner 검사 | ❌ 미커버 | ✅ `frontend/src/app/features/**/page.tsx` 추가 |
| templates/*.html 자문성 어휘 | ❌ 미커버 | ✅ `--include='*.html'` 추가 + "매수/매도 + (방향/우세/타이밍/세/구간)" 패턴 |
| 페르소나 overlay .md 영문 자문성 | ❌ 미커버 | ✅ `services/agents/prompts/**/*.md` 에 영문 `recommend\|advise\|suggest` 검사 |
| Journal Companion unit test 회귀 | ❌ 없음 | ✅ `pytest services/agents/ -k legal_gate` CI job 추가 |
| Anthropic API payload 실제 pseudonymization 검증 | ❌ 수동 | ✅ `test_data_bridge_pseudonymization.py` 에 실명/계좌/이메일 검사 assertion |
| DPA 링크 유효성 (URL 200 OK) | ❌ 미연결 | ✅ privacy/page.tsx 의 "Anthropic DPA" 링크 주간 canary |
| Kill switch 기본값(`AGENT_ENABLED=0`) 회귀 | ❌ 없음 | ✅ `.env.example` diff 가드 + `config.py` default grep |
| dd_checklist 등 artifact 템플릿 하드코딩 검사 | ❌ 없음 | ✅ `templates/*.html` 에서 `\| default\(.+[0-9]+.+\)` 패턴 감지 |

---

## 6. 최종 판정

### 판정 요약
- ✅ **CLEAR**: Journal Companion 핵심 설계 (system prompt + gate + audit) / broker read-only / legal_filter 89 regex / 2 DRAFT 약관·방침 구조.
- ⚠️ **RISK**: persona PDF partials 자문성 회색 영역 / legal_gate detect_prohibited 범위 협소 / DRAFT 미반영 상태로 프로덕션 운영.
- ❌ **BLOCKED (즉시 fix 전까지)**:
  - **dd_checklist.html 하드코딩** → 허위 사실 제공 리스크, 타 종목 유저 수신 시 자본시장법 §178 + 표시광고법 §3 3중 저촉 가능.
  - **13 features/ 페이지 disclaimer 누락** → 자본시장법 §57 투자광고 규제 위반 가능.
  - **legal-guard.yml 범위 허점** → 차기 feature add 시 동일 사태 반복 구조.

### 변호사 검토 필요 여부
- [x] **필수** — 다음 3건은 프로덕션 런칭 전 김앤장 또는 동급 금융규제 전문 로펌 검토 필수
  1. DRAFT_TERMS §7-§14 불공정약관규제법 §6-§9 저촉 여부
  2. DRAFT_PRIVACY §9.4 Anthropic 국외이전 TIA 적정성
  3. 유사투자자문업 신고 신청서 + Journal Companion 기능 범위 정합성

### 본 감사의 한계
- Bash 권한 일부 거부로 파일 읽기 기반 정적 검사로 진행. 런타임 동작(실제 PDF 렌더, API 응답, 모델 payload) 은 **검증하지 못함**.
- 데이터베이스 스키마(user_agent_audit, companion_waitlist) DDL 직접 확인 못 함. migration 파일 추적 필요.
- 동시 작업 중인 3 agent (QA/API/Security) 결과와 교차 검증 필요. 특히 Security agent 가 localStorage/cookie 영역 중복 검토 중.

---

**작성자**: Legal Agent (PivoxQuant 법무부) · 김앤장 기준 시뮬레이션
**리뷰 대상**: CEO (배상현) / 외부 로펌 (변호사 선임 후)
**다음 세션 필독**: Top 10 §3 항목 우선순위 순 반영, Critical 3건 (#1, #2, #3) 은 다음 commit batch 에 포함.
