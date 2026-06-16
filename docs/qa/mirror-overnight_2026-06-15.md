# 거울(Mirror) 야간 세션 — 2026-06-15

자율 야간 작업 결과. 브랜치 `feat/mirror-home`, **내 커밋 9개 (origin/main 미푸시 기존 이력 위에 쌓임)**. `main`/prod 무영향, 전부 가역.

## 빌드 / 변경
1. `98361457` 거울 홈 + `GET /api/mirror-home` (read-only, 기존 persona+twin 서비스 조합)
2. `99e139f0` 장식 italic 전면 제거 (CEO 지시) — 107 class + 14 inline + 19 css 규칙
3. `c22761a8` Mirror 네비 문 + `NEXT_PUBLIC_MIRROR_HOME` 플래그 (기본 OFF)
4. `cae1675b` 네비 3-door 재편 (Mirror / Portfolio / Pre-Trade), 나머지 More, KILL 숨김
5. `f14ca149` 거울이 Reports+Journal 품기 (fold)
6. `2e6c83ed` fix: 트윈 주간수익률 통화 정규화 + 거울 observed 게이트
7. `docs` 본 문서
8. `242affd2` fix(legal): persona 5라우트 `@legal_scrub_response` (방어 강화)
9. `fix(rolling)` sector-tilt HHI 통화 정규화 (Pattern-7 2번째 사례)

## 검증 (CEO "다 잘 확인" 요청 = 완료)
- **백엔드 풀 pytest: 3968 passed / 0 failed** (모든 fix 반영한 최종 재검증).
- **타겟**: 트윈 통화 1 + 거울 5 + rolling 통화 1 + persona/profile 361 + 트윈 26 — 전부 green.
- **프론트**: typecheck · eslint(변경파일) · 프로덕션 빌드 · vitest 573 — 전부 green.
- **독립 회귀 감사 에이전트**: 내 변경분에 P0/P1 0건.

## 잡은 버그 (fix + 검증 완료) — 4건
- **P1 트윈 통화(Pattern-7)** `_compute_twin_return`: KRW+USD 그대로 합산해 ₩-스케일 포지션이 %를 지배(US 수익 소실). ticker suffix로 통화 추론 후 KRW 정규화. 회귀 `tests/test_twin_weekly_currency.py`.
- **P1 rolling HHI 통화(Pattern-7, 2번째)** `rolling_metrics._sector_tilt_hhi`: 동일 패턴 — 섹터 집중도 HHI가 혼합 포트폴리오에서 틀림. KRW 정규화. HHI는 scale-invariant라 단일통화 불변. 회귀 `tests/test_rolling_metrics_currency.py`.
- **P2 거울 observed 게이트**: `data_sparse`(실효 10거래)를 AND해 Living Mirror(5거래)와 불일치 → `trade_count>=5`만 보게 수정.
- **P2 persona 라우트 scrub(법적 방어)**: `/persona`,`-detail`,`-explain`,`-history`,`-drift`에 `@legal_scrub_response` 추가. scrub 규칙은 `... CFO` 라벨만 surgical 매칭(bare code/숫자 불변) → 테스트 계약 보존, "Daytrader CFO"→"Growth CFO" 정화.

## 검증했으나 깨끗 / 무방비 아님
- **캐시 cross-user 누수(Pattern-6)**: 활성 누수 없음. persona/twin 캐시는 `(user_id, window)` 키. rec_shares는 죽은코드(엔진 미방출) P2.
- **artifacts FX**: 10개 아티팩트 서비스가 이미 `fx_service`/`amount_to_krw` 임포트 — 무방비 통화 합산 패턴 0건.

## ⚠️ 유예 (CEO 판단 필요 — blind 수정 안 함)
- **P1 twin_runner KR 포지션 사이징** — `_open_paper_buy`가 KR 종목 주식수를 `alloc_usd/price_krw`로, 현금을 `price_krw*shares`로 차감 → **KR 페이퍼 포지션이 소스에서 잘못 사이징.** 위 트윈 % fix는 보고값만 교정; 기저 KR 포지션은 여전히 틀림. **결정 필요: 트윈이 KR 거래하나? 안 하면 US 한정, 하면 통화 수정.** (시뮬 엔진이라 blind 수정 시 트윈 테스트 다수 영향 → 유예.) 그 전까지 KR-heavy 트윈 수치 신뢰 보류.
- **P2 persona `_drift` 공식** (`persona_analytics`): 스케일 다른 두 점수(리스크성향 vs 코사인 신뢰도)를 빼서 `/api/profile/persona`에 노출(프론트 >20=material drift 취급). **거울 홈은 무관**(`persona_history.compute_drift` 사용). 공식 변경은 제품 확인 필요(기존 테스트가 출력 고정 가능성).
- **코스메틱 stale 주석**: bottom-nav/terminal-sidebar docstring 옛 IA, ~8파일 "Playfair italic" 잔존. 기능 영향 0.

## 열린 제품 결정
- **`NEXT_PUBLIC_MIRROR_HOME=true`** (Vercel) → 거울이 첫 화면.
- **`feat/mirror-home` 머지 + 푸시** → 배포 (네 콜). 네비 3-door는 로그인해서 눈으로 확인 권장(자동 스샷 불가 영역).
- **페이지 레벨 fold** (Portfolio가 Risk/Watchlist 탭 흡수) — 더 깊고 시각 검토 필요, 유예.
- **twin_runner US/KR 결정** → 답 주면 바로 잡음.
