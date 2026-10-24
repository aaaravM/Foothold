# Deploying Foothold (Netlify + laptop API + Supabase)

Netlify only hosts static files, and the agent server (FastAPI + LangGraph + PyTorch + OR-Tools)
cannot run there. So the public demo is three pieces:

```
Browser -> Netlify (static Next.js export, web/out)
        -> https tunnel URL -> Python API on the laptop (127.0.0.1:8000)
                               -> Supabase Postgres (mirror of app data), else local SQLite
```

**Limitation:** the laptop has to stay on, with the API and the tunnel running, the whole time
people use the site. If it's off, the pages still load but the AI features (sim, coach, planner,
employer agents) fail with network errors. A quick-tunnel URL changes every time the tunnel restarts,
so after a restart you rebuild and redeploy.

## 1. Supabase (optional, about 2 min)

See [`supabase/README.md`](../supabase/README.md):
1. Dashboard -> SQL Editor -> paste `supabase/schema.sql` -> **Run**.
2. Project Settings -> API Keys -> copy the **`sb_secret_...`** key (the publishable key is not enough).
3. In `.env` set `SUPABASE_URL=https://zpdcmaqdowboscsrfmad.supabase.co`, `SUPABASE_SECRET_KEY=sb_secret_...`,
   `DB_BACKEND=auto`. Then check `curl http://127.0.0.1:8000/health`, which should show `"db":{"backend":"supabase",...}`.

Without it, everything still works on local SQLite (`"backend":"sqlite"`).

## 2. Start the API and a tunnel

```bash
scripts/run_api.sh            # if it isn't running already
scripts/tunnel.sh             # downloads cloudflared on first run, prints TUNNEL_URL=https://xxxx.trycloudflare.com
# If cloudflared can't download or connect (some school/office networks block github.com and trycloudflare.com):
TUNNEL_PROVIDER=ssh scripts/tunnel.sh   # localhost.run over ssh, prints https://xxxx.lhr.life
```

Leave this terminal open. A phone hotspot works if the local network blocks both tunnel services.
The API's CORS already allows `https://*.netlify.app`, `https://*.trycloudflare.com` and `https://*.lhr.life`.

## 3. Build the static site using the tunnel URL

```bash
scripts/build_web_static.sh https://xxxx.trycloudflare.com
```

This builds into `web/.next-export` (so the running `next dev` is untouched) and moves the result to
`web/out` (13 static pages).

## 4. Deploy to Netlify

Option A, no account setup: open https://app.netlify.com/drop and drag the **`web/out`** folder onto it.
You get a `https://<random>.netlify.app` link right away (sign in to keep it longer than an hour).

Option B, CLI with a token (User settings -> Applications -> Personal access tokens):

```bash
export NETLIFY_AUTH_TOKEN=...            # never commit it
npx netlify-cli deploy --dir web/out --prod            # first time: choose "Create & configure a new site"
# later: npx netlify-cli deploy --dir web/out --prod --site <site-id>
```

`netlify.toml` (repo root) sets base `web`, publish `out`, and security headers. If the repo is
connected to Netlify CI instead, set `NEXT_PUBLIC_API_URL` in the site's environment variables.

## After a tunnel restart

You get a new URL, so run `scripts/build_web_static.sh <new url>` again and redeploy (drag `web/out` again,
or run the same `netlify deploy --prod --site <id>`).

## Notes
- Secrets stay on the laptop (`.env`). The static site contains only the public API URL.
- Supabase tables have RLS enabled and no policies, so the publishable/anon key can't read them. Only
  the API's secret key can.
- All people and employers in the demo are fictional.
