# Sample PDF Renderer

Playwright headless로 sample report PDF를 React 템플릿에서 자동 생성.

## 사용법

```bash
cd frontend
# dev 서버 실행 (다른 터미널):
pnpm dev

# 단일 slug:
pnpm render:sample --slug=morning-brief-plus

# 전체 18 slug:
pnpm render:samples
```

## 출력 위치
`frontend/public/samples/<slug>.pdf`

## 슬러그 목록
weekly-memo, brag-card, morning-brief-plus, earnings-prebrief, dd-checklist,
risk-board, sp500-backtest, portfolio-segment, dividend-income, insider-mirror,
quarterly-self-report, self-audit, monthly-finance, kpi-dashboard,
capital-allocation, credit-rating, year-end-letter, burn-rate
