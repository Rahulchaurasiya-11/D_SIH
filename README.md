# Legal Metrology Compliance System

**Smart India Hackathon 2026 · Problem Statement 26034**
Ministry of Consumer Affairs, Food & Public Distribution — Department of Consumer Affairs

Scan a packaged commodity, and the system checks it against the mandatory
declarations required by the **Legal Metrology (Packaged Commodities) Rules, 2011** —
then produces a compliance report an enforcement officer can actually issue.

---

## What it does

| | |
| :--- | :--- |
| **Scan** | 1–4 package angles from a phone camera or upload. Also accepts typed label text or a pasted e-commerce listing. |
| **Extract** | OCR across five image variants (upscale, unsharp mask, CLAHE ×2, Otsu) fused into one reading, so blur, glare and faint print still resolve. |
| **Rule** | Seven statutory pipelines decide compliance and cite the provision, the evidence and the remedy for every finding. |
| **Show** | Bounding boxes drawn over the photograph, so an officer sees exactly where each declaration was read from. |
| **Correct** | Any OCR misread can be corrected and the rules re-run, so a bad frame never becomes a wrongful notice. |
| **Report** | PDF with real selectable text, an **editable Word notice**, and bulk Excel export. |
| **Record** | Where the pack was found — premises, address, licence, GPS. A notice is served on a person at a place; a finding without one cannot support it. |
| **Pursue** | Each contravention opens a numbered case (`LM/2026/DEL/000042`) that moves Open → Notice issued → Complied / Escalated → Closed, with a full history. |
| **Track** | Searchable repository, an enforcement dashboard covering outcomes as well as findings, repeat-offender detection, and role-based access for Inspector / Senior Officer / Administrator. |

---

## Quick start

```bash
# Backend
cd backend
python -m pip install -r requirements.txt
cp .env.example .env                 # leave MONGODB_URI blank to run with no database
python -m uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- App — <http://localhost:5173>
- API docs — <http://localhost:8000/docs>

Windows one-click: `run_system.bat`

**From VS Code:** open the folder, then `Ctrl+Shift+P` → *Tasks: Run Task* →
**Run everything**. It starts both servers in their own terminal panes. `F5`
instead runs the API under the debugger, so you can break inside the rule engine
and step through a real scan.

### Demo data

```bash
cd backend && python scripts/seed_demo.py
```

Seeds three officers and 24 inspections across 30 days, and prints the login
credentials. **Demonstration only — never deploy these accounts.**

> With `MONGODB_URI` blank the system stores everything in local JSON files. It is
> fully functional with no database, no credentials and no network — which is what
> you want when the venue Wi-Fi fails.

---

## Deploy it free

**Live:** <https://legal-metrology-compliance.netlify.app>
**API:** <https://legal-metrology-api-ft2v.onrender.com/api/v1/health>

Sign in with the administrator account seeded on first boot
(`admin@legalmetrology.gov.in`); the password is the `BOOTSTRAP_ADMIN_PASSWORD`
set on Render. **Change it before sharing the URL.**

The backend cannot go on Vercel or Netlify: its OCR dependencies are ~211 MB
against a 250 MB function limit, and a scan takes 10–15 s against a 10 s timeout.
It needs a container. The frontend is a static bundle and belongs on a CDN —
Vercel and Netlify are equivalent for that, and both configs ship here.

| | |
| :--- | :--- |
| Frontend | ✅ Netlify (`netlify.toml`). Vercel works too (`vercel.json`). |
| Backend | ✅ Render, Singapore, free plan, auto-deploys from `main`. |
| Wiring | `VITE_API_URL` on Netlify, `CORS_ORIGINS` on Render — both set. |

> **Render's free disk is ephemeral.** Inspections and evidence are lost whenever
> the instance sleeps (15 minutes idle) or redeploys. Set `MONGODB_URI` to an
> Atlas free cluster to keep them. Until then, restore a demo in a minute:
>
> ```bash
> cd backend && python scripts/seed_remote.py >     --api https://legal-metrology-api-ft2v.onrender.com >     --email admin@legalmetrology.gov.in --password '<your password>'
> ```

> **Cold start.** The free instance sleeps after 15 minutes idle; the next request
> waits ~50 s. Open the app a minute before demoing.

Step-by-step, including what the free tier costs you (cold starts, ephemeral
disk), is in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#4-free-tier-deployment-vercel--render).

> For judging, run it locally (`docker compose up` or `run_system.bat`). No cold
> start, no Wi-Fi dependency. Keep the deployed URL for sharing.

---

## Problem statement coverage

| Required capability | Where |
| :--- | :--- |
| Image upload and product scanning | Scan screen · `POST /analyze-package` |
| Extraction and detection of mandatory declarations | `app/engine/compliance_engine.py` |
| Correctness, completeness, placement | 7 rule pipelines; panel-relative geometry |
| Missing / non-compliant declarations | Violation cards with citation, evidence, remedy |
| Font size and readability | Rule 9 pipeline — **advisory estimate**, see below |
| Compliance reports and violation summaries | `app/services/report_*.py` |
| Repository of scanned products and history | Repository screen · `GET /inspections` |
| Search and retrieval | Full-text + status, rule, date, score, officer, source |
| Dashboards for enforcement officials | Dashboard screen · `GET /dashboard/stats` — findings **and** enforcement activity |
| Role-based access and secure authentication | JWT + bcrypt, 3 roles, enforced server-side |
| Export to PDF **and editable formats** | PDF · DOCX · XLSX |
| Photographs and supporting evidence | Downscaled and stored, linked to the inspection |
| Product listings (e-commerce) | `POST /analyze-listing` |
| Technical documentation | [`docs/`](docs/) |

---

## Honest limitations

**Font height is an estimate, not a measurement.** Rule 9 and Schedule II prescribe
minimum character heights **in millimetres**. A photograph has no physical scale, so
without a size reference in the frame or the pack's real dimensions, millimetres
cannot be derived from pixels. Font findings are therefore reported as an
**advisory estimate** and labelled as such in the report — a screening signal that
tells an officer which packs to go and measure, not an invented number. How to make
it definitive is in [`docs/RULE_COVERAGE.md`](docs/RULE_COVERAGE.md).

**There is no offline mode.** The browser can read text when the server is
unreachable, but compliance is always decided server-side — deliberately, so a
phone and the server can never disagree about whether a package is lawful. The
consequence is that an inspector with no signal cannot complete a scan. A proper
fix is a service worker plus a queue of pending scans that syncs on reconnect; it
is the largest remaining gap and is not built.

**Rate limiting is per process.** Behind more than one worker the effective limit
multiplies by the worker count. Enforce it at the reverse proxy, or move the
counters to Redis. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Architecture

```
backend/
  app/
    main.py            application wiring only
    config.py          settings; secrets from the environment, never in code
    deps.py            authentication and role enforcement
    api/v1/            auth · inspections · reports · rules
    core/              ocr.py · security.py
    engine/            compliance_engine.py  ← the statutory rules
    services/          report_pdf · report_docx · report_xlsx · listing_parser
    db/                store (MongoDB | JSON) → repositories
    data/              rule set as CSV, hot-reloadable
  tests/               93 tests, no network, no credentials
  scripts/seed_demo.py

frontend/src/
  App.jsx              router and providers (~100 lines)
  routes/              Login · Dashboard · Scan · Inspection · Repository ·
                       Rules · Officers · Settings
  features/scan/       capture slots · evidence viewer · result · verify panel
  components/          ui primitives · app shell
  context/             Auth · Theme · I18n
  lib/                 api.js (the only HTTP client) · browserOcr.js · format.js
  locales/             en, hi complete; 11 more fall back per key
  styles/tokens.css    light and dark design tokens
```

Two principles worth stating:

**One rule engine.** The browser can read text when the server is unreachable, but
it never decides compliance — that text goes to the server and the Python engine
rules on it. A phone and the server must not be able to disagree about whether a
package is lawful.

**Rules live in data.** The statutory rule set is CSV under `backend/app/data/`. An
officer can change a penalty band or add a regional keyword and hit *Reload from
CSV* — no developer, no redeploy.

---

## Documentation

| | |
| :--- | :--- |
| [Architecture](docs/ARCHITECTURE.md) | Components, data flow, design decisions, security |
| [Deployment](docs/DEPLOYMENT.md) | Local, Docker, Vercel + container host, checklist |
| [API reference](docs/API.md) | Every endpoint with examples |
| [Rule coverage](docs/RULE_COVERAGE.md) | Provision-by-provision status and tests |

---

## Tests

```bash
cd backend  && pytest -v     # 93 tests  (pytest -m "not slow" skips the real-OCR run)
cd frontend && npm test      # 29 tests
```

Golden cases pin the verdict for each statutory provision, so a future rule edit
that changes an outcome fails loudly instead of silently. `test_hardening.py`
covers the defects found in a post-build audit — hostile search input, brute-force
protection, upload ceilings, premises capture, and every case transition including
the illegal ones.

---

## Statutory references

- The Legal Metrology Act, 2009 (No. 1 of 2010)
- Legal Metrology (Packaged Commodities) Rules, 2011 — G.S.R. 202(E)
- Legal Metrology (Packaged Commodities) Amendment Rules, 2021 and 2022
- <https://consumeraffairs.gov.in/pages/legal-metrology-act>

---

## Note on findings

This system assists inspection; it does not replace it. Findings are derived from
optical character recognition and are intended to help an authorised officer decide
where to look. Every report carries that statement, and anything marked *advisory*
requires physical verification before enforcement action.
