# Supabase setup (3 steps)

Project: `zpdcmaqdowboscsrfmad` (API URL `https://zpdcmaqdowboscsrfmad.supabase.co`).

1. **Create the tables.** Open https://supabase.com/dashboard/project/zpdcmaqdowboscsrfmad/sql/new,
   paste the whole of [`schema.sql`](schema.sql), click **Run**. It is safe to run again.
2. **Copy the secret key.** Project Settings -> API Keys -> **Secret keys** -> reveal/copy the key that
   starts with `sb_secret_` (not the `sb_publishable_` one: that key is blocked by RLS and is ignored).
3. **Put it in `.env`** at the repo root (never commit it):

   ```
   SUPABASE_URL=https://zpdcmaqdowboscsrfmad.supabase.co
   SUPABASE_SECRET_KEY=sb_secret_...
   DB_BACKEND=auto
   ```

   Save any `.py` file in `api/` (or restart the API). `GET http://127.0.0.1:8000/health` then shows
   `"db": {"backend": "supabase", "reason": "ok", ...}`. If it says `sqlite` the `reason` explains why
   (missing key, publishable key, or tables not created).

How it works: the API keeps using local SQLite for reads (fast, works offline) and mirrors every write
to the five tables (`consent_requests`, `postings`, `circle_posts`, `progress_log`, `kanban`) to Supabase
in the background. On startup it pulls Supabase rows into SQLite and pushes local rows Supabase lacks.
Accounts (fictional demo personas) stay local and are re-seeded from `data/processed/personas.json`.
RLS is on with no policies, so the browser/publishable key can never read these tables.
