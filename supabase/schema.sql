-- Foothold app tables for Supabase Postgres (mirror of api/foothold/db.py SQLite tables).
-- Idempotent: safe to run more than once. Paste into Supabase -> SQL Editor -> Run.
-- Security: RLS is ENABLED on every table with NO policies, so the anon/publishable key
-- and signed-in users can read/write nothing. Only the backend's sb_secret_ key
-- (which bypasses RLS) can access these tables. Do not add policies for anon.
-- Column types are TEXT on purpose (ISO-8601 timestamps, *_json columns hold JSON text),
-- matching the SQLite schema exactly so rows round-trip unchanged.

create table if not exists public.consent_requests (
    id           text primary key not null default ('cr_' || substr(md5(random()::text), 1, 12)),
    employer_id  text not null,
    candidate_id text not null,
    posting_id   text,
    message      text not null default '',
    status       text not null default 'pending' check (status in ('pending', 'accepted', 'declined')),
    created_at   text not null default to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
    decided_at   text
);
create index if not exists ix_consent_candidate on public.consent_requests (candidate_id, status);
create index if not exists ix_consent_employer on public.consent_requests (employer_id, status);

create table if not exists public.postings (
    id               text primary key not null default ('po_' || substr(md5(random()::text), 1, 12)),
    employer_id      text not null,
    title            text not null default '',
    text_sanitized   text not null default '',
    profile_json     text not null default '{}',
    sim_variant_json text not null default '{}',
    created_at       text not null default to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
);
create index if not exists ix_postings_employer on public.postings (employer_id, created_at);

create table if not exists public.circle_posts (
    id                text primary key not null default ('cp_' || substr(md5(random()::text), 1, 12)),
    circle_id         text not null,
    handle            text not null,
    text              text not null,
    moderation_status text not null default 'held',
    moderation_reason text,
    created_at        text not null default to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
);
create index if not exists ix_circle_posts on public.circle_posts (circle_id, created_at);

create table if not exists public.progress_log (
    id           text primary key not null default ('pl_' || substr(md5(random()::text), 1, 12)),
    learner_id   text not null,
    kind         text not null,
    payload_json text not null default '{}',
    created_at   text not null default to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
);
create index if not exists ix_progress_learner on public.progress_log (learner_id, created_at);

create table if not exists public.kanban (
    learner_id text primary key not null,
    items_json text not null default '[]',
    updated_at text not null default to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
);

-- Lock everything down: RLS on, no policies, no grants to anon/authenticated.
alter table public.consent_requests enable row level security;
alter table public.postings         enable row level security;
alter table public.circle_posts     enable row level security;
alter table public.progress_log     enable row level security;
alter table public.kanban           enable row level security;

revoke all on public.consent_requests, public.postings, public.circle_posts,
              public.progress_log, public.kanban from anon, authenticated;

-- Make PostgREST see the new tables immediately.
notify pgrst, 'reload schema';

-- Runtime config the public Netlify site may read (e.g. the API's current tunnel URL, key 'api_url').
-- Anyone may read; only the backend's secret key (which bypasses RLS) can write.
create table if not exists public.public_config (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);
alter table public.public_config enable row level security;
drop policy if exists "public read config" on public.public_config;
create policy "public read config" on public.public_config for select to anon, authenticated using (true);
