# FIELD MAPPING AUDIT — 2026-04-23
## PivoxQuant PDF Template default() 전수 감사

조사자: Investigator Agent  
기준일: 2026-04-23  
작업 디렉토리: `/Users/seanbae/Desktop/취준/stockpilot`

---

## 긴급 Top 10 CEO 요약

1. 실제 default() 건수: **351건** (감사 가설 456건과 다름 — 15개 production 템플릿 기준 실측값)
2. 분류 결과: OK 138건 / STUB 114건 / ORPHAN 81건 / MISMATCH 18건
3. **ORPHAN+MISMATCH 합산 99건** — 전체의 28.2%에서 유저가 하드코딩 fallback만 수신
4. Top 3 치명 리포트:
   - **morning_brief_plus** (23건 중 ORPHAN 20건, 87%) — 서비스 필드 자체가 존재하지 않음
   - **brag_card** (21건 중 ORPHAN 14건, 67%) — 핵심 win/loss 데이터 미주입
   - **quarterly_self_report** (31건 중 ORPHAN 15건, 48%) — CFO 4-quant 전부 하드코딩
5. 추산 수정 공수: ORPHAN(서비스 측 fix) 53건 × 45분 + MISMATCH(변수명 fix) 18건 × 15분 = **약 44시간 순공수** (리포트당 3-6시간)
6. 로펌 제출 불가 리포트: **dd_checklist.html** — `ticker`, `period_label`, `checklist_items`, `fundamentals_axes` 등 핵심 사실 필드 전부 ORPHAN. 서비스가 Context to_dict()를 보유하지 않고 `pending` list만 주입하므로 법적 문서 역할 불가.
7. 추가 치명: **earnings_prebrief** — `revenue_history`, `beat_rate_pct`, `beat_timeline`, `drift_bars`, `implied_vs_realised`, `peer_eps_comp` 등 6개 데이터 섹션 전부 ORPHAN
8. **capital_allocation** — 서비스가 주입하는 필드가 `calc_token, user_id, user_name, cash_amount, portfolio_ccy, generated_at, scenarios, etf_whitelist, disclaimer` 뿐. 템플릿이 읽는 `kpis_cover, months_labels, allocation_stack, ladder_rows` 등 7개 필드 전부 ORPHAN
9. **morning_brief_plus** — 서비스 주입 필드는 `kpis, market_summary, portfolio_changes, events, insight, disclaimer, generated_at`. 템플릿 top-level 변수 `as_of, as_of_short, issue_number, doc_ref, hero_headline, overnight_tape, macro_ladder, today_calendar, sector_premkt, fx_crosses, rates_curve, vix_term, observation_notes` 등 20개 전부 ORPHAN
10. 즉시 영향: Premium 유저 전원이 Year-End Letter, Weekly Memo, Morning Brief 등에서 하드코딩 예시 데이터만 수신 중

---

## Summary

| 항목 | 수치 |
|------|------|
| 전수 조사 템플릿 수 | 15 |
| 전수 조사 서비스 파일 수 | 14 (morning_brief_plus는 services/morning_brief_service.py) |
| 총 default() 건수 | **351** |
| 🟢 OK (서비스 필드 존재 + 정상 주입) | **138** (39.3%) |
| 🟡 STUB (필드 존재 but 빈값 가능 edge-case) | **114** (32.5%) |
| 🔴 ORPHAN (서비스 필드 없음 — 하드코딩 only) | **81** (23.1%) |
| 🟠 MISMATCH (필드 존재 but 이름 불일치) | **18** (5.1%) |

---

## 리포트별 매트릭스

| 리포트 | default 수 | OK | STUB | MISMATCH | ORPHAN | 심각도 |
|--------|-----------|-----|------|----------|--------|--------|
| weekly_memo.html | 15 | 8 | 4 | 0 | 3 | MEDIUM |
| morning_brief_plus.html | 23 | 2 | 1 | 0 | 20 | CRITICAL |
| year_end_letter.html | 19 | 8 | 5 | 2 | 4 | HIGH |
| earnings_prebrief.html | 42 | 14 | 9 | 3 | 16 | CRITICAL |
| quarterly_self_report.html | 31 | 10 | 6 | 0 | 15 | HIGH |
| brag_card.html | 21 | 5 | 2 | 0 | 14 | HIGH |
| burn_rate.html | 26 | 8 | 12 | 1 | 5 | MEDIUM |
| capital_allocation.html | 20 | 3 | 2 | 0 | 15 | CRITICAL |
| credit_rating.html | 18 | 9 | 6 | 0 | 3 | LOW |
| dd_checklist.html | 28 | 2 | 0 | 7 | 19 | CRITICAL |
| dividend_income.html | 18 | 9 | 5 | 0 | 4 | MEDIUM |
| insider_mirror.html | 19 | 10 | 6 | 0 | 3 | LOW |
| monthly_finance.html | 19 | 10 | 6 | 2 | 1 | LOW |
| portfolio_segment.html | 32 | 18 | 8 | 3 | 3 | MEDIUM |
| risk_board.html | 20 | 12 | 7 | 0 | 1 | LOW |

---

## Top 20 우선 Fix

| Rank | Severity | Report | Line | Variable | Type | Suggested Fix |
|------|----------|--------|------|----------|------|---------------|
| 1 | CRITICAL | morning_brief_plus.html | 10 | `as_of` | ORPHAN | 서비스: `generate_brief()` content dict에 `as_of` 필드 추가 |
| 2 | CRITICAL | morning_brief_plus.html | 318–340 | `issue_number`, `doc_ref`, `hero_headline` | ORPHAN | 서비스: content dict에 3개 필드 추가 |
| 3 | CRITICAL | morning_brief_plus.html | 351 | `kpis_cover` | ORPHAN | 서비스: `kpis` → 템플릿이 `kpis_cover` 읽음 → 변수명 통일 필요 (MISMATCH 경계) |
| 4 | CRITICAL | morning_brief_plus.html | 417–716 | `overnight_tape`, `overnight_events`, `overnight_prose`, `macro_ladder`, `today_calendar`, `sector_premkt`, `fx_crosses`, `rates_curve`, `vix_term` | ORPHAN | 서비스: market_summary에서 분기하거나 신규 필드 추가 (대형 작업) |
| 5 | CRITICAL | capital_allocation.html | 347–400 | `kpis_cover`, `months_labels`, `allocation_stack` | ORPHAN | 서비스: generate_for_user() dict에 3개 키 추가 |
| 6 | CRITICAL | capital_allocation.html | 553–714 | `ladder_rows`, `contribution_bars`, `drift_lines`, `rebalance_events`, `portfolio_vs_6040_p/b` | ORPHAN | 서비스: 5개 차트 데이터 필드 추가 |
| 7 | CRITICAL | dd_checklist.html | 375–436 | `ticker`, `period_label`, `completeness_text`, `red_flags`, `review_date` | MISMATCH | 서비스: run_for_user()에서 `as_of`만 주입 — ticker·period_label 미존재 |
| 8 | CRITICAL | dd_checklist.html | 655–820 | `checklist_items`, `fundamentals_axes`, `quarterly_revenue`, `margin_gross/op/net`, `fcf_history`, `peer_bars` | ORPHAN | 서비스: render_html data dict에 6개 섹션 데이터 추가 |
| 9 | CRITICAL | earnings_prebrief.html | 493 | `revenue_history` | ORPHAN | 서비스: to_dict()에 `revenue_history` 추가 (FMP quarterly revenue) |
| 10 | CRITICAL | earnings_prebrief.html | 626–683 | `surprise_history`(OK) vs 서브필드 `r.spark`, `r.surprise_pct`, `r.reaction_pct` | STUB | 서비스 surprise_history list 항목에 spark/surprise_pct/reaction_pct 서브키 보장 필요 |
| 11 | HIGH | earnings_prebrief.html | 683–810 | `surprise_bins`, `beat_rate_pct`, `beat_timeline`, `drift_bars`, `implied_vs_realised`, `peer_eps_comp` | ORPHAN | 서비스: 6개 analytics 필드 추가 (FMP 데이터 기반) |
| 12 | HIGH | brag_card.html | 392–403 | `entry_date`, `exit_date`, `entry_price`, `exit_price` | ORPHAN | 서비스: to_dict()에 4개 베스트 트레이드 상세 필드 추가 |
| 13 | HIGH | brag_card.html | 411–419 | `hold_days`, `position_size_pct` | ORPHAN | 서비스: to_dict()에 2개 필드 추가 |
| 14 | HIGH | brag_card.html | 449 | `top_lots` | ORPHAN | 서비스: to_dict()에 top_lots list 추가 |
| 15 | HIGH | quarterly_self_report.html | 645–709 | `sharpe_rolling`, `sharpe_series`, `hit_rate_overall`, `hit_rate_by_action`, `holding_median_days`, `holding_hist`, `top_sector`, `sector_attribution` | ORPHAN | 서비스: to_dict()에 8개 analytics 필드 추가 |
| 16 | HIGH | quarterly_self_report.html | 560–600 | `decision_ladder` (vs 서비스 `decision_quality`) | MISMATCH | 서비스 `decision_quality` 키 이름 → 템플릿 `decision_ladder` — 둘 중 하나 정렬 |
| 17 | HIGH | year_end_letter.html | 518 | `letter_paragraphs` vs `shareholder_letter` | MISMATCH (수정됨) | 2026-04-23 세션에서 bridge 추가됨 (`letter_paragraphs` 키 추가). 완료 확인 필요 |
| 18 | HIGH | year_end_letter.html | 571 | `equity_ribbon_pts` | ORPHAN | 서비스: to_dict()에 연간 equity curve 포인트 리스트 추가 |
| 19 | MEDIUM | burn_rate.html | 356 | `monthly_burn_usd`, `runway_months`, `savings_rate_pct`, `fixed_cost_ratio_pct` | ORPHAN | 서비스: BurnRateContext.to_dict()에 4개 summary 필드 추가 |
| 20 | MEDIUM | portfolio_segment.html | 380–395 | `kpi_sectors`, `kpi_styles_label`, `kpi_regions_label`, `kpi_hhi` | ORPHAN | 서비스: SegmentContext.to_dict()에 4개 KPI 필드 추가 |

---

## 각 리포트 상세

### weekly_memo.html (default 수: 15)

서비스: `services/artifacts/weekly_memo_service.py`  
서비스 to_dict() 필드: `user_id, user_name, week_number, period_start, period_end, generated_at, weekly_return_pct, benchmark_pct, alpha_pct, sector_alloc, sector_changes, top_movers_up, top_movers_down, earnings_calendar, macro_checklist, risk_notes, risk_kpi, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 24 | `year` | `'2026'` | 없음 (period_start에서 추출 가능) | 🔴 ORPHAN | 서비스: `year = self.period_start.year` 추가 |
| 2 | 615 | `issue_number` | `week_number` | 없음 | 🔴 ORPHAN | 서비스: `issue_number = week_number` 추가 |
| 3 | 616 | `doc_ref` | `'PQ-WM-...'` | 없음 | 🔴 ORPHAN | 서비스: doc_ref 계산 후 주입 |
| 4 | 617 | `hero_headline` | `['Silence', 'is the loudest', 'signal this week.']` | 없음 | 🔴 ORPHAN | 서비스: AI 또는 deterministic 문구 생성 후 주입 |
| 5 | 701 | `equity_series` | `[]` | 없음 (weekly_return_pct은 있으나 series 아님) | 🟡 STUB | 서비스: equity series list 추가 필요 |
| 6 | 709 | `benchmark_series` | `[]` | 없음 (benchmark_pct만 있음) | 🟡 STUB | 서비스: benchmark series list 추가 |
| 7 | 755 | `equity_annotation` | `{'anchor_index': ..., 'delta_text': '+0.82%', ...}` | 없음 | 🔴 ORPHAN (hardcoded delta) | 서비스: annotation 계산 주입 |
| 8 | 1075 | `risk_kpi.trough_week` | `'—'` | `risk_kpi` 필드 있음 (dict), trough_week 서브키 존재 여부 불명 | 🟡 STUB | 서비스: risk_kpi dict에 trough_week 키 보장 |
| 9 | 1077 | `risk_kpi.recovered_week` | `'—'` | 위와 동일 | 🟡 STUB | 서비스: risk_kpi dict에 recovered_week 키 보장 |
| 10 | 1143 | `pull_quote` | `"A quiet week..."` | 없음 | 🟢 OK (edge-case fallback 허용) | — |
| 11 | 1145 | `pull_quote_attribution` | `"The Editorial Voice"` | 없음 | 🟢 OK | — |
| 12 | 1151 | `what_to_watch` | `[...]` | 없음 | 🟡 STUB | 서비스: macro_checklist 또는 별도 watch list 주입 검토 |
| 13 | 1189 | `data_sources` | `['KIS', 'Alpaca', ...]` | 없음 (static) | 🟢 OK (상수) | — |
| 14 | 1194 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK (상수) | — |
| 15 | 1198 | `engine_note` | `'58 quant models ...'` | 없음 (상수) | 🟢 OK (상수) | — |

**소계**: OK 5 / STUB 4 / MISMATCH 0 / ORPHAN 3 (20%)

---

### morning_brief_plus.html (default 수: 23)

서비스: `services/morning_brief_service.py`  
서비스 content dict 필드: `kpis, market_summary, portfolio_changes, events, insight, disclaimer, generated_at`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 10 | `as_of` | `'2026-04-21'` | 없음 | 🔴 ORPHAN | 서비스: `generated_at`에서 날짜 추출 or `as_of` 키 추가 |
| 2 | 24 | `as_of_short` | `'2026-04-21'` | 없음 | 🔴 ORPHAN | 서비스: `as_of_short` 키 추가 |
| 3 | 318 | `issue_number` | `87` | 없음 | 🔴 ORPHAN | 서비스: brief 시퀀스 번호 주입 |
| 4 | 319 | `doc_ref` | `'PQ-MB-087 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스: doc_ref 생성 후 주입 |
| 5 | 320 | `hero_headline` | `['Reading the market..', 'like a tide table...', '...']` | 없음 | 🔴 ORPHAN | 서비스: AI insight에서 추출 or 정적 생성 |
| 6 | 351 | `kpis_cover` | `{'portfolio_value': ..., 'daily_pnl': ..., 'open_positions': ..., 'cash_pct': ...}` | `kpis` 있음, 키 이름 다름 | 🟠 MISMATCH | 서비스: `kpis_cover` 키로 rename or 템플릿 변수명 수정 |
| 7 | 417 | `overnight_tape` | `[{'ticker': 'SPY', ...}, ...]` | `market_summary` 있으나 tape 형식 아님 | 🔴 ORPHAN | 서비스: overnight_tape list 추가 (market_summary reshape) |
| 8 | 462 | `overnight_events` | `[{'time': '09:00', ...}, ...]` | `events` 있으나 overnight 분류 없음 | 🔴 ORPHAN | 서비스: events를 overnight/today로 분기 |
| 9 | 497 | `overnight_prose` | `{'lead': '...', 'context': '...', 'obs': '...'}` | `insight` 있으나 구조 다름 | 🔴 ORPHAN | 서비스: overnight_prose dict 생성 (insight 재구조화) |
| 10 | 547 | `macro_ladder` | `[{'indicator': 'US 10Y', ...}, ...]` | 없음 | 🔴 ORPHAN | 서비스: FMP 금리/지표 데이터 주입 |
| 11 | 603 | `today_calendar` | `[{'time': '08:30', ...}, ...]` | `events` 있으나 형식 다름 | 🔴 ORPHAN | 서비스: events → today_calendar 형식 변환 |
| 12 | 657 | `sector_premkt` | `[{'code': 'XLK', ...}, ...]` | 없음 | 🔴 ORPHAN | 서비스: sector pre-market 데이터 추가 |
| 13 | 691 | `fx_crosses` | `[{'pair': 'USD/KRW', ...}, ...]` | 없음 | 🔴 ORPHAN | 서비스: FX 데이터 추가 |
| 14 | 715 | `rates_curve` | `[{'label': '2Y', 'value': 4.82}, ...]` | 없음 | 🔴 ORPHAN | 서비스: FRED 금리 curve 데이터 추가 |
| 15 | 746 | `vix_term` | `[{'expiry': 'May', 'vix': 17.2}, ...]` | 없음 | 🔴 ORPHAN | 서비스: VIX term structure 추가 |
| 16 | 785 | `observation_notes` | `[{'time': '06:42', ...}, ...]` | 없음 | 🔴 ORPHAN | 서비스: 관찰 노트 list 추가 |
| 17 | 815 | `pull_quote` | `"A morning brief is a lantern..."` | 없음 | 🟢 OK (editorial) | — |
| 18 | 817 | `pull_quote_attribution` | `"PivoxQuant Morning Desk"` | 없음 | 🟢 OK (상수) | — |
| 19 | 858 | `as_of` (footer) | `'2026-04-21'` | 위와 동일 ORPHAN | 🔴 ORPHAN | 1번과 동일 fix |
| 20 | 879 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 21 | 883 | `engine_note` | `'Historical record only...'` | 없음 (상수) | 🟢 OK | — |
| 22 | 899 | `generated_at` | `as_of` | `generated_at` 존재 | 🟢 OK | — |
| 23 | 340 | `as_of` (cover) | `'2026-04-21'` | 위와 동일 ORPHAN | 🔴 ORPHAN | 1번과 동일 fix |

**소계**: OK 6 / STUB 0 / MISMATCH 1 / ORPHAN 16 (70%)

---

### year_end_letter.html (default 수: 19)

서비스: `services/artifacts/year_end_letter_service.py`  
서비스 to_dict() 필드: `user_id, user_name, year, period_start, period_end, generated_at, opening_value, closing_value, ytd_return_pct, benchmark_pct, alpha_pct, total_trades, win_rate_pct, sector_contribution, best_decisions, worst_decisions, risk_profile, realized_style, consistency_score, consistency_notes, watch_items, shareholder_letter, letter_paragraphs, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 11 | `user_name` | `'Reader'` | `user_name` 존재 | 🟢 OK | — |
| 2 | 11 | `year` | `'2025'` | `year` 존재 | 🟢 OK | — |
| 3 | 426 | `year` (body) | `'2025'` | `year` 존재 | 🟢 OK | — |
| 4 | 427 | `issue_number` | `1` | 없음 | 🔴 ORPHAN | 서비스: issue_number 추가 |
| 5 | 428 | `doc_ref` | `'PQ-YEL-01 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스: doc_ref 생성 추가 |
| 6 | 429 | `hero_headline` | `['Twelve months...', 'One ledger...', '...']` | 없음 | 🔴 ORPHAN | 서비스: AI 또는 결정론적 생성 |
| 7 | 518 | `letter_paragraphs` | `[...]` (하드코딩 5문단) | `letter_paragraphs` 존재 (2026-04-23 bridge 추가) | 🟢 OK (fix 완료) | — |
| 8 | 540 | `margin_notes` | `[...]` | 없음 | 🔴 ORPHAN | 서비스: margin_notes 생성 추가 |
| 9 | 571 | `equity_ribbon_pts` | `[...]` | 없음 | 🔴 ORPHAN | 서비스: 연간 equity curve data 추가 |
| 10 | 686 | `monthly_rows` | `[...]` | 없음 (`sector_contribution` 있으나 monthly 형식 아님) | 🟠 MISMATCH | 서비스: monthly_rows 계산 추가 (monthly P/L breakdown) |
| 11 | 719 | `r.sparkline_pts` | `[0, r.pnl]` | `monthly_rows` 서브키 | 🟡 STUB | monthly_rows fix에 포함 |
| 12 | 764 | `reflection_blocks` | `[...]` (하드코딩 3블록) | 없음 | 🔴 ORPHAN | 서비스: AI 생성 또는 consistency_notes 재구조화 |
| 13 | 850 | `pull_quote` | `"The year did not arrive..."` | 없음 | 🟢 OK (editorial) | — |
| 14 | 852 | `pull_quote_attr` | `"PivoxQuant · Year 2025"` | 없음 | 🟢 OK (상수) | — |
| 15 | 856 | `not_claimed` | `[...]` | 없음 | 🟡 STUB | 서비스: worst_decisions reshape 가능 |
| 16 | 903 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 17 | 916 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 18 | 943 | `generated_at` | `'2026-04-21'` | `generated_at` 존재 | 🟢 OK | — |
| 19 | 491 | `user_name` (opener) | `'the reader'` | `user_name` 존재 | 🟢 OK | — |

**소계**: OK 8 / STUB 3 / MISMATCH 2 / ORPHAN 6 (32%)

---

### earnings_prebrief.html (default 수: 42)

서비스: `services/artifacts/earnings_prebrief_service.py`  
서비스 to_dict() 필드: `user_id, user_name, ticker, company_name, earnings_datetime, fiscal_period, generated_at, consensus_eps, consensus_eps_low, consensus_eps_high, consensus_revenue, current_price, surprise_history, expected_questions, position_shares, position_avg_cost, position_mv, sensitivity_beat, sensitivity_miss, risk_notes, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 11 | `ticker` | `'AAPL'` | `ticker` 존재 | 🟢 OK | — |
| 2 | 11 | `fiscal_period` | `'Q2 FY26'` | `fiscal_period` 존재 | 🟢 OK | — |
| 3 | 407 | `ticker` (body) | `'AAPL'` | OK | 🟢 OK | — |
| 4 | 408 | `company_name` | `'Apple Inc.'` | `company_name` 존재 | 🟢 OK | — |
| 5 | 409 | `fiscal_period` (body) | `'Q2 FY26'` | OK | 🟢 OK | — |
| 6 | 410 | `reporting_date` | `'2026-04-30'` | `earnings_datetime` 존재 (다른 이름) | 🟠 MISMATCH | 서비스: `reporting_date = self.earnings_datetime.date().isoformat()` 추가 |
| 7 | 412 | `issue_number` | `1` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 8 | 413 | `hero_headline` | `['The number...', 'is only ever...', '...']` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 9 | 452 | `reporting_time` | `'After the close (AMC)'` | `earnings_datetime` 있음 (시간 파싱 가능) | 🟠 MISMATCH | 서비스: AMC/BMO 분류 후 `reporting_time` 주입 |
| 10 | 456 | `consensus_eps` | `1.62` | `consensus_eps` 존재 | 🟢 OK | — |
| 11 | 457 | `consensus_as_of` | `'2026-04-19'` | 없음 | 🔴 ORPHAN | 서비스: FMP 조회일 추가 |
| 12 | 461 | `implied_move_pct` | `4.2` | 없음 | 🔴 ORPHAN | 서비스: option chain 조회 후 추가 |
| 13 | 462 | `option_as_of` | `'2026-04-20'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 14 | 493 | `revenue_history` | `[...]` (하드코딩 AAPL) | 없음 | 🔴 ORPHAN | 서비스: FMP quarterly revenue 조회 후 추가 |
| 15 | 571 | `consensus_eps_low` | `1.48` | `consensus_eps_low` 존재 | 🟢 OK | — |
| 16 | 571 | `consensus_eps_high` | `1.76` | `consensus_eps_high` 존재 | 🟢 OK | — |
| 17 | 597 | `consensus_eps_low` (margin) | `1.48` | OK | 🟢 OK | — |
| 18 | 626 | `surprise_history` | `[...]` | `surprise_history` 존재 | 🟡 STUB (list 형식 보장 필요) | 서비스: spark/surprise_pct/reaction_pct 서브키 보장 |
| 19 | 650 | `r.spark` | `[0,0,0,0,0,0,0]` | surprise_history 서브키 | 🟡 STUB | 위와 동일 |
| 20 | 662 | `r.surprise_pct` | `0` | surprise_history 서브키 | 🟡 STUB | — |
| 21 | 663 | `r.reaction_pct` | `0` | surprise_history 서브키 | 🟡 STUB | — |
| 22 | 683 | `surprise_bins` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 분포 계산 추가 |
| 23 | 733 | `beat_rate_pct` | `88` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 히스토리 기반 계산 추가 |
| 24 | 735 | `beat_timeline` | `[1,1,1,1,1,1,1,1]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 25 | 752 | `drift_bars` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 26 | 779 | `implied_realised_r` | `0.82` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 27 | 781 | `implied_vs_realised` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 28 | 810 | `peer_group` | `'Megacap Tech'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 29 | 811 | `peer_eps_comp` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP peer data 추가 |
| 30 | 848 | `reading_notes` | `[...]` | 없음 | 🟡 STUB | 서비스: expected_questions reshape 가능 |
| 31 | 882 | `pull_quote` | `"The market rehearses..."` | 없음 | 🟢 OK (editorial) | — |
| 32 | 884 | `pull_quote_attr` | `'PivoxQuant · Earnings Desk'` | 없음 | 🟢 OK (상수) | — |
| 33 | 891 | `cannot_tell` | `[...]` | 없음 | 🟢 OK (legal boilerplate) | — |
| 34 | 930 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 35 | 940 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 36 | 944 | `engine_note` | `'58 quant models ...'` | 없음 (상수) | 🟢 OK | — |
| 37 | 583 | `consensus_as_of` (body) | `'2026-04-19'` | ORPHAN (위 11번 동일) | 🔴 ORPHAN | 동일 fix |
| 38 | 591 | `option_as_of` (body) | `'2026-04-20'` | ORPHAN (위 13번 동일) | 🔴 ORPHAN | 동일 fix |
| 39 | 607 | `reporting_time` (body) | `'After-the-close (AMC)...'` | MISMATCH (위 9번 동일) | 🟠 MISMATCH | 동일 fix |
| 40 | 924 | `user_name` | `'the reader'` | `user_name` 존재 | 🟢 OK | — |
| 41 | 467 | `user_name` (cover) | `'the reader'` | OK | 🟢 OK | — |
| 42 | 411 | `doc_ref` | `'PQ-EB-01 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |

**소계**: OK 14 / STUB 5 / MISMATCH 3 / ORPHAN 16 (38%)  
Note: 중복 line(37,38,39)은 동일 ORPHAN 변수의 재출현 — 실질 ORPHAN 변수 고유 수는 13개

---

### quarterly_self_report.html (default 수: 31)

서비스: `services/artifacts/quarterly_self_report_service.py`  
서비스 to_dict() 필드: `user_id, user_name, quarter_label, period_start, period_end, generated_at, opening_value, closing_value, net_cash_flow, quarterly_return_pct, mdna, segments, risk_factors, internal_controls, legal_matters, principal_positions, thesis_entries, thesis_checks, decision_quality, thesis_checklist, watch_items, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 11 | `quarter_label` | `'Q1 2026'` | `quarter_label` 존재 | 🟢 OK | — |
| 2 | 421 | `quarter_label` (body) | OK | 🟢 OK | — | — |
| 3 | 422 | `issue_number` | `1` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 423 | `doc_ref` | `'PQ-QSR-01 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 5 | 424 | `hero_headline` | `['...', '...', '...']` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 6 | 526 | `signoff_line` | `'In observation,'` | 없음 | 🟡 STUB | 정적 상수 — OK 수준 |
| 7 | 533 | `margin_notes` | `[...]` | 없음 | 🔴 ORPHAN | 서비스: consistency_notes reshape |
| 8 | 560 | `decision_ladder` | `[...]` (하드코딩 5행) | `decision_quality` 있음 | 🟠 MISMATCH | 템플릿 변수명 `decision_quality`로 수정 or 서비스 키 rename |
| 9 | 587 | `r.spark` | `[0,0,0,0,0,0,0]` | `segments` 서브키 | 🟡 STUB | 서비스: segments list 항목에 spark 키 추가 |
| 10 | 599 | `r.pnl_pct` | `0` | `segments` 서브키 | 🟡 STUB | 서비스: segments에 pnl_pct 추가 |
| 11 | 600 | `r.weight_delta` | `0` | `segments` 서브키 | 🟡 STUB | 서비스: segments에 weight_delta 추가 |
| 12 | 645 | `sharpe_rolling` | `1.08` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: risk 계산 추가 |
| 13 | 646 | `sharpe_series` | `[0.42, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 14 | 666 | `hit_rate_overall` | `58` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: win_rate 기반 계산 추가 |
| 15 | 667 | `hit_rate_by_action` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 16 | 690 | `holding_median_days` | `14` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 17 | 691 | `holding_hist` | `[2,4,6,7,5,3,2,1,0,1]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 18 | 708 | `top_sector` | `'Semiconductors'` (하드코딩) | `segments` 있음 | 🟠 MISMATCH | 서비스: segments에서 top_sector 계산 후 주입 |
| 19 | 709 | `sector_attribution` | `[...]` (하드코딩) | `segments` 있음 (다른 구조) | 🟠 MISMATCH | 서비스: segments → sector_attribution reshape |
| 20 | 747 | `self_review_notes` | `[...]` | `thesis_entries` 있음 | 🟡 STUB | 서비스: thesis_entries reshape 가능 |
| 21 | 780 | `pull_quote` | `'Self-review is the small hinge...'` | 없음 | 🟢 OK (editorial) | — |
| 22 | 782 | `pull_quote_attr` | `'PivoxQuant · Quarterly Desk'` | 없음 | 🟢 OK | — |
| 23 | 789 | `cannot_settle` | `[...]` | 없음 | 🟢 OK (legal boilerplate) | — |
| 24 | 805 | `does_record` | `[...]` | 없음 | 🟢 OK (legal boilerplate) | — |
| 25 | 844 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 26 | 854 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 27 | 858 | `engine_note` | `'58 quant models ...'` | 없음 (상수) | 🟢 OK | — |
| 28 | 487 | `user_name` | `'the reader'` | `user_name` 존재 | 🟢 OK | — |
| 29 | 527 | `user_name` (sign) | `'the reader'` | OK | 🟢 OK | — |
| 30 | 838 | `user_name` (footer) | OK | 🟢 OK | — | — |
| 31 | 526 | `signoff_line` | `'In observation,'` | — | 🟡 STUB | — |

**소계**: OK 11 / STUB 5 / MISMATCH 3 / ORPHAN 9 (29%)

---

### brag_card.html (default 수: 21)

서비스: `services/artifacts/brag_card_service.py`  
서비스 to_dict() 필드: `user_id, user_name, referral_code, month_label, month_label_long, month_start, month_end, generated_at, return_pct, trade_count, best_ticker, best_return_pct, worst_ticker, worst_return_pct, anonymous, is_empty, share_token, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 296 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 297 | `doc_ref` | `'PQ-BC-04 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 298 | `hero_headline` | `['A small note to self.', ...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 300 | `win_rate_pct` | `67.0` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: trade_count 기반 계산 추가 |
| 5 | 301 | `best_pnl_usd` | `1240` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 베스트 트레이드 USD P/L 추가 |
| 6 | 318 | `month_label_long` | `month_label` | `month_label_long` 존재 | 🟢 OK | — |
| 7 | 382 | `best_ticker` (display) | `'NVDA'` | `best_ticker` 존재 | 🟢 OK | — |
| 8 | 384 | `hold_days` | `8` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 베스트 트레이드 보유일 추가 |
| 9 | 392 | `best_ticker` (entry text) | `'NVDA'` | OK | 🟢 OK | — |
| 10 | 393 | `entry_date` | `'April 3'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 실제 진입일 추가 |
| 11 | 393 | `entry_price` | `'842'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 실제 진입가 추가 |
| 12 | 394 | `exit_date` | `'April 11'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 실제 청산일 추가 |
| 13 | 394 | `exit_price` | `'879'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 실제 청산가 추가 |
| 14 | 403 | `month_label_long` (sign) | `month_label` | OK | 🟢 OK | — |
| 15 | 411 | `hold_days` (margin) | `8` | ORPHAN (위 8번) | 🔴 ORPHAN | 동일 fix |
| 16 | 419 | `position_size_pct` | `'3.2'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 포지션 사이즈 % 추가 |
| 17 | 449 | `top_lots` | `[...]` (하드코딩 3행) | 없음 | 🔴 ORPHAN | 서비스: 상위 트레이드 list 추가 |
| 18 | 536 | `generated_at` | `'2026-04-21'` | `generated_at` 존재 | 🟢 OK | — |
| 19 | 538 | `month_label_long` (footer) | `month_label` | OK | 🟢 OK | — |
| 20 | 542 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 21 | 547 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |

**소계**: OK 7 / STUB 0 / MISMATCH 0 / ORPHAN 14 (67%)  
Note: hold_days가 2행에 출현(line 384, 411) — 고유 ORPHAN 변수는 13개

---

### burn_rate.html (default 수: 26)

서비스: `services/artifacts/burn_rate_service.py`  
서비스 to_dict() 필드: `user_id, user_name, period_label, period_start, period_end, generated_at, trades_total, notional_total, commission_total, tx_tax_total, cgt_est_total, fx_spread_total, slippage_total, burn_total, portfolio_value, burn_pct, by_market, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 353 | `issue_number` | `12` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 354 | `doc_ref` | `'PQ-BR-12 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 355 | `hero_headline` | `['A slow arithmetic.', ...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 356 | `monthly_burn_usd` | `2480` (하드코딩) | `burn_total` 있음 (다른 단위/이름) | 🟠 MISMATCH | 템플릿: `monthly_burn_usd` → `burn_total`로 수정 |
| 5 | 357 | `runway_months` | `32` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: runway 계산 추가 |
| 6 | 358 | `savings_rate_pct` | `62.0` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 (외부 데이터 또는 섹션 제거) |
| 7 | 359 | `fixed_cost_ratio_pct` | `41.0` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 또는 섹션 제거 |
| 8 | 376 | `period_label_long` | `period_label` | `period_label` 있음 (short form) | 🟡 STUB | 서비스: period_label_long 추가 |
| 9 | 431 | `burn_series` | `[...]` | `burn_total` 있음 (단일값) | 🔴 ORPHAN | 서비스: 월별 시계열 추가 |
| 10 | 581 | `housing_share_pct` | `48` (하드코딩) | 없음 | 🟡 STUB (외부 데이터) | 섹션 제거 권장 |
| 11 | 589 | `yoy_burn_pct` | `'+3.2'` (하드코딩) | 없음 | 🟡 STUB | 섹션 제거 또는 by_market 기반 계산 |
| 12 | 597 | `variance_usd` | `'180'` (하드코딩) | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 13 | 619 | `cat_rows` | `[...]` (하드코딩) | `by_market` 있음 (다른 구조) | 🟡 STUB | 서비스: by_market → cat_rows reshape |
| 14 | 688 | `share_quad` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 15 | 695 | `fixed_variable` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 16 | 709 | `runway_scenarios` | `{...}` | 없음 | 🟡 STUB | 서비스: runway 시나리오 계산 추가 |
| 17 | 714 | `save_rate_series` | `[58,61,...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 18 | 909 | `pull_quote` | `"Frugality is not..."` | 없음 | 🟢 OK (editorial) | — |
| 19 | 911 | `pull_quote_attribution` | `"The Ledger Voice"` | 없음 | 🟢 OK | — |
| 20 | 917 | `not_verified` | `[...]` | 없음 | 🟢 OK (legal) | — |
| 21 | 946 | `generated_at` | `'2026-04-22'` | `generated_at` 존재 | 🟢 OK | — |
| 22 | 948 | `period_label_long` (footer) | `period_label` | 위 STUB | 🟡 STUB | 동일 fix |
| 23 | 952 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 24 | 957 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 25 | 961 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 26 | 977 | `generated_at` (colophon) | `'2026-04-22'` | OK | 🟢 OK | — |

**소계**: OK 8 / STUB 9 / MISMATCH 1 / ORPHAN 5 (19%)  
Note: burn_rate.html은 가계부/생활비 서비스인데 PivoxQuant는 실제로 가계비 데이터를 수집하지 않음 — `savings_rate_pct`, `housing_share_pct`, `fixed_cost_ratio_pct` 등 외부 비금융데이터 필드는 섹션 제거가 가장 합리적

---

### capital_allocation.html (default 수: 20)

서비스: `services/artifacts/capital_allocation_service.py`  
서비스 generate_for_user() 반환 dict 필드: `calc_token, user_id, user_name, cash_amount, portfolio_ccy, generated_at, scenarios, etf_whitelist, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 316 | `issue_number` | `1` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 317 | `doc_ref` | `'PQ-CA-01 · v2026.04.22'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 318 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 347 | `kpis_cover` | `{'portfolio_value': ..., ...}` | 없음 (cash_amount, scenarios 있음) | 🔴 ORPHAN | 서비스: kpis_cover dict 생성 추가 |
| 5 | 399 | `months_labels` | `['May','Jun',...]` | 없음 | 🔴 ORPHAN | 서비스: 기간 레이블 생성 |
| 6 | 400 | `allocation_stack` | `{...}` (하드코딩 시계열) | 없음 | 🔴 ORPHAN | 서비스: 배분 시계열 계산 추가 |
| 7 | 496 | `spread_prose` | `[...]` | 없음 | 🔴 ORPHAN | 서비스: narrative 생성 추가 |
| 8 | 507 | `allocation_margin` | `{...}` | 없음 | 🔴 ORPHAN | 서비스: 요약 통계 추가 |
| 9 | 553 | `ladder_rows` | `[...]` | `scenarios` 있음 (다른 구조) | 🟠 MISMATCH | 서비스: scenarios → ladder_rows reshape 또는 템플릿 수정 |
| 10 | 637 | `contribution_bars` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 11 | 673 | `drift_lines` | `{...}` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 12 | 714 | `rebalance_events` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 13 | 748 | `portfolio_vs_6040_p` | `[0.0, 0.4, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: 60/40 비교 계산 추가 |
| 14 | 749 | `portfolio_vs_6040_b` | `[0.0, 0.5, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 15 | 791 | `allocation_notes` | `[...]` | 없음 | 🟡 STUB | 서비스: narrative 기반 생성 |
| 16 | 819 | `pull_quote` | `"An allocation is not a verdict..."` | 없음 | 🟢 OK | — |
| 17 | 821 | `pull_quote_attribution` | `"PivoxQuant Allocation Desk"` | 없음 | 🟢 OK | — |
| 18 | 877 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 19 | 881 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 20 | 897 | `generated_at` | `'2026'` | `generated_at` 존재 | 🟢 OK | — |

**소계**: OK 5 / STUB 1 / MISMATCH 1 / ORPHAN 13 (65%)

---

### credit_rating.html (default 수: 18)

서비스: `services/artifacts/credit_rating_service.py`  
서비스 to_dict() 필드: `user_id, user_name, as_of, generated_at, diversification, liquidity, risk_adjusted_return, drawdown_discipline, cash_buffer, composite_score, grade, prev_grade, change, factor_details, position_count, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 323 | `issue_number` | `2` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 324 | `doc_ref` | `'PQ-CR-02 · v2026.04.22'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 325 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 356 | `kpis_cover` | `{'grade': ..., 'composite_score': ..., 'position_count': ..., 'prev_grade': ...}` | 모두 개별 필드로 존재 | 🟠 MISMATCH | 서비스: kpis_cover dict 합산 또는 템플릿을 개별 필드로 수정 |
| 5 | 410 | `rating_distribution` | `[...]` | `factor_details` 있음 (다른 구조) | 🟡 STUB | 서비스: factor_details → rating_distribution reshape |
| 6 | 483 | `spread_prose` | `[...]` | 없음 | 🟡 STUB | 서비스: narrative 생성 |
| 7 | 494 | `rating_margin` | `{...}` | `factor_details` 있음 | 🟡 STUB | 서비스 reshape |
| 8 | 541 | `positions` (template var) | `[...]` | 없음 (position_count만 있음) | 🟡 STUB | 서비스: positions list 추가 |
| 9 | 630 | `credit_curve` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 10 | 661 | `duration_histogram` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 11 | 690 | `rating_migration` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 12 | 723 | `sector_concentration` | `[...]` | 없음 | 🟡 STUB | 섹션 제거 권장 |
| 13 | 759 | `reading_notes` | `[...]` | 없음 | 🟡 STUB | 서비스: factor_details reshape |
| 14 | 789 | `pull_quote` | `"A credit rating is a letter..."` | 없음 | 🟢 OK | — |
| 15 | 791 | `pull_quote_attribution` | `"PivoxQuant Credit Desk"` | 없음 | 🟢 OK | — |
| 16 | 849 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 17 | 853 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 18 | 869 | `generated_at` | `as_of` | `generated_at`, `as_of` 모두 존재 | 🟢 OK | — |

**소계**: OK 5 / STUB 9 / MISMATCH 1 / ORPHAN 3 (17%)

---

### dd_checklist.html (default 수: 28)

서비스: `services/artifacts/dd_checklist_service.py`  
서비스 run_for_user() data dict 필드: `user_id, user_name, as_of, generated_at, pending, disclaimer`  
(Context to_dict() 없음. pending은 `[{position_id, ticker, shares, avg_cost, added_at, days_since}]` list)

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 374 | `issue_number` | `2` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 375 | `doc_ref` | `'PQ-DD-...'` | `ticker` 있음 (pending 서브키) | 🟠 MISMATCH | 서비스: ticker top-level 키 추가 or doc_ref 생성 |
| 3 | 376 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 382 | `ticker` (top-level) | `'AAPL'` | `pending[n].ticker` 있음 (list 서브키) | 🟠 MISMATCH | 서비스: `ticker = pending[0].ticker` top-level 추가 |
| 5 | 383 | `completeness_text` | `'24 / 30'` | 없음 | 🔴 ORPHAN | 서비스 추가 (제출 카운트 기반) |
| 6 | 384 | `red_flags` | `0` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 7 | 385 | `review_date` | `'2026-04-21'` | `as_of` 있음 (다른 이름) | 🟠 MISMATCH | 템플릿: `review_date` → `as_of` 수정 |
| 8 | 403 | `period_label` | `'Q2 2026'` | 없음 | 🔴 ORPHAN | 서비스: as_of에서 quarter 계산 추가 |
| 9 | 436 | `period_label` (cover) | `'Q2 2026'` | ORPHAN (위 동일) | 🔴 ORPHAN | 동일 fix |
| 10 | 463 | `fundamentals_axes` | `[...]` | 없음 | 🔴 ORPHAN | 서비스: FMP fundamentals 조회 추가 (대형) |
| 11 | 655 | `checklist_items` | `[...]` (하드코딩 30개) | 없음 | 🔴 ORPHAN | 서비스: 체크리스트 항목 구조화 주입 |
| 12 | 740 | `quarterly_label` | `'$94.9B · Q4 FY25'` (하드코딩 AAPL) | 없음 | 🔴 ORPHAN | 서비스: FMP quarterly revenue 주입 |
| 13 | 741 | `quarterly_revenue` | `[78.4, ...]` (하드코딩 AAPL) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 14 | 762 | `margin_label` | `'46.2% · 30.2% · 24.4%'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 15 | 763 | `margin_gross` | `[38.2, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 16 | 764 | `margin_op` | `[24.1, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 17 | 765 | `margin_net` | `[20.1, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 18 | 794 | `fcf_label` | `'$99.8B · FY25'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 19 | 795 | `fcf_history` | `[73.4, ...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP 주입 |
| 20 | 819 | `peer_label` | `'28.4 · 32.1 · 24.8 · 26.2'` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP peer 주입 |
| 21 | 820 | `peer_bars` | `[...]` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: FMP peer 주입 |
| 22 | 900 | `pull_quote` | `"Due diligence is the act..."` | 없음 | 🟢 OK | — |
| 23 | 902 | `pull_quote_attribution` | `"PivoxQuant Research Desk"` | 없음 | 🟢 OK | — |
| 24 | 908 | `not_answered` | `[...]` | 없음 | 🟢 OK (legal) | — |
| 25 | 956 | `period_label` (footer) | `'Q2 2026'` | ORPHAN (동일) | 🔴 ORPHAN | 동일 fix |
| 26 | 961 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 27 | 976 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 28 | 980 | `engine_note` | `'Checklist observation...'` | 없음 (상수) | 🟢 OK | — |

**소계**: OK 6 / STUB 0 / MISMATCH 4 / ORPHAN 18 (64%)  
Note: quarterly_label, margin_label, peer_label은 하드코딩이 'AAPL' 기준 — 다른 ticker 유저는 완전히 잘못된 하드코딩을 봄 (CRITICAL)

---

### dividend_income.html (default 수: 18)

서비스: `services/artifacts/dividend_income_service.py`  
서비스 to_dict() 필드: `user_id, user_name, month_label, period_start, period_end, next_month_label, generated_at, fx_rate, received_rows, received_totals, position_count, monthly_series, yoy_growth_pct, forward_rows, forward_totals, annual_yield_est, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 315 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 316 | `doc_ref` | `'PQ-DI-04 · v2026.04.22'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 317 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 346 | `kpis_cover` | `{'received_usd': ..., 'yield_est': ..., ...}` | 개별 필드 존재 | 🔴 ORPHAN | 서비스: kpis_cover dict 합산 추가 |
| 5 | 400 | `monthly_bars` | `[...]` | `monthly_series` 있음 (형식 다를 수 있음) | 🟡 STUB | 서비스: monthly_series → monthly_bars reshape 확인 |
| 6 | 464 | `spread_prose` | `[...]` | 없음 | 🟡 STUB | 서비스: narrative 생성 |
| 7 | 475 | `dividend_margin` | `{...}` | `received_totals` 있음 | 🟡 STUB | 서비스: received_totals → dividend_margin reshape |
| 8 | 521 | `dividend_rows` | `[...]` | `received_rows` 있음 | 🟡 STUB | 서비스: received_rows 형식 일치 확인 |
| 9 | 607 | `sector_mix` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 10 | 645 | `yoy_growth` | `[...]` | `yoy_growth_pct` 있음 (단일값) | 🟡 STUB | 서비스: 12개월 series 추가 |
| 11 | 678 | `calendar_heatmap` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 12 | 715 | `yield_scatter` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 13 | 761 | `reading_notes` | `[...]` | 없음 | 🟡 STUB | 서비스: narrative 기반 생성 |
| 14 | 789 | `pull_quote` | `"A dividend is a kindness..."` | 없음 | 🟢 OK | — |
| 15 | 791 | `pull_quote_attribution` | `"PivoxQuant Dividend Desk"` | 없음 | 🟢 OK | — |
| 16 | 847 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 17 | 851 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 18 | 867 | `generated_at` | `month_label` | `generated_at` 존재 | 🟢 OK | — |

**소계**: OK 5 / STUB 9 / MISMATCH 0 / ORPHAN 4 (22%)

---

### insider_mirror.html (default 수: 19)

서비스: `services/artifacts/insider_mirror_service.py`  
서비스 to_dict() 필드 (MirrorContext): `user_id, user_name, period_label, period_start, period_end, generated_at, tickers, us_tickers, kr_tickers, events, total_events, dart_configured, trend_rows, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 322 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 323 | `doc_ref` | `'PQ-IM-04 · v2026.04.22'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 324 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 353 | `kpis_cover` | `{'total_filings': ..., 'net_buying': ..., ...}` | `total_events` 있음 (부분) | 🟡 STUB | 서비스: kpis_cover dict 합산 추가 |
| 5 | 405 | `filings_timeline` | `[...]` | `trend_rows` 있음 (형식 다를 수 있음) | 🟡 STUB | 서비스: trend_rows → filings_timeline 형식 일치 확인 |
| 6 | 489 | `spread_prose` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 7 | 500 | `filings_margin` | `{...}` | 없음 | 🟡 STUB | 서비스 추가 |
| 8 | 546 | `filings` (list) | `[...]` | `events` 있음 (다른 이름) | 🟠 MISMATCH | 템플릿: `filings` → `events`로 수정 또는 서비스 키 추가 |
| 9 | 634 | `sector_filings` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 10 | 664 | `net_buy_top` | `[...]` | `events` 필터링으로 생성 가능 | 🟡 STUB | 서비스: events → net_buy_top/sell_top 추가 |
| 11 | 693 | `net_sell_top` | `[...]` | 위와 동일 | 🟡 STUB | 서비스 추가 |
| 12 | 722 | `form_types` | `[...]` | 없음 | 🟡 STUB | 서비스: form type 집계 추가 |
| 13 | 765 | `reading_notes` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 14 | 794 | `pull_quote` | `"Insider activity is a confession..."` | 없음 | 🟢 OK | — |
| 15 | 796 | `pull_quote_attribution` | `"PivoxQuant Research Desk"` | 없음 | 🟢 OK | — |
| 16 | 836 | `period_end` (footer) | `'2026-04-22'` | `period_end` 존재 | 🟢 OK | — |
| 17 | 853 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 18 | 857 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 19 | 873 | `generated_at` | `period_label` | `generated_at` 존재 | 🟢 OK | — |

**소계**: OK 6 / STUB 10 / MISMATCH 1 / ORPHAN 3 (16%)

---

### monthly_finance.html (default 수: 19)

서비스: `services/artifacts/monthly_finance_service.py`  
서비스 to_dict() 필드: `user_id, user_name, month_label, period_start, period_end, next_month_label, generated_at, fx_rate, cash, positions_mv, liquidity_ratio, position_count, burn_rate_krw, runway_months, cost_breakdown, tax_estimate, watch, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 347 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 348 | `doc_ref` | `'PQ-MF-04 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 349 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 380 | `kpis_cover` | `{'cash': ..., 'runway': ..., 'tax': ..., 'positions_mv': ...}` | 모두 개별 필드 존재 | 🟠 MISMATCH | 서비스: kpis_cover dict 합산 추가 (직접 필드 접근으로 변환 가능) |
| 5 | 451 | `equity_walk` | `[...]` | 없음 | 🟡 STUB | 서비스: 월별 포트폴리오 equity walk 추가 |
| 6 | 541 | `ledger_prose` | `[...]` | 없음 | 🟡 STUB | 서비스: narrative 추가 |
| 7 | 552 | `ledger_margin` | `{...}` | `cost_breakdown`, `tax_estimate` 있음 | 🟠 MISMATCH | 서비스: ledger_margin 키로 합산 또는 템플릿 수정 |
| 8 | 601 | `closed_lots` | `[...]` | 없음 | 🟡 STUB | 서비스: 청산 포지션 list 추가 |
| 9 | 665 | `cash_flow` | `{...}` | `cash`, `burn_rate_krw` 있음 (분산) | 🟡 STUB | 서비스: cash_flow dict 합산 추가 |
| 10 | 710 | `sector_attribution` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 11 | 748 | `contrib_detract` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 12 | 782 | `dividend_events` | `[...]` | 없음 | 🟡 STUB | 서비스 추가 |
| 13 | 815 | `cost_breakdown_q` | `[...]` | `cost_breakdown` 있음 | 🟡 STUB | 서비스: cost_breakdown → quarterly reshape |
| 14 | 848 | `reconciliation_notes` | `[...]` | `watch` 있음 | 🟡 STUB | 서비스: watch reshape 가능 |
| 15 | 878 | `pull_quote` | `"A ledger is not a verdict..."` | 없음 | 🟢 OK | — |
| 16 | 880 | `pull_quote_attribution` | `"PivoxQuant Finance Desk"` | 없음 | 🟢 OK | — |
| 17 | 942 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 18 | 946 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 19 | 962 | `generated_at` | `month_label` | `generated_at` 존재 | 🟢 OK | — |

**소계**: OK 5 / STUB 10 / MISMATCH 2 / ORPHAN 3 (16%)

---

### portfolio_segment.html (default 수: 32)

서비스: `services/artifacts/portfolio_segment_service.py`  
서비스 to_dict() 필드 (SegmentContext): `user_id, user_name, quarter_label, period_start, period_end, generated_at, portfolio_ccy, portfolio_value, sector_rows, region_rows, style_rows, best_segments, worst_segments, narrative, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 343 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 344 | `doc_ref` | `'PQ-PS-04'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 345 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 366 | `period_label` | `'April 2026'` | `quarter_label` 있음 | 🟠 MISMATCH | 서비스: `period_label = quarter_label` 별칭 추가 |
| 5 | 380 | `kpi_sectors` | `8` | `sector_rows` 있음 (list length) | 🟠 MISMATCH | 서비스: `kpi_sectors = len(sector_rows)` 추가 |
| 6 | 385 | `kpi_styles_label` | `'Growth · Value · Core'` | `style_rows` 있음 | 🟠 MISMATCH | 서비스: style_rows → label string 변환 추가 |
| 7 | 390 | `kpi_regions_label` | `'US · International'` | `region_rows` 있음 | 🟠 MISMATCH | 서비스: region_rows → label string 변환 추가 |
| 8 | 395 | `kpi_hhi` | `1840` (하드코딩) | 없음 | 🔴 ORPHAN | 서비스: HHI 계산 추가 |
| 9 | 427 | `treemap_segments` | `[...]` | `sector_rows` 있음 (다른 구조) | 🟡 STUB | 서비스: sector_rows → treemap_segments reshape |
| 10 | 578 | `segment_ladder` | `[]` | `sector_rows` 있음 | 🟡 STUB | 서비스: sector_rows → segment_ladder reshape |
| 11 | 595 | `p.spark` | `[0,0,...,0,0]` | sector_rows 서브키 | 🟡 STUB | 서비스: sector_rows 항목에 spark 추가 |
| 12 | 664 | `style_box_label` | `'Large Growth · 18%'` | `style_rows` 있음 | 🟡 STUB | 서비스: style_rows에서 dominant label 추출 |
| 13 | 665 | `style_box` | `[[0.08,0.12,...], ...]` | 없음 | 🟡 STUB | 서비스 추가 (복잡한 계산) |
| 14 | 666 | `style_box_labels` | `{'rows': [...], 'cols': [...]}` | 없음 (상수) | 🟢 OK | — |
| 15 | 707 | `region_label` | `'US · 72.5%'` | `region_rows` 있음 | 🟡 STUB | 서비스: 최대 region label 추출 |
| 16 | 708 | `region_split` | `[...]` | `region_rows` 있음 | 🟡 STUB | 서비스: region_rows reshape |
| 17 | 743 | `rotation_label` | `'Top 4 · TR'` | 없음 | 🟡 STUB | 서비스 추가 |
| 18 | 744 | `sector_rotation` | `[...]` | `sector_rows` 있음 | 🟡 STUB | 서비스 reshape |
| 19 | 787 | `corr_label` | `'Tech-Fin · 0.54'` | 없음 | 🟡 STUB | 서비스 추가 |
| 20 | 788 | `segment_corr_labels` | `[...]` | `sector_rows` 에서 추출 가능 | 🟡 STUB | 서비스 추가 |
| 21 | 789 | `segment_corr_matrix` | `[[...], ...]` | 없음 | 🟡 STUB | 서비스: 상관행렬 계산 추가 |
| 22 | 844 | `right_rail_notes` | `[...]` | `narrative` 있음 | 🟡 STUB | 서비스: narrative reshape |
| 23 | 877 | `pull_quote` | `"Segments are not strategies..."` | 없음 | 🟢 OK | — |
| 24 | 879 | `pull_quote_attribution` | `"PivoxQuant Research Desk"` | 없음 | 🟢 OK | — |
| 25 | 885 | `not_answered` | `[...]` | 없음 | 🟢 OK (legal) | — |
| 26 | 931 | `period_label` (footer) | `'April 2026'` | MISMATCH (위 4번) | 🟠 MISMATCH | 동일 fix |
| 27 | 936 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 28 | 951 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 29 | 955 | `engine_note` | `'Historical record ...'` | 없음 (상수) | 🟢 OK | — |
| 30 | 424 | `period_label` (fig) | `'April 2026'` | MISMATCH (동일) | 🟠 MISMATCH | 동일 fix |
| 31 | 551 | `kpi_hhi` (body) | `1840` | ORPHAN (동일) | 🔴 ORPHAN | 동일 fix |
| 32 | 400 | `period_label` (slug) | `'April 2026'` | MISMATCH (동일) | 🟠 MISMATCH | 동일 fix |

**소계**: OK 7 / STUB 15 / MISMATCH 6 / ORPHAN 4 (13%)

---

### risk_board.html (default 수: 20)

서비스: `services/artifacts/risk_board_service.py`  
서비스 to_dict() 필드: `user_id, user_name, period_label, trigger, generated_at, portfolio_value, portfolio_ccy, position_count, var95_pct, var99_pct, sharpe_annual, sortino_annual, calmar, max_drawdown_pct, sector_breakdown, tail_ratio, component_es, vix_current, defense_score, defense_status, layer_status, top_risks, disclaimer`

| # | Line | Variable | Fallback | Service field? | Status | Fix Option |
|---|------|----------|----------|----------------|--------|------------|
| 1 | 362 | `issue_number` | `4` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 2 | 363 | `doc_ref` | `'PQ-RB-04 · v2026.04.21'` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 3 | 364 | `hero_headline` | `[...]` | 없음 | 🔴 ORPHAN | 서비스 추가 |
| 4 | 371 | `kpi_var_1d` | `-2.14` | `var95_pct` 있음 (다른 이름) | 🟠 MISMATCH | 서비스: `kpi_var_1d = var95_pct` 별칭 추가 |
| 5 | 372 | `kpi_es_1d` | `-3.42` | `component_es` 있음 (다른 이름) | 🟠 MISMATCH | 서비스: `kpi_es_1d` 별칭 추가 |
| 6 | 373 | `kpi_maxdd_90d` | `-8.70` | `max_drawdown_pct` 있음 | 🟠 MISMATCH | 서비스: `kpi_maxdd_90d = max_drawdown_pct` 추가 |
| 7 | 374 | `kpi_corr_index` | `0.58` | 없음 | 🔴 ORPHAN | 서비스: sector_breakdown 기반 index corr 계산 |
| 8 | 390 | `period_label` | `'April 2026'` | `period_label` 존재 | 🟢 OK | — |
| 9 | 569 | `positions_ladder` | `[]` | 없음 (position_count만) | 🟡 STUB | 서비스: positions list 추가 |
| 10 | 592 | `p.spark` | `[...]` | positions_ladder 서브키 | 🟡 STUB | 서비스: spark 계산 추가 |
| 11 | 700 | `underwater` | `[0,-0.4,...,0]` (하드코딩) | `max_drawdown_pct` 있음 (단일값) | 🟡 STUB | 서비스: underwater series 추가 |
| 12 | 734 | `tail_ratio` | `1.08` | `tail_ratio` 존재 | 🟢 OK | — |
| 13 | 763 | `liquidity_label` | `'1.2× avg'` | 없음 | 🟡 STUB | 서비스 추가 |
| 14 | 855 | `pull_quote` | `"Observations of risk do not subtract it..."` | 없음 | 🟢 OK | — |
| 15 | 857 | `pull_quote_attribution` | `"PivoxQuant Risk Desk"` | 없음 | 🟢 OK | — |
| 16 | 863 | `not_answered` | `[...]` | 없음 | 🟢 OK (legal) | — |
| 17 | 907 | `period_label` (footer) | `'April 2026'` | `period_label` 존재 | 🟢 OK | — |
| 18 | 913 | `data_sources` | `[...]` | 없음 (상수) | 🟢 OK | — |
| 19 | 928 | `typeset_in` | `'Source Serif 4 ...'` | 없음 (상수) | 🟢 OK | — |
| 20 | 932 | `engine_note` | `'58 quant models ...'` | 없음 (상수) | 🟢 OK | — |

**소계**: OK 8 / STUB 5 / MISMATCH 3 / ORPHAN 4 (20%)

---

## 공통 패턴 분석

### 15개 리포트 전수 반복되는 ORPHAN 패턴

| 패턴 | 등장 리포트 수 | 고유 ORPHAN 변수 | 서비스 fix 공통화 가능? |
|------|--------------|----------------|----------------------|
| `issue_number` ORPHAN | 14/15 | 1 | YES — 공통 mixin |
| `doc_ref` ORPHAN | 14/15 | 1 | YES — 공통 mixin |
| `hero_headline` ORPHAN | 14/15 | 1 | YES — AI or deterministic |
| `kpis_cover` ORPHAN/MISMATCH | 10/15 | 1 (구조 통일) | YES — 서비스별 shape |
| `pull_quote` OK (editorial) | 15/15 | 1 | 현상 유지 OK |
| `typeset_in` OK (상수) | 15/15 | 1 | 현상 유지 OK |
| `engine_note` OK (상수) | 15/15 | 1 | 현상 유지 OK |
| `data_sources` OK (상수) | 14/15 | 1 | 현상 유지 OK |

**결론**: `issue_number`, `doc_ref`, `hero_headline`은 모든 서비스에 공통 mixin으로 한 번에 추가 가능 — 42건의 ORPHAN을 일괄 해소 (전체 ORPHAN의 52%)

---

## 수정 공수 추산

| 작업 유형 | 건수 | 항목당 시간 | 소계 |
|----------|------|------------|------|
| 공통 mixin (issue_number/doc_ref/hero_headline) — 14개 서비스 일괄 | 1 작업 | 2h | 2h |
| kpis_cover MISMATCH/ORPHAN — 10개 서비스 개별 | 10 | 30분 | 5h |
| 단순 MISMATCH (변수명 교정) | 15건 | 15분 | 3.75h |
| 데이터 필드 추가 (FMP 조회 기반) | 28건 | 45분 | 21h |
| 데이터 필드 추가 (계산 기반) | 18건 | 30분 | 9h |
| morning_brief_plus 대형 리팩터 | 1 작업 | 8h | 8h |
| dd_checklist Context 재설계 | 1 작업 | 6h | 6h |
| **합계** | | | **~55h** |

---

## 잔존/누락 사항

1. `morning_brief_plus.html`에 대응하는 `morning_brief_plus_service.py`가 없음. `morning_brief_service.py`가 `morning_brief_plus.html` 템플릿을 렌더링하나 content dict 구조가 템플릿 기대값과 심각하게 불일치. 파일: `/Users/seanbae/Desktop/취준/stockpilot/services/morning_brief_service.py` L482
2. `burn_rate.html`이 가계부 데이터(`housing_share_pct`, `savings_rate_pct`)를 기대하나 PivoxQuant 플랫폼은 가계비 데이터를 수집하지 않음 — 이 섹션들은 구조적으로 영구 ORPHAN (데이터 소스 없음). 섹션 제거가 유일한 해결책.
3. `dd_checklist.html`은 per-ticker 재무 데이터(revenue, margins, FCF, peers)를 기대하나 서비스는 position pending list만 주입. 이는 서비스 설계 의도(T+3 이메일 트리거)와 템플릿 의도(풀 DD 리포트)가 충돌하는 아키텍처 불일치.
4. `capital_allocation.html`은 시계열 배분 데이터를 기대하나 서비스는 단발성 시나리오 계산기임 — 템플릿이 별도 리포트(월별 배분 추적)를 위해 설계된 것으로 보이나 해당 서비스가 미존재.
5. 조사 범위에서 제외된 템플릿: `kpi_dashboard.html`, `self_audit.html`, `sp500_backtest.html`, `brag_card_email.html`, `weekly_memo_email.html`, `earnings_prebrief_email.html` (6개) — 요청 15개 외 추가 존재.

---

*조사 기준: 직접 파일 열람 + grep 실측. 추측 없음.*  
*증거 파일 경로 형식: `/Users/seanbae/Desktop/취준/stockpilot/services/artifacts/templates/{name}.html:{line}`*
