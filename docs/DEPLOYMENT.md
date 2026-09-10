# Deployment

---

## 1. Local development

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env          # fill in, or leave MONGODB_URI blank for local storage
python -m uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>

With `MONGODB_URI` blank the system uses the bundled JSON store — no database, no
credentials, fully functional. This is the recommended setup for a demo.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

<http://localhost:5173>

### One-click (Windows)

```bat
run_system.bat
```

### Demo data

```bash
cd backend
python scripts/seed_demo.py
```

Seeds three officer accounts and 24 inspections across 30 days so the dashboard
and repository have something to show. Credentials are printed on completion —
they are demonstration only and must never reach a public URL.

---

## 2. First administrator

The very first account registered on an empty system becomes `ADMIN`; every later
self-registration is `INSPECTOR`, whatever the request asks for. Promote others
from **Officers**, or via `PATCH /api/v1/auth/users/{id}/role`.

For an unattended deployment set `BOOTSTRAP_ADMIN_EMAIL` and
`BOOTSTRAP_ADMIN_PASSWORD`; the admin is seeded on first start. With a blank
password nothing is created — a well-known default credential on a public URL is
worse than an unreachable system.

---

## 3. Environment variables

| Variable | Required | Notes |
| :--- | :--- | :--- |
| `MONGODB_URI` | No | Blank ⇒ local JSON store |
| `MONGODB_DB_NAME` | No | Default `legal_metrology_db` |
| `JWT_SECRET_KEY` | **In production** | `python -c "import secrets; print(secrets.token_urlsafe(48))"`. In development an ephemeral key is generated; outside development a missing key is a hard error, because an ephemeral key invalidates every token on restart |
| `ENVIRONMENT` | No | `development` / `staging` / `production` |
| `CORS_ORIGINS` | Yes in production | Comma-separated exact origins. `*` is rejected — the API sends credentials |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Default 7 |
| `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | No | First-run admin |
| `MAX_IMAGE_BYTES` | No | Per-photograph ceiling, default 12 MB |
| `MAX_LISTING_CHARS` | No | Pasted-listing ceiling, default 200,000 |
| `VLM_API_KEY`, `VLM_BASE_URL`, `VLM_MODEL` | No | Optional vision-model pass |

### Rate limiting

`/auth/login` and `/auth/register` are rate limited in-process, per IP **and** per
e-mail address, so an attacker rotating addresses still cannot brute-force one
officer's account. Being in-process, each worker keeps its own counters: behind
more than one worker the effective limit multiplies by the worker count. For a
multi-node deployment, enforce it at the reverse proxy or move the counters to
Redis.

Frontend: `VITE_API_URL` at build time, or change the API address in **Settings**
at runtime.

---

## 4. Free-tier deployment (Vercel + Render)

### Why the backend cannot go on Vercel or Netlify

Both are excellent for the frontend and unusable for this API:

| | Vercel / Netlify functions | This backend needs |
| :--- | :--- | :--- |
| Bundle size | 250 MB unzipped | ~211 MB of OCR deps (opencv 108, onnxruntime 43, numpy 31) **before** FastAPI, ReportLab, python-docx |
| Request timeout | 10 s (Hobby / free) | 10–15 s per scan — five preprocessing variants through OCR |
| Filesystem | read-only, ephemeral | model weights, evidence blobs |

Even if it squeezed under the size limit, every scan would time out. The backend
needs a container host; the frontend is a static bundle and belongs on a CDN.

**So: frontend → a CDN, backend → a container host.** Both free, no card.

For the CDN, Vercel and Netlify are equivalent for a static SPA — this repo ships
`vercel.json` and `netlify.toml`, so either works. The live deployment is on
Netlify: <https://legal-metrology-compliance.netlify.app>

### ⚠️ Claim the administrator account before sharing the URL

Self-registration is open, and **the first account created on an empty system
becomes ADMIN**. On a public URL that is a race anyone can win. Before the API is
reachable by others, do one of:

- set `BOOTSTRAP_ADMIN_PASSWORD` on Render, so the admin exists from first boot; or
- register your own account the moment the API goes live.

Then promote colleagues from **Officers**. Later registrations are always
INSPECTOR regardless of what the request asks for.

### Step 1 — Backend on Render

1. <https://render.com> → sign in with GitHub
2. **New → Blueprint** → select this repository → Render reads `render.yaml`
3. Set the two values it asks for:
   - `CORS_ORIGINS` — leave blank for now, fill in after step 2
   - `MONGODB_URI` — blank for the bundled JSON store, or an Atlas URI to persist
4. Deploy. First build takes ~5 minutes (the OCR image is large).
5. Note the URL, e.g. `https://legal-metrology-api.onrender.com`

Check it: `curl https://<your-api>.onrender.com/api/v1/health`

### Step 2 — Frontend

Already deployed: <https://legal-metrology-compliance.netlify.app>

To redeploy after changes, from the repository root:

```bash
npx -y netlify-cli deploy --build --prod --dir frontend
```

Or connect the repository in the Netlify dashboard (**Project configuration →
Build & deploy → Link repository**) for automatic deploys on every push;
`netlify.toml` already carries the build settings.

On Vercel instead: **Add New → Project** → import the repository. It reads
`vercel.json`; leave the build settings alone.

### Step 3 — Point the two at each other

**On the frontend host**, set `VITE_API_URL = https://<your-api>.onrender.com`
and redeploy. Until then the app defaults to `http://localhost:8000` and shows
"Server unreachable".

> No redeploy handy? The **Settings** screen changes the API address at runtime,
> stored per browser. Useful for a quick demo, but set the build variable for
> anything shared.

**On Render**, set `CORS_ORIGINS` to the exact frontend origin
(`https://legal-metrology-compliance.netlify.app`, no trailing slash) and save.
The service restarts. A wildcard is rejected in config because the API sends
credentials.

Then open the Vercel URL, register the first account (it becomes ADMIN), and scan.

### What the free tier costs you

| | |
| :--- | :--- |
| **Cold starts** | Render free sleeps after 15 minutes idle; the next request waits ~50 s while it wakes. Open the app a minute before a demo. |
| **Ephemeral disk** | Without `MONGODB_URI`, inspections and evidence are lost on redeploy or sleep. Use Atlas free (512 MB) to keep them. |
| **512 MB RAM** | One worker only, and the blueprint caps evidence at 1280 px. A larger instance or a host with more RAM (Hugging Face Spaces gives 16 GB free on Docker) removes this. |
| **Demo risk** | For judging, prefer `docker compose up` or `run_system.bat` locally — no cold start, no Wi-Fi dependency. Keep the deployed URL for sharing. |

---

## 5. Manual production deployment

### 5.1 Frontend — Vercel

`vercel.json` at the repository root builds `frontend/` and rewrites all paths to
`index.html` for client-side routing.

```
Build command:      cd frontend && npm install && npm run build
Output directory:   frontend/dist
Environment:        VITE_API_URL = https://<your-api-host>
```

### 5.2 Backend — container host (Render, Railway, Fly, any VM)

The backend is **not** deployable to Vercel serverless functions: the OCR model
weights exceed the bundle limit and cold starts would time out. This is why the
earlier public deployment silently fell back to browser OCR.

```bash
docker build -t lm-compliance-api ./backend
docker run -p 8000:8000 --env-file backend/.env lm-compliance-api
```

Set on the host:

```
JWT_SECRET_KEY=<generated>
ENVIRONMENT=production
CORS_ORIGINS=https://<your-frontend-domain>
MONGODB_URI=<atlas uri>
```

### 5.3 Both together — Docker Compose

```bash
docker compose up --build
```

Frontend on `:5173`, API on `:8000`. Use this for offline judging: it needs no
external service once the images are built.

---

## 6. MongoDB Atlas

1. Create a cluster and a database user with a **strong, unique** password.
2. Network Access: add only the IPs that need it. Do **not** use `0.0.0.0/0`.
3. Put the connection string in the host's environment — never in the repository.

Indexes are created automatically on first connection: `users.email` (unique),
`inspections.created_at`, `.status`, `.officer_id`, `.violation_rule_ids`, a text
index on `brand`/`product_name`, and `audit_log.created_at`.

Evidence goes to GridFS, downscaled to 1600 px JPEG first. An Atlas free tier is
512 MB; a raw phone frame is ~4 MB, so storing originals would exhaust the cluster
within roughly a hundred inspections.

---

## 7. Security checklist before going public

- [ ] `JWT_SECRET_KEY` set to a generated value, not the example
- [ ] `ENVIRONMENT=production`
- [ ] `CORS_ORIGINS` lists only real frontend origins
- [ ] Atlas Network Access restricted; database password strong and unique
- [ ] `.env` not committed (`git ls-files | grep -c "\.env$"` returns 0)
- [ ] Demo accounts from `seed_demo.py` deleted or deactivated
- [ ] HTTPS terminated in front of the API
- [ ] `pytest` green, and `npm test` in `frontend/` green
- [ ] Rate limiting enforced at the proxy if running more than one worker

> **If a credential has ever been committed, rotate it.** Rewriting git history
> does not un-leak a secret that was pushed to a public repository; only changing
> the password does.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `SettingsError: error parsing value for field "CORS_ORIGINS"` | Value is not a comma-separated string | `CORS_ORIGINS=http://localhost:5173,https://example.com` |
| Login works, then 401 on refresh | `JWT_SECRET_KEY` unset outside development, so a new key is generated per restart | Set a fixed secret |
| `ocr_engine: "none"` in `/health` | Neither PaddleOCR nor RapidOCR installed | `pip install rapidocr-onnxruntime`; browser OCR still works meanwhile |
| Frontend shows "Server unreachable" | Wrong API address, or origin not in `CORS_ORIGINS` | Fix in **Settings**, and check the allowlist |
| Seeded data invisible in a running server | Older builds cached the JSON store indefinitely | Fixed — the store reloads on file change |
| Scan takes 10–15 s | Five preprocessing variants on a large image | Expected on CPU; downscale, or run fewer variants |
| First request after idle takes ~50 s | Render free instance was asleep | Expected; open the app before a demo, or upgrade |
| Render build fails on memory | Free build container ran out during pip install | Retry — Render's free builder is variable — or build the image elsewhere and deploy by digest |
| Deployed app shows "Server unreachable" | `CORS_ORIGINS` on Render does not list the Vercel origin | Set it to the exact `https://…vercel.app` origin, no trailing slash |
| Data disappeared after a redeploy | Free disk is ephemeral and `MONGODB_URI` is unset | Point it at MongoDB Atlas |
| `netlify` CLI fails with `EXDEV` or `ENOSPC` | The system drive is full, so npm's cache and temp cannot be written | Free space, or redirect: `npm_config_cache`, `TEMP`, `TMP`, `APPDATA` to a drive with room |
| Netlify deploy returns 500 | The whole repo was zipped, `node_modules` included (~174 MB) | Deploy the `frontend` subtree, or ensure `node_modules` is excluded |
