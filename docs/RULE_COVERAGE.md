# Rule coverage

Mapping of each mandatory declaration under the Legal Metrology (Packaged
Commodities) Rules, 2011 to what the system checks and which test pins it.

---

## 1. Mandatory declarations — Rule 6(1)

| Provision | Declaration | Status | Rule ids emitted | Test |
| :--- | :--- | :--- | :--- | :--- |
| 6(1)(a) | Name & address of manufacturer / packer / importer | ✅ | `RULE_6_1_A_MFG_NAME` | `test_fully_compliant_label_passes` |
| 6(1)(b) | Common or generic name of commodity | ◐ Extracted, reported; not independently enforced | — | — |
| 6(1)(c) | Month & year of manufacture / packing / import | ✅ | `RULE_6_1_C_MISSING_DATE`, `RULE_6_1_C_UNREADABLE_DATE` | `test_missing_manufacture_date_flagged` |
| 6(1)(d) | Expiry / best-before where applicable | ◐ Keywords parsed; commodity-specific applicability not modelled | — | — |
| 6(1)(da) | Retail sale price as MRP **inclusive of all taxes** | ✅ | `RULE_6_1_DA_MISSING`, `RULE_6_1_DA_TAX_SUFFIX_MISSING` | `test_missing_tax_suffix_flagged`, `test_missing_mrp_entirely_flagged` |
| 6(1)(e) | Net quantity | ✅ (see Rule 11) | `RULE_11_12_*` | `test_prohibited_imperial_units_flagged` |
| 6(1)(f) | Batch / lot / code number | ◐ Extracted and reported; absence not flagged | — | — |
| 6(1)(g) | Consumer care — name, address, **telephone and e-mail** | ✅ | `RULE_6_1_G_MISSING_ALL`, `RULE_6_1_G_EMAIL_MISSING`, `RULE_6_1_G_HELPLINE_MISSING` | `test_missing_consumer_helpline_flagged` |
| 6(10) | Country of origin | ✅ | `RULE_6_10_ORIGIN`, `RULE_6_10_ORIGIN_ADVISORY` | covered by golden case |

**Legend** ✅ enforced · ◐ extracted and shown, not enforced · ❌ not covered

---

## 2. Net quantity — Rules 11 & 12

| Requirement | Status | Notes |
| :--- | :--- | :--- |
| Declared in approved SI units | ✅ | 138 approved units incl. regional scripts |
| Count commodities (`N`, `U`, pcs) | ✅ | |
| Imperial units prohibited | ✅ | `oz`, `fl oz`, `lb`, `gallon`, `quart`, `yard`, `inch` — 24 forms |
| Drained weight for packed-in-liquid | ❌ | Not modelled |
| Standard package sizes (Sch. II Part A) | ❌ | Not modelled |

`test_each_prohibited_unit_is_detected` parametrises `fl oz`, `oz`, `lbs`, `gallon`.

---

## 3. Font size & legibility — Rule 9, Schedule II

| Requirement | Status |
| :--- | :--- |
| Declarations legible and conspicuous | ◐ Advisory |
| Minimum character height by net quantity band | ⚠️ **Advisory estimate only** |
| Principal Display Panel placement | ◐ Partial — panel-relative geometry |

### Why this is advisory, not measured

Schedule II prescribes heights in **millimetres**. A photograph carries no physical
scale: without a reference object of known size in frame, or the pack's real
dimensions, millimetres cannot be derived from pixels. Any millimetre figure
produced from an unreferenced photo is invented.

The system reports character height relative to the display panel and labels the
finding as an estimate requiring physical verification. It is a screening signal —
it tells an officer which packs to measure. The report's declaration section says
so explicitly.

**To make this definitive**, either place a fiducial marker of known size in frame,
or have the officer enter the pack dimensions; the Schedule II band lookup is then
a straightforward addition.

---

## 4. Not covered

Declared plainly rather than implied:

| Area | Provision |
| :--- | :--- |
| Standard pack sizes | Rule 5 / Sch. II Part A |
| Combination & multi-piece packages | Rule 17 |
| Wholesale package declarations | Rule 24 |
| Export package exemptions | Rule 26 |
| Commodity-specific rules (cement, fertiliser, …) | Various |
| Dual/regional-language declaration mandate | Rule 6(1) proviso — script *detected*, not enforced |
| Bar code / QR verification | — |
| Price-per-unit for variable-weight packs | Rule 6(1)(e) proviso |

---

## 5. Severity and penalty bands

From `backend/app/data/legal_metrology_rules.csv`, editable without code:

| Rule id | Severity | Penalty band (INR) |
| :--- | :--- | :--- |
| `RULE_6_1_DA_MRP` | CRITICAL | 25,000 – 100,000 |
| `RULE_11_12_NET_QTY` | CRITICAL | 25,000 – 100,000 |
| `RULE_6_1_G_CONSUMER_CARE` | HIGH | 25,000 – 50,000 |
| `RULE_6_1_C_MFG_DATE` | HIGH | 25,000 – 50,000 |
| `RULE_6_1_A_MFG_NAME` | HIGH | 25,000 – 50,000 |
| `RULE_9_FONT_SIZE` | MEDIUM | 10,000 – 25,000 |
| `RULE_6_10_ORIGIN` | MEDIUM | 10,000 – 50,000 |

Bands are indicative and reflect compounding ranges under the Legal Metrology Act,
2009. The adjudicating officer determines the actual penalty; the report presents
the band as context, never as a determination.

---

## 6. Two corrections made during the rebuild

Both were live defects that let a non-compliant package pass.

**Rule 6(1)(c) — substring keyword match.** Date-marker keywords were matched as
bare substrings, so `"lot"` matched inside `"Plot 14"` of a postal address and a
pack with no date at all was reported compliant. Now word-boundary matched.
Separately, a date keyword with no parseable month/year used to pass; it now raises
a MEDIUM contravention requiring physical verification, because Rule 6(1)(c)
requires the actual month and year.

**Rule 6(1)(g) — single channel treated as compliant.** A pack with only an e-mail,
or only a telephone number, passed with a LOW advisory. The rule as amended
requires name, address, telephone number **and** e-mail; a missing channel is now a
MEDIUM contravention. This also aligns the code with what the project's own README
already claimed it did.

---

## 7. Running the checks

```bash
cd backend
pytest tests/test_rules.py -v      # rule golden cases
pytest -v                          # everything, 51 tests
```

Each golden case names the provision it exercises, so a future rule edit that
changes a verdict fails loudly rather than silently.
