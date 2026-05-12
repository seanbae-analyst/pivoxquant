# GitHub Actions — Disabled (2026-05-12)

## 상태
**모든 workflow `.yml.disabled` 로 rename됨.** GitHub은 정확히 `.yml` 확장자만 인식하므로 자동 실행 안 됨. **사용량 0분 / 비용 0원.**

## 왜 비활성화?
1. 1인 운영 (외부 PR 없음) → CI 의미 적음
2. 매 wave 직접 검증 (Claude + 로컬 pytest/vitest/grep)
3. v34부터 54 PR 모두 `--admin` 우회 머지 — CI 결과 사실상 미사용
4. Free tier 2,000분/월 한도 초과 + 카드 미등록 → 모든 CI 차단 상태
5. 검증 redundancy 제거 = 비용 0원 + 토큰 효율

## 검증 대안 (로컬, 자동 작동)

### Secret leak 차단
- `.githooks/pre-commit` (W7.3 word-bounded regex, self-exclude 3 paths)
- `tests/test_pivoxaudit_secret_leak.py` (12 threat-model tests)

### Wave 검증 명령
```bash
# Backend
/usr/local/bin/python3.12 -m pytest tests/ -q

# Frontend
cd frontend && npx vitest run && npx tsc --noEmit

# Secret leak
/usr/local/bin/python3.12 -m pytest tests/test_pivoxaudit_secret_leak.py
```

## Dependabot 비활성화
`.github/dependabot.yml.disabled` — 자동 PR 생성 멈춤.
보안 알림은 GitHub web UI에서 그대로 받음 (Actions와 무관).

## 재활성화 방법
```bash
for f in .github/workflows/*.yml.disabled; do
  mv "$f" "${f%.disabled}"
done
mv .github/dependabot.yml.disabled .github/dependabot.yml
git add .github/ && git commit -m "chore: re-enable GitHub Actions"
```

조건: spending limit > $0 + 결제 수단 등록.
