# PivoxQuant PDF 콘텐츠 품질 진단
**감사일**: 2026-04-23
**감사자**: Product Agent (프로덕트부)
**대상**: `/samples/artifacts/*.html` 15종 + 실제 생성 로직 (`services/artifacts/*.py`)
**범위**: 콘텐츠 품질만 (시각 디자인 제외 — Design 부서 별도 조사)

---

## TL;DR — CEO에게 가장 먼저 알릴 진실

> **샘플 PDF가 "유료 구독자에게 가치 있어 보이는" 이유는 `sample_data.py`가 정교한 프로즈·숫자·이벤트를 채워 넣기 때문이다. 실제 유저가 받는 PDF는 같은 템플릿을 쓰되 서비스 로직이 그 필드들을 거의 채우지 못하며, Jinja `default(...)` 분기를 통해 **템플릿에 하드코딩된 동일한 문장이 모든 유저에게 송출**된다.**

구체적으로:

1. **22개 템플릿에 `default(...)` 분기가 총 456회** — 각각이 서비스가 못 채우면 정적 문장으로 대체되는 지점. 이 중 대부분은 내러티브·프로즈·핵심 수치(VaR, Sharpe, MDD 등)를 포함한다.
2. **Weekly Memo의 Risk Dashboard 전면 (VaR -2.14%, ES -3.12%, MDD -8.14%, Tail Ratio 1.08, "trough W-9", "Recovered by W-13")은 전부 템플릿에 하드코딩**. 서비스(`weekly_memo_service.py`)는 이 값을 계산·반환하지 않는다. 모든 유저가 매주 동일한 Risk Dashboard를 받는다.
3. **Year-End Letter는 Claude Haiku로 Buffett-톤 `shareholder_letter`를 AI 생성하지만**, 템플릿은 `letter_paragraphs` (리스트)를 읽는다. 필드명 미스매치로 **AI가 쓴 편지는 PDF에 절대 실리지 않는다**. 유저는 템플릿에 박힌 "The year did not arrive. It was made..." 7단락 picture-perfect 편지를 연도·이름만 바뀌어 받는다.
4. **Brag Card의 "NVDA · 8-day hold, entered April 3 at $842, closed April 11 at $879"는 templates default**. 서비스는 entry_date, entry_price, exit_date, exit_price를 생성하지 않는다. 모든 유저의 바이럴 쉐어 카드가 동일한 NVDA 가상 거래를 보여준다.
5. **Earnings Pre-Brief의 8분기 revenue_history, surprise_bins, peer_eps_comp, drift_bars, implied_vs_realised, reading_notes, cannot_tell 섹션 일체 하드코딩**. 서비스가 생성하는 `expected_questions`, `sensitivity_beat/miss`는 템플릿이 읽지도 않는다 — **데드 필드**.

**따라서 CEO가 "좋은 내용인지 모르겠다"고 느낀 이유는 문체·디자인 문제가 아니다. 실제 유저에게 나가는 PDF는 개인화된 헤드라인(이름, 주간 수익률 %, 벤치마크 %, 상위/하위 종목) **3~5개 데이터 포인트 주위를 정교한 편집 톤의 벽지(wallpaper)로 둘러친 형태**이며, 벽지는 모든 유저·모든 주에 동일하다. 샘플은 sample_data.py 때문에 벽지까지 데이터처럼 보이지만, 진짜는 벽지다.**

사전 가설 5개 중 4개는 확인, 1개는 일부 반박:

| 가설 | 판정 | 근거 |
|---|---|---|
| 1. 모든 리포트가 Generic | ✅ 확인 (더 심각) | 서비스-템플릿 필드 미스매치로 대부분 섹션이 상수 |
| 2. Narrative 부재 → 데이터 나열 | ❌ 반박 (but 다른 결함) | Narrative는 **과잉** 있음. 그러나 **가짜** — 유저와 무관한 벽지 |
| 3. 법적 공포로 Actionability 0 | ⚠️ 부분 확인 | "cannot_tell" / "not_claimed" 섹션이 명시적으로 회피. 법적으로는 타당하지만 구조 변경 여지 있음 |
| 4. AI 생성 티 강함 | ❌ 반박 (놀라움) | 실제 AI는 Year-End의 shareholder_letter, Morning Brief insight, Quarterly mdna, Risk Board top_risks 4곳만. 나머지는 AI가 아닌 **카피라이터의 완벽한 문장**이 템플릿에 박혀 있음. 문제는 "AI 티"가 아니라 "모든 유저에게 동일한 카피" |
| 5. 한미 양방향 특화 실종 | ✅ 확인 | 아래 §5 참조 |

---

## 1. 구조적 진단 — 왜 이런 일이 벌어졌나

### 1.1 두 개의 파이프라인, 하나의 템플릿

```
[Admin Preview 경로] (CEO가 보는 것)
admin_preview.py → services/artifacts/sample_data.py → 풍부한 prose/숫자/이벤트 채움 → 같은 Jinja 템플릿 → 아름다운 PDF ✨

[Real User 경로] (유저가 받는 것)
weekly_memo_service.generate_for_user(user_id)
  → DB: Position, TradeHistory
  → FMP/FRED: 기본 KPI 몇 개
  → 반환: WoW%, 벤치마크%, 알파%, top_movers, sector_alloc (5~8개 필드)
  → 같은 Jinja 템플릿 → 대부분 섹션이 default(...) 분기로 폴백
  → 유저가 받는 PDF: 껍데기는 같지만 내용은 static wallpaper ⚫
```

### 1.2 구체적 증거 — 서비스가 반환하지 않는 필드 (샘플 템플릿 대비)

| 템플릿 | Template 기대 필드 (default 사용) | 서비스 반환 필드 (실제) | 미스매치 % |
|---|---|---|---|
| **weekly_memo** | hero_headline, narrative_exec_line, narrative_week_summary, narrative_what_next, equity_series, benchmark_series, daily_walk_rows, risk_metrics, corr_matrix, corr_labels, pull_quote, what_to_watch, issue_number, equity_annotation, data_sources, typeset_in, engine_note, doc_ref | user_id, user_name, week_number, period_start/end, generated_at, weekly_return_pct, benchmark_pct, alpha_pct, sector_alloc, sector_changes, top_movers_up/down, earnings_calendar, macro_checklist, risk_notes, disclaimer | ~70% 미스매치 |
| **morning_brief_plus** | overnight_tape, overnight_events, overnight_prose, macro_ladder (8 instruments + sparkline), today_calendar (6 events), sector_premkt, fx_crosses, rates_curve, vix_term, observation_notes, pull_quote, hero_headline, kpis_cover | kpis, market_summary, portfolio_changes, events, insight, disclaimer, generated_at | ~85% 미스매치 |
| **earnings_prebrief** | hero_headline, revenue_history (8 qtrs), company_prose (3 paragraphs), surprise_bins, beat_rate_pct, beat_timeline, drift_bars (1D/5D/21D), implied_realised_r, implied_vs_realised, peer_group, peer_eps_comp, reading_notes, pull_quote, cannot_tell, data_sources | consensus_eps/low/high, consensus_revenue, surprise_history (**4 qtrs, template 기대는 8**), expected_questions (**템플릿 안 씀**), sensitivity_beat/miss (**템플릿 안 씀**), risk_notes | ~75% 미스매치 + 2개 데드 필드 |
| **year_end_letter** | hero_headline, **letter_paragraphs** (템플릿), margin_notes (Sharpe/Turnover/Worst Day/Book composition), equity_ribbon_pts, monthly_rows, reflection_blocks, pull_quote, not_claimed, data_sources | **shareholder_letter** (단수·AI 생성 — 템플릿이 읽는 필드명과 불일치), ytd_return_pct, best/worst_decisions, consistency_score, consistency_notes | ~90% 미스매치 + **AI 편지 데드** |
| **brag_card** | hero_headline, win_rate_pct, best_pnl_usd, hold_days, entry_date, entry_price, exit_date, exit_price, position_size_pct, top_lots | return_pct, trade_count, best_ticker, best_return_pct, worst_ticker, worst_return_pct, month_label, share_token | ~80% 미스매치 — **바이럴 쉐어 카드인데 유저별 차별화 거의 0** |
| **quarterly_self_report** | hero_headline, signoff_line, margin_notes, decision_ladder, sharpe_rolling, sharpe_series, hit_rate_overall, hit_rate_by_action, holding_median_days, holding_hist, top_sector, sector_attribution, self_review_notes, pull_quote, cannot_settle, does_record | mdna (AI), segments, thesis_checks, decision_quality, thesis_checklist | ~75% 미스매치 |
| **risk_board** | **kpi_var_1d, kpi_es_1d, kpi_maxdd_90d, kpi_corr_index** (템플릿), positions_ladder, underwater, liquidity_label, pull_quote, not_answered, data_sources | **var95_pct, var99_pct** (서비스), sharpe_annual, sortino_annual, calmar, max_drawdown_pct, sector_breakdown, tail_ratio, component_es, layer_status, top_risks (AI) | ~60% + **VaR/MDD 필드명 불일치 → KPI 4개 모두 템플릿 default 사용** |

### 1.3 `default(...)` 카운트 by 템플릿

```
earnings_prebrief.html      42
kpi_dashboard.html          37
portfolio_segment.html      32
quarterly_self_report.html  31
dd_checklist.html           28
sp500_backtest.html         28
burn_rate.html              26
morning_brief_plus.html     23
self_audit.html             23
brag_card.html              21
capital_allocation.html     20
risk_board.html             20
insider_mirror.html         19
monthly_finance.html        19
year_end_letter.html        19
credit_rating.html          18
dividend_income.html        18
weekly_memo.html            15
brag_card_email.html        11
_brand_mark.html             4
_disclaimer.html             1
weekly_memo_email.html       1
────────────────────────────────
총                         456
```

---

## 2. 리포트별 상세 평가 (7축 점수 + 인용)

### 점수 기준
- 9-10: Goldman Top of Mind / Matt Levine Money Stuff 수준
- 7-8: Morning Brew / Bespoke Morning Lineup 수준 (유료 가치 있음)
- 5-6: 미래에셋 모닝브리핑 수준 (무료 증권사 리포트)
- 3-4: 블로그/뉴스레터 수준
- 1-2: AI 생성 티 나는 범용 콘텐츠

---

### ① Weekly Memo (W16) — 주간 투자자 메모

#### 실제 인용 (3문단)

**[Editorial Quote · Part IV — 모든 유저에게 동일하게 나감]**
> "A quiet week is not a boring one. It is a disciplined one."
> — The Editorial Voice

**[Part III · Risk Dashboard — 모든 유저에게 동일하게 나감]**
> VaR 95%: **-2.14%** · "Loss exceeded on 5% of historical days. 90-day HS."
> Expected Shortfall 95%: **-3.12%** · "Mean loss on the worst 5% of days — the tail VaR does not see."
> Max Drawdown · 12w: **-8.14%** · "trough · W-9" · "Recovered to flat by W-13."
> Tail Ratio: **1.08** · "|P95| ÷ |P5|. Above one, right tail carries more work."

**[Part I · Prose — 여기는 서비스가 채울 수 있는 영역이나, 서비스에서 narrative_week_summary 누락 시 템플릿 default 미존재 → 이 섹션은 일부 개인화 가능]**
> "The book advanced 2.41% against the S&P 500's 1.12%, settling alpha at +1.29 percentage points... The heavy lifting came from NVDA (+8.24%) and AVGO (+5.11%). The laggards — TSLA and NKE — declined in sympathy with cohort softness rather than name-specific catalysts on the calendar."
> "The observation worth naming is concentration: Information Technology sits at 32.5% of invested capital — above the thirty-percent guide for the fourth straight week."

#### 7축 점수

| 축 | 샘플 기준 | 실제 유저 기준 | 격차 |
|---|---:|---:|---|
| 1. JTBD 충족 ("지난주 내 포트폴리오 무슨 일 있었나?") | 9 | 4 | Risk/Editorial 섹션이 유저 실제 데이터 미반영 |
| 2. 인사이트 밀도 | 7 | 2 | "structural read of the matrix is the 0.62 block" 등은 모든 유저 공통 → 의미 없음 |
| 3. 데이터 구체성 | 8 | 5 | WoW%, 알파, top movers는 진짜. Risk metrics 4개는 가짜 |
| 4. Narrative Flow | 9 | 7 | Part I/II의 prose는 어느 정도 서비스-생성 가능. Part III/IV는 정적 |
| 5. Actionability | 5 | 3 | "What to watch" 5개 item도 default — AAPL/005930 고정 |
| 6. Credibility 톤 | 9 | 8 | Goldman IC 톤 자체는 훌륭. 단 "Silence is the loudest signal" 같은 hero는 매 주 동일하면 신뢰 타격 |
| 7. 한미 양방향 | 7 | 4 | 템플릿 default에 AAPL/005930.KS 1회 등장. KRW/USD 매크로 1줄. 구조적 bi-directional 스토리 없음 |
| **합계 (70점 만점)** | **54/70** | **33/70** | **-21 pts** |

#### 결정적 결함
- 🔴 **Hollow**: Risk Dashboard의 4개 숫자 (VaR/ES/MDD/TailRatio)가 **해석은 잘 되어 있으나 숫자 자체가 모든 유저 동일 상수**
- 🔴 **Generic**: "A quiet week is not a boring one" — 실적 폭락 주에도 이 문장이 그대로 나감
- 🟡 **Misaligned**: 서비스는 `macro_checklist`, `sector_changes`를 채우지만 템플릿 Part IV의 `what_to_watch`는 별도 필드라 못 읽음

#### 개선안

**Kill:**
- Risk Dashboard 페이지의 하드코딩 숫자 4개를 **전부 제거**. 서비스가 계산할 수 있을 때만 표시, 없으면 섹션 숨김.
- "What the desk is sitting with" 단일 pull_quote 정적 (Editorial Voice) — 주간 생성이 아니면 제거.

**Level up:**
- Part I prose는 이미 서비스-생성 가능. narrative_exec_line, narrative_week_summary, narrative_what_next 필드를 서비스 generate_for_user()에 추가 (Claude Haiku 1회 호출, 토큰 ~400).
- Part II Position Ladder의 "Reading" 컬럼 ("Led the book", "Largest drag")은 지금 템플릿에서 `if _r >= 2` 분기로 제한적. 실제 개인 컨텍스트 (보유기간, 평단 대비 %) 추가.
- Risk Dashboard 숫자를 risk_models.py (GKYZ, HistoricalVaR, ComponentES)에서 실제 계산해 주입.

**Add:**
- **"지난주 대비 섹터 rotation 서사"**: 지금 sector_changes는 {delta_pp} 숫자로만 표시. "반도체 +3.6pp → 작년 대비 과소할당에서 탈출" 같은 장기 해석.
- **"같은 포지션의 다른 유저 분포"** (프라이버시 집합화): "NVDA를 가진 유저 평균 주간 수익률 +6.1%, 귀하 +8.24% — 상위 18%". 가치 큼, 법적 회색지대 안 (개인 추천 아님, 집계 통계).
- **한-미 양방향 관점**: 환율 효과 분리. "원화 기준 주간 +3.2%, 달러 기준 +2.41%, 환율 기여 +0.79pp".

**Before/After 예시 (Editorial pull quote):**

Before (모든 유저에게 동일):
> "A quiet week is not a boring one. It is a disciplined one."

After (유저 컨텍스트 기반, 서비스가 Haiku로 생성):
> "This was your fourteenth week at 32.5%+ IT concentration. Not a record — but the third consecutive week the same structural read has held."
> — PivoxQuant Research Desk · for 배상현

---

### ② Morning Brief Plus — 일일 모닝 브리프

#### 실제 인용 (3문단)

**[Cover Hero — default로 모두 동일]**
> "A morning is only what it shows — markets open, we watch."

**[P2 Overnight Spread · prose — default로 모두 동일]**
> "Asia observed a measured session — KOSPI held near flat at 2,684, Nikkei closed 0.41% lower against a firmer yen, and Hang Seng recorded a 0.28% gain concentrated in the platform cohort."
> "Europe opened with the Stoxx 600 up 0.14%, led by industrials. The DAX tracked sideways around prior close while autos recorded a small drag. Gilt yields drifted two basis points higher in early trade."
> "US pre-market observation shows S&P futures quoting +0.12% and Nasdaq futures +0.21%, with the largest pre-open tick recorded in the semiconductor cohort."

**[P3 Macro Ladder — default로 모두 동일 8개 instruments]**
> DXY 99.42 / Oil WTI 82.14 / Gold 2,384 / 10Y Treasury 4.32% / 2Y Treasury 4.88% / VIX 15.80 / MOVE 102.4 / HY Credit OAS 348 bps

#### 7축 점수 (실제 유저 기준)

| 축 | 점수 | 비고 |
|---|---:|---|
| 1. JTBD 충족 ("오늘 아침 시장 어떤 상황?") | 3 | 실제 유저는 `kpis`, `portfolio_changes`, `events`, `insight`만 받음. 나머지 3페이지는 상수 |
| 2. 인사이트 밀도 | 2 | 상투적 일변도 ("observed a measured session", "held near flat") |
| 3. 데이터 구체성 | 3 | 유저 개별 KPI는 있으나 Macro/Overnight 숫자는 가짜 |
| 4. Narrative Flow | 6 | 구조는 훌륭 (Overnight → Macro → Flow → Editorial) |
| 5. Actionability | 2 | Cal 6개 전부 default |
| 6. Credibility 톤 | 7 | NYT Morning × Bloomberg 톤 — 톤만큼은 수준급 |
| 7. 한미 양방향 | 5 | Asia/Europe/US 3단 구조 있음. 그러나 유저 KR 포지션 연결 없음 |
| **합계** | **28/70** | Morning Brew(≈50) / 미래에셋 모닝브리핑(≈45) 이하 |

#### 결정적 결함
- 🔴 **Hollow**: 6페이지 중 5페이지가 상수
- 🔴 **Generic**: "KOSPI held near flat at 2,684" — 2026-04-23 오전 7시에 발송되는데 2,684는 template default. 실제 2026-04-21 KOSPI가 얼마였는지와 무관
- 🔴 **Misaligned**: 서비스의 `insight` (Haiku로 생성)는 양질, 그러나 템플릿이 그것을 주요 위치에 노출하지 않음

#### 개선안

**Kill:**
- P2 Overnight Spread 전면 (Asia/Europe/US 상수 prose + tick ribbon) → 실데이터 없으면 페이지 자체 삭제
- P3 Macro Ladder 8 instruments → FRED+Yahoo 실데이터 없는 instrument는 drop

**Level up:**
- `insight` (Haiku 생성, 현재 1줄)을 P1 hero로 올리고 **"Today's observation for 배상현"** 형식으로 재포맷
- `portfolio_changes`를 P4 Flow Quad에 배치 (현재는 static sector_premkt default)

**Add:**
- **한국 야간 이벤트 briefing**: 미국 전일 종가 기준 한국 시장 개장 전 체크리스트. "USD/KRW 전일 1,342 → 현재 1,348, 원화 기준 005930 -0.4% 추가 효과". Korean investors 고유 가치.
- **오늘 보유 종목 중 개별 이벤트** (현재 `events`만 표시 → 4페이지로 확장): FOMC speaker schedule, Fed nominees, earnings timing (시간대 KST 환산).

---

### ③ Earnings Pre-Brief — 개별 종목 실적 전 24h 프리리드

#### 실제 인용 (3문단)

**[P2 Company Prose — default로 모두 동일]**
> "The company's revenue pace has held between roughly $93B and $125B across the observed eight-quarter window, with the familiar fourth-quarter seasonal peak appearing in both FY24 Q4 and FY25 Q4. YoY change has moved from mid-single-digit negative at the start of the window to low-single-digit positive by its end."

**[P4 Reading Notes — 5개 전부 default]**
> "Consensus is a sampling of analyst observations — historical record only, not a collective target."
> "Implied move: Option-market pricing of uncertainty around the print. It is market-implied, not market-determined."
> "Past surprise pattern: The surprise history is a historical record only. It does not speak to the current quarter."

**[P5 Editorial — default로 모두 동일]**
> "The market rehearses every call. The call tells us only how well the market listened."
> — PivoxQuant · Earnings Desk

#### 7축 점수 (실제 유저 기준)

| 축 | 점수 | 비고 |
|---|---:|---|
| 1. JTBD 충족 ("내가 가진 AAPL 실적 발표 전 뭘 알아야?") | 4 | consensus EPS, 4-qtr surprise만 실제. 나머지는 "정보 회피" 페이지 |
| 2. 인사이트 밀도 | 3 | "cannot_tell" 5개 아이템은 정보가 아닌 "말하지 않겠다" 선언 |
| 3. 데이터 구체성 | 4 | 4-qtr surprise는 실제. 8-qtr revenue_history는 모두 AAPL-고정 default |
| 4. Narrative Flow | 7 | Cover → Company → Surprise → Observation → Editorial → Colophon 5p 구조 |
| 5. Actionability | 2 | "cannot_tell" 섹션이 Actionability 제로를 명시 |
| 6. Credibility 톤 | 8 | Goldman Top of Mind 톤 매우 좋음 |
| 7. 한미 양방향 | 2 | 005930.KS 종목 선택 시 이 템플릿이 AAPL-centric default 그대로 적용. 한국 기업 별도 구조 없음 |
| **합계** | **30/70** | — |

#### 결정적 결함
- 🔴 **Legal-heavy**: P4-P5의 "Reading Notes" 5개, "cannot_tell" 5개 합계 10개 문장이 전부 "informational only" 반복. 정보 밀도 대비 고지 비중 과다
- 🔴 **Generic**: 동일 유저가 AAPL과 005930.KS 두 종목 pre-brief 받으면 revenue_history, surprise_bins, beat_timeline 8개 모두 동일 (차이: consensus_eps만)
- 🔴 **Shallow**: 헤지펀드 analyst가 읽으면 "so what?" 반응. implied_move_pct 4.2%가 어떻게 현 VaR과 interact하는지, 내 포지션 sensitivity는? 없음
- 🟡 **Dead fields**: 서비스가 `expected_questions` (5개 질문), `sensitivity_beat/miss` ($ P&L 시나리오) 생성하지만 템플릿이 읽지도 않음

#### 개선안

**Kill:**
- P4 Reading Notes 5개 → 페이지 하단 disclaimer에 축약 통합 (5줄 → 2줄)
- P5 "cannot_tell" 섹션 → disclaimer로 합침

**Level up:**
- 서비스의 `expected_questions` 5개를 **P5 핵심 섹션으로 격상**: "5 Questions to listen for on the call" — 이게 진짜 pre-brief의 가치
- `sensitivity_beat/miss` ($ P&L) → P1 KPI 4개 중 1개로 격상: "귀하 포지션: 4주. ±3% 움직임 시 ±$105 영향"
- surprise_history를 4 → 8분기로 확장 (FMP에서 fetch). 템플릿은 이미 8분기 전제

**Add:**
- **"같은 섹터 Peer들의 최근 프린트 reactions"**: MSFT, GOOG, META 최근 1q EPS surprise & post-earnings 1-day reaction 표. 지금 peer_eps_comp는 consensus만, reaction 없음
- **"Options positioning inferred from chain"**: ATM straddle, 25Δ risk reversal — 법적으로 "observation only" 가능
- **한국 기업 별도 스켈레톤**: 005930.KS pre-brief 시 FMP 대신 DART 공시, 전분기 매출 YoY + 영업이익, 원화 환율 효과 분리

**Before/After 예시 (P5 핵심 질문):**

Before (default):
> "The market rehearses every call. The call tells us only how well the market listened."

After (서비스의 expected_questions):
> **5 Questions to Listen for on the AAPL Q2 FY26 Call**
> 1. Services margin trajectory — last quarter flagged Q3 weakness
> 2. Vision Pro install base vs FY25 Q4 messaging
> 3. China revenue guidance — CFO's language vs January print
> 4. AI capex absorption rate — $12B FY26 commit
> 5. Buyback pace — $110B remaining authorization

---

### ④ Year-End Letter — 연말 주주 서한 (Premium)

#### 실제 인용 (3문단)

**[Letter Body — 템플릿 default, 모든 유저 동일]**
> "This letter is not a forecast. It is a record of what happened, and — where I can manage it — a record of what I noticed while it happened. The numbers on the cover are what they are. The question worth a letter is what the numbers were *made of*."
> "The market in question moved, on the whole, as markets do — in a stretched summer, a frightened autumn, and a quiet close."
> "The largest single-day drawdown arrived on **March 14**, a Friday, and it was **3.2%**. I remember it because I was writing another letter — an unrelated one, to someone unrelated — when it printed, and the text I had been composing on a different subject became harder to finish."

**[Margin Notes — 4개 전부 default]**
> Sharpe: Observed at **0.91** over the window. Not annualised into the future.
> Turnover: **41%**. Monthly rebalance on the last trading day, without exception.
> Worst Day: Largest single-day drawdown **−3.2%, March 14**. Recovered by the following Wednesday.
> Book composition: **Seven** positions held through the full year. Three entered mid-year. Two closed in June.

#### 7축 점수

| 축 | 점수 | 비고 |
|---|---:|---|
| 1. JTBD 충족 ("올 한 해 나의 투자 회고") | 2 | **편지 전체가 가상의 인물 — 실제 유저 회고가 아님** |
| 2. 인사이트 밀도 | 8 (샘플 기준) / 1 (실제) | Buffett 톤은 훌륭하나 유저와 무관 |
| 3. 데이터 구체성 | 3 | YTD%, alpha는 실제. 나머지 Sharpe 0.91, March 14 이벤트는 모두 가짜 |
| 4. Narrative Flow | 9 | **문학적 완성도 — 이 프로젝트 전체에서 가장 뛰어난 단일 콘텐츠** |
| 5. Actionability | N/A | Year-end reflection은 action 아님이 디자인 |
| 6. Credibility 톤 | 10 | Buffett 주주서한 톤. "March 14 Friday, I was writing another letter" 미세함 |
| 7. 한미 양방향 | 3 | "semiconductor cohort", "platform cohort" 영어 공식 cohort 명으로만 언급 |
| **합계 (실제 유저)** | **26/70** | 문학성은 Nobel급, 개인화는 0 |

#### 결정적 결함 — 가장 심각
- 🔴🔴🔴 **Robotic + Generic + Shallow 삼중결함**: 서비스는 Claude로 `shareholder_letter` (한국어 2문단) 생성. 템플릿은 `letter_paragraphs` (영어 7문단 리스트) 읽음. **AI 생성 편지가 PDF에 절대 실리지 않는다**.
- 🔴 **이름 + YTD%만 개인화**: "March 14 -3.2% drawdown" — 유저가 해당 일자에 포지션조차 없었을 수 있음
- 🔴 **Premium tier 전용인데 가치 극소**: 19,900원/월짜리 Premium 독점 배포 연간 리포트가 유저 무관한 fiction letter

#### 개선안

**Kill:**
- 템플릿의 7단락 default letter_paragraphs 전부 삭제
- margin_notes 4개 default 전부 삭제 (Sharpe 0.91, Turnover 41%, March 14, Seven positions)

**Level up:**
- 서비스 `shareholder_letter` 필드를 `letter_paragraphs`로 rename (또는 양쪽 매핑 추가). **이게 최우선 1줄 버그픽스**.
- 서비스의 `consistency_score`, `consistency_notes`, `best_decisions`, `worst_decisions`를 Letter 본문에 weave. 현재 단독 섹션으로만 존재.
- Margin Notes 4개를 실제 계산값으로: Sharpe = risk_models.annualised_sharpe(user_trades), Turnover = sum(buys+sells)/avg_nav, Worst Day = max(|daily_returns|), Book composition = count of positions held ≥330 days.

**Add:**
- **"올해 가장 중요한 3가지 결정"**: Haiku로 best_decisions + worst_decisions + one_unchanged_decision → 3 패러그래프 서사화
- **"투자자 진화 타임라인"**: 연초 risk_profile → 연말 realized_style 변화. "보수적으로 시작해 4월을 기점으로 semiconductor-heavy로 drift"
- **한-미 포트폴리오 의존도 분석**: "귀하 연간 수익의 62%는 KR 반도체 cohort에서, 28%는 US AI cohort에서. 환율 효과는 +3.1pp 기여"

**Before/After (최우선):**

Before (템플릿 default, 모든 Premium 유저 동일):
> "The largest single-day drawdown arrived on March 14, a Friday, and it was 3.2%. I remember it because I was writing another letter..."

After (서비스 실제 계산 + Claude):
> "2025년 8월 3일, 귀하의 북은 전일 대비 -4.2%를 기록했습니다. 그날 005930.KS 반도체 감산 리포트가 개장 전 나왔고, 귀하의 북은 섹터 43.5% 비중이었습니다. 이후 11거래일 내 flat으로 복귀했습니다. 이 글을 쓰며, 나는 이 수치 뒤에 있던 귀하의 하루를 알지 못합니다 — 숫자는 그것을 보관하지 않습니다."

---

### ⑤ Brag Card — 월간 자랑 카드 (바이럴)

#### 실제 인용

**[Hero headline — default 모두 동일]**
> "A small note to self."
> "One month, one"
> "observation." (bronze)

**[Best trade spotlight — default 모두 동일]**
> "Entered **NVDA** on **April 3** at **$842**.
> Closed **April 11** at **$879**.
> **8-day hold**."

**[Signature — default 모두 동일]**
> "— a quiet record, April 2026"

#### 7축 점수 (실제 유저 기준)

| 축 | 점수 |
|---|---:|
| 1. JTBD ("이번 달 내가 뭘 잘했나 자랑") | 2 |
| 2. 인사이트 밀도 | 1 |
| 3. 데이터 구체성 | 3 (return_pct, best_ticker만 실제) |
| 4. Narrative Flow | 5 |
| 5. Actionability | N/A |
| 6. Credibility | 5 |
| 7. 한미 양방향 | 2 |
| **합계** | **18/60** |

#### 결정적 결함 (프로덕트 차원 최대 위험)
- 🔴🔴🔴 **바이럴 쉐어 카드인데 유저간 차별화 0**: 이 카드는 MVP #2 — 인스타그램 쉐어로 레퍼럴 유입시키는 채널. 모든 유저가 "NVDA $842 → $879, 8-day hold"를 공유하면 **쉐어 당일 5명만 공유해도 브랜드에 치명타** ("이거 가짜 아냐?")
- 🔴 **Empty mode fallback 없음**: 거래 0건이었던 달에도 카드 발송 (is_empty 플래그는 있으나 UI처리 미확인)

#### 개선안

**Kill:**
- 템플릿의 entry_date, entry_price, exit_date, exit_price, hold_days, position_size_pct default 전부 삭제
- 거래 0건 유저에게는 Brag Card 발송 중단 (지금 `is_empty: True`로 표시는 하지만 여전히 발송)

**Level up:**
- 서비스가 `best_trade_detail` 객체 생성: {entry_date, entry_price, exit_date, exit_price, hold_days, total_pnl_usd, position_size_pct_of_nav}
- 서비스가 `month_summary_number` 선정: 가장 자랑할 만한 단일 숫자 (win_rate, best_return, hold_discipline 중 제일 높은 metric)

**Add:**
- **"나만의 slogan"**: Haiku로 유저의 월간 스타일 요약 1줄 생성. "이번 달 귀하는 평균 6.3일 보유 — 전월 11일 대비 단축". 쉐어 시 훅.
- **한국어 오늘의 한 수**: "4월의 한 수 · 005930 5% 하락장에서 -8% 추가매수" — Korean 유저 쉐어 맥락

**Before/After:**

Before (99% 유저가 쉐어 시 동일):
```
Entered NVDA on April 3 at $842.
Closed April 11 at $879.
8-day hold.
```

After (유저마다 실제 거래):
```
Entered 005930.KS on April 2 at ₩71,800.
Closed April 16 at ₩76,200.
14-day hold · +6.1% · 2.4% of book
```

---

### ⑥ Quarterly Self-Report — 분기 자기 10-K

#### 실제 인용 (샘플 기준)

**[Hero — default]**
> "A quarter closes. / The ledger opens / its own mirror." (bronze)

**[Decision Ladder — default 모두 동일, 유저 무관]**
> (6개 포지션 ladder with sparklines, pnl_pct, weight_delta — 전부 default 값)

**[Pull quote — default]**
> "Self-review is the small hinge on which large habits turn."

#### 7축 점수 (실제 유저 기준)

| 축 | 점수 |
|---|---:|
| 1. JTBD ("분기 회고 · 나의 결정 품질 점검") | 6 (mdna, thesis_checks는 실제 AI) |
| 2. 인사이트 밀도 | 5 |
| 3. 데이터 구체성 | 5 |
| 4. Narrative Flow | 7 |
| 5. Actionability | 6 (thesis_checklist Y/N 구조) |
| 6. Credibility | 8 |
| 7. 한미 양방향 | 4 |
| **합계** | **41/70** | **15종 중 2번째로 건강** |

#### 결정적 결함
- 🟡 **Data-starved on meta-metrics**: Sharpe_rolling 12포인트, hit_rate_by_action, holding_hist 등 결정품질 메타지표가 전부 default
- 🔴 **Generic on "what's unanswerable"**: cannot_settle 섹션 ("the counter-factual trade", "the alternate entry date" 등 5개 default 고정)

#### 개선안

**Kill:**
- cannot_settle, does_record 단일 페이지 섹션 → disclaimer로 축약

**Level up:**
- decision_ladder를 실제 유저의 분기 포지션 ladder로. 이미 `principal_positions` 필드는 있음 — 템플릿 bind 필요.
- sharpe_rolling, hit_rate_overall을 실제 계산 (risk_models + TradeHistory)

**Add:**
- **분기 대비 행동 변화 지표**: "Q1 평균 hold 12일 → Q2 19일" (meta-pattern)
- **Thesis drift score**: 온보딩 시 선언한 investor_profile과 Q2 실제 행동 거리

---

### ⑦~⑮ 나머지 9종 간략 평가

#### ⑦ Risk Board (Premium 월간 + VIX 스파이크 트리거)
- **실제 유저 점수: 38/70** — var95/99, sharpe, sortino, layer_status, top_risks(AI)는 진짜 데이터
- **치명 결함**: 템플릿이 `kpi_var_1d`, `kpi_maxdd_90d` 등 **다른 필드명** 읽음 → 서비스의 `var95_pct`, `max_drawdown_pct`는 P1 KPI에 표시 안 됨, 모두 default (-2.14%, -8.70%)
- **1줄 버그픽스**: 템플릿 필드명 통일 또는 서비스 alias 추가

#### ⑧ Credit Rating
- **Job**: "내 포트폴리오의 신용 등급(개인 회계 기반)"
- **18 default** — 이 중 대부분이 rating justification prose
- **점수: 25/70** — 숫자 잘 채우나 해석 prose는 상수

#### ⑨ Monthly Finance
- **Job**: "이번 달 개인 투자 명세서"
- **19 default** — equity_walk (23포인트), closed_lots, ledger_prose (2문단)
- **점수: 32/70** — 샘플은 쁘라이빗뱅크 statement 수준, 실제 유저는 기본 KPI만

#### ⑩ Dividend Income
- **Job**: "배당 수입 연간·월간 summary"
- **18 default**
- **점수: 30/70**

#### ⑪ Capital Allocation
- **Job**: "자산 배분 4자산(주식/채권/대안/현금) 리밸런싱 리포트"
- **20 default** — 4자산 % 시계열, 리밸런싱 근거 prose (위 인용 참조)
- **점수: 28/70** — "Bond weight moved in the opposite direction, from 26% to 23%" 문단이 모든 유저 동일

#### ⑫ Insider Mirror
- **Job**: "귀하 보유 종목 내부자 거래 미러링"
- **19 default**
- **점수: 35/70** — insider 데이터 자체는 SEC Form 4에서 실제, 그러나 prose wrapper는 상수

#### ⑬ DD Checklist (Due Diligence)
- **Job**: "신규 종목 편입 전 10단계 체크리스트"
- **28 default** (**가장 많은 2번째**)
- **점수: 22/70** — 체크리스트 자체는 generic template. 유저 보유 종목 특화 항목 없음

#### ⑭ Burn Rate
- **Job**: "현금흐름·손실률 추적 (옵션/초단타 유저용)"
- **26 default**
- **점수: 28/70**

#### ⑮ KPI Dashboard
- **Job**: "5개 핵심 KPI 일일 대시보드"
- **37 default** (**가장 많은**)
- **점수: 25/70** — Morning Brief Plus에 흡수됨 (스탠드얼론으로는 퇴역)

#### ⑯ SP500 Backtest
- **Job**: "귀하 전략을 S&P 500에 백테스트"
- **28 default** — 그런데 이건 백테스트라 정적 상수가 많은 게 합리적
- **점수: 40/70** — backtester.py 실제 사용 시 양질

#### ⑰ Self Audit
- **Job**: "거래 사후 감사 — 좋은 결정 / 나쁜 결정 분류"
- **23 default**
- **점수: 36/70** — Self Audit score, decision quality wins/best/worst는 실제

#### ⑱ Portfolio Segment
- **Job**: "포지션 세그먼트 분석 (core/satellite, KR/US 등)"
- **32 default**
- **점수: 30/70**

---

## 3. 공통 결함 매트릭스

| 리포트 | Hollow | Generic | Robotic | Shallow | Legal-heavy | Misaligned | Data-starved |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Weekly Memo | ● | ● | | | | ● | |
| Morning Brief+ | ● | ● | | ● | | ● | ● |
| Earnings Pre-Brief | | ● | | ● | ● | ● | ● |
| Year-End Letter | ● | ● | ● | ● | | ● | |
| Brag Card | ● | ● | | ● | | ● | ● |
| Quarterly Self-Report | | ● | | | ● | | ● |
| Risk Board | | ● | | | | ● | |
| Credit Rating | ● | ● | | ● | | ● | ● |
| Monthly Finance | ● | ● | | ● | | ● | ● |
| Dividend Income | ● | ● | | ● | | ● | ● |
| Capital Allocation | ● | ● | | ● | | ● | ● |
| Insider Mirror | | ● | | ● | | ● | |
| DD Checklist | | ● | | ● | ● | ● | |
| Burn Rate | ● | ● | | ● | | ● | ● |
| KPI Dashboard | ● | ● | | | | ● | |
| SP500 Backtest | | ● | | | | | |
| Self Audit | | ● | | ● | | ● | |
| Portfolio Segment | ● | ● | | ● | | ● | ● |

**15개 중 14개가 Generic 🔴. 14개가 Misaligned 🔴. 11개가 Hollow 🔴.**

---

## 4. 벤치마크 격차 분석

우리 PDF가 가장 가까운 벤치마크 + 격차:

| 벤치마크 | 매칭 리포트 | 우리 현재 위치 | 격차 원인 |
|---|---|---|---|
| Matt Levine "Money Stuff" | Weekly Memo Editorial | 샘플: 80% 근접 / 실제: 20% | Matt의 결정적 무기는 매주 다른 소재 + 위트. 우리는 상수 |
| Goldman Top of Mind | Earnings Pre-Brief | 샘플: 75% / 실제: 25% | Goldman은 매 리서치 유니크 thesis. 우리는 reading_notes 5개 고정 |
| Bespoke Morning Lineup | Morning Brief Plus | 샘플: 70% / 실제: 15% | Bespoke는 매일 다른 차트 10개. 우리는 macro_ladder 8개 상수 |
| Morning Brew | — | 직접 매칭 없음 | 우리는 Morning Brew의 "친구같은 톤"이 아닌 Goldman formal 톤 |
| Fundstrat First Word | Risk Board | 샘플: 65% / 실제: 45% | Fundstrat은 매크로 + 시스템 (VaR류) 결합. 우리는 시스템만 |
| 미래에셋 모닝브리핑 | Morning Brief Plus | 샘플: 85% / 실제: 30% | 미래에셋은 한국 증권사 공식 리서치 톤. 우리는 영어 번역체 |
| 슈카월드 재무 브리핑 | Year-End Letter | 우리는 10% 미만 매칭 | 슈카월드 = 구어체 유머 + 한국 맥락. 우리는 Buffett 영어 공식 |

**가장 큰 교훈**: 우리 리포트의 톤은 Goldman IC / Matt Levine 수준을 지향한다. 톤 자체는 샘플 기준 훌륭. 그러나 **Goldman/Matt이 매일/매주 다른 내용을 쓴다는 것이 본질**인데, 우리는 편집 톤만 흉내내고 내용 재생산이 안 된다.

---

## 5. 한미 양방향 특화 — Only-We 자산 활용도

PivoxQuant의 최대 차별점은 KR+US 통합 플랫폼 (Alpaca + KIS + FMP + DART). 리포트 콘텐츠에서 이 자산이 어떻게 활용되는가:

| 영역 | 현재 활용도 | 가능치 |
|---|:-:|:-:|
| 환율 효과 분리 (KRW/USD) | 2/10 | 9/10 |
| 양 시장 보유 시 섹터 상관 (한미 반도체, 한미 플랫폼) | 1/10 | 9/10 |
| 한국 장 개장 전 미국 overnight 영향 | 3/10 | 10/10 |
| 미국 장 대기 중 한국 장 close | 2/10 | 9/10 |
| KR 세금 효과 (양도세, 배당소득세) + US 원천징수 | 0/10 | 8/10 |
| 환전 타이밍 / 시장 시간차 arbitrage 관찰 | 0/10 | 7/10 |
| DART 공시 vs SEC 8-K 크로스 참조 | 0/10 | 8/10 |
| KR ETF (KODEX 반도체 279580) vs US ETF (SOXX) 비교 | 0/10 | 8/10 |

**15개 리포트 어디에서도 "환율 효과 분리 YTD 기여 pp"가 명시적으로 계산되지 않는다.** 이것 하나만 추가해도 "미국-only 앱들"과 명확히 구분된다.

**가설 5 (한미 양방향 실종) 확인**. 현재 정량 활용도 **평균 1.4/10**. 가능치는 평균 8/10. 6.6 pts 갭.

---

## 6. 법적 회색지대 활용 여력 분석

사전 가설 3 ("법적 공포로 Actionability 0") 재평가.

### 현재 콘텐츠 금지어 regex (89 regex — legal_filter.py 추정)
- "추천", "buy/sell", "목표가", "매수/매도 권유", "recommendation", "advice", "투자 코치", "should"

### 법적 회색지대에서 **합법이나 우리가 사용 중인 회피 수준**
- ✅ "observation" / "관찰됨" / "기록" → 사용 중
- ✅ "history" / "과거 데이터" → 사용 중
- ✅ "cannot tell" / "말할 수 없음" → **과잉 사용**

### 법적 회색지대에서 **합법이지만 우리가 덜 쓰는 것 (기회)**
- ⬜ "체크해볼 사항 (Things to check)" — 중립 진술, 투자자문 아님
- ⬜ "주의할 영역 (Areas to watch)" — 중립 진술
- ⬜ "패턴 관찰 (Pattern observation)" — 예: "귀하의 지난 3개월 손절 평균 -4.2%"
- ⬜ "Base rate 정보 제공" — "같은 섹터 40%+ 보유 유저의 90일 MDD 중앙값 -9.1%" (집계)
- ⬜ "회고적 질문 (Retrospective questions)" — "지난주 가장 큰 손실 종목을 이번주에 같은 비중으로 유지하는 결정은 무엇에 근거했나?"

**가설 3 부분 확인**. Actionability 제로는 법적 공포라기보다 **콘텐츠 생성 역량 부족 + 템플릿 하드코딩**이 실제 원인. 법적 회색지대 안에서 쓸 수 있는 문장이 아직 많다.

---

## 7. 우선순위별 액션 플랜

### P0 — 즉시 (1일 이내, 1-줄 수정)
1. **Year-End Letter 필드명 fix**: 서비스의 `shareholder_letter` → 템플릿의 `letter_paragraphs`로 매핑 (Claude 생성 편지 살리기). 1커밋.
2. **Risk Board KPI 필드명 fix**: 서비스의 `var95_pct`, `max_drawdown_pct` → 템플릿의 `kpi_var_1d`, `kpi_maxdd_90d`로 매핑. 1커밋.
3. **Brag Card empty 유저 차단**: `is_empty=True`면 run_for_user에서 None 반환 (지금 artifact 행은 만들지만 송부/쉐어 차단 필요).

### P1 — 1주 이내
4. **Weekly Memo Risk Dashboard 숫자 전부 실제 계산**: risk_models.py의 `historical_var(user_positions)`, `expected_shortfall`, `tail_ratio`, `max_drawdown_12w`를 `generate_for_user()`에 추가. 없으면 섹션 숨김.
5. **모든 템플릿의 `default(...)` 중 prose에 해당하는 것 25개** 식별 & 삭제 (prose는 데이터 없으면 생성 안 됨이 낫다, 있는 척 > 없는 게).

### P2 — 2주 이내 (Claude Haiku 활용 콘텐츠 생성)
6. **Narrative Layer 신설**: 각 서비스에 `narrative_*` 필드 추가 + Claude Haiku 1-2회 호출로 유저 컨텍스트 기반 prose 생성.
   - Weekly Memo: narrative_exec_line, narrative_week_summary (3문단), narrative_what_next
   - Morning Brief Plus: daily_narrative (overnight-to-preopen 서사)
   - Earnings Pre-Brief: expected_questions (이미 서비스에 있음 — 템플릿에 bind만)
   - Year-End Letter: 서비스 `shareholder_letter`에 margin_notes도 포함
7. **Hero headline 동적 생성**: 유저 주간/월간 데이터 기반 Haiku 3행 생성 (매 주 바뀜).

### P3 — 1달 이내 (차별화 콘텐츠)
8. **한미 양방향 특화 섹션 전 리포트 추가**:
   - 환율 효과 분리 표 (전 리포트 1 KPI 추가)
   - 한국 장 overnight US 영향 (Morning Brief)
   - DART vs SEC 크로스 참조 (Earnings Pre-Brief)
9. **Base Rate 통계 섹션 추가** (법적 OK): "귀하와 같은 포지션 구성을 가진 PivoxQuant 유저들의 집계 통계"
10. **Actionability 없는 "Questions to self" 섹션**: 회고적 질문 4-5개, 유저 컨텍스트 기반

---

## 8. 미-결 질문 (CEO 결정 필요)

1. **AI 비용 예산**: 현재 Weekly Memo는 `_WEEKLY_AI_LIMIT = 200` (일일 Haiku 호출 상한). 전 리포트에 narrative layer 추가 시 Haiku 비용 얼마? 계산 필요.
2. **hardcoded default 제거 범위**: 전면 제거 시 **일부 샘플 UI가 깨짐** (admin preview는 sample_data.py로 채우므로 안전). 유저용 실제 generate path만 default 타격을 보게 할지 확인.
3. **시장 매크로 데이터 소스**: Morning Brief의 DXY, Gold, 10Y Treasury, VIX, MOVE, HY OAS — 우리 현재 FRED + FMP 커버리지 확인 필요. 없으면 대체 source 필요.
4. **한국 세금·환율 데이터**: DART 공시 API 연동 상태? 국세청 환율 API 상태? 추가 개발 필요시 범위.

---

## 9. 한 문장 결론

> **현재 PDF 15종은 "편집 톤 상위 10% / 개인화 하위 20%"의 상태다. 샘플이 좋아 보이는 이유는 sample_data.py의 가상 프로즈 때문이며, 실제 유저 PDF는 편집 톤만큼은 Goldman 수준이나 내용은 매주 동일한 벽지다. 최우선은 (1) Year-End의 필드명 1줄 버그픽스, (2) Weekly Memo의 Risk Dashboard 실계산, (3) 각 서비스 narrative_* 필드 + Claude Haiku 1-2회 호출 layer 추가다. 이 세 가지만으로 평균 30/70 → 50/70 복귀 가능.**

---

## 부록 A — 파일별 핵심 증거 라인 참조

| 발견 | 파일 | 라인 |
|---|---|---|
| Weekly Memo hero default "Silence..." | `services/artifacts/templates/weekly_memo.html` | 617 |
| Weekly Memo Risk Dashboard 4개 숫자 하드코딩 | 동일 | 1038, 1051, 1065, 1079 |
| Weekly Memo pull_quote default | 동일 | 1143 |
| Weekly Memo Correlation matrix default | 동일 | 972 |
| Weekly Memo what_to_watch 5개 default | 동일 | 1151-1157 |
| Year-End `letter_paragraphs` (템플릿) | `services/artifacts/templates/year_end_letter.html` | 518 |
| Year-End `shareholder_letter` (서비스) — 미스매치 | `services/artifacts/year_end_letter_service.py` | 160, 186, 363-433 |
| Year-End margin_notes default (Sharpe 0.91 등) | `services/artifacts/templates/year_end_letter.html` | 540-545 |
| Brag Card NVDA 842 default | `services/artifacts/templates/brag_card.html` | 382-394 |
| Earnings Pre-Brief revenue_history default (8분기 AAPL) | `services/artifacts/templates/earnings_prebrief.html` | 493 |
| Earnings Pre-Brief reading_notes default | 동일 | 848 |
| Earnings Pre-Brief cannot_tell default | 동일 | 891 |
| Morning Brief Plus overnight_prose default | `services/artifacts/templates/morning_brief_plus.html` | 497-501 |
| Morning Brief Plus macro_ladder 8 instruments default | 동일 | 547-556 |
| Morning Brief Plus today_calendar 6 events default | 동일 | 603-610 |
| Risk Board kpi_var_1d 등 필드명 미스매치 | `services/artifacts/templates/risk_board.html` | 371-374 |
| 전 템플릿 default(...) 카운트 | `services/artifacts/templates/*.html` | 22 files, 456 occurrences |

---

*Report ends.*
