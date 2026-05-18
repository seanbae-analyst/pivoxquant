# PivoxQuant — Production Cleanup Spec (2026-05-18)

**대상**: CEO (배상현) 직접 실행용 단일 문서
**소요**: 5분 - 30분 (변호사·이메일 셋업 제외 시)
**추가 비용**: 0원 (§6 통신판매업 신고 45,000원 행정 수수료만 별도)
**근거**: HANDOVER v43-v45 외부 액션 #9, #10, #12 + 본 세션 신규 #17-#20

---

## §1. #10 prod DB rogue rows 정리 (5분, 0원)

### 문제
Wave 7 reproduce + verify 부산물로 sim 사용자 (id 21, 22) 잔재.
- 예상 email: `korean@example.com`, `newtest@example.com`
- 베타테스터·CEO 본인 데이터 아님을 반드시 사전 확인

### 사전 요건
- Railway CLI 설치됨 (`railway --version`)
- `railway link` 완료 (PivoxQuant 프로젝트에 연결)
- 가능하면 작업 직전 Railway DB snapshot/backup 트리거 (대시보드)

### 실행 명령

**Step 1. 현재 rogue rows 확인 (DRY RUN — 읽기만, 변경 0)**

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

railway run psql -c "SELECT id, email, created_at FROM users WHERE id IN (21, 22);"
railway run psql -c "SELECT COUNT(*) FROM positions WHERE user_id IN (21, 22);"
railway run psql -c "SELECT COUNT(*) FROM watchlist WHERE user_id IN (21, 22);"
railway run psql -c "SELECT COUNT(*) FROM alerts WHERE user_id IN (21, 22);"
```

**Step 2. 결과 확인 (반드시 보고 진행)**
- [ ] `users.email`이 `korean@example.com` 또는 `newtest@example.com` 인가?
- [ ] 본인 또는 실제 베타테스터 데이터가 아닌가?
- [ ] positions/watchlist/alerts 카운트가 sim 규모인가? (수십 건 이하 기대)

**Step 3. 삭제 (CASCADE 순서 — FK 의존성 역순)**

```bash
railway run psql -c "DELETE FROM positions WHERE user_id IN (21, 22);"
railway run psql -c "DELETE FROM watchlist WHERE user_id IN (21, 22);"
railway run psql -c "DELETE FROM alerts WHERE user_id IN (21, 22);"
railway run psql -c "DELETE FROM users WHERE id IN (21, 22) AND email IN ('korean@example.com','newtest@example.com');"
```

**Step 4. Verify**

```bash
railway run psql -c "SELECT id, email FROM users WHERE id IN (21, 22);"
# 기대 결과: 0 rows
```

### 롤백
- **DELETE는 롤백 불가**. PostgreSQL backup에서만 복구 가능.
- Railway 대시보드 → Database → Backups → 작업 직전 시점 restore.

### Safety Gates
- Step 3 직전 `users.email` AND 조건이 일치하지 않으면 DELETE 0 rows (실패-안전 default).
- `id IN (21, 22)`만으로 삭제하지 말 것 — 미래에 동일 id가 실 사용자로 재할당될 가능성 차단.

---

## §2. #9 iCloud OFF (1분, 0원)

### 문제
v44.7 iCloud 동기화에 `.git` 폴더 포함 → 메타데이터 corruption (응급 복구 사고 발생).

### 실행 (macOS)

**옵션 A — 간단 (권장, 1분)**
1. System Settings → Apple ID → iCloud → iCloud Drive → Options
2. **"Desktop & Documents Folders"** 체크 해제
3. 대화상자에서 "Keep a Copy" 선택 (로컬에 파일 보존)

**옵션 B — 더 안전 (30분, 권장 X)**
1. 프로젝트 폴더를 iCloud 영역 밖으로 이동:
   ```bash
   mv /Users/seanbae/Desktop/취준 ~/dev/pivoxquant-workspace
   ```
2. 모든 경로 재설정 필요:
   - Vercel CLI link 재설정
   - Railway CLI link 재설정
   - VSCode/Cursor workspace 재오픈
   - 본 문서 모든 경로 갱신

**현 시점 권고**: **옵션 A** (Desktop & Documents 체크 해제).

### Verify
```bash
ls -la@ /Users/seanbae/Desktop/취준/pivoxquant/.git | head -3
# com.apple.fileprovider.* xattr 없으면 OK
```

### 롤백
- iCloud Drive Options에서 다시 체크하면 즉시 재동기화 (단 .git 손상 위험 재발).

---

## §3. #12 GitHub Actions billing 차단 (5분, 0원)

### 문제
v28 SWOT 500 사고 root cause = Anthropic 크레딧 소진. GitHub Actions도 같은 패턴 (한도 초과 시 자동 결제) 위험.

### 실행
1. https://github.com/settings/billing/spending_limit
2. **"Spending limit"** → `$0` 설정 → Save
3. **"Get notified when 75% of limit reached"** 활성화

### 효과
- private repo 무료 한도 (2000 min/월) 초과 시 자동 결제 거부
- pivoxquant는 public repo → Actions unlimited (현재 영향 없음)
- 미래 private repo 추가 시 안전망

### Verify
- Settings → Billing → Spending limit이 `$0.00 / Unlimited` 가 아닌 `$0.00 / $0.00` 표시되면 OK.

### 롤백
- 동일 페이지에서 한도 재설정 가능.

---

## §4. #17 DNS 셋업 (30-60분, 0원)

### 링크
[`docs/ops/email-setup-2026-05-18.md`](./email-setup-2026-05-18.md) — CEO step-by-step

### 요약
- ImprovMX 5분 (인박운드 이메일 → 개인 Gmail forwarding)
- SendGrid 10분 (아웃바운드 transactional email)
- 가비아 DNS 10분 (MX / SPF / DKIM / DMARC 레코드)
- DNS 전파 검증 30분 - 2시간

### 추가 비용
- 0원 (ImprovMX free / SendGrid free 100/day)

---

## §5. #18 artifact-qa fixture (완료 ✅)

이미 본 세션 commit `bfd00f6c`에 포함. **별도 작업 X**.

### Verify (선택)
```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
git log --oneline bfd00f6c -1
```

---

## §6. #19 통신판매업 신고 (변호사 답변 후, 30분, 45,000원)

### 링크
[`docs/legal-consultation-guide-2026-05-18.md`](../legal-consultation-guide-2026-05-18.md) §7

### 요약
- 사전 조건: 변호사 자문 (Q1-Q15) 답변 수령 — 본인 사업 형태가 통신판매업 적용 대상인지 최종 확인 후 진행
- 신고처: 정부24 또는 관할 시군구청
- 수수료: 45,000원 (지자체별 상이 가능)
- 소요: 30분 (온라인 신고 시)

### 실행 순서
1. 변호사 답변 수령 (§7 선행)
2. 사업자등록증 + 도메인 등록증 + 결제대행사 계약서 준비
3. 정부24 → 통신판매업 신고 → 온라인 제출
4. 신고번호 발급 시 푸터·이용약관에 표기

### 롤백
- 신고 자체는 폐업 신고로 취소 가능 (수수료 환불 X).

---

## §7. #20 변호사 자문 Q1-Q15 (1-2주, 100-700만원)

### 링크
[`docs/legal-consultation-guide-2026-05-18.md`](../legal-consultation-guide-2026-05-18.md) — 전체 가이드

### 요약
- 금융규제·자본시장법 전문 변호사 3 firm 동시 컨택 (1시간 분배)
- Q1-Q15: §101 면제 트랙 / 유사투자자문업 / 정통망법 §50 / PIPA / 금소법 / 전자상거래법
- 예상 비용: 100-700만원 (firm별 견적 차이 큼)
- 유료결제 활성화 BLOCKER — 답변 수령 전 launch 불가

### CEO 액션
1. `docs/legal-consultation-guide-2026-05-18.md` §3 (3 firm 리스트 + 컨택 템플릿)
2. 동시 견적 요청 메일 발송
3. 답변 수령 후 §6 통신판매업 + 출시 final check 진행

---

## §8. 출시 직전 final check (compliance-gatekeeper agent 자동)

다음 체크리스트는 출시 D-Day 직전 `compliance-gatekeeper` agent가 자동 실행:

| ID | 항목 | Status |
|----|------|--------|
| B-1 | Q1-Q15 변호사 답변 수령 | ⬜ |
| B-2 | 통신판매업 신고 완료 (신고번호 푸터 표기) | ⬜ |
| B-3 | 정통망법 §50 email opt-out 구현 | ⬜ |
| B-4 | AI 생성물 표시제 구현 (artifact 메타데이터) | ⬜ |
| B-5 | PIPA §28-8 마케팅 동의 분리 구현 | ⬜ |
| B-6 | 전자상거래법 §17 청약철회 구현 | ⬜ |
| B-7 | 금소법 §19 설명의무 구현 (가격·환불 사전 고지) | ⬜ |

**Gate**: 7개 모두 ✅ 아니면 launch BLOCKED.

---

## §9. 실행 순서 권고 (CEO 30분 안에 가능)

| 순서 | 작업 | 소요 | 비용 | 차단 여부 |
|------|------|------|------|-----------|
| 1 | §2 iCloud OFF | 1분 | 0원 | 즉시 |
| 2 | §3 GitHub billing 차단 | 5분 | 0원 | 즉시 |
| 3 | §1 prod DB rogue rows 정리 (DRY RUN 먼저) | 5분 | 0원 | 즉시 |
| 4 | §4 이메일 셋업 (별도 가이드) | 30-60분 | 0원 | 즉시 |
| 5 | §7 변호사 3 firm 동시 컨택 | 1시간 | 100-700만원 | 답변 1-2주 대기 |
| 6 | §6 통신판매업 신고 (변호사 답변 후) | 30분 | 45,000원 | 5번 완료 후 |
| 7 | §8 출시 final check | agent 자동 | 0원 | 1-6 완료 후 |

**Total CEO 직접 시간**: ~30분 (1-3번) + ~1시간 (4-5번) = **1.5시간** 이내 즉시 가능.

---

## 제약 / 안전 가이드

- **롤백 불가 작업**: §1 DELETE (PostgreSQL backup만 복구), §6 통신판매업 신고 (폐업 신고로 취소 가능)
- **사전 백업 권장**: §1 실행 전 Railway 대시보드에서 manual snapshot 트리거
- **typo 0**: 모든 psql 명령은 `id IN (21, 22)` 정확 매칭 — 단일 id 추측 금지
- **추가 비용 0원**: §6 (45,000원 행정 수수료) + §7 (변호사 견적, 별도 결제) 외 신규 결제·구독·API 발생 X
- **본 문서 외 자료 변경 금지**: 모든 cross-reference는 기존 파일 (`email-setup-2026-05-18.md`, `legal-consultation-guide-2026-05-18.md`) 링크

---

**문서 버전**: 1.0 (2026-05-18)
**작성**: PivoxQuant Engineering (CC autonomous session v44.9)
**관련 메모리**: `feedback_no_extra_cost`, `feedback_pre_launch_full_throttle`, HANDOVER v45 외부 액션 #9/#10/#12/#17-#20
