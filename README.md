# ⚖️ Legal Metrology Compliance Auditing System
### Automated AI Statutory Auditing Engine under the Legal Metrology (Packaged Commodities) Rules, 2011

Built for **Smart India Hackathon (SIH 2026)** to automate legal enforcement, detect packaging infringements, protect consumer rights, and streamline inspection procedures for Legal Metrology officers.

---

## 📌 Problem Statement Overview
Under the **Legal Metrology Act, 2009** and **Legal Metrology (Packaged Commodities) Rules, 2011 (as amended 2021/2022)**, every pre-packaged commodity sold in India must strictly bear mandatory statutory declarations. Violations attract compounding penalties and legal prosecution under **Section 36(1)** of the Act.

Manual inspection of millions of retail and e-commerce SKUs is infeasible. This platform provides an **end-to-end automated compliance auditor** that ingests package images or scans, runs high-precision OCR extraction, and rigorously verifies 5 statutory legal pipelines.

---

## 🚀 Key Statutory Pipelines Implemented

| Rule | Legal Requirement | Automated Verification Mechanism | Infringement Classification |
| :--- | :--- | :--- | :--- |
| **Rule 6(1)(da)** | **Maximum Retail Price (MRP)** | Validates presence of exact price (`₹`/`Rs.`) **AND** mandatory statutory suffix `"Inclusive of all taxes"` / `"Incl. of all taxes"`. | `HIGH SEVERITY`: Missing Tax Suffix / Missing MRP |
| **Rule 11 & 12** | **Net Quantity Standards** | Enforces approved SI metric units (`g`, `kg`, `ml`, `l`, `units`, `pcs`, `N`). Detects and instantly flags prohibited imperial units (`oz`, `fl oz`, `lbs`, `pt`, `gal`). | `HIGH SEVERITY`: Prohibited Non-Metric Imperial Units |
| **Rule 6(1)(g)** | **Consumer Grievance Redressal** | Verifies presence of Consumer Care keywords and enforces **concurrent** presence of both valid **Email (`@` domain)** and **Telephone Helpline / Toll-Free Number**. | `HIGH / MEDIUM`: Incomplete Redressal Mechanism |
| **Rule 6(1)(c)** | **Manufacturing / Packaging Timeline** | Parses month/year metadata (`MM/YY`, `MM/YYYY`, `Month-Year`, `Pkd`, `Mfg Date`) and validates timeline legitimacy (anti-predating check). | `HIGH`: Missing Date of Packaging |
| **Rule 9 & Sched II** | **Font Size & Aspect Estimation** | Estimates character bounding box height relative to the Principal Display Panel (PDP) to ensure declarations meet statutory minimum height rules. | `LOW / ADVISORY`: Micro-font / Ill-proportioned layout |

---

## 🏗️ System Architecture

```
SIH26/
├── backend/
│   ├── compliance_engine.py   # Core LegalMetrologyComplianceEngine class with 5 rule pipelines
│   ├── main.py                # FastAPI REST API with PaddleOCR pipeline & sample presets
│   ├── test_engine.py         # Automated verification test suite
│   └── requirements.txt       # Production pip dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # High-fidelity Compliance Auditor Dashboard
│   │   ├── index.css          # Cyber-legal dark theme & glassmorphism styles
│   │   └── main.jsx           # React DOM root mount
│   ├── index.html             # HTML entrypoint with Inter font
│   ├── package.json           # Frontend package definitions
│   ├── tailwind.config.js     # Custom Tailwind color palette & animations
│   └── vite.config.js         # Vite configuration
│
├── run_system.bat             # 1-Click launcher for Windows
└── README.md                  # System Documentation & SIH Guide
```

---

## ⚡ Quick Start & Execution

### 1. Launch Everything with 1-Click (Windows)
Double-click `run_system.bat` or run:
```bat
.\run_system.bat
```

### 2. Manual Launch

#### Backend:
```bash
cd backend
python -m pip install -r requirements.txt
python test_engine.py
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)

---

## 🎯 SIH Jury Presentation & Demo Workflow

1. Open **[http://localhost:5173](http://localhost:5173)**.
2. Under **"SIH Fast-Demo Test Scenarios"** on the left panel:
   - **Click Test Case 1 (`✅ 100% Fully Compliant Indian FMCG`)**: Observe the glowing green `🟢 PACKAGE COMPLIANT` badge, 100/100 score, and all passed clearances.
   - **Click Test Case 2 (`❌ Severe Infringement: Prohibited Imperial Units`)**: Notice how the system flags `Rule 11 & 12` violation for `fl oz / oz` with Section 36 penalty citation.
   - **Click Test Case 3 (`❌ Statutory Breach: Missing Tax Suffix on MRP`)**: Shows instant detection of `Rule 6(1)(da)` for missing `"Inclusive of all taxes"`.
   - **Click Test Case 4 (`❌ Statutory Breach: Missing Customer Care Helpline`)**: Shows missing telephonic helpline detection under `Rule 6(1)(g)`.
3. In the **"Legal Notice"** tab, click **"Print Official Metrology Audit Notice"** to showcase the instant official government notice generation ready for enforcement officers.
4. Upload any custom real-world package photo using the drag-and-drop zone.

---

## 🛡️ Statutory Legal References
- *The Legal Metrology Act, 2009 (No. 1 of 2010)*
- *Legal Metrology (Packaged Commodities) Rules, 2011 (G.S.R. 202(E))*
- *Legal Metrology (Packaged Commodities) Amendment Rules, 2021 & 2022*
- *Department of Consumer Affairs, Ministry of Consumer Affairs, Food & Public Distribution, Government of India*
