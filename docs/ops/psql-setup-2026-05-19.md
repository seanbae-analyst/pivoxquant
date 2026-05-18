# Local psql Client Setup — Wave G BLOCKED 해소

**Date**: 2026-05-19 (v45.2)
**Audience**: CEO (seanbae)
**Cost**: 0원 (Homebrew + postgresql@16 무료, Railway Hobby plan 기존 결제)
**관련**: `session_2026-05-18.md` Wave G prod DB DRY-RUN BLOCKED — `psql not found`

---

## 배경

Wave G 에서 prod Railway PostgreSQL 에 직접 query 시도 → 로컬에 `psql` 미설치로 BLOCKED.
본 문서는 3가지 옵션 중 CEO 가 선택할 수 있는 설치/접근 가이드.

---

## 옵션 비교

| 옵션 | 방식 | 설치 시간 | 사용 편의 | GUI | 권고 대상 |
| ---- | ---- | -------- | --------- | --- | --------- |
| **A** | psql CLI (script 자동) | 약 2분 | ⭐⭐⭐ (terminal 익숙 시) | ❌ | 자율 wave / CI 호환 / 빠른 ad-hoc query |
| **B** | DBeaver / TablePlus (GUI) | 약 5분 | ⭐⭐⭐⭐⭐ | ✅ | 시각적 schema 탐색 / 결과 표 보기 / 비개발자 |
| **C** | Railway Dashboard SQL 콘솔 | 0분 (즉시) | ⭐⭐ (단순 query 만) | ✅ (웹) | 1회성 SELECT / 설치 회피 |

> **권고**: 옵션 A (자동 script) 가 자율 wave 와 호환되고 가장 재현 가능. 옵션 B 는 schema 탐색용으로 병행 추천. 옵션 C 는 응급 backup.

---

## 옵션 A — psql CLI 자동 설치 (권고)

### 실행

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
chmod +x scripts/setup_dev_psql.sh   # 최초 1회만
./scripts/setup_dev_psql.sh
```

### Script 동작 (§1~§6)

1. `psql` 이미 설치 시 즉시 종료
2. Homebrew 확인 (없으면 abort + 가이드)
3. `brew install postgresql@16` (client only, server 는 Railway 사용)
4. `~/.zshrc` 에 `PATH` 추가 (keg-only formula 이므로 명시 export 필요)
5. 절대 경로로 `psql --version` 검증
6. Railway CLI 안내 (옵션) — 미설치 시 `brew install railway` 권고

### 사후 검증

```bash
# 새 terminal 또는 현재 shell 갱신
source ~/.zshrc

# psql 확인
psql --version
# expected: psql (PostgreSQL) 16.x

# Railway prod DB 연결 (railway CLI 사전 link 필요)
cd /Users/seanbae/Desktop/취준/pivoxquant
railway link          # 첫 실행만 — 프로젝트 선택
railway run psql -c "SELECT version();"
```

### 안전성

- **server 미설치** — postgresql@16 formula 는 client + server 모두 포함하지만 본 script 는 `brew services start` 호출 안 함 → 로컬에 PostgreSQL 데몬 안 뜸. macOS 자원 소모 0.
- **데이터 변경 안 함** — 설치 + PATH 등록만. DB 접속 정보는 별도 (railway run / DATABASE_URL).
- **rollback**: `brew uninstall postgresql@16` + `~/.zshrc` 에서 해당 export 라인 제거.

---

## 옵션 B — GUI Client (DBeaver / TablePlus)

### DBeaver Community (무료, cross-platform)

1. https://dbeaver.io/download/ → **DBeaver Community Edition** macOS dmg 다운로드
2. 설치 후 실행 → **New Database Connection** → **PostgreSQL**
3. Railway 대시보드 → 프로젝트 → PostgreSQL 서비스 → **Connect** → **PostgreSQL Connection URL** 복사
4. DBeaver 의 **URL** 필드에 붙여넣기 → **Test Connection** → **Finish**

### TablePlus (유료 $89, 무료 limited 모드 존재)

1. https://tableplus.com/download → macOS dmg
2. `Cmd+N` → **PostgreSQL** → Railway connection URL 입력
3. 무료 모드: 동시 2 tab + 2 connection 제한 — 단순 query 용으로 충분

### 안전성

- **prod DB 직접 접속** — 실수로 `UPDATE`/`DELETE` 실행 가능. 반드시 **read-only role** 사용 권고:
  - Railway 콘솔에서 read-only user 생성 후 connection URL 분리
  - 또는 DBeaver/TablePlus 설정에서 **Read-only mode** 토글 ON

---

## 옵션 C — Railway Dashboard SQL Console (응급)

### 사용법

1. https://railway.app/dashboard → PivoxQuant 프로젝트
2. 좌측 service 목록에서 **PostgreSQL** 선택
3. 상단 탭 **Data** 또는 **Query** (Railway UI 버전마다 명칭 다름)
4. SQL 입력 → **Run**

### 제약

- 결과 표 row 수 제한 (UI 기본 100-1000 rows)
- multi-statement transaction 제한적
- export 옵션 제한 (CSV 다운로드만)
- 인터넷 필요 (오프라인 불가)

### 안전성

- **prod 접속** — 실수 위험 동일. `BEGIN; ... ROLLBACK;` 패턴으로 항상 dry-run 먼저 권고.

---

## Wave G 후속 — DRY-RUN 권고

옵션 A 설치 완료 후 Wave G DRY-RUN 재시도:

```bash
cd /Users/seanbae/Desktop/취준/pivoxquant
railway run psql << 'SQL'
\d users
\d artifacts
SELECT current_database(), current_user, version();
SELECT count(*) FROM users;
SELECT count(*) FROM artifacts;
SQL
```

> 출력을 `session_2026-05-19.md` 또는 후속 wave docs 에 캡처.

---

## 비용 검증

| 항목 | 비용 |
| ---- | ---- |
| Homebrew | 0원 |
| postgresql@16 (client) | 0원 |
| Railway Hobby plan (기존 결제) | $5/mo (CEO 기존) |
| DBeaver Community | 0원 |
| TablePlus | 0원 (limited) / $89 옵션 |

→ **옵션 A 채택 시 추가 비용 0원**. `feedback_no_extra_cost` 준수.

---

**문서 종료**. 권고 순서: 옵션 A 우선 → 필요 시 옵션 B 병행 → 옵션 C 는 응급 backup.
