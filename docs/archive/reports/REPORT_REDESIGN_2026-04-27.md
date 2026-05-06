# Report Redesign — Phase 1 Complete (2026-04-27)

## TL;DR
- 18개 PDF 디자인 핸드오프(`design_handoff_pdf_reports/`) → React 컴포넌트 + 라우트 100% 포팅
- TypeScript clean (`npx tsc --noEmit` 0 errors)
- 대시보드 `/reports` catalog가 18개 모두 새 React 라우트로 연결됨
- 디자인 시스템 v3 (Vantablack + Bronze) 무손상 — 새 PDF 디자인은 `.pq-report` 스코프로 격리

## 완성 사항

### 기반 라이브러리
| File | Purpose |
|---|---|
| `frontend/src/components/reports/pdf-primitives.tsx` | 35개 프리미티브 (PdfPage, PdfHeader, PdfKpiRow, PdfExecSum, PdfDonut, PdfWaterfall, PdfLimitRow, PdfRatingLadder, PdfIcCoverPage 등 base.css 1:1 매핑) |
| `frontend/src/lib/reports/disclaimer.ts` | 한/영 면책 (자본시장법 + PIPA + AI + Backtest), composeDisclaimer() |
| `frontend/src/app/globals.css` | `.pq-report` 스코프 + 디자인 토큰 |

### 18개 React 템플릿 (`frontend/src/components/reports/templates/`)
| # | Slug | Tier | Cadence | Pages | Status |
|---|------|------|---------|-------|--------|
| 01 | weekly-memo | Free | Weekly | 1 | ✅ |
| 02 | morning-brief-plus | Free | Daily | 1 | ✅ |
| 03 | brag-card | Free | Monthly | 1 | ✅ |
| 04 | earnings-prebrief | Pro | Per-event | 2 | ✅ |
| 05 | risk-board | Pro | Weekly | 2 | ✅ |
| 06 | quarterly-self-report | Pro | Quarterly | 2 | ✅ |
| 07 | self-audit | Pro | On-demand | 2 | ✅ |
| 08 | dd-checklist | Pro | On-demand | 2 | ✅ |
| 09 | dividend-income | Pro | Monthly | 1 | ✅ |
| 10 | insider-mirror | Pro | Weekly | 2 | ✅ |
| 11 | sp500-backtest | Pro | On-demand | 2 | ✅ |
| 12 | portfolio-segment | Pro | Monthly | 2 | ✅ |
| 13 | capital-allocation | Premium | Quarterly | 4 | ✅ |
| 14 | credit-rating | Premium | Quarterly | 3 | ✅ |
| 15 | burn-rate | Premium | Monthly | 2 | ✅ |
| 16 | monthly-finance | Premium | Monthly | 4 | ✅ |
| 17 | kpi-dashboard | Premium | Monthly | 3 (dark IC cover) | ✅ |
| 18 | year-end-letter | Premium | Annual | 5 | ✅ |

**총 페이지**: 38 페이지 / 18 라우트

### 18개 Preview 라우트 (`frontend/src/app/(dashboard)/reports/preview/{slug}/page.tsx`)
모두 같은 패턴 — `ReportSurface` + `PdfToolbar` + 해당 템플릿 import. `Cmd/Ctrl+P → Save as PDF` 직접 동작.

URL 컨벤션: kebab-case
- `/reports/preview/weekly-memo`
- `/reports/preview/morning-brief-plus`
- `/reports/preview/year-end-letter`
- ...

### 대시보드 catalog 연결
`frontend/src/app/(dashboard)/reports/page.tsx`:
- Catalog 18개 슬러그 (snake_case for /samples/*.pdf 파일명 호환) 그대로 유지
- `viewHref` 로직 변경: live artifact 없을 때 `/samples/{slug}.pdf` (옛 PDF) → `/reports/preview/{kebab-slug}` (새 React 라우트)
- `downloadHref`는 일단 `/samples/{slug}.pdf` 유지 (다음 단계: Chromium headless로 새 PDF 빌드)
- 티어 게이팅 + DisclaimerBanner 무손상

## 검증

### TypeScript
```bash
$ cd frontend && npx tsc --noEmit
(no output — 0 errors)
```

### 디자인 정독 (CEO 강조 사항 반영)
18개 HTML 모두 정독, 다음 디테일 반영:
- 17번 (KPI Dashboard) — **유일한 다크 IC-pack 커버** — `PdfIcCoverPage` 별도 컴포넌트로 처리
- 05번 (Risk Board) — 가장 데이터 dense — `PdfExecSum` + `PdfLimitRow` + `PdfWaterfall` 복합 사용
- 14번 (Credit Rating) — `RatingLadder` 대신 base.css 패턴의 outline-bordered watch 카드 사용 (HTML 원본도 ladder를 안 씀)
- 16번 (Monthly Finance) — `PdfDonut` (BS) + 차트 두 개 + Income/CashFlow 표 분리
- 18번 (Year-End Letter) — 5페이지 풀 letter, withBacktest 면책 추가 (decision EV 시뮬레이션 포함)
- 모든 Pro/Premium → `PdfGovBlock` 필수 적용
- 모든 페이지 → `PdfDisclaimer` (한/영) + `PdfPageFooter`

## 미완료 / 다음 단계

### 옛 PDF /public/samples/ 정리
- 18개 옛 PDF 존재 (Apr 22)
- 새 PDF로 교체하려면 Chromium headless 빌드 필요:
  ```bash
  CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  for html in design_handoff_pdf_reports/reports/[0-9]*.html; do
    slug=$(basename "$html" .html | sed 's/^[0-9]*_//')
    "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
      --print-to-pdf="frontend/public/samples/$slug.pdf" \
      "file://$(realpath "$html")"
  done
  ```
- 또는 Playwright/Puppeteer 자동화. CI에 추가 권장.

### 랜딩 (/features/reports) — 의도적 미수정
마케팅 쇼케이스 페이지. 5개 representative artifacts (Weekly/Earnings/Risk/Quarterly/Year-End) 폴리시드 카드. 18개 다 노출은 디자인 의도 깨짐. 추후 "View all 18 →" CTA 추가 가능.

### Hero ReportFlipDeck — 의도적 미수정
3개 flagship 커버 6초 로테이션. 디자인 의도 보존. 18개 다 보여주려면 별도 그리드 섹션 필요.

### 잔여 기능 fix (HANDOVER.md 참조)
디자인 핸드오프와 별개:
- Search/Watchlist/알림벨/Alpaca/코스피데이터 (HANDOVER.md 우선순위 P0)

## 변경 파일 목록

### Created (선행 + 이번 세션)
```
frontend/src/components/reports/pdf-primitives.tsx
frontend/src/components/reports/templates/01_weekly-memo.tsx ... 18_year-end-letter.tsx (18개)
frontend/src/lib/reports/disclaimer.ts
frontend/src/app/(dashboard)/reports/preview/{slug}/page.tsx (18개)
```

### Modified
```
frontend/src/app/(dashboard)/reports/page.tsx (viewHref → previewRoute)
frontend/src/app/globals.css (.pq-report 스코프 + 토큰 — 선행)
```

### Deleted
없음 — 옛 PDF는 Chromium 빌드 후 일괄 교체 예정

## 운동 다녀온 CEO 검토 사항

1. **시각 검토**: 다음 5개 라우트 직접 확인 권장 (가장 복잡한 것들)
   - `/reports/preview/risk-board` (5번, 데이터 dense)
   - `/reports/preview/monthly-finance` (16번, 4페이지 P&L+BS donut)
   - `/reports/preview/kpi-dashboard` (17번, 다크 IC 커버)
   - `/reports/preview/year-end-letter` (18번, 5페이지)
   - `/reports/preview/capital-allocation` (13번, 4페이지)
2. **데이터 연결**: 현재 모든 템플릿이 `DEFAULT` 샘플 데이터 사용. 실제 SWR hook 매핑은 다음 세션
3. **PDF 자동화**: 위 Chromium 스크립트 한번 돌리면 옛 PDF 18개 일괄 교체
4. **법적 검토**: 면책 한/영 양버전 (`disclaimer.ts`) 한번 읽어보시면 좋음
5. **CI 가드**: BUY/SELL/HOLD 단어 grep 통과 확인됨 (자본시장법 준수)

---

*Generated by Opus 4.7 — main session, foreground execution after multiple background agents stream-timed out. CEO instruction "디자인들도 다 다시 잘 봐봐" reflected in per-template detailed JSDoc + reading of all 18 source HTMLs before writing.*
