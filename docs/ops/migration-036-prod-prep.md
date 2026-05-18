# Migration 036 — Growth user_id FK constraint (prod prep)

External action #16 (HANDOVER v44.9, H-3 audit). Adds an explicit FK
`growth_reflections.user_id -> users.id ON DELETE CASCADE` and the same on
`growth_scores`. Hard-deletes orphan rows (`user_id=0` from the 020 backfill,
plus any `user_id NOT IN users.id` strays).

## What changes

| Table                | Before                          | After                                            |
|----------------------|---------------------------------|--------------------------------------------------|
| `growth_reflections` | `user_id Integer` (no FK)       | `user_id Integer FK users(id) ON DELETE CASCADE` |
| `growth_scores`      | `user_id Integer` (no FK)       | `user_id Integer FK users(id) ON DELETE CASCADE` |

Orphan rows (`user_id` not present in `users.id`) are hard-deleted before
the FK is created — otherwise the FK creation itself errors on Postgres
(`violates foreign key constraint`).

## Pre-deploy checklist

1. **Count prod orphans** (read-only — Railway Postgres SQL console or
   `railway run psql $DATABASE_URL`):

   ```sql
   SELECT
     'growth_reflections' AS table_name,
     COUNT(*)             AS orphan_count
   FROM growth_reflections
   WHERE user_id NOT IN (SELECT id FROM users)
   UNION ALL
   SELECT
     'growth_scores',
     COUNT(*)
   FROM growth_scores
   WHERE user_id NOT IN (SELECT id FROM users);
   ```

   Expected on current prod (v44.9): a small number of `user_id=0` rows
   from the 020 backfill, plus zero genuine strays (`routes/growth.py`
   always writes `current_user.id`). If the count exceeds ~10 per table,
   stop and investigate before deploying.

2. **Backup the two tables** (cheap — both tables are small):

   ```sql
   CREATE TABLE growth_reflections_pre036_backup
       AS SELECT * FROM growth_reflections;
   CREATE TABLE growth_scores_pre036_backup
       AS SELECT * FROM growth_scores;
   ```

   The backup is the rollback path for the orphan delete (the FK drop
   itself is in `downgrade()` and is reversible). Drop the backup tables
   after a successful canary window (~72 h).

3. **Confirm `alembic heads` is single** before deploy:

   ```bash
   cd migrations && alembic heads
   # → 036_growth_user_id_fk (head)
   ```

   If two heads appear, do NOT deploy — branched migrations require a
   merge revision first.

## Apply

Migration runs automatically as part of the standard deploy path:

```bash
# Railway deploys execute this via Procfile / Dockerfile entrypoint.
flask db upgrade
```

Manual one-shot if needed (rare):

```bash
railway run --service web "cd migrations && alembic upgrade head"
```

## Verify after deploy

```sql
-- FK is in place
SELECT conname, conrelid::regclass, confrelid::regclass, confdeltype
FROM pg_constraint
WHERE conname LIKE 'fk_growth_%user_id%';
-- Expected: confdeltype='c' (CASCADE) on both rows.

-- Orphans gone
SELECT COUNT(*) FROM growth_reflections WHERE user_id NOT IN (SELECT id FROM users);
SELECT COUNT(*) FROM growth_scores      WHERE user_id NOT IN (SELECT id FROM users);
-- Expected: 0, 0.
```

## Rollback

Schema-level rollback drops the FK only — orphan rows are NOT restored
(DELETE is not reversible at the migration level). Two-step recovery:

```bash
# 1) Drop the FK
railway run --service web "cd migrations && alembic downgrade -1"

# 2) Restore orphan rows from the backup (if needed — usually you don't,
#    the 020 user_id=0 marker rows are dead weight by construction).
railway run --service Postgres "psql $DATABASE_URL -c \"
  INSERT INTO growth_reflections
  SELECT * FROM growth_reflections_pre036_backup
  WHERE id NOT IN (SELECT id FROM growth_reflections);
\""
```

After a clean canary, drop the backup tables:

```sql
DROP TABLE growth_reflections_pre036_backup;
DROP TABLE growth_scores_pre036_backup;
```

## Cross-references

- Source migration: `migrations/versions/036_growth_user_id_fk_constraint.py`
- Tests: `tests/test_migration_036_growth_user_fk.py`
- Prior art (FK + cascade pattern): `migrations/versions/029_user_cascade_delete.py`
- Original IDOR fix: `migrations/versions/020_growth_user_id.py`
- Backstory: HANDOVER v44.9 H-3 audit, external action #16
