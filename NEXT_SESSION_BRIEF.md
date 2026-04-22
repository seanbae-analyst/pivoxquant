# Next Session — Kick-off Brief (2026-04-21)

**이 문서 1분 독독 → HANDOVER.md 로 상세 확인**

---

## 1. 지금 어디?

랜딩 AIDA funnel 재구성(영어 전환) + weekly_memo Goldman IC v2 6p + Brand System v2 완료.
Railway/Vercel 배포 Active, OAuth 정상화, 법적 grep 0건.
S&P 500 Backtest PDF는 이번 세션 Agent timeout으로 전혀 생성 안 됨 — 다음 세션 첫 작업.

---

## 2. 가장 먼저 할 일 (1-2시간)

**S&P 500 Backtest PDF 생성**

- 신규 파일: `services/artifacts/templates/sp500_backtest.html`
- weekly_memo.html Goldman v2 구조 그대로 복제 후 콘텐츠 교체
- 6페이지 구조: COVER → EQUITY CURVE SPREAD → ANNUAL LADDER → RISK DASHBOARD → EDITORIAL → COLOPHON
- KPI 수치: CAGR 15.2% / Sharpe 0.94 / Alpha +9.66% / 2022 Bear +2.1% (Jinja `{% set %}` literal)
- 렌더 후 `frontend/public/samples/sp500_backtest.pdf` 복사
- 랜딩 "View Full Backtest" 링크를 `/samples/sp500_backtest.pdf`로 업데이트
- 담당 agent: pdf-report-designer (단독, timeout 방지)
- 완료 조건: PDF 6페이지 렌더 성공 + 랜딩 링크 HTTP 200

---

## 3. 반드시 쓸 도구 (3가지)

### UI/UX Pro Max Skill
`.claude/skills/ui-ux-pro-max/` — 색상 결정은 `data/colors.csv`, 레이아웃은 `landing.csv`, 차트 타입은 `charts.csv`, 폰트는 `google-fonts.csv`. 매 디자인 결정 전 CSV 조회 필수.

### 21st.dev Components
`https://21st.dev/community/components` — Dashboard P0 작업 시 Data Table / Command Menu / Modal 컴포넌트 여기서 가져와 Vantablack 리스킨. Chrome MCP 불안정 시 `https://21st.dev/r/{creator}/{slug}` curl로 대체.

### weekly_memo.html (Goldman v2 기준)
`services/artifacts/templates/weekly_memo.html` — 모든 신규 PDF 구조 레퍼런스. 복제 후 콘텐츠만 교체.

---

## 4. Agent 전략

- pdf-report-designer: PDF 전담
- frontend-dev: Dashboard P0 전담
- audit: 완료물 검수
- 동시 2개 이하 (3개+ = 컴퓨터 꺼짐 확인됨)
- 스코프 작게 쪼개서 dispatch (timeout 방지)

---

## 5. 절대 건드리지 말 것

- `engine.py` / `quant_models.py` / `autotrader.py` / `risk_defense.py`
- `_disclaimer.html` 내용 (자본시장법 §6 방어)
- Jinja2 `{% %}` / `{{ }}` 구조

---

## 6. 법적 Iron Rules

BUY / SELL / HOLD / recommend / advice / signal / 매수 / 매도 / 추천 / 조언 추가 금지.
방어 부정("not advice") OK. `_disclaimer.html` include 필수. `legal_filter.py` 74패턴 통과 확인.

---

## 7. 리소스 주의

- 동시 agent 2개 이하
- Chrome MCP 불안정 — WebFetch/curl로 대체
- Turbopack 한글 경로 bug — `next.config.ts turbopack.root: __dirname` 필수 유지

---

## 8. 우선순위 작업 6가지

1. **S&P 500 Backtest PDF** — weekly_memo 구조 복제, 6p, `/samples/sp500_backtest.pdf` 배포. 예상 1-2h. 완료 조건: 렌더 성공 + 랜딩 링크 연결.

2. **risk_board.pdf Goldman v2** — heatmap 중심 레이아웃. `charts.csv` 참조. 예상 1h.

3. **year_end_letter.pdf Goldman v2** — letter 포맷 특화. 예상 1h.

4. **Dashboard P0** — Portfolio 404 신규 구현 / Search 검색바 / Watchlist 추가. 21st.dev 컴포넌트 활용. 예상 2-3h.

5. **quarterly_self_report / earnings_prebrief / monthly_finance Goldman v2** — 각 30-45min.

6. **나머지 10 PDF Goldman v2 확장** — 일괄 처리, 스코프별 agent dispatch.

---

## 9. 완료 조건 체크리스트 (다음 세션 종료 전)

- [ ] S&P Backtest PDF 생성 + 랜딩 링크 연결
- [ ] 최소 2개 추가 PDF Goldman v2 확장
- [ ] Dashboard P0 최소 1개 (Portfolio / Search / Watchlist 중)
- [ ] HANDOVER.md v4 업데이트
- [ ] 이 브리프 v2 업데이트

---

*작성: 2026-04-21 세션 종료 / 상세: HANDOVER.md v3 참조*
