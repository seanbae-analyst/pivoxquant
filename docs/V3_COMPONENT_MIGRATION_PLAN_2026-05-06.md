# V3 Mandatory Component Migration Plan

**Date:** 2026-05-06
**Source of truth:** `/Users/seanbae/Desktop/취준/.claude/agents/design.md` §7
**Trigger:** `component-usage-analytics` dry-run reported NumDisplay 0 / "Editorial" 0 → reconciliation needed.
**Brand:** PivoxQuant
**Memory rules:** feedback_feature_preservation, feedback_no_false_reports, feedback_thorough_fixes

---

## 1. Phase 1 진단 결과 (evidence-based)

### 1-A. v3 의무 컴포넌트 실존 확인

| Symbol | File | Lines | Status |
|---|---|---|---|
| `Eyebrow` | `frontend/src/components/landing/eyebrow.tsx` | 65 | ✅ real implementation |
| `Fleuron` | `frontend/src/components/ui/editorial.tsx:17` | — | ✅ real |
| `RuledKicker` | `frontend/src/components/ui/editorial.tsx:48` | — | ✅ real |
| `Caption` | `frontend/src/components/ui/editorial.tsx:113` | — | ✅ real |
| `NumDisplay` | `frontend/src/components/ui/editorial.tsx:136` | — | ✅ real |
| `StatRow` | `frontend/src/components/ui/editorial.tsx:228` | — | ✅ real |
| `FootSignature` | `frontend/src/components/ui/editorial.tsx:258` | — | ✅ real |
| `DisclaimerBanner` | `frontend/src/components/ui/disclaimer-banner.tsx:49` | 148 | ✅ real |
| `TierGate` | `frontend/src/components/ui/tier-gate.tsx:24` | 90 | ✅ real |
| `Editorial` | — | — | ❌ **DOES NOT EXIST** as a component |

**`Editorial`의 실체:** design.md §7 line 168 의 섹션 헤더("Landing/Editorial")가 component name 으로 잘못 인용된 것. `editorial.tsx` 파일 안에는 7개 sub-component 가 들어있을 뿐, `Editorial` 이라는 export 는 **없다**. `component-usage-analytics` SKILL.md §2-F line 21 + §2-B line 107 가 `Editorial` 을 v3 의무 목록에 포함시킨 것은 오류.

### 1-B. dry-run 측정값 vs 실제 사용 현황 (2026-05-06 grep)

| Component | dry-run import_count (skill regex) | 실측 single-line `from '...editorial'` | JSX 사용 (`<Component>`) | 실측 정확값 |
|---|---:|---:|---:|---:|
| Eyebrow | 3 | — | 7 (JSX) | ≥ 7 |
| Editorial | 0 | n/a | n/a | **존재하지 않음** |
| DisclaimerBanner | 7 | — | 28 (`grep -rln`) | 28 |
| NumDisplay | 0 | — | 1 (alerts) | 1 |
| StatRow | 1 | — | 8 | 8 |
| RuledKicker | 2 | — | — | ≥ 2 |
| Caption | 1 | — | — | ≥ 1 |
| Fleuron | 3 | — | — | ≥ 3 |
| FootSignature | 13 | — | 18 | 18 |
| TierGate | 3 | — | — | 3 |

**dry-run 0 의 진짜 원인 = 측정 버그 (multi-line imports)**

증거: `frontend/src/app/(dashboard)/alerts/page.tsx:25-32`

```
import {
  Caption,
  Fleuron,
  FootSignature,
  NumDisplay,
  RuledKicker,
} from "@/components/ui/editorial";
```

skill §2-A 의 regex 는 `import[^;]*\bX\b[^a-zA-Z0-9_]` — `grep -h` 가 line 단위로 매칭하므로 multi-line import 의 중간 라인 (`  NumDisplay,`)은 매칭되지 않음. 실제 NumDisplay import 가 존재해도 **0 으로 카운트됨**. 이는 `component-usage-analytics` skill 자체의 결함이며, design.md §7 의무 명세 잘못이 아님.

---

## 2. Phase 2 시나리오 결정

| Component | 시나리오 | 결정 |
|---|---|---|
| `Editorial` | A (존재하지 않음) | design.md §7 + skill §2-F 에서 `Editorial` 토큰 **제거** |
| `NumDisplay` | B (있는데 미마이그) | 의무 유지, 마이그 candidates 10개 페이지 (§3) |
| `StatRow` | B | 의무 유지, 일부 fundamentals panel 마이그 |
| Eyebrow | C (광범위 사용 ↑, 직접 패턴도 잔존) | 의무 유지, `_v1` 페이지 정리 단계와 묶음 |
| RuledKicker / Caption / Fleuron | C (얇게 사용) | "권장" 으로 강도 조정 — 본문 콘텐츠 영역에만 의무 |
| FootSignature | B (사용량 ↑) | 의무 유지 — page footer 패턴 |
| DisclaimerBanner | B (잘 사용 중) | 의무 유지 — legal 의무, 페이지 누락 없음 검증 필요 |
| TierGate | B | 의무 유지 — Free/Pro/Premium 잠금 |

---

## 3. NumDisplay 마이그레이션 — 🚨 CANCELLED (2026-05-06)

**상태: 본 plan 작성 시 grep 오인 → 마이그 후보 전부 false positive**

### 발견 (2026-05-06 frontend-dev BLOCK 보고)

원래 plan은 `fontSize: 22~40` 인라인을 NumDisplay 1차 후보로 박았으나, 실측 결과 **7 sites 전부 serif heading text** (Playfair Display). 숫자 0건.

| # | file:line | size | 실제 content | 실제 type |
|---|---|---|---|---|
| 1 | home/_v2:140 | 40 | "Six rooms." | serif h2 (Playfair) |
| 2 | risk/_v2:172 | 32 | "Notes." | serif h2 |
| 3 | settings/_v2:488 | 30 | "Who is signed in." | serif heading |
| 4 | settings/_v2:626 | 30 | "When the CFO should reach you." | serif heading |
| 5 | profile/_v2:494 | 30 | "How your persona drifted." | serif heading |
| 6 | profile/_v2:577 | 30 | "Tell the CFO how you read." | serif heading |
| 7 | watchlist:179 | 22 | "No symbols on watch." | serif empty-state |

### NumDisplay swap이 잘못인 이유

`editorial.tsx:136-171` NumDisplay 시그니처:
- `fontFamily: var(--font-mono)` — mono 폰트 강제
- `fontVariantNumeric: tabular-nums` + `fontFeatureSettings: "tnum"` — 숫자 전용
- `tone: "pos" | "neg" | "neu"` — 수익/손실 의미

위 7 sites swap 시:
1. **typeface 깨짐**: Playfair Display (serif) → mono. v3 락-인 (2026-04-27) 위반
2. **content 미스매치**: 숫자 0건 → tabular-nums 의미 없음
3. **tone prose 부적합**: 헤딩에 pos/neg 의미 없음
4. **참조 예시 misattributed**: plan이 "alerts/page.tsx:288 이미 NumDisplay 사용"이라 했으나 실제는 동일 serif 패턴, NumDisplay 아님

### 결정 (caller 옵션)

- **A. EditorialHead 신규 컴포넌트** — `<EditorialHead size>` (Playfair serif heading) 추가. 위 7 sites는 그쪽으로 마이그. 별도 task.
- **B. cancel 그대로** — 본 §3 폐기. NumDisplay는 실제 숫자 sites (`alerts/page.tsx:288` 등 alerts 1 site)에만 사용 중인 그대로 유지.
- **C. re-grep** — 활성 v2 페이지에서 진짜 numeric `<span style={{fontSize: 큰값}}>{포맷된숫자}</span>` 패턴 별도 탐색 후 그 sites만 마이그.

### Iron Rules 준수

- 본 §3은 grep 오해 기반의 false plan으로 판정.
- frontend-dev이 file edit 0건 (BLOCKED). regression 없음.
- feature_preservation 룰 강제 적용 — Playfair → mono 강제 swap 회피.

---

## 4. Eyebrow 마이그레이션 후보 (P1)

`className="*uppercase*tracking-*"` 직접 패턴 (line counts):

| 파일 | 매칭 라인 |
|---|---:|
| `app/(dashboard)/discover/page.tsx` | 6 |
| `app/(dashboard)/ai/page.tsx` | 10 |
| `app/(dashboard)/detail/[ticker]/page.tsx` | 9 |
| `app/(dashboard)/pre-trade/page.tsx` | 10 |
| `app/(dashboard)/growth/page.tsx` | 5 |
| `app/(dashboard)/risk/_v1/page-v1.tsx` | 5 |
| `app/(dashboard)/reports/_v1/page-v1.tsx` | 4 |
| `app/(dashboard)/alerts/page.tsx` | 2 |
| `app/(dashboard)/watchlist/page.tsx` | 1 |
| `app/(dashboard)/portfolio/_v1/page-v1.tsx` | 1 |
| `app/(dashboard)/signals/_v1/page-v1.tsx` | 1 |

**우선순위:** 활성 v2 / 루트 페이지 우선 (discover, ai, detail, pre-trade, growth, alerts, watchlist). `_v1` 페이지는 별도 정리.

**리스크:** `<Eyebrow>` 의 `withDashLeft|Right` prop 매핑 결정 필요. 대부분 단순 small-caps 라벨이면 prop 없이 swap 가능.

---

## 5. StatRow 마이그레이션 후보 (P2)

이미 8개 JSX 사용 site 있음. fundamentals panel 추가 후보:
- `app/(dashboard)/detail/[ticker]/page.tsx` — fundamentals (Market cap, P/E, EPS 등)
- `app/(dashboard)/portfolio/_v2/page-v2.tsx` — position metric rows
- `app/(dashboard)/risk/_v2/page-v2.tsx` — risk metric rows

**리스크:** StatRow 는 `pq-detail-stat-row` 클래스에 의존. globals.css 에 hairline separator 정의 확인 후 swap.

---

## 6. design.md §7 권장 업데이트

§7 (`164-183`) 다음 변경 권고:

### 6-A. `Editorial` 토큰 제거
section 헤더 "Landing/Editorial" 은 유지 (문법적 의미). 하지만 `<Editorial>` 같은 컴포넌트로 오해되는 표현 제거.

### 6-B. 의무 vs 권장 분류

**의무 (Mandatory — 미사용 시 PR fail):**
- `<DisclaimerBanner>` — 분석/시그널/페르소나/추천 페이지 (자본시장법 §101 면제 의무)
- `<TierGate>` — Free/Pro/Premium 잠금 표면
- `<Eyebrow>` — section 라벨 (`<span uppercase tracking-*>` 직접 패턴 금지)
- `<NumDisplay>` — Bloomberg-style 큰 숫자 (≥ 22px), portfolio/risk/home/detail KPI 카드
- `<FootSignature>` — 모든 dashboard page footer

**권장 (Recommended — 직접 markup 허용, 단 design polish 시 swap):**
- `<RuledKicker>` — section 헤더 위 ruled kicker (전 페이지 강제 X)
- `<Caption>` — 이미지/차트 캡션 (alt text 의무, 컴포넌트는 권장)
- `<Fleuron>` — 섹션 디바이더 (장식 — 권장)
- `<StatRow>` — 라벨/값 row (권장 — 일부 dense panel 에 적합)

### 6-C. 적용 컨텍스트 명시
각 의무 컴포넌트에 "어디서 의무인가" 명시 — vague "전부 필수" 표현을 구체화.

(실제 §7 rewrite 는 별도 PR 로. 본 plan 은 권고만.)

---

## 7. component-usage-analytics SKILL 수정 권고

### 7-A. multi-line import regex 버그 수정
현재 §2-A:
```bash
grep -rEh "import[^;]*\b${comp}\b[^a-zA-Z0-9_]" ...
```
→ multi-line import 의 중간 라인을 놓침. 권고:
```bash
# A) ripgrep multiline (-U) 사용 가능시
rg -U "import\s*\{[^}]*\b${comp}\b[^}]*\}\s*from" --type=tsx --type=ts | wc -l
# B) ripgrep 없으면 perl
perl -0777 -ne 'while(/import\s*\{[^}]*\b'"$comp"'\b[^}]*\}\s*from/g){$c++} END{print $c+0,"\n"}' file.tsx
```
또는 single-line `from '...editorial'` 카운트 + `<Component>` JSX 카운트 둘 다 수집해 max() 보고.

### 7-B. `Editorial` 토큰 제거
SKILL.md §2-F line 21 + §2-B line 107 에서 `Editorial` 삭제. 대체: 위 §6-B 의 5+4 분류로 교체.

### 7-C. ENFORCE 임계값 조정 (현실화)

| 단계 | 기간 | v3 의무 채택률 임계값 |
|---|---|---|
| 현재 측정 (2026-05-06) | baseline | NumDisplay 1 file, Eyebrow 7+ JSX, DisclaimerBanner 28 — 0~40% spread |
| 1주차 (2026-05-13까지) | 측정 버그 수정 + Editorial 제거 후 재측정 | warn-only |
| 2주차 (2026-05-20) | NumDisplay P0 마이그 5건 완료 후 | 10% |
| 1개월 (2026-06-06) | Eyebrow P1 + NumDisplay P1 완료 | 30% |
| 분기 (2026-08-06) | `_v1` 정리 + StatRow 확대 | 50% |
| 락-인 (Q4) | 신규 PR 강제 + 스냅샷 가드 | 80% |

기존 SKILL §2-F 판정 "페이지당 채택률 < 80% → 리팩토링 권고" 는 점진적 ramp-up 전까지 **warn 만**, fail X.

DisclaimerBanner 누락 = 즉시 fail (legal) 은 유지.

### 7-D. 측정값과 사실 reconcile
SKILL §10 "design-token-drift skill 과 보완" 표 옆에 "측정 한계 (multi-line import 문제 + Editorial false token)" footnote 추가.

---

## 8. 실행 단계 (요약)

| 단계 | 액션 | 비용 | 책임 |
|---|---|---|---|
| 1 | design.md §7 rewrite (`Editorial` 제거 + 의무/권장 분류) | $0 — text edit | design agent |
| 2 | SKILL.md §2-A multi-line regex 수정 | $0 | docs / skill maintainer |
| 3 | SKILL.md §2-F 의무 목록에서 `Editorial` 제거 | $0 | 동상 |
| 4 | SKILL ENFORCE 임계값 ramp-up 적용 | $0 | 동상 |
| 5 | NumDisplay P0 마이그 (5 files) | dev time | frontend-dev agent |
| 6 | Eyebrow P1 마이그 (활성 v2 페이지) | dev time | frontend-dev agent |
| 7 | StatRow P2 확대 (3 files) | dev time | frontend-dev agent |
| 8 | `_v1` 정리 묶음 PR (별도 task — feature_preservation 매핑 표 선행) | dev time | frontend-dev + audit |

본 plan 자체는 코드 변경 0건 — design 의사결정 + 마이그 우선순위 + skill 수정 권고만.

---

## 9. Status

**진단 (Phase 1)**: COMPLETE — evidence: grep 카운트 (10 components × 2 measure: skill regex + JSX) + design.md §7 인용 (line 164-183) + skill regex 버그 reproduce.

**결정 (Phase 2)**: COMPLETE — 시나리오 매핑 9 components × {A/B/C}.

**산출물 (Phase 3)**: 본 문서 (마이그 plan) + 권고 (design.md §7 rewrite + SKILL.md 수정). 실제 design.md §7 / SKILL.md edit 은 본 plan 승인 후 별도 작업.
