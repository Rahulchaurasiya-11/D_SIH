"""
Seeds demonstration data: officer accounts and a spread of inspections.

Run this before a demo so the dashboard and repository have something to show:

    cd backend
    python scripts/seed_demo.py

It is idempotent for users (existing accounts are reused) and additive for
inspections. It talks to the repositories directly rather than over HTTP, so it
works with whichever store is configured.
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password  # noqa: E402
from app.db import repositories as repo  # noqa: E402
from app.db.store import get_store, new_id  # noqa: E402
from app.engine.compliance_engine import LegalMetrologyComplianceEngine  # noqa: E402
from app.models import Role  # noqa: E402

engine = LegalMetrologyComplianceEngine()

OFFICERS = [
    ("admin@legalmetrology.gov.in", "Demo@Admin2026!", "A. Krishnan", Role.ADMIN.value,
     "Controller of Legal Metrology", "National"),
    ("senior@legalmetrology.gov.in", "Demo@Senior2026!", "S. Banerjee", Role.SENIOR_OFFICER.value,
     "Senior Enforcement Officer", "Delhi"),
    ("inspector@legalmetrology.gov.in", "Demo@Inspect2026!", "R. Sharma", Role.INSPECTOR.value,
     "Legal Metrology Inspector", "Delhi North"),
]

# Each entry is a realistic label. The compliance verdict is NOT hardcoded - the
# rule engine decides it, so the demo data reflects the real engine's behaviour.
LABELS = [
    ("Sunrise Foods", "Premium Roasted Almonds 500 g", [
        "SUNRISE FOODS PREMIUM ROASTED ALMONDS",
        "Marketed by: Sunrise Foods Pvt Ltd, 14 Industrial Area, Ludhiana, Punjab - 141003",
        "Net Quantity: 500 g",
        "MRP Rs. 450.00 (Inclusive of all taxes)",
        "Mfg Date: 02/2026",
        "Customer Care: care@sunrisefoods.in",
        "Toll Free: 1800-111-2233",
        "Country of Origin: India",
        "Batch No: SF2026A114",
    ]),
    ("Himveda", "Cold Pressed Mustard Oil 1 L", [
        "HIMVEDA COLD PRESSED MUSTARD OIL",
        "Packed by: Himveda Naturals, Plot 22, Haridwar, Uttarakhand - 249401",
        "Net Volume: 1 L",
        "MRP Rs. 285.00 (Incl. of all taxes)",
        "Pkd: 01/2026",
        "consumercare@himveda.co.in",
        "Helpline: 1800-425-9090",
        "Country of Origin: India",
    ]),
    ("NutriGlow", "Whey Protein Isolate", [
        "NUTRIGLOW WHEY PROTEIN ISOLATE",
        "Imported by: NutriGlow Nutrition LLP, Andheri East, Mumbai - 400069",
        "Net Contents: 32 oz",
        "MRP Rs. 3,499.00",
        "Mfg: 12/2025",
        "support@nutriglow.com",
        "Country of Origin: USA",
    ]),
    ("Kanchan Masale", "Turmeric Powder 200 g", [
        "KANCHAN HALDI POWDER / हल्दी पाउडर",
        "Kanchan Masale, Nagpur, Maharashtra - 440008",
        "Net Qty: 200 g",
        "MRP Rs. 68.00",
        "Pkd: 03/2026",
        "info@kanchanmasale.in",
        "Country of Origin: India",
    ]),
    ("Blue Harbour", "Tuna Chunks in Brine", [
        "BLUE HARBOUR TUNA CHUNKS IN BRINE",
        "Blue Harbour Seafoods, Kochi, Kerala - 682005",
        "Net Weight: 185 g (Drained 130 g)",
        "MRP Rs. 210.00 (Inclusive of all taxes)",
        "care@blueharbour.in",
        "Customer Care: 0484-2345678",
        "Country of Origin: India",
    ]),
    ("Everfresh", "Instant Noodles Masala", [
        "EVERFRESH INSTANT NOODLES MASALA",
        "Everfresh Foods Ltd, Bhiwandi, Maharashtra - 421302",
        "Net Quantity: 70 g",
        "MRP Rs. 15.00 (Inclusive of all taxes)",
        "Mfg Date: 04/2026",
        "Country of Origin: India",
    ]),
    ("Aroma Gold", "Basmati Rice 5 kg", [
        "AROMA GOLD BASMATI RICE",
        "Aroma Gold Exports, Karnal, Haryana - 132001",
        "Net Quantity: 5 kg",
        "MRP Rs. 720.00 (Inclusive of all taxes)",
        "Pkd: 02/2026",
        "grievance@aromagold.in",
        "Toll Free: 1800-200-4545",
        "Country of Origin: India",
    ]),
    ("PureSip", "Packaged Drinking Water", [
        "PURESIP PACKAGED DRINKING WATER",
        "PureSip Beverages, Sonipat, Haryana - 131001",
        "Net Vol: 1 litre",
        "MRP Rs. 20.00 (Inclusive of all taxes)",
        "Pkd: 05/2026",
        "care@puresip.in",
        "Helpline: 1800-121-3131",
        "Country of Origin: India",
    ]),
]


PREMISES = [
    ("Sharma General Store", "12 Nehru Market, Karol Bagh, New Delhi - 110005", "RETAIL",
     "DL-LM-2026-4417", 28.6519, 77.1909),
    ("BigValue Supermart", "Sector 18 Market, Noida, Uttar Pradesh - 201301", "SUPERMARKET",
     "UP-LM-2025-8823", 28.5708, 77.3260),
    ("Gupta Wholesale Traders", "Naya Bazaar, Chandni Chowk, New Delhi - 110006", "WHOLESALE",
     "DL-LM-2024-1190", 28.6562, 77.2301),
    ("Metro Cash Depot", "Plot 7, Okhla Industrial Area Phase II, New Delhi - 110020", "WAREHOUSE",
     "DL-LM-2026-7731", 28.5355, 77.2730),
    ("Krishna Kirana Store", "Main Road, Ghaziabad, Uttar Pradesh - 201001", "RETAIL",
     "", 28.6692, 77.4538),
]


def as_segments(lines):
    segments = []
    for i, text in enumerate(lines):
        top = 20 + i * 42
        segments.append({
            "text": text,
            "box": [[24, top], [560, top], [560, top + 30], [24, top + 30]],
            "confidence": round(random.uniform(0.86, 0.99), 3),
        })
    return segments


def ensure_officers():
    created = []
    for email, password, name, role, designation, jurisdiction in OFFICERS:
        existing = repo.users.by_email(email)
        if existing:
            created.append(existing)
            continue
        created.append(repo.users.create(
            email=email, password_hash=hash_password(password), full_name=name,
            role=role, designation=designation, jurisdiction=jurisdiction,
        ))
        print("  created officer: %-40s %s" % (email, role))
    return created


def seed_inspections(officers, per_label=3):
    store = get_store()
    total = 0
    scanners = [o for o in officers if o["role"] != Role.ADMIN.value] or officers

    for brand, product, lines in LABELS:
        for n in range(per_label):
            officer = random.choice(scanners)
            segments = as_segments(lines)
            report = engine.evaluate_compliance(segments=segments, image_dimensions=(600, 600))

            payload = {
                "success": True,
                "filename": product,
                "status": report["status"],
                "overall_score": report["overall_score"],
                "is_manually_verified": False,
                "manual_fields_applied": [],
                "multilingual_profile": report.get("multilingual_profile", {}),
                "violations": report["violations"],
                "passed_checks": report["passed_checks"],
                "warnings": report["warnings"],
                "extracted_metadata": report["extracted_metadata"],
                "rules_breakdown": report["rules_breakdown"],
                "raw_text_dump": lines,
                "raw_segments": segments,
                "source": "image",
            }

            name, address, ptype, licence, lat, lon = random.choice(PREMISES)
            context = {
                "premises_name": name, "premises_address": address,
                "premises_type": ptype, "premises_licence": licence,
                "latitude": round(lat + random.uniform(-0.004, 0.004), 6),
                "longitude": round(lon + random.uniform(-0.004, 0.004), 6),
                "location_accuracy_m": round(random.uniform(5, 25), 1),
            }

            doc = repo.inspections.create(payload, officer, [], source="image", context=context)

            # Spread the records across the last 30 days so the trend chart has shape.
            backdated = datetime.now(timezone.utc) - timedelta(
                days=random.randint(0, 29), hours=random.randint(0, 23)
            )
            store.update_one("inspections", {"id": doc["id"]},
                             {"created_at": backdated.isoformat(),
                              "brand": brand, "product_name": product})

            # Walk some cases forward, so the dashboard shows enforcement activity
            # rather than a column of untouched OPEN findings.
            if doc.get("case_status") == "OPEN" and random.random() < 0.65:
                senior = next(
                    (o for o in officers if o["role"] != Role.INSPECTOR.value), officer
                )
                repo.inspections.update_case(
                    doc["id"], "NOTICE_ISSUED", senior,
                    "Notice served on the packer.", "LM/NOT/2026/%03d" % random.randint(1, 400),
                )
                roll = random.random()
                if roll < 0.45:
                    repo.inspections.update_case(doc["id"], "COMPLIED", senior,
                                                 "Re-inspected; declarations corrected.")
                elif roll < 0.6:
                    repo.inspections.update_case(doc["id"], "ESCALATED", senior,
                                                 "Referred for compounding.")
            total += 1
    return total


def main():
    print("Seeding demonstration data...")
    officers = ensure_officers()
    count = seed_inspections(officers)

    print("\nSeeded %d inspections across %d products." % (count, len(LABELS)))
    print("\nSign in with any of:")
    for email, password, _, role, _, _ in OFFICERS:
        print("  %-40s %-18s  (%s)" % (email, password, role))
    print("\nThese are demonstration credentials. Never deploy them to a public URL.")


if __name__ == "__main__":
    main()
