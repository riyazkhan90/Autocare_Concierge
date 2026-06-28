# Deployment Guide — Railway

Deploy the Al Futtaim Automotive Concierge FastAPI app to [Railway](https://railway.app).

> **Why Railway?** This app is a long-running Python process with SQLite. Railway fits better than Vercel (serverless). For a production CRM integration you would later move SQLite to PostgreSQL.

---

## Prerequisites

- GitHub repo pushed: https://github.com/riyazkhan90/Autocare_Concierge
- [Railway account](https://railway.app) (GitHub login)
- Groq API key from [console.groq.com](https://console.groq.com)

---

## Step 1 — Create project

1. Go to [railway.app/new](https://railway.app/new)
2. Choose **Deploy from GitHub repo**
3. Select **riyazkhan90/Autocare_Concierge**
4. Railway detects Python via `pyproject.toml` and uses `railway.toml` start command

---

## Step 2 — Environment variables

In Railway → your service → **Variables**, add:

| Variable | Value | Required |
|----------|-------|----------|
| `GROQ_API_KEY` | Your Groq API key | Yes |
| `SKIP_TTS` | `true` | Recommended (saves Orpheus quota; browser TTS on voice) |

Do **not** commit `.env` to GitHub.

---

## Step 3 — Generate public URL

1. Railway → service → **Settings** → **Networking**
2. Click **Generate Domain**
3. Open `https://your-app.up.railway.app` — redirects to the chat UI

Health check: `https://your-app.up.railway.app/health`  
Admin dashboard: `https://your-app.up.railway.app/admin`

---

## Step 4 — SQLite persistence (optional)

By default SQLite lives in `data/alfuttaim.db`. Railway’s filesystem is **ephemeral** — metrics and bookings reset on redeploy unless you add a volume.

**To persist demo metrics:**

1. Railway → service → **Volumes** → **Add volume**
2. Mount path: `/app/data`
3. Redeploy

The app creates `data/alfuttaim.db` on first request.

---

## Step 5 — Verify deployment

```bash
curl -s https://YOUR-RAILWAY-DOMAIN/health
# {"status":"ok"}

curl -s -X POST https://YOUR-RAILWAY-DOMAIN/chat/text \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","thread_id":"deploy-test-001"}'
```

In the browser:

1. Open the Railway URL
2. Run a guided booking or trade-in flow
3. Check `/admin` for metrics

---

## Voice on Railway

- Railway serves **HTTPS** by default — required for microphone access in the browser
- Set `SKIP_TTS=true` unless you have accepted Orpheus terms and have TPD quota
- Voice replies fall back to browser `speechSynthesis` when TTS is skipped or rate-limited

---

## Security notes (public demo)

| Item | Demo | Production |
|------|------|------------|
| Admin dashboard (`/admin`) | Open | Add auth / IP allowlist |
| Groq key | Railway env var | Secrets manager |
| Customer data | Mock profiles only | Real CRM with consent |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails | Check Railway build logs; ensure `uv.lock` is committed |
| `500` on chat | Verify `GROQ_API_KEY` is set in Variables |
| App sleeps / cold start | Railway hobby plan; first request may be slow |
| Metrics empty after redeploy | Add a Volume (Step 4) or accept fresh DB per deploy |
| TTS errors | Set `SKIP_TTS=true` |

---

## Redeploy after code changes

Push to `main` on GitHub — Railway auto-redeploys if connected to the repo.

```bash
git push origin main
```

---

## Related

- [TECHNICAL.md](TECHNICAL.md) — API and env vars  
- [README.md](../README.md) — local setup
