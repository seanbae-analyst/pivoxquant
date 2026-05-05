# 변호사 미팅 사전 준비 — Claude Code 통합 작업 지시서

**사용법:** 이 파일 전체를 Claude Code 세션에 붙여넣어. 프로젝트 루트(`/Users/seanbae/Desktop/취준/pivoxquant`)에서 실행해야 함.

**CEO 사전 결정사항:**
- 모든 6개 작업 일괄 진행
- safe_scrub: 브랜치 머지 + 문서 정정 양쪽
- autotrader: 물리 삭제 (rollback은 git tag로만 보존)
- 기타 권장 작업: 4개 모두 진행

---

## 사전 정리 (0번)

### 0-1. 잔존 테스트 파일 삭제

이전 세션에서 sandbox 권한 테스트 중 생성된 파일이 있음:

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
rm -f test_bash_write.txt test_write.txt test_write2.txt
```

### 0-2. git 락 정리

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
rm -f .git/index.lock .claude/skills/ui-ux-pro-max/.git/index.lock 2>/dev/null
git worktree prune
git status
```

stale worktree 포인터가 있으면 `git worktree remove --force <path>` 또는 직접 `rm -rf .git/worktrees/agent-*` 로 정리.

### 0-3. 사전 검증

```bash
git branch --show-current  # main 이어야 함
git fetch origin
git status  # clean 이어야 함
git pull origin main
```

dirty 상태면 작업 시작 전에 stash 또는 commit.

---

## ① safe_scrub 브랜치 main 머지

### 작업 내용

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

# 1) 머지
git checkout main
git merge --no-ff fix/twin-rationale-safe-scrub-2026-05-04 \
  -m "Merge fix/twin-rationale-safe-scrub-2026-05-04 (PR #116)

Apply safe_scrub at twin BUY rationale write boundary
+ regression guard test. Per legal package Q9 — closes
HANDOVER F5 P0 (자본시장법 §17 advisory leak).

Commits:
- 907539f fix(twin): scrub paper-buy rationale at write time
- 1100f6d test(twin): regression guard for rationale safe_scrub
"

# 2) 검증
pytest tests/test_ai_twin.py tests/test_legal_filter.py -v

# 3) 머지 SHA 기록 (다음 단계에서 v2.3 문서에 박을 거임)
MERGE_SHA=$(git rev-parse HEAD)
echo "MERGE_SHA=$MERGE_SHA" >> /tmp/legal_prep_shas.txt

# 4) push
git push origin main
```

### 검증 포인트

```bash
grep -nE "from services.legal_filter import safe_scrub|safe_scrub.cand.rationale" services/twin/twin_runner.py
```

두 줄 모두 매칭돼야 함 (import + 적용).

---

## ② autotrader 잔존 파일 물리 삭제

### 작업 내용

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

# 1) rollback용 tag 미리 찍기
git tag -a legal-pre-autotrader-removal HEAD \
  -m "Pre-autotrader-removal snapshot.
Restore autotrader code via:
  git checkout legal-pre-autotrader-removal -- services/trading/autotrader.py routes/autotrade.py
  + restore container.py / app.py / routes/__init__.py / __init__ comments per pre-tag state."
git push origin legal-pre-autotrader-removal

# 2) 물리 삭제
git rm services/trading/autotrader.py
git rm routes/autotrade.py
```

### 잔존 참조 정리 (각 파일 직접 수정)

#### `services/container.py` — 주석들 + dead code 정리

기존:
```python
# REMOVED 2026-04-27 per CEO + legal: top-level `from services.trading.autotrader import AutoTrader`
# eliminated alongside the autotrade feature removal (투자일임업 등록 회피).
# `services/trading/autotrader.py` is preserved on disk for rollback; importing it here at module
# load would still execute its module side-effects (AutoTrader class build,
# circuit-breaker constants, etc.), which is undesirable when the feature is
# disabled. Re-enable by restoring the import + the `init_trader()` body below.
```

→ 위 6줄 주석 블록 통째로 삭제 (rollback 의도가 더 이상 없음).

또한 다음 부분도 단순화:
```python
# AutoTrader removed 2026-04-27. `trader` kept as `None` for backward
# compatibility with any caller that still references `services.container.trader`
# (those callers should treat None as "feature disabled" and short-circuit).
trader: Any = None


def init_trader(db, Position, TradeHistory, app):
    """No-op since 2026-04-27 (per CEO + legal — autotrade feature removed).
    ... (긴 주석)
    """
    return None
```

→ 호출자가 정말 없는지 먼저 확인:
```bash
grep -rn "container.trader\|svc.trader\|svc.init_trader\|init_trader(" --include="*.py" --exclude-dir=venv --exclude-dir=.claude .
```

호출자 0건이면 **`trader = None`과 `init_trader()` 함수 자체 삭제**.
호출자 있으면 그 호출자도 함께 정리.

#### `services/trading/__init__.py`

```bash
# 다음 줄을 삭제하거나 주석 정리
# autotrader는 명시 export 안 함 (disabled). 직접 from services.trading.autotrader import 가능.
```

→ 이 줄을 통째로 삭제. `from services.trading.autotrader import` 가능하다는 안내가 거짓이 됨.

#### `routes/__init__.py`

기존 line 14-22, 71의 다음 주석들 모두 삭제:
```python
# REMOVED 2026-04-27 per CEO + legal: autotrade blueprint disabled
# (자동매매 기능 제거 — 투자일임업 등록 회피).
# File routes/autotrade.py preserved for rollback. To restore:
#   1) Re-add: from .autotrade import autotrade_bp
#   2) Re-add autotrade_bp to the blueprints list below.
#   3) Re-enable autotrader.py worker boot in app.py.
# from .autotrade import autotrade_bp
```

또 line 71 근처:
```python
# REMOVED 2026-04-27 per CEO + legal: autotrade_bp,
```

→ 전부 통째로 삭제. blueprint 리스트가 깔끔해져야 함.

#### `app.py:199-205`

기존 line 199-205:
```python
# REMOVED 2026-04-27 per CEO + legal: AutoTrader boot disabled alongside
# the autotrade feature removal (투자일임업 등록 회피). The
# services/container.py module no longer imports `autotrader` at module
...
# To restore: re-enable both this line AND the AutoTrader import in
# services/container.py, then re-register routes/autotrade.py.
```

→ 통째로 삭제.

#### `services/artifacts/sample_data.py:1786`

기존:
```python
Preserved per CLAUDE.md `rollback 가능하도록 보존` (autotrader.py 동일 정책).
```

→ autotrader.py 비유 자체가 무효화되었으므로 이 주석 줄 삭제 또는 다른 비유로 대체.

#### `services/broker/user_alpaca_service.py:5`

기존:
```python
per-user KIS flow. We intentionally do NOT modify `autotrader.py` (frozen); its
```

→ "We intentionally do NOT modify `autotrader.py` (frozen)" 부분 삭제. 더 이상 frozen이 아니라 deleted임.

#### `scripts/self_healing/scan_railway_logs.py:67-68`

기존:
```python
"autotrader.py",
"services/trading/autotrader.py",
```

→ 두 줄 모두 삭제. protected path 리스트에서 제거.

#### `scripts/self_healing/propose_fix.py:12`

기존:
```python
1. Protected-path allowlist: error patterns in `autotrader.py`,
```

→ "autotrader.py" 언급 부분 삭제.

#### `routes/autotrade.py:21,64,66`

이 파일은 ②의 첫 단계에서 이미 `git rm` 함. 해당 라인들도 함께 삭제됨. 확인만 필요.

### CLAUDE.md 정리

기존:
```markdown
├── autotrader.py       # ⚠️ REMOVED 2026-04-27 per CEO + legal — 자동매매 기능 제거 (투자일임업 회피). 파일 유지(rollback용), routes/__init__.py에서 blueprint 등록 해제.
```

→ "파일 유지(rollback용)" 부분이 거짓이 됨. 다음으로 교체:
```markdown
# autotrader.py — 2026-04-27 비활성화 → 2026-05-XX 물리 삭제 (commit <DELETE_SHA>). rollback은 git tag legal-pre-autotrader-removal에서만.
```

또는 라인 자체를 삭제하고 백엔드 구조 트리에서 빼버리는 게 더 깔끔.

### 검증

```bash
# 1) 전 코드베이스에 autotrader 잔존 0건
grep -rn "AutoTrader\|autotrader\|autotrade" --exclude-dir=.git --exclude-dir=venv --exclude-dir=.claude --exclude-dir=node_modules . | grep -v "CHANGELOG\|^docs/\|legal-pre-autotrader-removal"
# 결과 0건이어야 함 (또는 git tag 메시지만 남음)

# 2) pytest 통과
pytest tests/ -x -v

# 3) 백엔드 부팅 테스트
python3 -c "from app import create_app; app = create_app(); print('OK')"

# 4) frontend 빌드 (dependency 오류 없는지)
cd frontend && npm run build 2>&1 | tail -20
```

### 커밋

```bash
git add -A
git commit -m "chore(legal): remove autotrader code physically — was disabled, now deleted

Per legal counsel prep. Previous state: autotrader.py existed on disk
as 'preserved for rollback' but variable AutoTrader class + 415-line
file would prompt lawyer questions about reachability. CEO (2026-05-XX)
decided to delete physically; rollback path retained via git tag
legal-pre-autotrader-removal.

Removed:
- services/trading/autotrader.py
- routes/autotrade.py
- services/container.py: trader=None + init_trader() no-op + 6-line comment block
- routes/__init__.py: REMOVED autotrade comments (line 14-22, 71)
- app.py: REMOVED AutoTrader boot comments (line 199-205)
- services/trading/__init__.py: autotrader export comment
- services/artifacts/sample_data.py: autotrader.py 비유
- services/broker/user_alpaca_service.py: 'frozen' reference
- scripts/self_healing/scan_railway_logs.py: protected paths (2 lines)
- scripts/self_healing/propose_fix.py: autotrader.py reference
- CLAUDE.md: autotrader.py 라인 갱신 또는 삭제

Verification:
- grep autotrader → 0 hits (excluding git tag)
- pytest tests/ — all pass
- backend boot — OK
- frontend build — OK

Rollback path:
  git checkout legal-pre-autotrader-removal -- services/trading/autotrader.py routes/autotrade.py
  + restore container.py / app.py / routes/__init__.py / __init__ comments per pre-tag state.
"

DELETE_SHA=$(git rev-parse HEAD)
echo "DELETE_SHA=$DELETE_SHA" >> /tmp/legal_prep_shas.txt
git push origin main
```

---

## ③ signup 5번째 체크박스 (PIPA §28-8 국외이전 동의)

### ⚠️ 사전 발견 — 데이터 계층은 이미 적용되어 있음

검증 결과, 다음은 **이미 main에 머지된 상태**:
- `migrations/versions/024_cross_border_consent.py` (2026-05-03 작성)
- `models/user.py:82-83` — `cross_border_consent_at`, `cross_border_consent_revoked_at` 컬럼

따라서 본 작업은 **API 엔드포인트 + lib 함수 + signup UI** 만 추가하면 됨.

### Backend — `routes/consents.py`에 cross_border 엔드포인트 추가

기존 `/api/consents/marketing` 패턴을 그대로 복제. 파일 끝에 추가:

```python
def _cross_border_state(user) -> dict:
    """Compute the effective cross-border consent payload (PIPA §28-8)."""
    consent_at = getattr(user, "cross_border_consent_at", None)
    revoked_at = getattr(user, "cross_border_consent_revoked_at", None)
    is_opted_in = consent_at is not None and (
        revoked_at is None or revoked_at < consent_at
    )
    return {
        "cross_border_consent_at": consent_at.isoformat() if consent_at else None,
        "cross_border_consent_revoked_at": (
            revoked_at.isoformat() if revoked_at else None
        ),
        "opted_in": is_opted_in,
    }


@consents_bp.route("/cross-border", methods=["GET"])
@api_auth
def get_cross_border_consent():
    """Return the authenticated user's cross-border consent record (PIPA §28-8)."""
    return jsonify({"ok": True, **_cross_border_state(current_user)})


@consents_bp.route("/cross-border", methods=["POST"])
@api_auth
def record_cross_border_consent():
    """Persist explicit cross-border data transfer opt-in (PIPA §28-8).

    PIPA §28-8 (개인정보보호법, 2024-09 시행): 개인정보 국외이전 시
    정보주체에게 별도로 알리고 명시적 동의를 받아야 함. processed-by
    위탁처(Anthropic / Stripe / Vercel / Railway / Google)가 모두 미국
    소재이므로 본 컬럼이 NULL 인 사용자에게는 향후 국외이전 코드 경로를
    가드한다 (별도 PR — 본 엔드포인트는 동의 기록 계층만 다룸).
    """
    now = _utcnow_naive()
    current_user.cross_border_consent_at = now
    current_user.cross_border_consent_revoked_at = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.record_cross_border_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not record consent"}), 500
    return jsonify({"ok": True, **_cross_border_state(current_user)})


@consents_bp.route("/cross-border", methods=["DELETE"])
@api_auth
def revoke_cross_border_consent():
    """Record a cross-border consent revocation. Future cross-border
    data flows for this user must short-circuit when the kill-switch
    runtime guard is added (separate PR)."""
    now = _utcnow_naive()
    current_user.cross_border_consent_revoked_at = now
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.revoke_cross_border_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not revoke consent"}), 500
    return jsonify({"ok": True, **_cross_border_state(current_user)})
```

### Backend — `lib/endpoints.ts` (frontend) 갱신

`API.consents` 객체에 `crossBorder` 추가:
```typescript
consents: {
  marketing: "/api/consents/marketing",
  crossBorder: "/api/consents/cross-border",  // ← 추가
},
```

### Frontend — `frontend/src/lib/consents.ts` 갱신

기존 marketing 함수들 패턴을 그대로 복제하여 cross_border 버전 추가:

```typescript
export interface CrossBorderConsentState {
  opted_in: boolean;
  cross_border_consent_at: string | null;
  cross_border_consent_revoked_at: string | null;
}

interface SignupConsentSnapshot {
  terms?: boolean;
  non_advisory?: boolean;
  age?: boolean;
  cross_border?: boolean;  // ← 추가
  marketing?: boolean;
  consented_at?: string;
}

/**
 * Persist the staged cross-border consent (PIPA §28-8) snapshot to the
 * backend after OAuth round-trip. Mirrors flushPendingMarketingConsent
 * behavior — best-effort, silent failures.
 */
export async function flushPendingCrossBorderConsent(): Promise<boolean> {
  const staged = readStagedSnapshot();
  if (!staged) return false;
  // NB: do NOT clearStagedSnapshot here — flushPendingMarketingConsent
  // already does that on the same key. We assume marketing-flush runs
  // first and we only POST if cross_border was checked.
  if (!staged.cross_border) return true;

  try {
    await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
      API.consents.crossBorder,
      { method: "POST" },
    );
  } catch (err) {
    if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.warn("[consents] cross-border flush failed (non-fatal):", err);
    }
  }
  return true;
}

export async function fetchCrossBorderConsent(): Promise<CrossBorderConsentState | null> {
  try {
    const res = await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
      API.consents.crossBorder,
    );
    return {
      opted_in: !!res.opted_in,
      cross_border_consent_at: res.cross_border_consent_at ?? null,
      cross_border_consent_revoked_at: res.cross_border_consent_revoked_at ?? null,
    };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
      return null;
    }
    return null;
  }
}
```

또한 OAuth callback handler에서 `flushPendingCrossBorderConsent()` 도 호출되도록 추가 (어디서 `flushPendingMarketingConsent`를 호출하는지 grep으로 찾고 같은 곳에 추가):

```bash
grep -rn "flushPendingMarketingConsent" frontend/src/ --include="*.ts" --include="*.tsx"
```

호출처에 한 줄 추가:
```typescript
await flushPendingMarketingConsent();
await flushPendingCrossBorderConsent();  // ← 추가
```

### Frontend — `frontend/src/app/(auth)/signup/_v2/page-v2.tsx`

#### Consents 타입 갱신

기존 (line 44-47 부근):
```typescript
type Consents = { terms: boolean; non_advisory: boolean; age: boolean; marketing: boolean }
```

→ 변경:
```typescript
type Consents = {
  terms: boolean;
  non_advisory: boolean;
  age: boolean;
  cross_border: boolean;  // ← 추가 (필수)
  marketing: boolean;     // (선택)
}
```

#### 초기값

```typescript
const [consents, setConsents] = useState<Consents>({
  terms: false,
  non_advisory: false,
  age: false,
  cross_border: false,  // ← 추가
  marketing: false,
});
```

#### 필수 검증 (line 122 부근)

```typescript
setAllRequired(
  consents.terms &&
  consents.non_advisory &&
  consents.age &&
  consents.cross_border  // ← 추가
);
```

#### UI — 체크박스 추가

`<span style={consentLabelStyle}>` 영역에 다른 체크박스 옆/밑에:

```tsx
<label style={{ ...consentRowStyle, ...pulseRowStyle(pulseUnchecked && !consents.cross_border) }}>
  <input
    type="checkbox"
    checked={consents.cross_border}
    onChange={(e) => setConsents({ ...consents, cross_border: e.target.checked })}
    aria-required="true"
  />
  <span style={consentLabelStyle}>
    [필수] 개인정보의 국외 이전 동의
    <a href="/privacy#cross-border" target="_blank" rel="noopener" style={{ marginLeft: 6, fontSize: '0.85em' }}>
      보기
    </a>
  </span>
</label>
```

#### POST payload (line 172 부근)

```typescript
body: JSON.stringify({
  ...consents,
  consented_at: new Date().toISOString(),
  cross_border_consented_at: consents.cross_border ? new Date().toISOString() : null,
}),
```

#### localStorage payload

`pivox_signup_consents` 저장 시에도 cross_border 포함되도록 (객체 spread만 쓰면 자동 포함).

### Frontend — 처리방침 §6-1 anchor 추가

`frontend/src/content/privacy-ko.md`의 제6조 ① 국외 이전 표 직전에 anchor:

```markdown
<a id="cross-border"></a>

### ① 국외 이전 (...)
```

### Frontend — RTL 테스트

`frontend/src/app/(auth)/signup/__tests__/page-v2.test.tsx` (있으면 추가, 없으면 생성):

```typescript
test("cross_border 미체크 시 회원가입 버튼 disabled", () => {
  render(<SignupPageV2 />);
  // 다른 4개는 체크
  fireEvent.click(screen.getByLabelText(/이용약관/));
  fireEvent.click(screen.getByLabelText(/투자자문 아님/));
  fireEvent.click(screen.getByLabelText(/만 14세 이상/));
  // cross_border만 미체크
  const submit = screen.getByRole("button", { name: /가입/ });
  expect(submit).toBeDisabled();
  // cross_border 체크
  fireEvent.click(screen.getByLabelText(/국외 이전/));
  expect(submit).not.toBeDisabled();
});
```

### 검증

```bash
# alembic upgrade test
cd /Users/seanbae/Desktop/취준/pivoxquant
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# pytest
pytest tests/test_consents.py -v  # 또는 관련 테스트
pytest tests/ -k "consent" -v

# frontend
cd frontend && npm run test -- signup
cd frontend && npm run build
```

### 커밋

```bash
git add -A
git commit -m "feat(consent): add cross-border data transfer consent (PIPA §28-8)

회원가입 시 국외 이전 동의를 별도 필수 체크박스로 분리. 기존
처리방침 §6-1 국외이전 표(Stripe/Anthropic/Vercel/Railway/Google)
는 그대로 유지하고, '이용 시 동의로 간주' 추정 동의를 명시 동의로
승격.

PIPA 제28-8조: 개인정보 국외 이전 시 정보주체에게 별도 알리고
동의를 받아야 함. 통상적으로 별도 체크박스로 구현.

변경:
- frontend Consents 타입 + UI 체크박스 (4 → 5 required)
- backend consents 테이블 cross_border + cross_border_consented_at 컬럼
- alembic migration 011_cross_border_consent
- privacy-ko.md anchor (#cross-border)
- RTL 테스트

변호사 사인 후 약관 §6-1 표현도 'PIPA §28-8 명시 동의' 명확화.
"

CONSENT_SHA=$(git rev-parse HEAD)
echo "CONSENT_SHA=$CONSENT_SHA" >> /tmp/legal_prep_shas.txt
git push origin main
```

---

## ④ legal package v2.3 갱신

### 대상

`docs/LEGAL_CONSULT_PACKAGE.md` (또는 실제 위치 — `find . -name 'LEGAL_CONSULT*' -not -path '*/venv/*' -not -path '*/.claude/*'`로 확인)

### 변경 내역 (전체 v2.3 갱신본은 별도 첨부 `LEGAL_CONSULT_PACKAGE_v23.md` 참조)

요약 변경 사항:

1. **§0-3 핵심 결정 표**: "자동매매 제거" 행 갱신
   - 이전: "2026-04-27 코드 비활성화 (routes/__init__.py line 16-22, 71)"
   - 이후: "2026-04-27 비활성화 → 2026-05-XX 물리 삭제 (commit `${DELETE_SHA}`). rollback은 git tag `legal-pre-autotrader-removal`."

2. **§1-2 자동매매 제거 결정**:
   - "Rollback 가능성: 코드 주석으로 복원 절차 보존 — 의도적, 변호사 사인 후 결정" 줄 삭제
   - 새 줄: "물리 삭제로 코드 잔존 없음. 복원 필요 시 tag `legal-pre-autotrader-removal` cherry-pick."

3. **§2 Q9 / §4-8 / §6 #10**:
   - 라인 번호: 226→**225**, 305→**304**, 401→**394** (실제 코드 기준)
   - "PR #116 (commits 907539f + 1100f6d)" → "merge commit `${MERGE_SHA}` (브랜치 `fix/twin-rationale-safe-scrub-2026-05-04` → main)"
   - "위험 등급 LOW" 유지 (이제 사실 — main에 머지됨)
   - 검증 명령:
     ```bash
     grep -nE "from services.legal_filter import safe_scrub|safe_scrub.cand.rationale" services/twin/twin_runner.py
     ```

4. **§4-6 autotrader 비활성**:
   - 섹션 자체 갱신 — "비활성화" → "물리 삭제 완료"
   - routes/__init__.py 코드 인용 부분 삭제 (해당 코드가 더 이상 없음)
   - 새 인용: `git log --diff-filter=D --name-only --pretty=format:"%h %s" -- services/trading/autotrader.py routes/autotrade.py`

5. **§4-8 F5 AI Twin safe_scrub**:
   - grep 결과를 머지 후 상태로 갱신 (아래 검증 명령 결과 그대로):
     ```
     41:from services.legal_filter import safe_scrub
     394:            rationale=safe_scrub(cand.rationale, context="twin.buy.rationale"),
     ```

6. **§4-7 (PIPA §28-8 5번째 체크박스)**:
   - "회원가입 화면에는 동의 체크박스 4개(terms / non_advisory / age / marketing)만 있고 국외 이전 동의 별도 체크박스가 없음" 줄 갱신
   - 새 줄: "회원가입 화면에 5번째 필수 체크박스 추가됨 — `cross_border` (PIPA §28-8 명시 동의), commit `${CONSENT_SHA}`."

7. **§5-2 누락 보완 (Q4 사인 후)** 작업 완료 표시:
   - "[ ]" → "[x]" 표시 또는 줄 자체 삭제

8. **§5-3 F5 AI Twin rationale 보완 (Q9 사인 후)**:
   - "BUY 경로(line 401)는 PR #116으로 이미 적용됨" → "BUY 경로(line 394)는 merge commit `${MERGE_SHA}`으로 main에 적용됨"

9. **§6 검증 로그 (10건)** — 본 갱신 시점 기준 grep 재실행:
   ```bash
   bash docs/LEGAL_VERIFY_RUN.sh > docs/LEGAL_VERIFY_RUN_v23.txt
   ```
   (재실행 스크립트는 별도 첨부 `LEGAL_VERIFY_RUN.sh` 참조)

10. **§6-1 메모리 vs 코드 불일치** 표 갱신 — 변경 없음 (정확함)

11. **§8 변경 이력**에 v2.3 row 추가:
    ```markdown
    | v2.3 | 2026-05-XX | safe_scrub main 머지 (commit ${MERGE_SHA}) — Q9 위험 LOW 사실화. autotrader 코드 물리 삭제 (commit ${DELETE_SHA}, tag legal-pre-autotrader-removal). signup 5번째 체크박스 cross_border 추가 (commit ${CONSENT_SHA}) — Q4 별도 동의 충족. 라인 번호 drift 정정 (226→225, 305→304, 401→394). |
    ```

### 적용 명령

`/tmp/legal_prep_shas.txt`의 SHA들을 자리표시자에 일괄 치환:

```bash
MERGE_SHA=$(grep MERGE_SHA= /tmp/legal_prep_shas.txt | cut -d= -f2)
DELETE_SHA=$(grep DELETE_SHA= /tmp/legal_prep_shas.txt | cut -d= -f2)
CONSENT_SHA=$(grep CONSENT_SHA= /tmp/legal_prep_shas.txt | cut -d= -f2)

# Find the doc
LEGAL_DOC=$(find . -name "LEGAL_CONSULT_PACKAGE*" -not -path "*/venv/*" -not -path "*/.claude/*" | head -1)
echo "Editing: $LEGAL_DOC"

# Backup
cp "$LEGAL_DOC" "$LEGAL_DOC.v22.bak"
```

이후 위 변경 사항 11개를 수동으로 적용 (또는 첨부된 `LEGAL_CONSULT_PACKAGE_v23.md` 통째로 교체).

### 커밋

```bash
git add -A
git commit -m "docs(legal): v2.3 — sync with reality

v2.2 had 3 factual errors flagged in pre-meeting verification:

1. Q9 safe_scrub claimed merged but actually only on
   fix/twin-rationale-safe-scrub-2026-05-04 branch. Fixed by
   merging the branch (commit ${MERGE_SHA}).

2. autotrader.py claimed deleted but services/trading/autotrader.py
   (415 lines, full AutoTrader class) still on disk. Fixed by
   physical removal (commit ${DELETE_SHA}, tag legal-pre-autotrader-removal).

3. signup 5th checkbox (cross_border, PIPA §28-8) flagged as
   missing in v2.2. Now added (commit ${CONSENT_SHA}).

Also corrected line number drift in §4-8 (226→225, 305→304, 401→394).

References:
- v2.2 verification log §6 #10 was based on then-current main HEAD
- branch fix/twin-rationale-safe-scrub-2026-05-04 was created
  2026-05-04 23:14 KST but never PR-merged before package authoring
- v2.3 re-runs the §6 verification with main HEAD = ${MERGE_SHA after consent merge}
"

git push origin main
```

---

## ⑤ 약관 §11 (회사 책임 제한) 약관규제법 §7 보정

### 대상

`frontend/src/content/terms-ko.md` 제11조 (현재 line 197-216)

### 작업

먼저 현재 §11 내용 확인:

```bash
sed -n '197,216p' frontend/src/content/terms-ko.md
```

기존 조항이 광범위하게 책임 면제하는 경우 다음 단서 조항을 추가:

```markdown
③ 본조 ①②항의 책임 제한에도 불구하고, 「약관의 규제에 관한 법률」 제7조에 따라, 회사의 고의 또는 중대한 과실로 발생한 손해에 대하여는 회사가 책임을 부담합니다.

④ 회사가 부담하는 손해배상 책임의 한도는, 손해 발생 시점을 기준으로 직전 6개월 동안 회원이 회사에 지급한 유료 서비스 이용료의 합계 금액으로 합니다. 다만 회사의 고의 또는 중대한 과실에 의한 경우에는 그러하지 아니합니다.
```

(위 문구는 변호사 사인 전 임시 안전장치임 — 변호사가 더 정교한 문구 줄 가능성 높음)

또한 status는 그대로 `DRAFT — 최종 시행 전 변호사 검토 필요` 유지.

### 검증

```bash
grep -n "약관규제법\|제7조\|중대한 과실" frontend/src/content/terms-ko.md
```

### 커밋

```bash
git add frontend/src/content/terms-ko.md
git commit -m "fix(legal): 약관 §11 책임 제한 — 약관규제법 §7 고의·중과실 단서 추가

기존 §11이 광범위한 책임 면제 조항이었으나, 약관규제법 §7
(불공정 약관) 위반 위험이 있어 단서 조항 추가:

- §11 ③: 고의 또는 중대한 과실에 의한 손해는 책임 부담
- §11 ④: 손해배상 한도 (직전 6개월 결제액) 명시

DRAFT 상태 유지 — 변호사 ACTIVE 사인 전 임시 보정.
변호사가 정교한 문구로 교체할 가능성 높음.
"

git push origin main
```

---

## ⑥ 변호사 사전 송부용 cover letter

### 대상

새 파일: `docs/LEGAL_COVER_LETTER.md`

### 내용

별도 첨부 파일 `LEGAL_COVER_LETTER.md` 그대로 복사 (이 prompt와 같은 폴더에 있음).

### 커밋

```bash
git add docs/LEGAL_COVER_LETTER.md
git commit -m "docs(legal): cover letter for lawyer pre-meeting send-off"
git push origin main
```

---

## 작업 후 최종 확인

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant

# 1) 모든 변경사항 main에 반영됐는지
git log --oneline -10

# 2) 테스트 전체 통과
pytest tests/ -x

# 3) frontend 빌드
cd frontend && npm run build && cd ..

# 4) autotrader 잔존 0건
grep -rn "AutoTrader\|autotrader\|autotrade" --exclude-dir=.git --exclude-dir=venv --exclude-dir=.claude --exclude-dir=node_modules . | grep -v "CHANGELOG\|^docs/\|legal-pre-autotrader-removal" | wc -l
# 결과 0 이어야 함 (또는 git tag 메시지만)

# 5) safe_scrub 실 적용 검증
grep -nE "from services.legal_filter import safe_scrub|safe_scrub\(cand.rationale" services/twin/twin_runner.py
# 두 줄 모두 매칭

# 6) cross_border 컬럼 존재
sqlite3 instance/stockpilot.db ".schema consents" 2>/dev/null | grep -i cross_border  # SQLite 기준
# 또는 alembic current로 011 까지 적용 확인

# 7) v2.3 doc DRAFT 상태 유지
grep -i "DRAFT" docs/LEGAL_CONSULT_PACKAGE*.md frontend/src/content/terms-ko.md frontend/src/content/privacy-ko.md

# 8) 변호사한테 보낼 파일 묶음
ls -la docs/LEGAL_CONSULT_PACKAGE*.md docs/LEGAL_COVER_LETTER.md
```

---

## 변호사 미팅 시 추가 질의 (Q13~Q15)

문서 §2에 빠진 3개 항목. 미팅 중 구두 추가 또는 cover letter Q13~Q15로 던질 것:

**Q13** — 만 14~19세 미성년자 보호자 동의 (개인정보보호법 §22-2). 약관 §4에 만 14세 미만만 차단. 청소년 구간(14~18) 처리 누락.

**Q14** — 디지털 콘텐츠 청약철회 제한 (전자상거래법 §17 ② 5호). SaaS 구독을 14일 환불 일부 제한 디지털콘텐츠로 분류 가능 여부. 약관 §8에 미반영.

**Q15** — 자본시장법 §57 (투자권유 광고 표시 의무). 자문업 미등록이어도 광고 표시 의무 트리거 가능성. 회색지대.

---

**완료 후 알려줄 정보:**
- MERGE_SHA, DELETE_SHA, CONSENT_SHA 3개 (v2.3 doc에 박힘)
- pytest 결과
- frontend build 결과
- 변호사한테 보낼 파일 경로 2개 (`docs/LEGAL_CONSULT_PACKAGE_v2.3.md`, `docs/LEGAL_COVER_LETTER.md`)
