# Cache Pattern — CC Scheduled-Tasks 결과 file cache

**작성**: 2026-05-28 v55-X4 DevOps wave
**관련**: `CC_SCHEDULED_TASKS_EXPANSION.md`
**목적**: 16+ task 산출물을 file로 cache → 백엔드가 read 패턴으로 서빙

---

## 1. 디렉토리 구조

```
/Users/seanbae/dev/pivoxquant/cache/
├── .gitkeep                              # 디렉토리 보존
├── README.md                             # 구조 문서 (본 파일 요약)
│
├── artifacts/                            # T01 산출물 (유저별)
│   ├── 2026-05-29/
│   │   ├── weekly_memo/
│   │   │   ├── user_123.html
│   │   │   ├── user_123.png             # 썸네일 (선택)
│   │   │   └── user_456.html
│   │   ├── brag_card/
│   │   │   └── user_123.png
│   │   ├── earnings_pre_brief/
│   │   │   └── user_123.html
│   │   └── ...
│   ├── 2026-05-28/                       # 이전 일자 (24h 후 prune)
│   └── ...
│
├── ops/                                  # T02-T16 operations 결과
│   ├── competitor_scan/<date>.json
│   ├── user_feedback/<date>.json
│   ├── kpi_dashboard/<date>.{md,json}
│   ├── legal_packet/<date>.json
│   ├── marketing_calendar/<date>.md
│   ├── sprint_review/<date>.md
│   ├── inbox_triage/<date>.md
│   ├── security_sweep/<date>.json
│   ├── design_drift/<date>.json
│   ├── data_freshness/<date>.json
│   ├── pwa_sanity/<date>.json
│   ├── evening_recap/<date>.md
│   ├── next_day_planner/<date>.md
│   ├── growth_experiment/<date>.json
│   ├── memory_consolidate/<date>.md
│   └── carry_over/<date>.md              # autopilot-monitor 종합
│
└── _logs/                                # 디버깅용 (gitignore)
    └── <taskId>_<date>.log
```

**파일명 규칙**:
- 날짜: `YYYY-MM-DD` (KST 기준, task fire 일자)
- 유저별: `user_<int_id>.{ext}` — UUID 아닌 internal int id (개인정보 노출 최소화)
- 확장자: `.md` 사람 가독 / `.json` 백엔드 파싱 / `.html` 직접 서빙 / `.png` 이미지

---

## 2. 백엔드 read 패턴

### 2.1 Flask route 예 (artifacts)

```python
# routes/artifacts.py (다음 wave 신규)
from pathlib import Path
from flask import Blueprint, send_file, jsonify
from datetime import date

bp = Blueprint("artifacts_cache", __name__, url_prefix="/api/artifacts")
CACHE_ROOT = Path("/Users/seanbae/dev/pivoxquant/cache/artifacts")
# 프로덕션 Railway 환경에서는 ENV로 override:
# CACHE_ROOT = Path(os.getenv("ARTIFACT_CACHE_ROOT", "/app/cache/artifacts"))

@bp.get("/today")
@api_auth
def get_today_artifact():
    artifact_type = request.args.get("type")    # weekly_memo / brag_card / ...
    user_id = current_user.id
    today_str = date.today().strftime("%Y-%m-%d")

    cache_path = CACHE_ROOT / today_str / artifact_type / f"user_{user_id}.html"

    if cache_path.exists():
        # X-Cache: HIT — file 직접 서빙
        return send_file(cache_path, mimetype="text/html", as_attachment=False,
                         download_name=f"{artifact_type}.html",
                         max_age=3600)  # 1h browser cache
    else:
        # X-Cache: MISS — Anthropic API direct fallback (느림 + 토큰)
        # 또는 503 + 재시도 안내 (CEO 결정)
        return jsonify({"status": "miss", "retry_after": 3600}), 503
```

### 2.2 KPI dashboard read

```python
@bp.get("/api/internal/kpi-today")
@admin_auth  # internal only
def kpi_today():
    today_str = date.today().strftime("%Y-%m-%d")
    cache_path = Path(f"cache/ops/kpi_dashboard/{today_str}.json")
    if not cache_path.exists():
        return jsonify({"error": "not_generated_yet"}), 503
    return cache_path.read_text(), 200, {"Content-Type": "application/json"}
```

### 2.3 X-Cache 헤더 컨벤션

| 상태 | 헤더 | 동작 |
|---|---|---|
| HIT | `X-Cache: HIT` | file 직접 서빙, max_age=3600 |
| STALE | `X-Cache: STALE` | 어제 file 서빙 (오늘 아직 미생성), max_age=300 |
| MISS | `X-Cache: MISS` | 503 + retry_after 또는 Anthropic API direct fallback |
| ERROR | `X-Cache: ERROR` | 500 + log to Sentry |

CEO 결정: STALE 허용? — 신선도 중요한 KPI는 STALE 거부, artifact 같은 personal은 STALE OK.

---

## 3. TTL + prune 정책

**TTL**: 24h
**Prune 스케줄**: `ops_memory_consolidate` (T16, 23:00 KST)에서 7일 초과 cache 일자 삭제.

```bash
# T16 SKILL.md 본문 후반에 추가
find /Users/seanbae/dev/pivoxquant/cache -type d -name "20*-*-*" -mtime +7 -exec rm -rf {} \;
```

**예외**: `cache/ops/carry_over/` 는 30일 보존 (감사 추적용).

---

## 4. 동시성 / 원자성

**Write 패턴** (각 task SKILL.md에서):

```bash
# 1. 임시 path에 write
TMP=/tmp/pivox-<taskId>-$(date +%s).tmp
echo "$CONTENT" > "$TMP"

# 2. atomic rename
mv "$TMP" "/Users/seanbae/dev/pivoxquant/cache/ops/<taskId>/$(date +%Y-%m-%d).json"
```

**이유**: 백엔드가 partial write 중인 파일 읽지 않게.

**Read 패턴**: 백엔드는 file 존재 + size > 0 동시 확인.

---

## 5. gitignore 신규 항목

`/Users/seanbae/dev/pivoxquant/.gitignore` 에 추가 (다음 wave):

```
# CC Scheduled-Tasks cache (개인정보 포함 가능)
cache/
!cache/.gitkeep
!cache/README.md
```

**근거**: 
- 유저 artifact는 개인정보 → git commit 금지
- KPI / competitor scan / security sweep도 commit 부담 (diff 잡음 + 민감)
- `.gitkeep` + `README.md`만 commit하여 디렉토리 구조 + read 패턴 documentation 유지

---

## 6. 프로덕션 환경 (Railway) 적용

⚠️ 본 cache 패턴은 **로컬 CC scheduled-tasks 결과**만 cache. Railway prod 서버에는 동일 file 없음.

**옵션 A (현행 가능)**: 백엔드 read도 로컬에서만. Railway prod는 fallback (Anthropic API direct).
**옵션 B (다음 wave)**: rsync or `railway run` 으로 daily cache 업로드 — Railway disk 한도 1GB 주의. cache 일일 추정 50MB → 7일 보존 = 350MB → OK.
**옵션 C**: Cloudflare R2 (free tier 10GB) 업로드 — 단 R2 신규 계정 필요 → **feedback_no_extra_cost 위반 가능성** → CEO 확인 후만.

**현행 결정 (본 spec)**: 옵션 A. Railway prod는 cache MISS = 503 + retry_after 처리. 추가 비용 0원 유지.

---

## 7. 보안 / 개인정보

- `cache/artifacts/<date>/<type>/user_<id>.html` 내용에 개인정보 (이름, 이메일, 포트폴리오 종목) 포함 가능
- 로컬 disk 평문 저장 — CEO 맥북 disk 암호화 (FileVault) 의존
- gitignore로 commit 차단
- TTL 7일 prune으로 누적 차단
- 외부 업로드 시 (옵션 B/C) 암호화 필수 — 본 wave에서는 다루지 않음

**PIPA §28-8 외부 SaaS 인벤토리** (메모리 `legal_pipa_saas_inventory.md` 2026-05-28) 와 별개 — cache는 로컬, 외부 이전 아님.

---

## 8. 모니터링

- cache write 실패 시 task SKILL.md 본문에서 `autopilot_log.md` append `emit_failure` (CC_SCHEDULED_TASKS_EXPANSION.md §6)
- 백엔드 read MISS 비율 모니터링: `/api/internal/cache-stats` (다음 wave) → daily MISS rate > 5% 면 task 누락 의심
- `cache/_logs/<taskId>_<date>.log` 에 verbose 출력 (gitignore)

---

## 9. 미구현 / 다음 wave

1. `cache/` 디렉토리 + `.gitkeep` + `README.md` 생성 — DevOps
2. `.gitignore` 업데이트 — DevOps
3. backend `routes/artifacts.py` + `routes/internal.py` (read 4개 endpoint) — backend-dev
4. T16 SKILL.md에 prune 로직 — DevOps
5. atomic write helper script `scripts/cache_write.sh` — DevOps
6. `/api/internal/cache-stats` 모니터링 endpoint — backend-dev
7. Railway prod 옵션 결정 (A/B/C) — CEO

---

## 10. 절대 금지 (본 wave)

- ✅ `cache/` 디렉토리 실제 생성 안 함 (다음 wave)
- ✅ `.gitignore` 수정 안 함 (다음 wave)
- ✅ backend route 작성 안 함 (다음 wave)
- ✅ 외부 SaaS 업로드 안 함
- ✅ 추가 비용 0원

---

**파일 경로**: `/Users/seanbae/dev/pivoxquant/docs/devops/CACHE_PATTERN.md`
**총 줄수**: 약 195줄
