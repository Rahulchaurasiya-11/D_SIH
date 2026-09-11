"""
Seeds demonstration data into a RUNNING deployment, over HTTP.

Render's free tier has an ephemeral disk: when the instance sleeps or redeploys,
anything in the local JSON store is gone. Configure MONGODB_URI to keep data for
real; until then, this restores a demo in about a minute.

    python scripts/seed_remote.py \\
        --api https://legal-metrology-api-ft2v.onrender.com \\
        --email admin@legalmetrology.gov.in \\
        --password '...'

Unlike `seed_demo.py`, this talks to the public API rather than the repositories,
so it works against any deployment without shell access. Verdicts still come from
the server's rule engine — nothing here decides compliance.
"""

import argparse
import json
import random
import sys
import urllib.error
import urllib.request

# Reuse the same labels and premises as the local seeder so both demos match.
sys.path.insert(0, __file__.rsplit("scripts", 1)[0])
from scripts.seed_demo import LABELS, PREMISES  # noqa: E402


def call(api, path, token=None, payload=None, method=None, timeout=90):
    url = api.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or "{}")
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        raise SystemExit("  %s %s -> HTTP %s\n  %s" % (method or "POST", path, err.code, body))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True, help="Base URL of the deployed API")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--per-label", type=int, default=2)
    args = parser.parse_args()

    print("Waking the service (a free instance can take ~50s from cold)...")
    health = call(args.api, "/api/v1/health", timeout=180)
    print("  %s  store=%s  ocr=%s  rules=%s"
          % (health["status"], health["document_store"], health["ocr_engine"], health["rules_loaded"]))

    print("Signing in...")
    session = call(args.api, "/api/v1/auth/login",
                   payload={"email": args.email, "password": args.password})
    token = session["access_token"]
    print("  signed in as %s (%s)" % (session["user"]["full_name"], session["user"]["role"]))

    created, cases = 0, 0
    for brand, product, lines in LABELS:
        for _ in range(args.per_label):
            name, address, ptype, licence, lat, lon = random.choice(PREMISES)
            result = call(args.api, "/api/v1/analyze-text", token=token, payload={
                "raw_text": "\n".join(lines),
                "filename": product,
                "source": "manual",
                "context": {
                    "premises_name": name,
                    "premises_address": address,
                    "premises_type": ptype,
                    "premises_licence": licence,
                    "latitude": round(lat + random.uniform(-0.004, 0.004), 6),
                    "longitude": round(lon + random.uniform(-0.004, 0.004), 6),
                    "location_accuracy_m": round(random.uniform(5, 25), 1),
                },
            })
            created += 1

            if result.get("case_number"):
                cases += 1
                # Walk some cases forward so the dashboard shows activity, not just
                # a column of untouched findings.
                roll = random.random()
                if roll < 0.7:
                    call(args.api, "/api/v1/inspections/%s/case" % result["inspection_id"],
                         token=token, method="PATCH",
                         payload={"case_status": "NOTICE_ISSUED",
                                  "note": "Notice served on the packer.",
                                  "notice_reference": "LM/NOT/2026/%03d" % random.randint(1, 400)})
                    if roll < 0.35:
                        call(args.api, "/api/v1/inspections/%s/case" % result["inspection_id"],
                             token=token, method="PATCH",
                             payload={"case_status": "COMPLIED",
                                      "note": "Re-inspected; declarations corrected."})

            print("  %-32s %-14s %3d/100  %s"
                  % (product[:32], result["status"], result["overall_score"],
                     result.get("case_number") or "-"))

    stats = call(args.api, "/api/v1/dashboard/stats?days=30", token=token)
    print("\nSeeded %d inspections, %d enforcement cases." % (created, cases))
    print("  compliance rate %.1f%%  |  open cases %d  |  average score %.1f"
          % (stats["compliance_rate"], stats["open_cases"], stats["average_score"]))
    print("\nThis is demonstration data. Re-run after any Render restart, or set "
          "MONGODB_URI so it persists.")


if __name__ == "__main__":
    main()
