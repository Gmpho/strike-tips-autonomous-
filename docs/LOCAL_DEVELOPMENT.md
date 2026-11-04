# Local Development — Backend Switch, Docker, Env

## Backend selector (HUD)

Local dev must not burn prod (Modal GB-s + Groq). `vite.config.ts` routes
`/api`, `/docs`, `/openapi.json`, `/v1` by `VITE_BACKEND`:

| Value | Target | When |
|---|---|---|
| `local` (default) | `http://localhost:8000` (docker `strike-bot-new`) | Everyday dev — zero prod spend |
| `prod` | `https://gmpho--strike-tips-racing-serve-api.modal.run` | Explicit live-backend testing only |

```bash
npm run dev                          # local backend
VITE_BACKEND=prod npm run dev        # live backend (burns prod!)
```

The header shows an emerald **LOCAL** / amber **PROD** badge in dev builds so
you always know which backend you're spending. Production builds (Pages) are
unaffected — keyless reads go direct to origins, keyed calls via Functions.

## Docker

```bash
docker compose up -d            # strike-bot-new :8000, odds-monitor, redis, ollama
docker exec strike-bot-new pytest core_agent/tests/ -p no:cacheprovider -s --capture=no
docker compose stop ollama odds-monitor-new   # free RAM; keep redis if you want it
```

Notes:
- The repo bind-mounts to `/app` — local edits are live in-container, no rebuild.
- `start.sh` (and other `*.sh`) must keep the exec bit — a mode-strip broke
  container boot once; `chmod +x` if `exec: permission denied` appears.
- pytest's output capture crashes in this container; always pass `-s --capture=no`.
- Local `fastapi` is missing outside Docker — `test_security_hardening.py`
  only runs in-container.

## Env plumbing

- Root `.env` is the single source (gitignored, never committed).
- `vite.config.ts` backfills `GEMINI_API_KEY` / `GROQ_API_KEY` /
  `STRIKE_TIPS_API_KEY` from `.env` into `process.env` for the dev-server
  plugin services (chat/podcast/tts/transcribe/live) — `loadEnv` alone does
  NOT populate `process.env`, which once broke every cloud feature locally
  with "not configured on the server". Shell exports still win.
- `bun.lock` is not used (npm only); do not re-add it.
