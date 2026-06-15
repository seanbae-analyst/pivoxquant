# 거울(Mirror) 야간 세션 — 2026-06-15

자율 야간 작업 결과. 브랜치 `feat/mirror-home`, **커밋 6개, 푸시 안 함**. `main`/prod 무영향.

## 빌드된 것
1. `98361457` 거울 홈 + `GET /api/mirror-home` (read-only, 기존 persona+twin 서비스 조합)
2. `99e139f0` 장식 italic 전면 제거 (CEO 지시) — 107 class + 14 inline + 19 css 규칙
3. `c22761a8` Mirror 네비 문 + `NEXT_PUBLIC_MIRROR_HOME` 플래그 (기본 OFF)
4. `cae1675b` 네비 3-door 재편 (Mirror / Portfolio / Pre-Trade), 나머지 More, KILL 숨김
5. `f14ca149` 거울이 Reports+Journal 품기 (fold)
6. `2e6c83ed` fix: 트윈 주간수익률 통화 정규화 + 거울 observed 게이트

## 검증 (CEO "다 잘 확인" 요청)
- **백엔드 풀 pytest: 3965 passed / 0 failed** (fix 전) — 내 커밋이 백엔드 무회귀 확정. fix 후 재검증 별도 기록.
- **타겟 32 passed** — 트윈 26 + 거울 5 + 통화 회귀 1.
- **프론트**: typecheck 깨끗 · eslint 깨끗(변경파일) · 프로덕션 빌드 OK · vitest 573 passed.
- **독립 회귀 감사 에이전트**: 내 변경분에 P0/P1 없음 (법적 불변식·None/index·nav·dynamic import·disclaimer 전부 안전).

## 잡은 버그 (fix + 검증 완료)
- **P1 — 트윈 통화(Pattern-7)**: `_compute_twin_return`이 KRW+USD를 그대로 합산해 ₩-스케일 포지션이 %를 지배(US 수익 소실). 유저 레그·lifetime 레그처럼 ticker suffix로 통화 추론 후 KRW 정규화. 단일통화 주는 불변(fx가 비율에서 상쇄). 회귀테스트 `tests/test_twin_weekly_currency.py`.
- **P2 — 거울 observed 게이트**: `/api/mirror-home`이 `data_sparse`(실효 10거래)를 AND해서, Living Mirror 아티팩트(5거래)와 불일치. `trade_count>=5`만 보게 수정 → 두 표면 일치.

## ⚠️ 유예한 것 (CEO 판단 필요 — 건드리지 않음)
- **P1 — twin_runner KR 포지션 사이징 (더 깊은 통화 버그).** `twin_runner._open_paper_buy`가 KR 종목 주식수를 `alloc_usd / price_krw`로, 현금을 `price_krw * shares`로 차감 → **KR 페이퍼 포지션이 소스에서 잘못 사이징됨.** 위 P1 fix는 *보고되는 %*만 교정; 기저 KR 포지션은 여전히 틀림. **결정 필요**: 트윈이 KR을 거래하나? 한다면 twin_runner 통화 수정, 안 하면 트윈 유니버스 US 한정. 그 전까지 KR-heavy 트윈 수치는 신뢰 보류 → 거울 트윈 카드에 caveat 검토. (twin_runner는 시뮬 엔진이라 blind 수정 시 트윈 테스트 다수 영향 — 그래서 유예.)
- **P2 — persona drift 공식 (`persona_analytics._drift`).** 스케일 다른 두 점수(리스크성향 프록시 vs 코사인 신뢰도)를 빼서 `drift` 정수를 만들어 `/api/profile/persona`에 노출(프론트가 >20을 "material drift"로 취급). **거울 홈은 영향 없음** — 거울은 `persona_history.compute_drift`(올바른 것)를 씀. 공식 변경은 제품 확인 필요(기존 테스트가 출력 고정 가능성).
- **P2 — persona 라우트 `@legal_scrub_response` 누락.** `/persona`,`/persona-detail`,`/persona-explain`,`/persona-history`,`/persona-drift`가 `@api_auth`만. **라이브 누수 아님**(프론트가 8-code→3버킷 collapse, 테스트로 고정된 의도된 계약). 단 raw HTTP JSON엔 "Daytrader CFO" 라벨 등이 실림. mirror_home엔 스크러버 있고 이들엔 없음 → 추가 권장(단 `test_profile_layer2` green 유지 먼저 확인).
- **코스메틱 — stale 주석.** bottom-nav/terminal-sidebar docstring이 옛 IA 기술; italic 제거 후에도 ~8파일에 "Playfair italic" 주석 잔존. 기능 영향 0.

## 열린 제품 결정
- **`NEXT_PUBLIC_MIRROR_HOME=true`** (Vercel) → 거울이 첫 화면.
- **`feat/mirror-home` 머지 + 푸시** → 배포 (네 콜).
- **페이지 레벨 fold** (Portfolio가 Risk/Watchlist 탭 흡수 등) — 더 깊고 시각 검토 필요, 유예.
