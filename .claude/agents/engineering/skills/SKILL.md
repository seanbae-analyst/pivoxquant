# Engineering Skills
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


## code-implement
- 기능 구현: 스펙 기반 코드 작성
- `Next.js 페이지/컴포넌트/API route 생성`

## code-refactor
- 리팩토링: 기존 코드 개선
- `중복 제거, 패턴 통일, 성능 최적화`

## code-review
- 코드 리뷰: PR/변경사항 품질 검사
- `버그, 보안, 성능, 가독성 체크`

## debug
- 디버깅: 에러 추적 및 수정
- `에러 로그 분석 → 원인 파악 → 핫픽스`

## migration
- 마이그레이션: 기술 스택 전환
- `DB 스키마 변경, 라이브러리 업그레이드, React 전환`

## api-design
- API 설계: RESTful 엔드포인트 설계
- `Supabase RPC, Next.js API routes, Edge Functions`
