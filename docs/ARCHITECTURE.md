# Software architecture

System for checking compliance of packaged commodities under the Legal Metrology
(Packaged Commodities) Rules, 2011 — SIH problem statement **26034**, Department of
Consumer Affairs.

---

## 1. Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLIENT  (React 18 + Vite, mobile-first)                             │
│                                                                      │
│  Login → AppShell ─┬─ Dashboard      (Recharts, role-scoped)         │
│                    ├─ Scan           (4 angles / typed / listing)    │
│                    ├─ Repository     (search, filter, bulk export)   │
│                    ├─ Inspection     (report, evidence, audit trail) │
│                    ├─ Statutory rules                                │
│                    ├─ Officers       (ADMIN only)                    │
│                    └─ Settings                                       │
│                                                                      │
│  lib/api.js  — the only HTTP client: bearer token, refresh-on-401    │
│  lib/browserOcr.js — Tesseract fallback, TEXT ONLY (never verdicts)  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS, JSON, Bearer JWT
┌───────────────────────────────▼──────────────────────────────────────┐
│  API  (FastAPI)                                                      │
│                                                                      │
│  app/main.py      wiring only — CORS allowlist, routers, lifespan    │
│  app/deps.py      get_current_user, require_role(rank)               │
│                                                                      │
│  app/api/v1/  auth · inspections · reports · rules                   │
│       │                                                              │
│       ├── app/core/ocr.py       preprocessing variants → fused text  │
│       ├── app/core/security.py  bcrypt + JWT (access / refresh)      │
│       ├── app/engine/           ★ compliance_engine.py — the rules   │
│       ├── app/services/         report_pdf · report_docx ·           │
│       │                         report_xlsx · listing_parser         │
│       └── app/db/               store (Mongo | JSON) → repositories  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┴────────────────────────┐
        │                                                │
┌───────▼─────────┐                          ┌───────────▼────────────┐
│ MongoDB Atlas   │   ── or, with no ──      │ Local JSON store       │
│ + GridFS        │      credentials         │ + blob directory       │
│ (production)    │                          │ (offline demo)         │
└─────────────────┘                          └────────────────────────┘

        app/data/*.csv  — statutory rule set, hot-reloadable
```

---

## 2. Design decisions

### 2.1 One rule engine, never two

`compliance_engine.py` is the single authority on whether a package is lawful.

The browser can read text when the server is unreachable (`lib/browserOcr.js`), but
it posts that text to `POST /api/v1/analyze-text` and the Python engine rules on it.
The previous implementation carried a second JavaScript reimplementation of the
rules, so a phone and the server could reach different verdicts about the same
package. For an enforcement tool that is indefensible, so the JS rules were deleted.

### 2.2 Rules live in data, not code

The statutory rule set is CSV under `backend/app/data/`:

| File | Contents |
| :--- | :--- |
| `legal_metrology_rules.csv` | Rule id, provision, severity, penalty band, remedy |
| `approved_metric_units.csv` | SI and count units, incl. regional scripts |
| `prohibited_imperial_units.csv` | Non-metric units banned under Rule 11 |
| `tax_suffix_clauses.csv` | "Inclusive of all taxes" variants |
| `consumer_care_keywords.csv` | Grievance-redressal keywords |
| `mfg_date_keywords.csv` | Manufacture / packing date markers |

A Legal Metrology officer can amend a penalty band or add a regional keyword and
call `POST /api/v1/rules/reload` (ADMIN) — no developer, no redeploy.

### 2.3 Two storage backends behind one query dialect

`app/db/store.py` exposes `insert / find / count / find_one / update_one /
delete_one / put_blob / get_blob` over either MongoDB Atlas or local JSON files,
both speaking the same subset of the Mongo query language (`$in`, `$gte`, `$regex`,
`$or`, …). Repository code is written once and never branches on the backend.

The JSON backend is not a toy: it keeps the system fully demonstrable with no
network and no credentials, which matters for offline judging and for a fresh
clone. It reloads a collection when the file's mtime changes, so an external
writer (the seed script, an operator) is visible without a restart.

### 2.4 Reports rendered server-side

`report_content.py` flattens a stored inspection into one content model; the PDF,
DOCX and XLSX renderers all read from it, so the three formats cannot contradict
each other on penalty figures or legal citations.

The PDF is ReportLab, not a screenshot: text is selectable, searchable and
copyable into a notice, and a full report with an embedded photograph is ~60 kB.

### 2.5 Authorisation is server-side

`require_role(rank)` guards every protected route; `INSPECTOR < SENIOR_OFFICER <
ADMIN`. An inspector is pinned to their own records inside the query builder, so
passing another officer's `officer_id` cannot widen their scope. The frontend
hides what a role cannot use — that is convenience, not a control.

---

## 3. Request flow: scanning a package

```
1.  Officer captures 1–4 angles           →  POST /api/v1/analyze-package
2.  core/ocr.py builds 5 image variants      (upscale, unsharp, CLAHE ×2, Otsu)
3.  OCR runs on each variant                 (PaddleOCR, else RapidOCR ONNX)
4.  Detections fused                         (dedupe by text + box overlap)
5.  Segments sorted into reading order       (top→bottom, left→right)
6.  compliance_engine.evaluate_compliance()  → status, score, violations,
                                                passed checks, metadata
7.  Photos downscaled to 1600 px, stored     → evidence blob ids
8.  Inspection persisted, audit entry written
9.  Response includes raw_segments           → client draws boxes on the photo
```

If step 6 misreads a declaration, the officer opens **Verify & correct**, supplies
the true values, and `POST /api/v1/verify-and-audit` re-runs the same engine with
those overrides. The inspection is then marked officer-verified. Without this, one
bad frame becomes a wrongful enforcement notice.

---

## 4. Rule pipelines

| Pipeline | Provision | Checks |
| :--- | :--- | :--- |
| MRP | Rule 6(1)(da) | Price present **and** carries "inclusive of all taxes" |
| Net quantity | Rule 11 & 12 | Approved SI/count unit; flags imperial units |
| Consumer care | Rule 6(1)(g) | Requires **both** e-mail and telephone |
| Manufacture date | Rule 6(1)(c) | Parses month/year; unreadable date ≠ pass |
| Font & layout | Rule 9 / Sch. II | Character height vs. panel — see §5 |
| Country of origin | Rule 6(10) | Origin declared |
| Manufacturer | Rule 6(1)(a) | Name and address declared |

Supporting behaviour: cylindrical-label fragment reconstruction (text split across
a curved pack), multilingual script detection, and manual-override merging.

---

## 5. Known limitation: font height

Rule 9 and Schedule II prescribe **minimum character heights in millimetres**.

A photograph carries no physical scale. Without a reference object of known size in
frame, or the package's real dimensions, millimetres cannot be derived from pixels —
any figure claiming otherwise is invented.

The system therefore reports font findings as an **advisory estimate** based on
character height relative to the display panel, and says so in the report. It is a
screening signal that tells an officer which packs to measure, not a measurement.

Completing this properly requires either a fiducial marker in frame or an officer
entering the pack dimensions; both are viable extensions.

---

## 6. Security

| Concern | Treatment |
| :--- | :--- |
| Passwords | bcrypt, SHA-256 pre-hash so >72-byte passphrases keep full entropy |
| Tokens | JWT access (30 min) + refresh (7 days); type-tagged, so an access token cannot be redeemed as a refresh |
| Secrets | Environment only. No fallback connection string; a missing `MONGODB_URI` degrades to the local store rather than connecting somewhere unexpected |
| CORS | Explicit origin allowlist; `"*"` is rejected in config because the API sends credentials |
| Privilege escalation | Registration cannot self-assign a role; only the first account on an empty system becomes ADMIN |
| User enumeration | Unknown e-mail and wrong password return an identical 401 |
| SSRF | Listing ingestion parses pasted text/HTML; it never fetches a user-supplied URL |
| Header injection | Report filenames are sanitised before `Content-Disposition` |
| Evidence | Served only to authenticated officers with access to the inspection |
| Audit | Every scan, revision, export and role change is recorded |

---

## 7. Enforcement case lifecycle

A scan produces a finding. Enforcement is what happens next, and the problem
statement asks for a dashboard covering "inspections, violations and enforcement
activities" — activities meaning outcomes, which have to be tracked.

```
        scan finds a contravention
                  │
                  ▼
              ┌────────┐
              │  OPEN  │  case number allocated: LM/2026/DEL/000042
              └───┬────┘
        ┌─────────┴──────────┐
        ▼                    ▼
┌────────────────┐      ┌────────┐
│ NOTICE_ISSUED  │─────▶│ CLOSED │
└───┬────────┬───┘      └────────┘
    ▼        ▼               ▲
┌─────────┐ ┌───────────┐    │
│ COMPLIED│ │ ESCALATED │────┘
└────┬────┘ └─────┬─────┘
     └────────────┴──▶ CLOSED
```

Transitions are validated server-side against `CASE_TRANSITIONS`: a case cannot
reach COMPLIED without a notice having been issued, and CLOSED is terminal.
Advancing a case requires SENIOR_OFFICER or above — issuing a notice is an
enforcement decision, not a data-entry step. Every transition appends to
`case_history` with the officer, timestamp and note.

A compliant pack opens no case. It is still recorded and searchable; there is
simply nothing to enforce.

### Where the package was found

Every scan carries an `InspectionContext`: premises name, address, type, licence,
and optionally GPS coordinates from the device. A notice under the Act is served
on a person at a place, so a finding that records only "this pack was
non-compliant" cannot support one. When the premises is left blank the report
prints an explicit warning rather than quietly producing an incomplete notice.

---

## 8. Testing

**Backend** — `backend/tests/`, 93 tests, no network, no credentials, isolated
temp store.

- `test_rules.py` — golden cases per statutory provision, pinning verdicts so a
  rule edit cannot silently change an outcome.
- `test_api.py` — auth, role enforcement, inspector scoping, search filters,
  and that each export really is a PDF / DOCX / XLSX with the expected content.
- `test_hardening.py` — the defects and gaps found in the post-build audit:
  hostile search terms, rate limiting, password strength, upload ceilings,
  premises capture, and every case-lifecycle transition including the illegal ones.

One test (`-m slow`) exercises the real OCR engine end to end; the rest stub it,
because a suite that takes minutes stops being run.

**Frontend** — `frontend/src/**/*.test.{js,jsx}`, 29 tests under Vitest.

- `useSubmitGuard` — that a double-tap cannot fire two requests.
- `format` — that every rule id the engine emits has a readable label.
- `I18nContext` — that the Hindi locale is genuinely complete, placeholders
  survive translation, and a partial language falls back per key.

```bash
cd backend  && pytest -v          # or: pytest -m "not slow"
cd frontend && npm test
```
