# Foothold

Try the job. Prove the skill. Get the foothold. A career workday sim, pathway planner and consent-first employer network for California's Central Valley.

## Run it

Requires Python 3.12 and Node 22.

```bash
# API (http://localhost:8000)
python -m venv .venv
.venv/Scripts/pip install -r api/requirements.txt
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
cp .env.example .env        # add OPENAI_API_KEY; TAVILY_API_KEY and Supabase keys are optional
.venv/Scripts/python -m uvicorn main:app --app-dir api --port 8000

# Web (http://localhost:3000)
cd web && npm install && npm run dev
```

Tests: `python -m pytest api/tests` · End-to-end: `python scripts/e2e_golden.py` · Reset demo data: `python scripts/reset_demo.py`

Includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA), used under the [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license. O*NET® is a trademark of USDOL/ETA. Foothold has modified all or some of this information; USDOL/ETA has not approved, endorsed, or tested these modifications.
