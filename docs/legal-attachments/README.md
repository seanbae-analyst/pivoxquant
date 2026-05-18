# 변호사 컨택 첨부 자료 4종 (legal-attachments/)

**작성일**: 2026-05-18
**목적**: CEO가 변호사 이메일 보낼 때 즉시 첨부 가능한 자료 4종 + PDF 변환 가이드.

상위 가이드: `../legal-consultation-guide-2026-05-18.md` (15 firm, 488 lines)

---

## 파일 목록 (4 markdown + 1 README)

| # | 파일 | 용도 |
|---|---|---|
| 1 | `service-overview.md` | PivoxQuant 서비스 개요 — 변호사 이해 돕기 |
| 2 | `section-101-exemption-decision.md` | 자본시장법 §101 면제 트랙 유지 결정문 (CEO 2026-05-04 확정) |
| 3 | `regulatory-impact-2026-05.md` | 신규 규제 7건 (HIGH 3 / MEDIUM 3 / LOW 1) 영향도 |
| 4 | `legal-questions-q1-q15.md` | 변호사 자문 큐 Q1-Q15 정리본 |
| 5 | `README.md` | 본 문서 — 사용법 + PDF 변환 명령 |

---

## 이메일 첨부 시 (3-6번 자료 매핑)

상위 가이드 §4 이메일 템플릿 첨부 6종:

| # | 첨부물 | 위치 |
|---|---|---|
| 1 | 사업자등록증 PDF | `/Users/seanbae/Desktop/취준/사업자등록증-pivoxquant.pdf` (CEO 보유) |
| 2 | 서비스 화면 | https://pivoxquant.com (라이브 링크) |
| **3** | **§101 면제 트랙 결정문** | `legal-attachments/section-101-exemption-decision.pdf` |
| **4** | **신규 규제 7건 영향도** | `legal-attachments/regulatory-impact-2026-05.pdf` |
| **5** | **Q1-Q15 정리본** | `legal-attachments/legal-questions-q1-q15.pdf` |
| **6** | **서비스 개요** | `legal-attachments/service-overview.pdf` |

---

## PDF 변환 (2026-05-18 검증 완료 — 4종 PDF 이미 생성됨)

본 디렉터리에 markdown 4종 + PDF 4종 모두 동봉. **재변환 필요 시** 아래 옵션 사용.

### 옵션 A — WeasyPrint (검증된 명령, ✅ 2026-05-18 4/4 성공)

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant/docs/legal-attachments

DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 <<'PYEOF'
import markdown, weasyprint, glob, os
for md in sorted(glob.glob('*.md')):
    if md == 'README.md': continue
    body = markdown.markdown(open(md).read(), extensions=['tables', 'fenced_code'])
    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
        @page {{ size: A4; margin: 18mm; }}
        body {{ font-family: -apple-system, "Apple SD Gothic Neo", sans-serif; line-height: 1.55; color: #1a1a1a; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
        h1, h2, h3 {{ color: #1a1a1a; margin-top: 18px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 11pt; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
        th {{ background: #f5f5f5; font-weight: 600; }}
        code {{ background: #f4f4f4; padding: 1px 5px; border-radius: 3px; font-size: 10pt; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; font-size: 10pt; white-space: pre-wrap; }}
        hr {{ border: none; border-top: 1px solid #ddd; margin: 18px 0; }}
    </style></head><body>{body}</body></html>'''
    pdf_path = md.replace('.md', '.pdf')
    weasyprint.HTML(string=html).write_pdf(pdf_path)
    print(f'OK {pdf_path} ({os.path.getsize(pdf_path):,} bytes)')
PYEOF
```

**핵심**: `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` 필수 (weasyprint가 brew의 libgobject/pango/cairo 찾도록).

**선행 조건 (이미 충족)**:
- `weasyprint` (Framework Python 3.12 — `/Library/Frameworks/Python.framework/Versions/3.12/bin/weasyprint`)
- `markdown` (`pip3.12 install markdown` 완료)
- brew: `pango`, `cairo`, `gobject-introspection` (이미 설치됨)

**검증 결과 (2026-05-18 22:13)**:
```
OK legal-questions-q1-q15.pdf (118,756 bytes)
OK regulatory-impact-2026-05.pdf (330,971 bytes)
OK section-101-exemption-decision.pdf (381,847 bytes)
OK service-overview.pdf (107,162 bytes)
```

### 옵션 B — pandoc (현재 시스템 미설치, brew 필요)

```bash
brew install pandoc basictex  # 1회 설치
cd /Users/seanbae/Desktop/취준/pivoxquant/docs/legal-attachments
for f in *.md; do
  [ "$f" = "README.md" ] && continue
  pandoc "$f" -o "${f%.md}.pdf" --pdf-engine=xelatex -V mainfont="AppleSDGothicNeo-Regular"
done
```

### 옵션 C — VS Code Markdown PDF 확장 (수동, GUI)

1. VS Code에서 각 markdown 파일 열기
2. `Cmd+Shift+P` → "Markdown PDF: Export (pdf)"
3. 동일 디렉터리에 .pdf 생성됨

---

## 이메일 작성 흐름 (CEO)

1. **PDF 변환** (위 옵션 A 권고 — 추가 설치 불필요)
2. **변호사 이메일 작성** (상위 가이드 `../legal-consultation-guide-2026-05-18.md` §4 템플릿 사용)
3. **첨부 6종** (위 표 참조):
   - 사업자등록증 PDF (1)
   - 서비스 링크 (2) — 본문에 URL 명시
   - PDF 4종 (3-6) — 본 디렉터리에서 변환된 파일
4. **15개 firm 중 우선순위 3-5곳** 동시 발송 (상위 가이드 §1 우선순위 매트릭스)

---

## SoT 원본 (메모리 파일)

본 4종 문서는 다음 메모리 파일 100% 인용:

| 첨부 PDF | 원본 SoT |
|---|---|
| `service-overview.md` | `~/.claude/projects/.../memory/business_registration.md` + `product_concept_cfo.md` + 본 디렉터리 통합 |
| `section-101-exemption-decision.md` | `~/.claude/projects/.../memory/legal_decision_no_advisory.md` |
| `regulatory-impact-2026-05.md` | `~/.claude/projects/.../memory/regulatory_changes_2026-05.md` |
| `legal-questions-q1-q15.md` | `~/.claude/projects/.../memory/legal_question_queue.md` |

---

## 갱신 정책

- **신규 규제 발견 시**: `regulatory-impact-2026-05.md` 갱신 + 재변환
- **신규 변호사 자문 추가 시**: `legal-questions-q1-q15.md` 갱신 + 재변환
- **§101 면제 트랙 결정 변경 시**: `section-101-exemption-decision.md` 갱신 + CEO 사인 재기록
- **재스캔 예정**: 2026-08-15 (PIPA 9월 시행 직전 + 정통망법 시행령 확정)
