-- 지식 베이스 스키마 (Postgres 15+ / Supabase). pgvector 필요.
create extension if not exists vector;

create table if not exists kb_docs (
  id            text primary key,          -- sha1(url)
  source_id     text not null,
  url           text not null,
  title         text not null default '',
  content_hash  text not null,
  fetched_at    timestamptz not null
);

create table if not exists kb_chunks (
  id          text primary key,            -- doc_id#ordinal
  doc_id      text not null references kb_docs(id) on delete cascade,
  source_id   text not null,
  url         text not null,
  title       text not null default '',
  heading     text not null default '',
  ordinal     int  not null,
  text        text not null,
  fetched_at  timestamptz not null,
  embedding   vector(1024) not null,
  tsv         tsvector generated always as (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(heading,'') || ' ' || text)) stored
);

create index if not exists kb_chunks_doc_idx on kb_chunks (doc_id);
create index if not exists kb_chunks_tsv_idx on kb_chunks using gin (tsv);
-- HNSW: 코사인. 조각이 수십만 건이 되기 전까지는 기본 파라미터로 충분하다.
create index if not exists kb_chunks_emb_idx on kb_chunks using hnsw (embedding vector_cosine_ops);
