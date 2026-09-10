# API reference

Base URL `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

All routes require `Authorization: Bearer <access_token>` except `/health` and
`/auth/register` · `/auth/login` · `/auth/refresh`.

**Roles rank:** `INSPECTOR` < `SENIOR_OFFICER` < `ADMIN`. A higher rank satisfies
every requirement below it.

---

## Authentication

| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| POST | `/auth/register` | — | Create an account. Always `INSPECTOR`, except the first account on an empty system, which becomes `ADMIN`. A `role` in the payload is ignored. |
| POST | `/auth/login` | — | Exchange credentials for tokens. |
| POST | `/auth/refresh` | — | New access token from a refresh token. |
| GET | `/auth/me` | Inspector | Current officer. |
| GET | `/auth/users` | Admin | List officers. |
| PATCH | `/auth/users/{id}/role?role=` | Admin | Change a role. Cannot target yourself. |
| PATCH | `/auth/users/{id}/active?active=` | Admin | Activate / deactivate. Cannot target yourself. |

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"inspector@legalmetrology.gov.in","password":"..."}'
```

```json
{
  "access_token": "eyJ…",
  "refresh_token": "eyJ…",
  "token_type": "bearer",
  "expires_in_minutes": 30,
  "user": { "id": "usr_…", "full_name": "R. Sharma", "role": "INSPECTOR", … }
}
```

---

## Scanning

### `POST /analyze-package` — package photographs

Multipart. `images` (1–4 files, 12 MB each), optional `ocr_lang`, `ai_engine`
(`rapidocr` | `vlm`), `persist` (default true), and `context`.

`context` is an `InspectionContext` as a JSON string — where the package was found:

```json
{
  "premises_name": "Sharma General Store",
  "premises_address": "12 Nehru Market, Karol Bagh, New Delhi - 110005",
  "premises_type": "RETAIL",
  "premises_licence": "DL-LM-2026-4417",
  "latitude": 28.6519, "longitude": 77.1909, "location_accuracy_m": 8,
  "remarks": "Pack taken from the front shelf."
}
```

A notice under the Act is served on a person at a place, so a finding with no
premises cannot support one. Malformed context is rejected with 422 rather than
dropped, so the officer is told the details did not save. A non-compliant scan
also allocates a case number and opens an enforcement case.

```bash
curl -X POST "http://localhost:8000/api/v1/analyze-package" \
  -H "Authorization: Bearer $TOKEN" \
  -F "images=@front.jpg" -F "images=@back.jpg"
```

```json
{
  "success": true,
  "inspection_id": "insp_1e8d7cf2952e4071",
  "status": "NON_COMPLIANT",
  "overall_score": 35,
  "ocr_engine": "rapidocr_onnx",
  "processing_time_ms": 11634.48,
  "extracted_metadata": {
    "mrp": "3499.00", "taxes_included": false,
    "net_quantity": null, "unit_of_measure": null,
    "manufacturing_date": "12/2025",
    "consumer_care_email": "support@nutriglow.com",
    "consumer_care_phone": null,
    "country_of_origin": "Usa", "manufacturer_name": "…"
  },
  "violations": [
    {
      "rule_id": "RULE_11_12_PROHIBITED_UNIT",
      "rule_name": "Rule 11 & 12 - Prohibited Imperial Units Detected",
      "severity": "HIGH",
      "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11",
      "description": "Found non-standard imperial measurement '32 oz'…",
      "found_text": "Net Contents: 32 oz",
      "remediation": "Declare net quantity in approved SI metric units…"
    }
  ],
  "passed_checks": [ … ],
  "warnings": [ … ],
  "evidence": [ { "evidence_id": "evd_…", "angle": "Front", "width": 900, "height": 1200 } ],
  "raw_segments": [ { "text": "…", "box": [[x,y],…], "confidence": 0.97 } ],
  "raw_text_dump": [ "…" ]
}
```

`raw_segments` carries boxes in the original image's pixel space — the client
draws them over the photograph so a finding can be checked against the pack.

### `POST /analyze-text` — text extracted elsewhere

For the browser-OCR fallback and for typing a label by hand.

```json
{ "raw_text": "MRP Rs. 450 (Inclusive of all taxes)\nNet Quantity: 500 g",
  "filename": "Typed label", "source": "manual", "persist": true }
```

Optionally send pre-extracted `segments` with real boxes so font analysis has
genuine geometry.

### `POST /analyze-listing` — e-commerce listing

```json
{ "listing_text": "…", "listing_html": "<div>…</div>",
  "source_url": "https://…", "platform": "…", "product_title": "…" }
```

`source_url` is recorded as provenance only. **The server never fetches it** —
fetching arbitrary user-supplied URLs would be a server-side request forgery hole,
and marketplace pages are JavaScript-rendered anyway.

### `POST /verify-and-audit` — officer correction

```json
{ "inspection_id": "insp_…",
  "manual_overrides": { "mrp": "450.00", "taxes_included": true,
                        "net_quantity": "500", "unit_of_measure": "g" } }
```

Re-runs the same rule engine with the officer's values and marks the inspection
officer-verified.

---

## Repository

| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| GET | `/inspections` | Inspector | Paginated search |
| GET | `/inspections/{id}` | Inspector | Full report + audit trail |
| GET | `/evidence/{id}` | Inspector | Stored photograph (JPEG) |
| GET | `/dashboard/stats?days=` | Inspector | Aggregates |

**Search parameters:** `q`, `status`, `rule`, `officer_id`, `date_from`, `date_to`,
`min_score`, `max_score`, `source`, `case_status`, `premises`, `page`, `page_size`.

`q` is treated as literal text, not a pattern — it is escaped before it reaches the
store, so a search for `a+b` finds "a+b" rather than matching "aaab", and a stray
`[` cannot fail the query.

```bash
curl "http://localhost:8000/api/v1/inspections?status=NON_COMPLIANT&rule=RULE_11_12_PROHIBITED_UNIT&date_from=2026-08-01" \
  -H "Authorization: Bearer $TOKEN"
```

An `INSPECTOR` is pinned to their own records: supplying another officer's
`officer_id` does not widen the result set, and fetching a colleague's inspection
by id returns 403.

`date_to` accepts a bare date and is treated as inclusive to end-of-day.

---

## Enforcement cases

### `PATCH /inspections/{id}/case` — advance a case

Senior officer and above. Issuing a notice or closing a case is an enforcement
decision, not a data-entry step.

```json
{ "case_status": "NOTICE_ISSUED",
  "note": "Notice served on the packer.",
  "notice_reference": "LM/NOT/2026/88" }
```

Permitted transitions:

| From | To |
| :--- | :--- |
| `OPEN` | `NOTICE_ISSUED`, `CLOSED` |
| `NOTICE_ISSUED` | `COMPLIED`, `ESCALATED`, `CLOSED` |
| `COMPLIED` | `CLOSED` |
| `ESCALATED` | `CLOSED` |
| `CLOSED` | — terminal |

Anything else returns **409**, as does acting on an inspection that found no
contravention (it has no case). Each transition appends to `case_history` with the
officer, timestamp and note.

### `GET /repeat-offenders?days=&minimum=`

Senior officer and above. Brands contravening across separate inspections — one bad
pack may be a printing error, the same brand failing in several premises is a
pattern. Returns inspections and violation counts, distinct premises, open cases,
and the rules most often broken.

---

## Reports

| Method | Path | Role | Returns |
| :--- | :--- | :--- | :--- |
| GET | `/reports/{id}?format=pdf` | Inspector | `application/pdf` — real selectable text |
| GET | `/reports/{id}?format=docx` | Inspector | Editable Word notice |
| GET | `/reports?<search params>` | Senior officer | XLSX: Inspections · Violations · Summary |

```bash
curl "http://localhost:8000/api/v1/reports/insp_…?format=docx" \
  -H "Authorization: Bearer $TOKEN" -o notice.docx
```

---

## Statutory rules

| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| GET | `/rules/database` | Inspector | Full rule set, approved and prohibited units |
| POST | `/rules/reload` | Admin | Hot-reload the CSV knowledge base |
| GET | `/rules/audit-log?limit=` | Senior officer | System audit trail |

---

## System

`GET /health` — unauthenticated.

```json
{ "status": "online", "version": "3.0.0", "document_store": "json",
  "ocr_engine": "rapidocr_onnx", "rules_loaded": 7, "registered_users": 3 }
```

---

## Errors

FastAPI shape throughout: `{"detail": "…"}`.

| Code | Meaning |
| :--- | :--- |
| 400 | Malformed input — no image, empty text, undecodable file |
| 401 | Missing, invalid or expired token; wrong credentials |
| 403 | Authenticated but insufficient role, or another officer's record |
| 404 | No such inspection, evidence or user |
| 409 | E-mail already registered |
| 409 | Illegal case transition, or a case action on a compliant inspection |
| 413 | Upload exceeds the per-image ceiling |
| 422 | Validation failure (e.g. `format=exe`, malformed `context`) |
| 429 | Rate limited — the response carries `Retry-After` |
| 500 | Unexpected — check server logs |

Unknown e-mail and wrong password both return the same 401 message, so the endpoint
cannot be used to enumerate officer accounts.
