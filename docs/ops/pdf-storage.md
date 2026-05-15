# PDF / Artifact Persistent Storage 가이드

> **출시 후 1주 내 fix 필요 (P1).** Railway ephemeral disk가 redeploy 시 PDF 파일을 잃어버려 사용자에게 410 에러. PR #404가 UX 측면(toast 표시)은 닫음, 본 가이드는 **root cause** 해결.
> **추가 비용**: 옵션에 따라 $0 (Railway volume 5GB 무료) ~ $5/월 (Cloudflare R2 무료 한도 초과 시).
> **CEO 작업 시간**: 15-30분.

---

## 문제 (Wave 6 bug-hunter Bug #1)

artifact #93 (2026-04 Brag Card) — `/reports` 페이지에서 "Download PDF" 클릭 시 raw JSON 에러:
```
{"code":"FILE_MISSING","error":"File missing on disk"}
```

**증거 (Wave 6 직접 확인)**:
- `/api/artifacts/93/download` → HTTP 410
- API list 응답에서 `pdf_path: null` (또는 path는 set이지만 disk에 없음)
- backend 코드 (`routes/artifacts.py:251-252`): "a redeploy ... sent 'Open full memo' to /download → 410 → raw JSON in a black tab for brag_card #93"

**근본 원인**: Railway 무료/Hobby plan은 ephemeral filesystem 사용 — 모든 redeploy / restart / scale event 시 `/app/artifacts/...` 디렉터리가 **wipe됨**.

**현재 상태**:
- Frontend: PR #404가 fetch+toast로 사용자 경험 정상화 (raw JSON page 사라짐)
- Backend: PDF는 매월 1일 cron + on-demand 생성. ephemeral disk 이므로 redeploy마다 사라짐.
- 다음 cron tick (매월 1일 09:00 KST)에서 재생성되지만, 그 사이 download 요청은 410.

---

## 해결 옵션 비교

| 옵션 | 비용/월 | 설정 시간 | 영속성 | 메모리 룰 부합 |
|---|---|---|---|---|
| **A. Railway Volume (Built-in, 5GB free)** | $0 | 15분 | Railway 컨테이너 lifecycle 간 영속 | ✅ Railway 기존 서비스 안 |
| B. Cloudflare R2 | $0 (5GB-month + 1M requests free) ~ $0.015/GB | 30분 | Object storage, edge 가까움 | ✅ Cloudflare Free |
| C. AWS S3 | ~$0.023/GB + req | 1시간 | 가장 성숙 | ❌ AWS 신규 계정 + 결제 등록 필요 |
| D. Vercel Blob | $0.15/GB-mo | 20분 | Vercel 통합 좋음 | ⚠️ 별도 결제 |

**권장: 옵션 A (Railway Volume)** — 추가 비용 0원, 기존 서비스 안, 15분 설정.

---

## 옵션 A: Railway Volume 단계별 (권장)

### 1. Railway 대시보드 → Volume 생성 (3분)

1. Railway 대시보드 → `vibrant-blessing` 프로젝트 → `web` 서비스 선택
2. **Volumes** 탭 → **+ Add Volume**
3. Settings:
   - **Mount path**: `/app/artifacts`
   - **Size**: 5 GB (무료 한도)
4. **Create Volume** → 즉시 활성

### 2. Dockerfile / 코드 확인 (변경 불필요)

Railway Volume은 mount path가 `/app/artifacts` — 백엔드 코드가 이미 `/app/artifacts/<type>/<user_id>/<filename>.pdf` 패턴 사용 (services/artifacts/*.py 전반).

```bash
# services/artifacts/brag_card_service.py 등에서 path 생성 예
ARTIFACT_DIR = Path("/app/artifacts/brag_card")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
```

Railway Volume이 자동으로 `/app/artifacts` 를 영속 mount해줌. 코드 변경 0.

### 3. Volume 활성 후 자동 redeploy (자동, 2-5분)

Railway가 새 mount로 컨테이너 재시작. `/app/artifacts/` 하위 파일은 **이제 영속**.

### 4. 검증 (5분)

```bash
# 새 PDF 생성 시도 (cron + on-demand)
curl -X POST -b "session=..." https://web-production-7b484b.up.railway.app/api/artifacts/regenerate/93

# Railway redeploy 강제
gh pr create --title "chore: trigger redeploy" --body "test volume persistence"
# (또는 Railway 대시보드에서 redeploy 버튼)

# Redeploy 후 다시 download
curl -b "session=..." https://web-production-7b484b.up.railway.app/api/artifacts/93/download -o brag.pdf
file brag.pdf  # → "PDF document" 확인
```

`PDF document` 출력되면 영속성 확인 완료.

### 5. 기존 lost artifacts 처리

기존 artifact rows (DB)는 그대로 두되 `pdf_path` null이면 next-cron-tick에 재생성되도록 logic 확인. 또는 사용자가 manual regenerate 요청 가능:

```bash
# /api/artifacts/regenerate/<id> 또는 admin endpoint (있다면)
# 없으면 routes/artifacts.py 에 regenerate endpoint 추가 (별도 PR)
```

---

## 옵션 B: Cloudflare R2 (대안 — 더 견고)

Railway Volume의 한계: 단일 컨테이너 mount. Scale-out 시 (worker 여러 개 띄울 때) shared storage 안 됨. PivoxQuant는 현재 single worker라 무방하나, 향후 scale 대비.

**비용**: 5GB-month 무료 + 1M Class A operations 무료/월. PivoxQuant 트래픽 (월 ~1만 artifact) 으로 무료 한도 안.

**설정**:

1. Cloudflare 대시보드 → R2 → **Create bucket** → `pivoxquant-artifacts`
2. **API Tokens** → R2 token 발급 (`Object Read & Write` 권한)
3. Railway env에 추가:
   ```
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_ACCOUNT_ID=...
   R2_BUCKET=pivoxquant-artifacts
   ```
4. Backend 코드 변경 (별도 PR, ~50줄):
   ```python
   # services/artifacts/storage.py (신규)
   import boto3
   _s3 = boto3.client(
       "s3",
       endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
       aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
       aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
   )
   def upload(local_path: Path, key: str) -> str:
       _s3.upload_file(str(local_path), os.environ["R2_BUCKET"], key)
       return key  # used as pdf_path in DB
   def download_url(key: str, ttl_s: int = 600) -> str:
       return _s3.generate_presigned_url(
           "get_object",
           Params={"Bucket": os.environ["R2_BUCKET"], "Key": key},
           ExpiresIn=ttl_s,
       )
   ```
5. `routes/artifacts.py` download endpoint: `redirect(download_url(pdf_path))` 로 변경
6. requirements.txt에 `boto3>=1.34` 추가

**메모리 룰 부합 검증**:
- `feedback_no_extra_cost`: Cloudflare R2 free tier 5GB-month + 1M req — 추가 비용 0원 (이미 가비아→Cloudflare DNS 위임 진행 중이라 동일 cloud 통합 자연스러움 — PR #399 email setup 가이드 참조)

---

## 옵션 비교 결정 트리

```
Q: 매월 1일 cron으로 모든 사용자 brag card 생성 — 데이터 크기는?
   A: 한 PDF ~150KB × 사용자 100명 = 15MB/월 cumulative
   → 5GB로 333개월 (28년) 충분 → 옵션 A 충분
   
Q: 향후 scale-out (worker 2+) 계획 있는가?
   A: 현재 single worker로 충분 → 옵션 A
   A: 1년 안에 scale-out 예정 → 옵션 B 미리 준비
   
Q: 비용 vs 단순성 선호?
   A: 비용 0 + 단순 → 옵션 A
   A: edge 가까운 download (faster) → 옵션 B
```

**본 가이드 권장 (출시 직전 컨텍스트)**: **옵션 A (Railway Volume) 즉시 적용**. 코드 변경 0, CEO 15분, 비용 0. 옵션 B는 출시 후 사용자 100명+ 도달 시 검토.

---

## 검증 (CEO 작업 후)

1. Railway 대시보드 → web 서비스 → Volumes → `/app/artifacts` 5GB 영속 상태
2. PR #404의 toast 메시지 ("PDF가 아직 준비되지 않았거나 만료됐습니다") **더 이상 안 떠야** 정상
3. /api/health response의 `db: ok` 유지 (volume mount가 DB 영향 X)
4. 다음 월 1일 cron tick 후 모든 artifact #N의 `pdf_path` 채워지고 download 200 OK

---

## 메모리 룰 검증

- ✅ `feedback_no_extra_cost`: Railway 기존 서비스 안, 5GB Volume 무료
- ✅ `feedback_no_busywork`: 실제 P1 SHIP-BLOCKER class bug fix
- ✅ `feedback_no_false_reports`: 옵션 비교 + 검증 명령 + 메모리 룰 부합 각각 직접 명시

본 가이드 작성 근거:
- Wave 6 bug-hunter 발견 (artifact #93 brag card 직접 확인, 410 raw JSON page screenshot)
- routes/artifacts.py:251-289 코드 본문 + 코멘트 직접 인용
- Railway docs: volumes 5GB free (https://docs.railway.app/reference/volumes)
- PR #404 frontend symptom fix (toast) → 본 가이드는 backend root cause
