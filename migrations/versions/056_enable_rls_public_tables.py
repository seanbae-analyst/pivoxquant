"""public 스키마 모든 테이블에 RLS 켜기 (Supabase Data API 방어 겹).

Revision ID: 056_enable_rls_public_tables
Revises: 055_drop_broker_plaintext_tokens
Create Date: 2026-09-24

Why
===
2026-09-24 DB 보안 업그레이드. prod 는 Supabase 라 PostgREST(Data API)가
``anon`` / ``authenticated`` 롤로 public 스키마를 노출할 수 있다. 앱은 Data API 를
쓰지 않고 ``pivox_app`` 롤로 직접 접속한다(코드 grep 실측: supabase-js 0건).

같은 날 Supabase 쪽에서 이미 한 것 (MCP migration ``harden_public_schema_data_api``):
- anon/authenticated 의 public 테이블·시퀀스·함수 권한 전부 회수
- ``postgres`` 가 앞으로 만드는 객체에 두 롤 권한이 자동으로 붙는 default
  privileges 회수

RLS 는 테이블 소유자만 켤 수 있고 소유자가 ``pivox_app`` 이라 여기서 한다.
정책 없는 RLS = 소유자 외 전부 거부. 소유자는 ``FORCE`` 가 아니면 RLS 를
우회하므로 앱 동작은 그대로다. 권한이 실수로 다시 붙어도 행이 새지 않게 하는
두 번째 겹이다.

Scope
-----
PostgreSQL 전용. SQLite(dev/test)에는 RLS 가 없어 no-op. 현재 롤이 소유한
테이블만 건드린다(소유자 아닌 테이블에서 ALTER 는 실패하므로).
``db.create_all()`` 로 나중에 생기는 테이블은 RLS 가 꺼진 채 생기지만
anon/authenticated 권한이 없으니 노출되지 않는다 — 다음 리비전에서 다시
돌리면 켜진다.

Downgrade 는 RLS 를 끈다.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "056_enable_rls_public_tables"
down_revision = "055_drop_broker_plaintext_tokens"
branch_labels = None
depends_on = None


def _owned_public_tables(bind) -> list[str]:
    return [
        r[0]
        for r in bind.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tableowner = current_user"
            )
        )
    ]


def _set_rls(enable: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    verb = "ENABLE" if enable else "DISABLE"
    for name in _owned_public_tables(bind):
        quoted = bind.dialect.identifier_preparer.quote(name)
        op.execute(f"ALTER TABLE public.{quoted} {verb} ROW LEVEL SECURITY")


def upgrade():
    _set_rls(True)


def downgrade():
    _set_rls(False)
