# Security Skills
## ⚖️ Iron Rules (필수 — sub-skill 사용 시 절대 위반 금지)

1. **No assumption skipping** — "충돌 우려" "범위 밖일 듯" 같은 추측으로 스킵 금지. 의심되면 caller에게 escalate.
2. **Partial ≠ Complete** — 7개 중 4개만 끝났으면 "완료" 아님. INCOMPLETE 보고 + 남은 N개 명시.
3. **Reasoning ≠ Verification** — 도구 권한 거부됐으면 "수학적으로 검증" 금지. 즉시 "BLOCKED: <tool>" 명시 + 수동 검증 요청.
4. **Evidence required** — "OK" "정상" "통과" 보고 시 반드시 증거 첨부 (curl 응답 / file diff / build exit code / DOM snapshot).
5. **Brand: PivoxQuant** (NOT stockpilot) — 모든 출력 통일.
6. **Permission denied = ESCALATE** — 침묵 금지. "Bash 거부됨, 사용자 직접 실행 요청" 명시.

## 완료 보고 템플릿 (필수)

```
## ✅ Completion Checklist
- [ ] 항목 1: ✅완료/❌미완(이유)
- [ ] 항목 2: ...
- [ ] 모든 항목 verified (증거 첨부): ✅/❌

## Status: COMPLETE / INCOMPLETE / BLOCKED
```

---


## vuln-scan
- 취약점 스캔: OWASP Top 10 기반 코드 감사
- `XSS, CSRF, SQL Injection, 인증 우회`

## auth-review
- 인증 검토: 로그인/세션 보안 점검
- `Supabase Auth, JWT, RLS 정책`

## secret-audit
- 시크릿 감사: 민감 정보 노출 확인
- `env 파일, git history, 프론트엔드 번들`

## rls-check
- RLS 점검: Supabase Row Level Security 검증
- `모든 테이블 RLS 활성화, 정책 정확성`

## pentest-guide
- 모의 침투 가이드: 셀프 보안 테스트
- `인증, API, 데이터 접근 테스트 시나리오`
