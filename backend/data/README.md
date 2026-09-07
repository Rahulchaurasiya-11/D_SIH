# Legal Metrology Compliance Data Store & Knowledge Base

This directory contains the master statutory datasets, regulatory rules, approved metric units, prohibited units, and live audit buffers for the Legal Metrology Compliance Auditing System.

---

## 📁 Directory Structure & Datasets

| File | Type | Description | How to Modify / Add Data |
| :--- | :--- | :--- | :--- |
| **`legal_metrology_rules.csv`** | **Master Rule Database (CSV 1)** | Master statutory provisions under Legal Metrology (Packaged Commodities) Rules, 2011 (e.g., Rule 6(1)(da), Rule 11/12, Rule 6(1)(g), Rule 6(1)(c), Rule 9, Rule 6(10), Rule 6(1)(a)). | Open in Excel/VS Code. Add/edit rows with `rule_id`, `rule_name`, `penalty_min_inr`, `penalty_max_inr`, `severity`, `description`. |
| **`approved_metric_units.csv`** | **Approved SI Units** | Standard SI metric units (g, kg, ml, l, cm, m) and count indicators (units, pcs, pens, tablets, pages) in English and 10 Indian regional scripts (Hindi, Marathi, Telugu, Bengali, Punjabi, Urdu, Tamil, Gujarati, Kannada, Malayalam). | Add new approved commodity units or regional spellings to the list. |
| **`prohibited_imperial_units.csv`** | **Prohibited Units** | Banned non-metric imperial units (fl oz, oz, lbs, gallon, quart, yard, inch) and their statutory penalty clauses under Section 36 of Legal Metrology Act, 2009. | Add any non-standard measurement terms that must be flagged. |
| **`tax_suffix_clauses.csv`** | **Tax Suffix Patterns** | Exact and fuzzy regex clauses for "Inclusive of all taxes" across Indian languages. | Add regional variations or brand-specific patterns. |
| **`consumer_care_keywords.csv`** | **Consumer Care Keywords** | Helplines, care emails, toll-free phrases in multiple languages. | Add regional terms for consumer grievance. |
| **`mfg_date_keywords.csv`** | **Mfg / Expiry Keywords** | Terms indicating manufacturing, packaging, and expiry timeline declarations. | Add new terms for date packaging markers. |
| **`recent_audits_live.csv`** | **Dynamic Live Audit Log (CSV 2)** | Temporary rolling FIFO buffer (auto-capped at 50 records) storing real-time OCR extractions and compliance scores. | Automatically managed by backend. Cleared/reset via API or file reload. |

---

## 🔄 Dynamic Hot-Reloading via REST API

Whenever any CSV file in this directory is edited or modified, you do **not** need to restart the server. Simply trigger:

```http
POST /api/v1/rules/reload
```

Response:
```json
{
  "success": true,
  "message": "Statutory rules and metric datasets hot-reloaded successfully from CSV.",
  "loaded_rules_count": 7,
  "approved_units_count": 138,
  "prohibited_units_count": 24
}
```

---

## 🍃 MongoDB Integration (Optional)

If a MongoDB connection is desired for multi-server synchronization, configure the environment variable:

```bash
export MONGODB_URI="mongodb+srv://<user>:<password>@cluster.mongodb.net/legal_metrology_db"
```

The `DatabaseManager` will automatically sync the master statutory rules and stream live audit events directly to MongoDB collections (`master_rules` and `live_audit_logs`) while maintaining local CSV backups!
