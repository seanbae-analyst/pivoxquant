# 체결 화면 캡처 평가 세트

설계: `docs/product/SCREENSHOT_IMPORT_DESIGN.md` §7. 캡처는 브라우저에서 Tesseract.js 로 읽고
(`frontend/src/lib/fill-ocr/ocr.ts`), 규칙 파서(`parse.ts`)가 증명된 칸만 채운다.

## 있는 것
- `synthetic/*.png` — 합성 증권사 화면 12장(실제 계좌 정보 없음). `ground_truth.json` = 사람이 읽은 정답.
- `synthetic/ocr/*.png.json` — 프로덕션 OCR 경로의 단어 덤프(헤드리스 Chromium). 재생성:
  ```
  cd frontend && node scripts/copy-tesseract-assets.mjs
  node scripts/ocr-eval-dump.mjs ../tests/fixtures/screenshot_import/synthetic ../tests/fixtures/screenshot_import/synthetic/ocr
  ```
- `kr_names.json` — `services/kr_stock_registry` 에서 뽑은 {종목명: 코드}. 채점이 서버와 같은 기준(정확 일치만 자동)을 쓰려고 둔다.
- 채점: `cd frontend && OCR_EVAL_PRINT=1 npx vitest run src/lib/fill-ocr/__tests__/eval.test.ts --silent=false`
  (틀리게 확신 > 0 이면 실패).

## 없는 것 — 실기기 캡처 (TODO)
**실제 증권사 앱 캡처로는 한 번도 재지 않았다.** 규칙은 위 합성 12장을 보며 조정했으니 그 점수는 낙관적이다.

| 증권사 | 국내 체결 | 해외(USD) 체결 | 보유(거절돼야 함) | 미체결(거절돼야 함) |
|---|---|---|---|---|
| 한국투자 | | | | |
| 키움 | | | | |
| 토스증권 | | | | |
| 미래에셋 | | | | |
| 삼성 | | | | |
| NH | | | | |

실기기 캡처는 **커밋하지 않는다**(개인 거래 정보) — `real/` 아래 두면 `.gitignore` 가 막는다.
