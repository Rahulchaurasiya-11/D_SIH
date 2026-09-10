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
| **Track** | Searchable repository of every inspection, an enforcement dashboard, and role-based access for Inspector / Senior Officer / Administrator. |

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
| Dashboards for enforcement officials | Dashboard screen · `GET /dashboard/stats` |
| Role-based access and secure authentication | JWT + bcrypt, 3 roles, enforced server-side |
| Export to PDF **and editable formats** | PDF · DOCX · XLSX |
| Photographs and supporting evidence | Downscaled and stored, linked to the inspection |
| Product listings (e-commerce) | `POST /analyze-listing` |
| Technical documentation | [`docs/`](docs/) |

---

## An honest limitation

Rule 9 and Schedule II prescribe minimum character heights **in millimetres**.

A photograph has no physical scale. Without a reference object of known size in the
frame, or the pack's real dimensions, millimetres cannot be derived from pixels.

So the system reports font findings as an **advisory estimate** based on character
height relative to the display panel, labels them as such in the report, and treats
them as a screening signal — it tells an officer which packs to go and measure. It
does not print an invented millimetre figure.

Full details, and how to make the check definitive, are in
[`docs/RULE_COVERAGE.md`](docs/RULE_COVERAGE.md).

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
  tests/               51 tests, no network, no credentials
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
cd backend && pytest -v      # 51 tests
```

Golden cases pin the verdict for each statutory provision, so a future rule edit
that changes an outcome fails loudly instead of silently.

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
