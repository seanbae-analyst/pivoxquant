# PivoxQuant 문서 정리 감사 — 2026-04-24

**작성일**: 2026-04-24  
**작성**: 문서부 (Docs Agent, Stripe Documentation Standard)  
**목적**: reports/ + docs/ 전수 inventory → 중복/stale 판정 → 안전 정리 실행  
**범위**: 총 71개 파일 (reports/ 15개 + docs/ 56개)  

---

## 1. 전체 Inventory

### reports/ (15개 .md)

| 파일 | 카테고리 | 날짜 | 판정 |
|------|----------|------|------|
| audit/FIELD_MAPPING_AUDIT_2026-04-23.md | audit | 2026-04-23 | KEEP — 현행 ship 기준 |
| audit/EXISTING_ARTIFACTS_2026-04-23.md | audit | 2026-04-23 | KEEP |
| audit/MODEL_INVENTORY_2026-04-23.md | audit | 2026-04-23 | KEEP |
| audit/LEGAL_RISK_SWEEP_2026-04-23.md | audit | 2026-04-23 | KEEP |
| audit/CLEANUP_DOCS_2026-04-24.md | audit | 2026-04-24 | KEEP (이 파일) |
| design/PDF_REDESIGN_SPEC_2026-04-23.md | design | 2026-04-23 | KEEP |
| legal/DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md | legal | 2026-04-23 | KEEP |
| legal/DRAFT_TERMS_AI_CLAUSE_2026-04-23.md | legal | 2026-04-23 | KEEP |
| legal/LEGAL_CONSULT_DELTA_2026-04-23.md | legal | 2026-04-23 | KEEP |
| legal/SAFE_FEATURE_SPECS_2026-04-23.md | legal | 2026-04-23 | KEEP |
| product/PDF_CONTENT_AUDIT_2026-04-23.md | product | 2026-04-23 | KEEP |
| product/PERSONA_SPEC_2026-04-23.md | product | 2026-04-23 | KEEP |
| strategy/CFO_FEATURE_DEEP_DIVE_2026-04-23.md | strategy | 2026-04-23 | KEEP |
| strategy/COMPETITIVE_ANALYSIS_2026-04-23.md | strategy | 2026-04-23 | KEEP |
| strategy/RADICAL_NEVER_DONE_2026-04-23.md | strategy | 2026-04-23 | KEEP |
| **vercel-redirect-fix.md** | 운영 | 2026-04-23 | **ARCHIVED** → reports/archive/ |

> 비고: reports/lighthouse/ 하위 2개 JSON은 문서 파일 아님 (바이너리 리포트). 인덱스 제외.

### docs/ active (18개 .md)

| 파일 | 날짜 | 판정 |
|------|------|------|
| BACKTEST_RESULTS.md | 2026-04-20 | KEEP |
| DEAD_CODE.md | 2026-04-19 | KEEP |
| DESIGN_BRIEF_FOR_CLAUDE.md | 불명 | KEEP |
| JOURNAL_COMPANION_BETA.md | 2026-04-23 | KEEP |
| LANDING_PAGE_CONTENT.md | 2026-04-20 | KEEP |
| OPERATIONS_RUNBOOK.md | 2026-04-17 | KEEP + pw 갱신 |
| QA_TEST_SCENARIOS.md | 불명 | KEEP |
| QUANT_MODEL_EXPLAINED.md | 2026-04-17 | KEEP |
| RISK_PAGE_EXPLAINED.md | 불명 | KEEP |
| SYSTEM_ARCHITECTURE.md | 2026-04-17 | KEEP + pw 갱신 |
| TODO.md | 2026-04-19 | KEEP |
| USER_GUIDE.md | 2026-04-17 → 2026-04-24 갱신 | KEEP + pw 갱신 |
| design-system.md | 2026-04-10 | KEEP (PivoxQuant로 이미 rebranded) |
| INDEX.md | 2026-04-24 | KEEP (신규 생성) |
| legal/disclaimer.md | - | KEEP (법적 문서) |
| legal/privacy-policy.md | - | KEEP (법적 문서) |
| legal/terms-of-service.md | - | KEEP (법적 문서) |
| launch/ 8개 | 2026-04-17~20 | KEEP 전원 |

### docs/archive/ (38개 .md)

이미 archive/ 경로에 있는 파일은 역사적 기록으로 전원 유지.  
단, 아래 1건을 삭제 처리.

| 파일 | 판정 | 이유 |
|------|------|------|
| archive/rules/no-invalid-html-attribute.md | **DELETED** | 파일 크기 0바이트, 내용 없음 |

---

## 2. 실행 결과

### 2-A. HANDOVER 구버전

- `HANDOVER.md` 단독 존재, v1~v5 파일 없음 (과거 버전 파일명으로 커밋됨).
- 현행 버전 보존. 별도 조치 없음.

### 2-B. Audit/Strategy 중복

- 모든 audit/strategy/product/design/legal 리포트가 `2026-04-23` 단일 날짜.
- 구버전 중복 없음. 전원 유지.

### 2-C. Stale 후보 (StockPilot 잔재)

docs/ 내 StockPilot 언급 파일 7건 확인:
- `docs/launch/SECRETS_ROTATION_GUIDE.md` — 의도적: `***REDACTED***` 구버전 노출 사고 기록 문서. 맥락상 정확한 역사 기록이므로 **유지**.
- `docs/archive/SESSION_2026-04-16.md` — 이미 archive. **유지**.
- `docs/archive/BETA_READINESS_PLAN.md` — 이미 archive. **유지**.
- `docs/archive/env-setup.md` — 이미 archive. **유지**.
- `docs/archive/deploy-guide.md` — 이미 archive. **유지**.
- `docs/archive/rebranding-candidates.md` — 이미 archive. **유지**.
- `docs/launch/AUTO_SYNC_TECH_PLAN.md` — stockpilot 소문자 언급은 디렉토리명 참조. 내용은 PivoxQuant 브랜드. **유지**.

reports/ 내 StockPilot 언급: FIELD_MAPPING_AUDIT + vercel-redirect-fix 2건.
- vercel-redirect-fix → archive로 이동 완료.
- FIELD_MAPPING_AUDIT → 삭제 금지 파일, 내용 내 stockpilot은 디렉토리 경로 참조. **유지**.

### 2-D. 비어있거나 임시 파일

- `docs/archive/rules/no-invalid-html-attribute.md` — 0바이트. **삭제 완료**.

---

## 3. 삭제 목록 (1건)

| 파일 | 삭제 이유 | 증거 |
|------|-----------|------|
| `docs/archive/rules/no-invalid-html-attribute.md` | 0바이트 빈 파일, 내용 없음 | `wc -c` → `0` |

---

## 4. Archive 이동 목록 (1건)

| 원본 | 이동 후 | 이유 |
|------|---------|------|
| `reports/vercel-redirect-fix.md` | `reports/archive/vercel-redirect-fix.md` | docs/launch/DOMAIN_SETUP.md 가 동일 주제를 더 완전하게 커버. 운영 리포트가 아닌 CEO 작업 가이드 성격. 역사적 가치로 archive 보존. |

---

## 5. Stale 데이터 수정 (5건)

구버전 베타 비밀번호 `***REDACTED***` (2026-04-15 공개 노출로 폐기됨) → `***REDACTED***` (2026-04-19 rotate) 갱신.

| 파일 | 수정 위치 | 변경 내용 |
|------|-----------|-----------|
| `docs/USER_GUIDE.md` | 헤더 + 베타 접속 방법 + FAQ (3곳) | `***REDACTED***` → `***REDACTED***` |
| `docs/SYSTEM_ARCHITECTURE.md` | Section 7 Vercel 환경변수 표 | `***REDACTED***` → `***REDACTED***` |
| `docs/OPERATIONS_RUNBOOK.md` | Section 2-5 기능 플래그 표 + 2-6 프론트엔드 표 (2곳) | `***REDACTED***` → `***REDACTED***` |
| `docs/launch/LAWYER_CONSULTATION_PACKAGE.md` | Section 6 미팅 준비물 + URL 갱신 | `***REDACTED***` → `***REDACTED***`, URL을 `pivoxquant.vercel.app` → `pivoxquant.com`으로 갱신 |

> archive/ 내 파일의 `***REDACTED***` 언급은 역사적 기록이므로 수정하지 않음.  
> SECRETS_ROTATION_GUIDE.md 의 `***REDACTED***` 언급은 보안 사고 기록 문서이므로 수정하지 않음 (기록 보존이 목적).

---

## 6. 유지 결정 + 판단 근거

| 파일 그룹 | 유지 이유 |
|-----------|-----------|
| reports/audit/ 5건 | 2026-04-23 단일 세션 산출물. 중복 없음. FIELD_MAPPING은 ship 기준. |
| reports/legal/ 4건 | 법적 초안. 삭제 금지. |
| reports/design/ + product/ + strategy/ | 각 고유 내용. 중복 없음. |
| docs/active 18개 | 각 고유 책임 영역. 설명 문서, 런북, QA, 법적 문서. |
| docs/launch/ 8개 | 런칭 준비 문서. 계획/법무/인프라 내용. |
| docs/archive/ 38개 | 역사적 가치. 2026-04-09~17 기간 결정의 근거. |
| docs/archive/business-plan/ 11개 | 초기 사업 계획. 피칭/투자 자료로 재활용 가능. |

---

## 7. 신규 생성 파일

| 파일 | 목적 |
|------|------|
| `reports/INDEX.md` | reports/ 카테고리별 문서 목록 |
| `docs/INDEX.md` | docs/ 전체 문서 목록 (active + archive) |
| `reports/archive/` | archive 디렉토리 신규 생성 |
| `reports/audit/CLEANUP_DOCS_2026-04-24.md` | 이 파일 |

---

## Completion Checklist

- [x] Phase 1 전수 inventory (reports/ 15 + docs/ 56 = 71개): COMPLETE
- [x] Phase 2-A HANDOVER 구버전 점검: 단일 버전 확인, 조치 없음
- [x] Phase 2-B Audit/Strategy 중복 점검: 중복 없음 확인
- [x] Phase 2-C StockPilot 잔재 점검: archive 이미 완료, 능동 변경 불필요
- [x] Phase 2-D 비어있는/임시 파일: 0바이트 파일 1건 삭제
- [x] Phase 3 안전 정리 실행: 삭제 1건, archive 이동 1건, pw 갱신 5파일
- [x] Phase 4 INDEX.md 생성: reports/INDEX.md + docs/INDEX.md 신규 생성

## Status: COMPLETE
