"""
Database & CSV Storage Manager for Legal Metrology Auditing System
Provides dual-dataset support:
1. Master Statutory Knowledge Base (CSV 1 / MongoDB): Rules, Approved Units, Prohibited Imperial Units, Tax Clauses.
2. Temporary Live Extracted Product Audits (CSV 2): Dynamic FIFO rolling buffer (capped at max N records)
   to ensure system storage never overflows on continuous scanning.
"""

import csv
import io
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("legal_metrology_db")

# Base directory for datasets
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RULES_CSV_PATH = os.path.join(DATA_DIR, "legal_metrology_rules.csv")
APPROVED_UNITS_CSV_PATH = os.path.join(DATA_DIR, "approved_metric_units.csv")
PROHIBITED_UNITS_CSV_PATH = os.path.join(DATA_DIR, "prohibited_imperial_units.csv")
TAX_SUFFIX_CSV_PATH = os.path.join(DATA_DIR, "tax_suffix_clauses.csv")
CONSUMER_CARE_CSV_PATH = os.path.join(DATA_DIR, "consumer_care_keywords.csv")
MFG_KEYWORDS_CSV_PATH = os.path.join(DATA_DIR, "mfg_date_keywords.csv")
LIVE_AUDITS_CSV_PATH = os.path.join(DATA_DIR, "recent_audits_live.csv")

# Maximum records to keep in temporary live audits CSV (FIFO buffer)
MAX_LIVE_AUDIT_RECORDS = 50


class DatabaseManager:
    """
    Central Database and CSV Data Store Manager.
    Manages persistent master rules from CSV/MongoDB and temporary rolling audit logs.
    """

    def __init__(self, data_dir: str = DATA_DIR, max_live_records: int = MAX_LIVE_AUDIT_RECORDS):
        self.data_dir = data_dir
        self.max_live_records = max_live_records
        self._lock = threading.RLock()
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # In-Memory Cached Master Datasets
        self.master_rules: List[Dict[str, Any]] = []
        self.approved_units_set: Set[str] = set()
        self.approved_units_list: List[Dict[str, str]] = []
        self.prohibited_units_dict: Dict[str, str] = {}
        self.tax_suffix_patterns: List[str] = []
        self.consumer_care_keywords: List[str] = []
        self.mfg_keywords: List[str] = []

        # Optional MongoDB Client
        self.mongo_client = None
        self.mongo_db = None
        self._init_mongodb()

        # Initialize and load master datasets
        self.reload_master_datasets()
        self._ensure_live_audit_csv_initialized()

    def _init_mongodb(self):
        """Initializes MongoDB connection if MONGODB_URI environment variable is provided."""
        mongo_uri = os.environ.get("MONGODB_URI")
        if mongo_uri:
            try:
                import pymongo
                self.mongo_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
                self.mongo_db = self.mongo_client.get_database("legal_metrology_db")
                logger.info("MongoDB connection initialized successfully.")
            except Exception as e:
                logger.warning(f"MongoDB connection notice: {e}. Falling back to CSV data store.")
                self.mongo_client = None
                self.mongo_db = None

    def reload_master_datasets(self) -> Dict[str, Any]:
        """
        Loads and parses all statutory rules, approved units, and keyword lists from CSV files.
        Thread-safe and can be called on-demand (Hot Reload).
        """
        with self._lock:
            # 1. Master Statutory Rules
            self.master_rules = self._load_rules_csv(RULES_CSV_PATH)

            # 2. Approved Metric Units
            self.approved_units_set, self.approved_units_list = self._load_approved_units_csv(APPROVED_UNITS_CSV_PATH)

            # 3. Prohibited Imperial Units
            self.prohibited_units_dict = self._load_prohibited_units_csv(PROHIBITED_UNITS_CSV_PATH)

            # 4. Tax Suffix Clauses
            self.tax_suffix_patterns = self._load_single_column_csv(TAX_SUFFIX_CSV_PATH, "phrase_regex")

            # 5. Consumer Care Keywords
            self.consumer_care_keywords = self._load_single_column_csv(CONSUMER_CARE_CSV_PATH, "keyword")

            # 6. Manufacturing Timeline Keywords
            self.mfg_keywords = self._load_single_column_csv(MFG_KEYWORDS_CSV_PATH, "keyword")

            # Sync to MongoDB if connected
            if self.mongo_db is not None:
                try:
                    rules_col = self.mongo_db["master_rules"]
                    rules_col.delete_many({})
                    if self.master_rules:
                        rules_col.insert_many(self.master_rules)
                    logger.info(f"Synced {len(self.master_rules)} master rules to MongoDB.")
                except Exception as sync_err:
                    logger.warning(f"MongoDB sync notice: {sync_err}")

            summary = {
                "success": True,
                "rules_count": len(self.master_rules),
                "approved_units_count": len(self.approved_units_set),
                "prohibited_units_count": len(self.prohibited_units_dict),
                "tax_suffix_patterns_count": len(self.tax_suffix_patterns),
                "consumer_care_keywords_count": len(self.consumer_care_keywords),
                "mfg_keywords_count": len(self.mfg_keywords),
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"Master datasets reloaded from CSV: {summary}")
            return summary

    def _load_rules_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """Loads master statutory rules from CSV."""
        rules = []
        if not os.path.exists(file_path):
            logger.warning(f"Rules CSV file not found at {file_path}, using built-in defaults.")
            return self._get_default_master_rules()

        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("enabled", "True").strip().lower() in ["true", "1", "yes"]:
                        rules.append({
                            "rule_id": row.get("rule_id", "").strip(),
                            "rule_name": row.get("rule_name", "").strip(),
                            "legal_act_section": row.get("legal_act_section", "").strip(),
                            "category": row.get("category", "").strip(),
                            "is_mandatory": row.get("is_mandatory", "True").strip().lower() == "true",
                            "severity": row.get("severity", "HIGH").strip().upper(),
                            "penalty_min_inr": int(row.get("penalty_min_inr", 25000) or 25000),
                            "penalty_max_inr": int(row.get("penalty_max_inr", 50000) or 50000),
                            "description": row.get("description", "").strip(),
                            "remediation": row.get("remediation", "").strip()
                        })
        except Exception as e:
            logger.error(f"Error reading rules CSV {file_path}: {e}")
            return self._get_default_master_rules()

        return rules if rules else self._get_default_master_rules()

    def _load_approved_units_csv(self, file_path: str) -> Tuple[Set[str], List[Dict[str, str]]]:
        """Loads approved SI metric units and count terms from CSV."""
        units_set: Set[str] = set()
        units_list: List[Dict[str, str]] = []

        if not os.path.exists(file_path):
            return self._get_default_approved_units()

        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get("unit_symbol", "").strip()
                    if symbol:
                        units_set.add(symbol.lower())
                        units_set.add(symbol)  # Preserve original regional characters
                        units_list.append({
                            "unit_symbol": symbol,
                            "category": row.get("category", "General"),
                            "full_name": row.get("full_name", symbol),
                            "language_code": row.get("language_code", "en"),
                            "statutory_schedule": row.get("statutory_schedule", "Schedule I")
                        })
        except Exception as e:
            logger.error(f"Error reading approved units CSV {file_path}: {e}")
            return self._get_default_approved_units()

        return (units_set, units_list) if units_set else self._get_default_approved_units()

    def _load_prohibited_units_csv(self, file_path: str) -> Dict[str, str]:
        """Loads prohibited non-metric imperial units from CSV."""
        prohibited_dict: Dict[str, str] = {}
        if not os.path.exists(file_path):
            return self._get_default_prohibited_units()

        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get("unit_symbol", "").strip().lower()
                    name = row.get("unit_name", symbol).strip()
                    reason = row.get("prohibition_reason", "Prohibited under Rule 11").strip()
                    if symbol:
                        prohibited_dict[symbol] = f"{name} (Imperial Unit - {reason})"
        except Exception as e:
            logger.error(f"Error reading prohibited units CSV {file_path}: {e}")
            return self._get_default_prohibited_units()

        return prohibited_dict if prohibited_dict else self._get_default_prohibited_units()

    def _load_single_column_csv(self, file_path: str, column_name: str) -> List[str]:
        """Loads a list of strings from a single column of a CSV file."""
        items: List[str] = []
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    val = row.get(column_name, "").strip()
                    if val:
                        items.append(val)
        except Exception as e:
            logger.error(f"Error reading column {column_name} from {file_path}: {e}")
            return []

        return items

    # =========================================================================
    # TEMPORARY LIVE AUDIT CSV (CSV 2) - ROLLING BUFFER (FIFO)
    # =========================================================================
    def _ensure_live_audit_csv_initialized(self):
        """Initializes the live audit CSV header if the file does not exist."""
        with self._lock:
            if not os.path.exists(LIVE_AUDITS_CSV_PATH) or os.path.getsize(LIVE_AUDITS_CSV_PATH) == 0:
                headers = [
                    "audit_id", "timestamp", "product_name", "mrp", "taxes_included",
                    "net_quantity", "unit_of_measure", "mfg_date", "consumer_care_email",
                    "consumer_care_phone", "country_of_origin", "manufacturer_name",
                    "compliance_status", "overall_score", "violations_count",
                    "violations_summary", "dominant_language"
                ]
                with open(LIVE_AUDITS_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)

    def log_live_audit(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logs a single real-time audit record to the temporary live audit CSV (`recent_audits_live.csv`).
        Applies a rolling buffer (FIFO):
        When records exceed `max_live_records` (e.g. 50), older records roll off to protect storage.
        """
        with self._lock:
            self._ensure_live_audit_csv_initialized()

            meta = audit_data.get("extracted_metadata", {})
            violations = audit_data.get("violations", [])
            multilingual = audit_data.get("multilingual_profile", {})

            # Prepare violations summary
            viol_summary_list = [v.get("rule_name", v.get("rule_id", "")) for v in violations]
            viol_summary_str = " | ".join(viol_summary_list) if viol_summary_list else "None (Fully Compliant)"

            audit_id = audit_data.get("audit_id") or f"AUD_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:18]}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            new_record = {
                "audit_id": audit_id,
                "timestamp": timestamp,
                "product_name": audit_data.get("filename") or meta.get("brand_name") or meta.get("manufacturer_name") or "Package Specimen",
                "mrp": str(meta.get("mrp") or "Not Detected"),
                "taxes_included": "Yes" if meta.get("tax_suffix_present") else "No",
                "net_quantity": str(meta.get("net_quantity") or "Not Detected"),
                "unit_of_measure": str(meta.get("unit") or "N/A"),
                "mfg_date": str(meta.get("mfg_date") or meta.get("pkg_date") or "Not Detected"),
                "consumer_care_email": str(meta.get("consumer_care_email") or "Not Detected"),
                "consumer_care_phone": str(meta.get("consumer_care_phone") or "Not Detected"),
                "country_of_origin": str(meta.get("country_of_origin") or "Not Detected"),
                "manufacturer_name": str(meta.get("manufacturer_name") or "Not Detected"),
                "compliance_status": audit_data.get("status", "UNKNOWN"),
                "overall_score": str(audit_data.get("overall_score", 0)),
                "violations_count": str(len(violations)),
                "violations_summary": viol_summary_str,
                "dominant_language": multilingual.get("language_name") or "English"
            }

            # Read existing rows
            existing_rows = []
            headers = list(new_record.keys())

            if os.path.exists(LIVE_AUDITS_CSV_PATH):
                try:
                    with open(LIVE_AUDITS_CSV_PATH, mode="r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        if reader.fieldnames:
                            headers = reader.fieldnames
                        for row in reader:
                            existing_rows.append(row)
                except Exception as read_err:
                    logger.warning(f"Error reading live audits CSV: {read_err}")

            # Prepend new record (most recent first)
            existing_rows.insert(0, new_record)

            # Enforce rolling buffer (FIFO limit)
            if len(existing_rows) > self.max_live_records:
                existing_rows = existing_rows[:self.max_live_records]

            # Atomic Write back to CSV
            try:
                temp_path = LIVE_AUDITS_CSV_PATH + ".tmp"
                with open(temp_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(existing_rows)
                os.replace(temp_path, LIVE_AUDITS_CSV_PATH)
            except Exception as write_err:
                logger.error(f"Error writing rolling live audit to CSV: {write_err}")

            # Also log to MongoDB if active
            if self.mongo_db is not None:
                try:
                    self.mongo_db["live_audit_logs"].insert_one(dict(new_record))
                except Exception as m_err:
                    logger.warning(f"MongoDB audit log notice: {m_err}")

            return new_record

    def get_live_audit_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent live extracted product audit logs."""
        with self._lock:
            records = []
            if not os.path.exists(LIVE_AUDITS_CSV_PATH):
                return []

            try:
                with open(LIVE_AUDITS_CSV_PATH, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        records.append(row)
                        if len(records) >= limit:
                            break
            except Exception as e:
                logger.error(f"Error reading live audit history: {e}")
                return []

            return records

    def clear_live_audit_history(self) -> bool:
        """Clears/resets the temporary live audit CSV."""
        with self._lock:
            try:
                headers = [
                    "audit_id", "timestamp", "product_name", "mrp", "taxes_included",
                    "net_quantity", "unit_of_measure", "mfg_date", "consumer_care_email",
                    "consumer_care_phone", "country_of_origin", "manufacturer_name",
                    "compliance_status", "overall_score", "violations_count",
                    "violations_summary", "dominant_language"
                ]
                with open(LIVE_AUDITS_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)

                if self.mongo_db is not None:
                    try:
                        self.mongo_db["live_audit_logs"].delete_many({})
                    except Exception as me:
                        logger.warning(f"MongoDB clear notice: {me}")

                logger.info("Temporary live audit CSV successfully cleared.")
                return True
            except Exception as e:
                logger.error(f"Error clearing live audit CSV: {e}")
                return False

    def get_database_status(self) -> Dict[str, Any]:
        """Returns storage diagnostics, record counts, and database health."""
        with self._lock:
            live_count = 0
            live_size_bytes = 0
            if os.path.exists(LIVE_AUDITS_CSV_PATH):
                live_size_bytes = os.path.getsize(LIVE_AUDITS_CSV_PATH)
                try:
                    with open(LIVE_AUDITS_CSV_PATH, mode="r", encoding="utf-8-sig") as f:
                        reader = csv.reader(f)
                        next(reader, None)  # Skip header
                        live_count = sum(1 for _ in reader)
                except Exception:
                    pass

            return {
                "status": "healthy",
                "data_directory": self.data_dir,
                "master_rules_count": len(self.master_rules),
                "approved_units_count": len(self.approved_units_set),
                "prohibited_units_count": len(self.prohibited_units_dict),
                "live_audit_records_count": live_count,
                "live_audit_max_buffer": self.max_live_records,
                "live_audit_file_size_bytes": live_size_bytes,
                "mongodb_connected": self.mongo_client is not None,
                "timestamp": datetime.now().isoformat()
            }

    # =========================================================================
    # BUILT-IN FALLBACK DEFAULTS (IN CASE CSV IS MISSING OR DELETED)
    # =========================================================================
    def _get_default_master_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "rule_id": "RULE_6_1_DA_MRP",
                "rule_name": "Maximum Retail Price (MRP) & All Inclusive of Taxes",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 6(1)(da)",
                "category": "MRP_TAXATION",
                "is_mandatory": True,
                "severity": "CRITICAL",
                "penalty_min_inr": 25000,
                "penalty_max_inr": 100000,
                "description": "Every retail package must declare Maximum Retail Price (MRP) inclusive of all taxes clearly.",
                "remediation": "Ensure MRP is prominently displayed in statutory format with tax suffix."
            },
            {
                "rule_id": "RULE_11_12_NET_QTY",
                "rule_name": "Net Quantity & Approved SI Metric Units",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 11 and Rule 12",
                "category": "NET_QUANTITY",
                "is_mandatory": True,
                "severity": "CRITICAL",
                "penalty_min_inr": 25000,
                "penalty_max_inr": 100000,
                "description": "Net quantity must be declared using standard SI metric units (g, kg, ml, l, count).",
                "remediation": "Declare net quantity strictly in approved SI Metric units. Remove prohibited imperial units."
            },
            {
                "rule_id": "RULE_6_1_G_CONSUMER_CARE",
                "rule_name": "Consumer Care & Redressal Mechanism",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 6(1)(g)",
                "category": "CONSUMER_REDRESSAL",
                "is_mandatory": True,
                "severity": "HIGH",
                "penalty_min_inr": 25000,
                "penalty_max_inr": 50000,
                "description": "Package must declare contact details of consumer grievance helpline/email.",
                "remediation": "Print dedicated consumer care details including phone number and email."
            },
            {
                "rule_id": "RULE_6_1_C_MFG_DATE",
                "rule_name": "Manufacturing / Packaging Timeline Declaration",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 6(1)(c)",
                "category": "MANUFACTURING_TIMELINE",
                "is_mandatory": True,
                "severity": "HIGH",
                "penalty_min_inr": 25000,
                "penalty_max_inr": 50000,
                "description": "Month and Year of manufacture, packaging, or import must be declared.",
                "remediation": "Print clearly the Month and Year of manufacture or packaging."
            },
            {
                "rule_id": "RULE_9_FONT_SIZE",
                "rule_name": "Principal Display Panel & Minimum Font Height",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 9 & Schedule II",
                "category": "FONT_LAYOUT",
                "is_mandatory": True,
                "severity": "MEDIUM",
                "penalty_min_inr": 10000,
                "penalty_max_inr": 25000,
                "description": "Statutory declarations must meet minimum height thresholds.",
                "remediation": "Ensure font size meets statutory minimum requirements under Schedule II."
            },
            {
                "rule_id": "RULE_6_10_ORIGIN",
                "rule_name": "Country of Origin Declaration",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 6(10)",
                "category": "COUNTRY_OF_ORIGIN",
                "is_mandatory": True,
                "severity": "MEDIUM",
                "penalty_min_inr": 10000,
                "penalty_max_inr": 50000,
                "description": "Name of country of origin or manufacture must be clearly declared.",
                "remediation": "Explicitly mention 'Country of Origin: India' or originating nation."
            },
            {
                "rule_id": "RULE_6_1_A_MFG_NAME",
                "rule_name": "Name and Address of Manufacturer / Packer",
                "legal_act_section": "Legal Metrology (Packaged Commodities) Rules 2011 - Rule 6(1)(a)",
                "category": "MANUFACTURER_DETAILS",
                "is_mandatory": True,
                "severity": "HIGH",
                "penalty_min_inr": 25000,
                "penalty_max_inr": 50000,
                "description": "Name and complete address of the manufacturer or packer must be declared.",
                "remediation": "Mention full name and factory/office address of the manufacturer with PIN code."
            }
        ]

    def _get_default_approved_units(self) -> Tuple[Set[str], List[Dict[str, str]]]:
        units = {
            "g", "gm", "gms", "gram", "grams", "kg", "kgs", "kilogram", "kilograms", "mg", "milligram", "milligrams",
            "ml", "mls", "millilitre", "millilitres", "milliliter", "milliliters", "l", "ltr", "ltrs", "litre", "litres", "liter", "liters",
            "units", "unit", "u", "pcs", "piece", "pieces", "pc", "pkts", "packets", "packet", "pack", "n", "count", "ct", "nos", "no", "set", "sets",
            "pens", "pen", "refills", "refill", "pencils", "pencil", "markers", "marker", "highlighters", "highlighter",
            "tablets", "tablet", "tabs", "tab", "capsules", "capsule", "strips", "strip", "vials", "vial",
            "pages", "page", "pgs", "pg", "sheets", "sheet", "rolls", "roll",
            "m", "meter", "meters", "metre", "metres", "cm", "centimeter", "centimeters", "centimetre", "centimetres", "mm", "millimeter",
            "ग्राम", "किग्रा", "मिली", "लीटर", "मीटर", "सेमी", "नग", "संख्या",
            "గ్రాములు", "గ్రా", "మి.లీ", "మిలీ", "లీటర్", "కేజీ", "కిలో", "సంఖ్య",
            "निव्वळ", "कि.ग्रॅ.", "लिटर", "গ্রাম", "কেজি", "মিলি", "লিটার", "ਗ੍ਰਾਮ", "ਕਿਲੋ", "ਮਿਲੀ", "ਲਿਟਰ"
        }
        return units, [{"unit_symbol": u, "category": "General", "full_name": u, "language_code": "en", "statutory_schedule": "Schedule I"} for u in units]

    def _get_default_prohibited_units(self) -> Dict[str, str]:
        return {
            "fl oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "floz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "fl.oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "fl. oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "fluid ounce": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "fluid ounces": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
            "oz": "Ounce (Imperial Unit - Prohibited under Rule 11)",
            "ounce": "Ounce (Imperial Unit - Prohibited under Rule 11)",
            "ounces": "Ounces (Imperial Unit - Prohibited under Rule 11)",
            "lbs": "Pounds (Imperial Unit - Prohibited under Rule 11)",
            "pound": "Pound (Imperial Unit - Prohibited under Rule 11)",
            "pounds": "Pounds (Imperial Unit - Prohibited under Rule 11)",
            "gallon": "Gallon (Imperial Unit - Prohibited under Rule 11)",
            "gallons": "Gallons (Imperial Unit - Prohibited under Rule 11)",
            "gal": "Gallon (Imperial Unit - Prohibited under Rule 11)",
            "quart": "Quart (Imperial Unit - Prohibited under Rule 11)",
            "quarts": "Quart (Imperial Unit - Prohibited under Rule 11)",
            "qt": "Quart (Imperial Unit - Prohibited under Rule 11)",
            "yard": "Yard (Imperial Unit - Non-standard under Rule 11)",
            "yards": "Yards (Imperial Unit - Non-standard under Rule 11)",
            "yds": "Yards (Imperial Unit - Non-standard under Rule 11)",
            "inches": "Inches (Imperial Unit - Non-standard under Rule 11)",
            "inch": "Inch (Imperial Unit - Non-standard under Rule 11)",
        }


# Global Database Manager Singleton Instance
db_manager = DatabaseManager()
