"""
Legal Metrology Compliance Engine
Implementation for Legal Metrology (Packaged Commodities) Rules, 2011 (as amended).

This module verifies OCR extracted text segments against statutory requirements:
1. Rule 6(1)(da) - Maximum Retail Price (MRP) & Tax Suffix Clause (Fuzzy & Curvature Resilient)
2. Rule 11 & 12 - Net Quantity Standards & Approved Metric Units (Stationery, Pens, FMCG, Bottles, Cylinders)
3. Rule 6(1)(g) - Consumer Care & Redressal Mechanism (Fragment Stitching for care@ emails, helplines)
4. Rule 6(1)(c) - Manufacturing / Packaging Timeline Metadata
5. Rule 9 & Schedule II - Minimum Font Height & PDP Aspect Ratio Estimation
6. Rule 6(10) - Country of Origin (Infers India from 6-digit PIN codes & State names with Low-Severity Advisory)
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from db_manager import db_manager
except ImportError:
    try:
        from backend.db_manager import db_manager
    except ImportError:
        db_manager = None



class LegalMetrologyComplianceEngine:
    """
    Core Compliance Auditing Engine for the Legal Metrology (Packaged Commodities) Rules, 2011.
    Features:
    - Cylindrical label fragment stitching (PaddleOCR / RapidOCR curvature resilience).
    - Non-failing consumer care redressal detection (care@, help@, 10-digit phone near manufacturing).
    - Intelligent Country of Origin inference from Indian states/PIN codes with Low-Severity Advisory.
    - Product Identifier isolation (Art No, Item Code, Model No, Batch No) with zero false imperial unit positives.
    """

    # Script Unicode Ranges for Regional Script Detection
    SCRIPT_RANGES = {
        "Devanagari": (0x0900, 0x097F), # Hindi, Marathi, Sanskrit, Nepali, Konkani
        "Telugu": (0x0C00, 0x0C7F),     # Telugu
        "Bengali": (0x0980, 0x09FF),    # Bengali, Assamese
        "Gurmukhi": (0x0A00, 0x0A7F),   # Punjabi
        "Arabic": (0x0600, 0x06FF),     # Urdu, Arabic, Kashmiri, Sindhi
        "Tamil": (0x0B80, 0x0BFF),      # Tamil
        "Gujarati": (0x0A80, 0x0AFF),   # Gujarati
        "Kannada": (0x0C80, 0x0CFF),    # Kannada
        "Malayalam": (0x0D00, 0x0D7F),  # Malayalam
        "Odia": (0x0B00, 0x0B7F),       # Odia
    }

    # Rule 11 & 12: Approved SI Metric Units and Approved Commodity Units under Legal Metrology Act
    APPROVED_METRIC_UNITS = {
        # Mass
        "g", "gm", "gms", "gram", "grams", "g.", "gm.",
        "kg", "kgs", "kilogram", "kilograms", "kg.",
        "mg", "milligram", "milligrams",
        # Volume / Capacity
        "ml", "mls", "millilitre", "millilitres", "milliliter", "milliliters", "ml.",
        "l", "ltr", "ltrs", "litre", "litres", "liter", "liters", "l.",
        "cl", "dl",
        # Numbers / Units / Count
        "units", "unit", "u", "pcs", "piece", "pieces", "pc", "pkts", "packets", "packet", "pack",
        "n", "count", "ct", "nos", "no.", "no", "set", "sets", "items", "item", "pair", "pairs",
        # Stationery & Writing Instruments (Pens, Refills, Pencils, Notebooks)
        "pens", "pen", "refills", "refill", "pencils", "pencil", "markers", "marker",
        "highlighters", "highlighter", "erasers", "eraser", "sharpeners", "sharpener",
        "rulers", "ruler", "notebooks", "notebook", "crayons", "crayon", "paints", "paint",
        # Pharmaceutical / Medical
        "tablets", "tablet", "tabs", "tab", "capsules", "capsule", "caps", "cap",
        "strips", "strip", "vials", "vial", "ampoules", "ampoule", "sachets", "sachet",
        # Paper & Publication
        "pages", "page", "pgs", "pg", "sheets", "sheet", "leaves", "leaf", "rolls", "roll",
        # Containers
        "tubes", "tube", "bottles", "bottle", "pouches", "pouch", "cans", "can", "jars", "jar",
        "tins", "tin", "boxes", "box", "cartons", "carton",
        # Length & Dimensions
        "m", "meter", "meters", "metre", "metres", "m.",
        "cm", "centimeter", "centimeters", "centimetre", "centimetres", "cm.",
        "mm", "millimeter", "millimeters", "millimetre", "millimetres", "mm.",
        # Area & Volume
        "sq.m", "sq.cm", "sq.mm", "sqm", "sqcm", "sqmm", "cbm", "cu.m", "cu.cm", "cc",
        # Multilingual Regional Metric Units (Hindi, Marathi, Telugu, Bengali, Punjabi, Urdu, etc.)
        "ग्राम", "किग्रा", "कि.ग्रा.", "मिली", "मि.ली.", "लीटर", "ली.", "मीटर", "सेमी", "नग", "संख्या",
        "గ్రాములు", "గ్రా", "మి.లీ", "మిలీ", "లీటర్", "కేజీ", "కిలో", "కిలోలు", "సంఖ్య", "నెం", "మీటర్లు", "సెం.మీ",
        "निव्वळ", "कि.ग्रॅ.", "लिटर", "मिली",
        "গ্রাম", "কেজি", "মিলি", "লিটার", "সংখ্যা", "প্যাকেট",
        "ਗ੍ਰਾਮ", "ਕਿਲੋ", "ਮਿਲੀ", "ਲਿਟਰ", "ਨੰਬਰ", "ਪੈਕਟ",
        "گرام", "کلو", "ملی", "لیٹر", "تعداد",
        "கிராம்", "கிலோ", "மில்லி", "லிட்டர்", "எண்ணிக்கை",
        "ગ્રામ", "કિલો", "મિલી", "લીટર", "નંગ",
        "ಗ್ರಾಂ", "ಕೆಜಿ", "ಮಿಲಿ", "ಲೀಟರ್", "ಸಂಖ್ಯೆ",
        "ഗ്രാം", "കിലോഗ്രാം", "മില്ലി", "ലിറ്റർ"
    }

    # Prohibited non-standard / imperial units in India
    UNAMBIGUOUS_IMPERIAL_UNITS = {
        "fl oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
        "floz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
        "fl.oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
        "fl. oz": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
        "fl. oz.": "Fluid Ounce (Imperial Unit - Prohibited under Rule 11)",
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

    # Product Identifier Patterns (Art No, Item Code, Model No, Batch No, HSN, etc.)
    PRODUCT_IDENTIFIER_PATTERNS = [
        (r"(?i)\b(?:art(?:\.|icle)?\s*(?:no\.?|num(?:ber)?|code|#)?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "art_number"),
        (r"(?i)\b(?:item\s*(?:no\.?|num(?:ber)?|code|#)?|itm\s*no\.?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "item_code"),
        (r"(?i)\b(?:model\s*(?:no\.?|num(?:ber)?|code|#)?|mod\.?\s*no\.?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "model_number"),
        (r"(?i)\b(?:style\s*(?:no\.?|num(?:ber)?|code|#)?|sty\.?\s*no\.?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "style_number"),
        (r"(?i)\b(?:prod(?:uct)?\s*(?:no\.?|code|#)?|part\s*(?:no\.?|num(?:ber)?|#)?|p/n|prd\s*no\.?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "part_number"),
        (r"(?i)\b(?:cat(?:alog(?:ue)?)?\s*(?:no\.?|num(?:ber)?|#)?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "cat_number"),
        (r"(?i)\b(?:ref(?:\.|erence)?\s*(?:no\.?|num(?:ber)?|#)?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "ref_number"),
        (r"(?i)\b(?:batch\s*(?:no\.?|num(?:ber)?|#)?|b\.?no\.?|lot\s*(?:no\.?|#)?|బ్యాచ్\s*నెం|बैच\s*नं)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "batch_number"),
        (r"(?i)\b(?:hsn(?:\s*code)?|sac(?:\s*code)?)\s*[:=-]?\s*(\d{4,8})", "hsn_code"),
        (r"(?i)\b(?:barcode|ean|upc|gtin|isbn)\s*[:=-]?\s*([0-9\-]{8,18})", "barcode"),
        (r"(?i)\b(?:sku\s*(?:id|no\.?|code|#)?)\s*[:=-]?\s*([a-zA-Z0-9\-_/]+)", "sku_id"),
        (r"(?i)\b(?:fssai(?:\s*lic(?:ence)?(?:\s*no\.?)?)?)\s*[:=-]?\s*([0-9]{14})", "fssai_lic"),
        (r"(?i)\b(?:gstin|gst\s*no\.?)\s*[:=-]?\s*([0-9]{2}[a-zA-Z]{5}[0-9]{4}[a-zA-Z]{1}[1-9a-zA-Z]{1}[zZ]{1}[0-9a-zA-Z]{1})", "gstin"),
        (r"(?i)\b(?:pin(?:\s*code)?|postal(?:\s*code)?|zip(?:\s*code)?|పిన్\s*కోడ్|पिन\s*कोड)\s*[:=-]?\s*([1-9][0-9]{5})\b", "pincode"),
    ]

    # Rule 6(1)(da): Statutory Tax Suffix Patterns (English + Regional Indian Languages)
    TAX_SUFFIX_PATTERNS = [
        # Full Statutory Clauses - English
        r"inclusive\s*of\s*all\s*taxes",
        r"incl?\.?\s*of\s*all\s*taxes",
        r"inc[l1i]?\.?\s*(?:of\s*)?all\s*taxes",
        r"inc[l1i]?\s*ofalltaxes",
        r"incl?[\s_]*of[\s_]*all[\s_]*taxes",
        r"incl?\.?\s*all\s*taxes",
        r"inclusive\s*all\s*taxes",
        r"all\s*taxes\s*incl?",
        r"all\s*taxes\s*included",
        r"taxes\s*included",
        r"taxes\s*incl\.?",
        r"incl\.?\s*tax(?:es)?",
        r"incl\.?\s*of\s*all\s*taxes\.?",
        # Curvature & Label Edge Truncation Partial Matches
        r"inclusive\s*of\s*all\s*tax?",
        r"inclusive\s*of\s*al\b",
        r"inclusive\s*of\b",
        r"incl?\.?\s*of\s*all\s*tax?",
        r"incl?\.?\s*of\s*all\b",
        r"incl?\.?\s*of\s*al\b",
        r"incl?\.?\s*all\s*tax?",
        r"all\s*taxes\s*inc?",
        r"all\s*tax\s*inc?",
        r"taxes\s*inc\b",
        r"tax\s*incl?\b",
        r"inc[l1i]?\.?\s*of\s*all",
        r"inc[l1i]?\.?\s*all\s*tax",
        # Multilingual Regional Statutory Phrases
        # Hindi / Devanagari
        r"सभी\s*करों?\s*सहित", r"करों?\s*सहित", r"सब\s*टैक्स\s*सहित", r"सर्व\s*करांसह", r"सर्व\s*कर\s*समाविष्ट",
        # Telugu
        r"అన్ని\s*పన్నులతో\s*కలిపి", r"అన్ని\s*పన్నులు\s*కలుపుకొని", r"పన్నులు\s*సహా", r"పన్నులతో\s*కలిపి",
        r"అన్ని\s*పన్నులు\s*సహా", r"పన్నులతో\s*సహా",
        # Bengali
        r"সমস্ত\s*কর\s*সহ", r"সমস্ত\s*কর\s*অন্তর্ভুক্ত", r"সব\s*ট্যাক্স\s*সহ",
        # Punjabi
        r"ਸਾਰੇ\s*ਟੈਕਸਾਂ?\s*ਸਮੇਤ", r"ਸਾਰੇ\s*ਟੈਕਸ\s*ਸ਼ਾਮਲ",
        # Urdu
        r"تمام\s*ٹیکسز?\s*سمیت", r"تمام\s*ٹیکس\s*شامل",
        # Tamil
        r"அனைத்து\s*வரிகளும்\s*உட்பட", r"வரிகள்\s*உட்பட",
        # Gujarati
        r"તમામ\s*કર\s*સહિત", r"બધા\s*કર\s*સહિત",
        # Kannada
        r"ಎಲ್ಲಾ\s*ತೆರಿಗೆಗಳು\s*ಸೇರಿವೆ", r"ತೆರಿಗೆ\s*ಸಹಿತ",
        # Malayalam
        r"എല്ലാ\s*നികുതികളും\s*ഉൾപ്പെടെ"
    ]

    # Rule 6(1)(g): Consumer Care Keywords in English & Regional Languages
    CONSUMER_CARE_KEYWORDS = [
        "customer care", "customer service", "consumer care", "consumer feedback",
        "consumer redressal", "helpline", "toll free", "toll-free", "complaint",
        "complaints", "feedback", "queries", "query", "contact us", "reach us",
        "write to us", "grievance officer", "grievance", "support", "care executive",
        "customer query", "consumer cell", "care cell", "cell", "in case of consumer complaints",
        "redressal", "for complaints", "for feedback", "patient care", "contact",
        "cust care", "cust. care", "customr", "consumr", "helplin", "toll fre",
        "tol free", "feedbk", "care@",
        # Hindi & Marathi
        "ग्राहक सेवा", "उपभोक्ता शिकायत", "हेल्पलाइन", "टोल फ्री", "संपर्क", "शिकायत", "ग्राहक तक्रार", "ग्राहक मदत",
        # Telugu
        "వినియోగదారుల సంరక్షణ", "వినియోగదారుల ఫిర్యాదులు", "హెల్ప్‌లైన్", "టోల్ ఫ్రీ", "సంప్రదించండి", "సహాయం",
        # Bengali
        "গ্রাহক সেবা", "গ্রাহক সহায়তা", "অভিযোগ", "হেল্পলাইন",
        # Punjabi
        "ਗ੍ਰਾਹਕ ਸੇਵਾ", "ਸਹਾਇਤਾ", "ਸ਼ਿਕਾਇਤ ਨਿਵਾਰਣ", "ਹੈਲਪਲਾਈਨ",
        # Urdu
        "صارفین کی دیکھ بھال", "شکایات سیل", "ہیلپ لائن",
        # Tamil, Gujarati, Kannada
        "வாடிக்கையாளர் சேவை", "உதவி எண்", "ગ્રાહક સેવા", "સહાયતા", "ಗ್ರಾಹಕರ ಸೇವೆ", "ಸಹಾಯವಾಣಿ"
    ]

    # Rule 6(1)(c): Manufacturing, Packaging & Expiry Keywords in English & Regional Languages
    MFG_KEYWORDS = [
        "mfg", "manufactured", "manufacturing", "mfg date", "date of mfg", "pkd",
        "packed", "packaging", "date of packaging", "pkg", "packed date", "import",
        "imported", "import date", "batch", "lot", "b.no", "b.n", "btch", "mfd",
        "mfd.", "mfd. on", "mfd on", "date of import", "exp", "exp.", "expiry",
        "exp date", "use before", "best before", "best bef", "use by", "mfg/exp",
        "mfg dt", "pkd dt",
        # Hindi & Marathi
        "निर्माण तिथि", "पैकिंग तिथि", "उत्पादन", "बैच नं", "उपयोग से पहले", "उत्पादन दिनांक", "पॅकिंग दिनांक",
        # Telugu
        "తయారీ తేదీ", "ప్యాకింగ్ తేదీ", "బ్యాచ్ నెం", "గడువు తేదీ",
        # Bengali
        "উত্পাদন তারিখ", "প্যাকিং তারিখ", "মেয়াদ উত্তীর্ণের তারিখ",
        # Punjabi
        "ਤਿਆਰੀ ਮਿਤੀ", "ਪੈਕਿੰਗ ਮਿਤੀ", "ਬੈਚ ਨੰਬਰ",
        # Urdu
        "تاریخ تیاری", "پیکنگ تاریخ", "بیچ نمبر",
        # Tamil, Gujarati, Kannada
        "தயாரிப்பு தேதி", "பேக்கிங் தேதி", "ઉત્પાદન તારીખ", "પેકિંગ તારીખ", "ಉತ್ಪಾದನಾ ದಿನಾಂಕ"
    ]

    # Comprehensive Knowledge Base of Indian States, Union Territories & Manufacturing Hubs
    INDIAN_STATES_AND_UTS = {
        # Full Names
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
        "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
        "delhi", "jammu & kashmir", "jammu and kashmir", "ladakh", "puducherry",
        "chandigarh", "dadra and nagar haveli", "daman and diu", "lakshadweep",
        "andaman and nicobar",
        # State Abbreviations
        "mh", "gj", "hr", "dl", "up", "ka", "tn", "rj", "pb", "mp", "ap", "ts", "wb",
        "hp", "uk", "ga", "jh", "cg", "kl", "or", "od", "as", "br",
        # Prominent Indian Manufacturing / Industrial Hubs & Cities
        "baddi", "vapi", "ankleshwar", "ahmedabad", "surat", "vadodara", "rajkot",
        "morbi", "pune", "mumbai", "thane", "nagpur", "nashik", "aurangabad",
        "manesar", "gurgaon", "gurugram", "faridabad", "noida", "greater noida",
        "ghaziabad", "kundli", "sonipat", "panipat", "karnal", "ambala", "ludhiana",
        "jalandhar", "haridwar", "pantnagar", "dehradun", "roorkee", "solan",
        "kala amb", "bengaluru", "bangalore", "mysore", "peenya", "hosur", "chennai",
        "coimbatore", "tirupur", "sri city", "hyderabad", "secunderabad", "medchal",
        "kolkata", "howrah", "jamshedpur", "ranchi", "bhubaneswar", "cuttack",
        "guwahati", "indore", "bhopal", "pithampur", "jaipur", "bhiwadi", "neemrana",
        "alwar", "kota", "kochi", "ernakulam", "silvassa", "daman", "pondicherry",
        # Regional Script Country & State Names
        "भारत", "भारत गणराज्य", "భారతదేశం", "భారత్", "ভারত", "ਭਾਰਤ", "ہندوستان", "இந்தியா", "ભારત", "ಭಾರತ",
        "गुजरात", "महाराष्ट्र", "हरियाणा", "पंजाब", "తెలంగాణ", "ఆంధ్ర ప్రదేశ్", "గుజరాత్", "మహారాష్ట్ర"
    }

    # Prepositions indicating 'in' is NOT an inch measurement
    IN_PREPOSITION_FOLLOWERS = {
        "india", "bharat", "delhi", "mumbai", "kolkata", "chennai", "bengaluru", "hyderabad",
        "ahmedabad", "pune", "jaipur", "surat", "lucknow", "kanpur", "nagpur", "indore", "thane",
        "bhopal", "patna", "vadodara", "ghaziabad", "ludhiana", "agra", "nashik", "faridabad",
        "meerut", "rajkot", "varanasi", "srinagar", "amritsar", "noida", "gurgaon", "chandigarh",
        "gujarat", "maharashtra", "haryana", "rajasthan", "karnataka", "tamil", "nadu", "kerala",
        "punjab", "bengal", "up", "uttar", "pradesh", "mp", "madhya", "usa", "uk", "china",
        "japan", "germany", "korea", "taiwan", "vietnam", "thailand", "france", "italy",
        "box", "pack", "packet", "carton", "pouch", "bottle", "can", "case", "container",
        "sachet", "tray", "blister", "tub", "jar", "bag", "strip", "vial", "ampoule", "wrapper",
        "tin", "foil", "bucket", "drum", "stock", "store",
        "a", "an", "the", "each", "every", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine", "ten", "all", "total", "both", "this", "that", "these", "those", "our",
        "your", "its", "any", "such", "case", "order", "accordance", "compliance", "terms",
        "place", "event", "form", "shape", "liquid", "powder", "tablet", "solid", "spray",
        "paste", "gel", "water", "milk", "oil", "air", "dry", "cool", "dark", "shade",
        "sunlight", "heat", "ambient", "temperature", "condition", "conditions",
        "shades", "colours", "colors", "sizes", "variants", "flavours", "flavors", "styles",
        "models", "types", "grades", "designs", "patterns"
    }

    IN_PRECEDING_VERBS = [
        "made", "packed", "mfg", "mfd", "manufactured", "imported", "printed", "bottled",
        "available", "packaged", "formulated", "used", "mix", "dissolve", "store", "keep",
        "born", "designed", "assembled", "tested", "marketed", "licensed", "produced",
        "created", "fill", "all", "pack of", "set of", "box of", "buy", "combo"
    ]

    def __init__(self):
        self.email_regex = re.compile(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
        )
        self.phone_regex = re.compile(
            r"(?:(?:\+91|91|0)[\- ]?)?(?:[6-9]\d{9}|1800[\- ]?\d{3}[\- ]?\d{3,4}|1860[\- ]?\d{3}[\- ]?\d{3,4}|\d{3,5}[\- ]?\d{6,8})",
            re.IGNORECASE
        )
        # Price Patterns - Resilient to OCR symbols, colon/dash spacing, and blurry decimal formats in English and Indian Scripts
        self.price_regex = re.compile(
            r"(?:(?:m\.?r\.?p\.?|mr\.?p|m\.?r\.?|max(?:imum)?\s+retail\s+price|retail\s+price|price|अधिकतम\s*खुदरा\s*मूल्य|अ\.?खु\.?मू\.?|एमआरपी|कमाल\s*किरकोळ\s*किंमत|గరిష్ట\s*రిటైల్\s*ధర|ధర|সর্বোচ্চ\s*খুচরা\s*মূল্য|ਵੱਧ\s*ਤੋਂ\s*ਵੱਧ\s*ਪ੍ਰਚੂਨ\s*ਮੁੱਲ|زیادہ\s*سے\s*زیادہ\s*خوردہ\s*قیمت|அதிகபட்ச\s*சில்லறை\s*விலை|કિંમત)\s*[\.:=-]*\s*(?:rs\.?|₹|inr|re\.?|रु\.?|రూ\.?|টাকা|ਰੁ\.?|روپے)?\s*[\.:=-]*\s*(\d+(?:,\d+)*(?:\.\d{1,2})?))",
            re.IGNORECASE
        )
        self.standalone_price_regex = re.compile(
            r"(?:(?:rs\.?|₹|inr|re\.?|रु\.?|రూ\.?|টাকা|ਰੁ\.?|روپے)\s*[\.:=-]*\s*(\d+(?:,\d+)*(?:\.\d{1,2})?))",
            re.IGNORECASE
        )
        self.pincode_regex = re.compile(r"\b[1-9][0-9]{5}\b")

        # Ingest Datasets from CSV Database Manager (with fallback to class constants)
        self.reload_rules()

    def reload_rules(self) -> Dict[str, Any]:
        """
        Dynamically reloads statutory rules, approved units, prohibited imperial units,
        tax suffix patterns, and keywords from the CSV master database.
        """
        try:
            if db_manager is not None:
                db_manager.reload_master_datasets()
                self.approved_metric_units = set(self.APPROVED_METRIC_UNITS) | db_manager.approved_units_set
                self.unambiguous_imperial_units = dict(self.UNAMBIGUOUS_IMPERIAL_UNITS)
                self.unambiguous_imperial_units.update(db_manager.prohibited_units_dict)
                
                combined_tax = list(self.TAX_SUFFIX_PATTERNS) + [
                    p for p in db_manager.tax_suffix_patterns if p not in self.TAX_SUFFIX_PATTERNS
                ]
                self.tax_suffix_patterns = combined_tax
                self.tax_suffix_regex = re.compile(
                    r"(" + "|".join(self.tax_suffix_patterns) + r")", re.IGNORECASE
                )
                self.consumer_care_keywords = list(set(self.CONSUMER_CARE_KEYWORDS + db_manager.consumer_care_keywords))
                self.mfg_keywords = list(set(self.MFG_KEYWORDS + db_manager.mfg_keywords))
                self.master_rules = db_manager.master_rules
                return {"success": True, "message": "Statutory rules reloaded from CSV database."}
            else:
                raise ValueError("db_manager module unavailable")
        except Exception:
            # Safe Fallback to class defaults
            self.approved_metric_units = set(self.APPROVED_METRIC_UNITS)
            self.unambiguous_imperial_units = dict(self.UNAMBIGUOUS_IMPERIAL_UNITS)
            self.tax_suffix_patterns = list(self.TAX_SUFFIX_PATTERNS)
            self.tax_suffix_regex = re.compile(
                r"(" + "|".join(self.TAX_SUFFIX_PATTERNS) + r")", re.IGNORECASE
            )
            self.consumer_care_keywords = list(self.CONSUMER_CARE_KEYWORDS)
            self.mfg_keywords = list(self.MFG_KEYWORDS)
            self.master_rules = []
            return {"success": False, "message": "Loaded built-in default rules."}

    def reconstruct_cylindrical_fragments(self, raw_text: str) -> str:
        """
        Logically stitches fragmented OCR strings caused by cylindrical bottle curvature:
        - Stitches broken emails: ['customer', 'care', '@', 'herbal.com'] -> 'customercare@herbal.com'
        - Stitches broken phone numbers: ['1800', '222', '3333'] -> '1800-222-3333'
        - Stitches broken PIN codes: ['396', '195'] -> '396195'
        - Stitches broken dates: ['02', '/', '2026'] -> '02/2026'
        - Stitches broken net quantities: ['200', 'ml'] -> '200 ml'
        """
        t = raw_text

        # 1. Stitch fragmented emails
        t = re.sub(r'([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})', r'\1@\2.\3', t)
        t = re.sub(r'(?:customer|consumer)\s+care\s*@\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'customercare@\1', t, flags=re.I)
        t = re.sub(r'(help|support|contact|feedback|care|info|service)\s*@\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1@\2', t, flags=re.I)

        # 2. Stitch fragmented phone numbers
        t = re.sub(r'\b(1800|1860)\s*(\d{3,4})\s*(\d{3,4})\b', r'\1-\2-\3', t)
        t = re.sub(r'\b(?:\+91|91|0)?\s*([6-9]\d{4})\s*(\d{5})\b', r'\1\2', t)
        t = re.sub(r'\b(0\d{2,4})\s*(\d{6,8})\b', r'\1-\2', t)

        # 3. Stitch fragmented 6-digit Indian PIN codes (e.g. '396 195' -> '396195')
        t = re.sub(r'\b([1-9][0-9]{2})\s*([0-9]{3})\b', r'\1\2', t)

        # 4. Stitch fragmented dates (e.g. '02 / 2026' -> '02/2026')
        t = re.sub(r'\b(0[1-9]|1[0-2])\s*[\/\.-]\s*(20\d{2}|\d{2})\b', r'\1/\2', t)

        # 5. Stitch fragmented net quantities and tip sizes (e.g. '200 ml' -> '200 ml', '0.5 mm' -> '0.5 mm')
        t = re.sub(r'\b(\d+(?:\.\d+)?)\s*(m[l1|!]|g[mns]*|k[g9]|lt?r?s?|pens?|units?|pcs?|n)\b', r'\1 \2', t, flags=re.I)

        return t

    def extract_product_identifiers(self, full_text: str) -> Dict[str, str]:
        """
        Extracts product cataloging numbers (Art No, Item Code, Model No, Batch No, Barcode, etc.)
        """
        identifiers: Dict[str, str] = {}
        for pattern, key_name in self.PRODUCT_IDENTIFIER_PATTERNS:
            match = re.search(pattern, full_text)
            if match:
                val = match.group(1).strip()
                if val and key_name not in identifiers:
                    identifiers[key_name] = val
        return identifiers

    def sanitize_text_for_metric_scan(self, full_text: str) -> str:
        """
        Masks product identifiers, emails, URLs, dates, phone numbers to eliminate false unit matches.
        """
        cleaned = full_text
        cleaned = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", " [EMAIL_REMOVED] ", cleaned)
        cleaned = re.sub(
            r"https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.(?:co\.in|com|in|org|net|gov\.in|edu\.in)",
            " [URL_REMOVED] ",
            cleaned
        )
        for pattern, _ in self.PRODUCT_IDENTIFIER_PATTERNS:
            cleaned = re.sub(pattern, " [PRODUCT_IDENTIFIER_MASKED] ", cleaned)
        cleaned = re.sub(r"(?i)\b(?:art(?:\.|icle)?|item|model|style|code|ref|cat|no\.?|#)\s*[:=-]?\s*[a-zA-Z0-9\-_/]+", " [CODE_MASKED] ", cleaned)
        cleaned = re.sub(r"(?i)\b(?:iso\s*\d+(?::\d+)?|is\s*\d+(?::\d+)?)\b", " [STD_MASKED] ", cleaned)
        cleaned = re.sub(r"\b\d{1,2}[\/\.-]\d{2,4}\b", " [DATE_MASKED] ", cleaned)
        cleaned = self.phone_regex.sub(" [PHONE_MASKED] ", cleaned)
        return cleaned

    def detect_multilingual_profile(self, full_text: str) -> Dict[str, Any]:
        """
        Detects primary script, regional language, and multi-script presence across text.
        """
        script_counts = {script: 0 for script in self.SCRIPT_RANGES}
        latin_count = 0
        digit_count = 0

        for char in full_text:
            code = ord(char)
            if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
                latin_count += 1
            elif 0x0030 <= code <= 0x0039:
                digit_count += 1
            else:
                for script, (start_cp, end_cp) in self.SCRIPT_RANGES.items():
                    if start_cp <= code <= end_cp:
                        script_counts[script] += 1
                        break

        total_regional_chars = sum(script_counts.values())
        dominant_script = "Latin"
        dominant_lang = "en"
        lang_name = "English"

        if total_regional_chars > 0:
            top_script = max(script_counts.items(), key=lambda x: x[1])[0]
            if script_counts[top_script] > 0:
                dominant_script = top_script
                if top_script == "Devanagari":
                    if any(w in full_text for w in ["कमाल", "किरकोळ", "करांसह", "निव्वळ", "पॅकिंग", "तक्रार", "दिनांक"]):
                        dominant_lang = "mr"
                        lang_name = "Marathi (मराठी)"
                    else:
                        dominant_lang = "hi"
                        lang_name = "Hindi (हिंदी)"
                elif top_script == "Telugu":
                    dominant_lang = "te"
                    lang_name = "Telugu (తెలుగు)"
                elif top_script == "Bengali":
                    dominant_lang = "bn"
                    lang_name = "Bengali (বাংলা)"
                elif top_script == "Gurmukhi":
                    dominant_lang = "pa"
                    lang_name = "Punjabi (ਪੰਜਾਬੀ)"
                elif top_script == "Arabic":
                    dominant_lang = "ur"
                    lang_name = "Urdu (اردو)"
                elif top_script == "Tamil":
                    dominant_lang = "ta"
                    lang_name = "Tamil (தமிழ்)"
                elif top_script == "Gujarati":
                    dominant_lang = "gu"
                    lang_name = "Gujarati (ગુજરાતી)"
                elif top_script == "Kannada":
                    dominant_lang = "kn"
                    lang_name = "Kannada (ಕನ್ನಡ)"
                elif top_script == "Malayalam":
                    dominant_lang = "ml"
                    lang_name = "Malayalam (മലയാളം)"
                elif top_script == "Odia":
                    dominant_lang = "or"
                    lang_name = "Odia (ଓଡ଼ିଆ)"

        scripts_present = [s for s, count in script_counts.items() if count > 0]
        if latin_count > 0:
            scripts_present.append("Latin")

        return {
            "dominant_language": dominant_lang,
            "language_name": lang_name,
            "dominant_script": dominant_script,
            "is_multilingual": len(scripts_present) > 1 or total_regional_chars > 0,
            "scripts_present": scripts_present,
            "regional_char_count": total_regional_chars,
            "latin_char_count": latin_count
        }

    def evaluate_compliance(
        self,
        segments: List[Dict[str, Any]],
        image_dimensions: Optional[Tuple[int, int]] = None,
        manual_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes all verification pipelines and returns comprehensive audit report.
        Supports Hybrid AI + Manual Verification overrides to eliminate false positives.
        """
        violations: List[Dict[str, Any]] = []
        passed_checks: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        manual_fields_applied: List[str] = []

        extracted_metadata: Dict[str, Any] = {
            "brand_name": None,
            "mrp": None,
            "taxes_included": False,
            "net_quantity": None,
            "unit_of_measure": None,
            "dimensions": None,
            "manufacturing_date": None,
            "consumer_care_email": None,
            "consumer_care_phone": None,
            "consumer_care_address": None,
            "country_of_origin": None,
            "manufacturer_name": None,
            "article_number": None,
            "item_code": None,
            "model_number": None,
            "batch_number": None,
            "barcode": None,
            "detected_language": "en",
            "language_name": "English",
            "detected_script": "Latin",
            "manual_fields": []
        }

        # Combine text for holistic document scanning & apply cylindrical fragment reconstruction
        raw_text_joined = " \n ".join([seg.get("text", "") for seg in segments])
        full_text = self.reconstruct_cylindrical_fragments(raw_text_joined)
        full_text_lower = full_text.lower()
        normalized_condensed = re.sub(r"[^a-zA-Z0-9@.]+", "", full_text_lower)

        # Detect Multilingual Profile
        multilingual_profile = self.detect_multilingual_profile(full_text)
        extracted_metadata["detected_language"] = multilingual_profile["dominant_language"]
        extracted_metadata["language_name"] = multilingual_profile["language_name"]
        extracted_metadata["detected_script"] = multilingual_profile["dominant_script"]

        # Extract product identifiers (Art No, Item Code, Model No, Batch No)
        identifiers = self.extract_product_identifiers(full_text)
        if "art_number" in identifiers:
            extracted_metadata["article_number"] = identifiers["art_number"]
        if "item_code" in identifiers:
            extracted_metadata["item_code"] = identifiers["item_code"]
        if "model_number" in identifiers:
            extracted_metadata["model_number"] = identifiers["model_number"]
        if "batch_number" in identifiers:
            extracted_metadata["batch_number"] = identifiers["batch_number"]
        if "barcode" in identifiers:
            extracted_metadata["barcode"] = identifiers["barcode"]

        # Pipeline 1: Rule 6(1)(da) - MRP & Tax Suffix Clause (Fuzzy & Curvature Resilient)
        p1_res = self._check_rule_mrp(segments, full_text, full_text_lower, normalized_condensed)
        if p1_res["passed"]:
            passed_checks.append(p1_res["check"])
            extracted_metadata["mrp"] = p1_res["data"].get("mrp")
            extracted_metadata["taxes_included"] = p1_res["data"].get("taxes_included", False)
        else:
            violations.extend(p1_res["violations"])
            if p1_res.get("data"):
                extracted_metadata["mrp"] = p1_res["data"].get("mrp")
                extracted_metadata["taxes_included"] = p1_res["data"].get("taxes_included", False)

        # Pipeline 2: Rule 11 & 12 - Net Quantity Standards & Approved Metric Units
        p2_res = self._check_rule_net_quantity(segments, full_text, full_text_lower)
        if p2_res["passed"]:
            passed_checks.append(p2_res["check"])
            extracted_metadata["net_quantity"] = p2_res["data"].get("net_quantity")
            extracted_metadata["unit_of_measure"] = p2_res["data"].get("unit")
            extracted_metadata["dimensions"] = p2_res["data"].get("dimensions")
        else:
            violations.extend(p2_res["violations"])
            if p2_res.get("data"):
                extracted_metadata["net_quantity"] = p2_res["data"].get("net_quantity")
                extracted_metadata["unit_of_measure"] = p2_res["data"].get("unit")
                extracted_metadata["dimensions"] = p2_res["data"].get("dimensions")

        # Pipeline 3: Rule 6(1)(g) - Consumer Redressal Mechanism (Fragment Stitched & Resilient)
        p3_res = self._check_rule_consumer_care(segments, full_text, full_text_lower)
        if p3_res["passed"]:
            passed_checks.append(p3_res["check"])
            extracted_metadata["consumer_care_email"] = p3_res["data"].get("email")
            extracted_metadata["consumer_care_phone"] = p3_res["data"].get("phone")
        else:
            violations.extend(p3_res["violations"])
            if p3_res.get("data"):
                extracted_metadata["consumer_care_email"] = p3_res["data"].get("email")
                extracted_metadata["consumer_care_phone"] = p3_res["data"].get("phone")
        if p3_res.get("warnings"):
            warnings.extend(p3_res["warnings"])

        # Pipeline 4: Rule 6(1)(c) - Manufacturing & Packaging Timeline
        p4_res = self._check_rule_mfg_date(segments, full_text, full_text_lower)
        if p4_res["passed"]:
            passed_checks.append(p4_res["check"])
            extracted_metadata["manufacturing_date"] = p4_res["data"].get("date")
        else:
            violations.extend(p4_res["violations"])
            if p4_res.get("data"):
                extracted_metadata["manufacturing_date"] = p4_res["data"].get("date")

        # Pipeline 5: Font Size & Aspect Estimation (Rule 9 & Schedule II)
        p5_res = self._check_font_and_aspect(segments, image_dimensions)
        if p5_res["passed"]:
            passed_checks.append(p5_res["check"])
        else:
            if p5_res.get("violations"):
                violations.extend(p5_res["violations"])
        if p5_res.get("warnings"):
            warnings.extend(p5_res["warnings"])

        # Supplementary Clauses: Rule 6(10) Country of Origin & Manufacturer Scan
        self._check_supplementary_clauses(full_text, full_text_lower, extracted_metadata, passed_checks, warnings)

        rules_breakdown = {
            "rule_6_1_da_mrp": p1_res["passed"],
            "rule_11_12_net_quantity": p2_res["passed"],
            "rule_6_1_g_consumer_care": p3_res["passed"],
            "rule_6_1_c_mfg_date": p4_res["passed"],
            "rule_9_font_aspect": p5_res["passed"]
        }

        # =====================================================================
        # HYBRID AI + MANUAL VERIFICATION OVERLAY MERGE
        # Re-evaluates compliance rules against inspector-entered fields
        # =====================================================================
        if manual_overrides and isinstance(manual_overrides, dict):
            for field, val in manual_overrides.items():
                if val is not None and str(val).strip() != "":
                    manual_fields_applied.append(field)

            # 1. Brand / Commodity Name
            if manual_overrides.get("brand_name"):
                extracted_metadata["brand_name"] = str(manual_overrides["brand_name"]).strip()

            # 2. MRP & Tax Suffix Override
            if "mrp" in manual_overrides and manual_overrides["mrp"] is not None:
                mrp_val = str(manual_overrides["mrp"]).strip().replace("₹", "").replace("Rs.", "").strip()
                tax_incl = bool(manual_overrides.get("taxes_included", True))
                extracted_metadata["mrp"] = mrp_val
                extracted_metadata["taxes_included"] = tax_incl

                # Clear previous MRP violations
                violations = [v for v in violations if not v.get("rule_id", "").startswith("RULE_6_1_DA")]
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_6_1_DA"]

                if tax_incl:
                    passed_checks.append({
                        "rule_id": "RULE_6_1_DA",
                        "rule_name": "Rule 6(1)(da) - Maximum Retail Price (MRP)",
                        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(da)",
                        "description": "Maximum Retail Price declared with statutory tax inclusive clause.",
                        "evidence": f"Declared MRP: ₹ {mrp_val} (Inclusive of all taxes) [Inspector Verified]"
                    })
                    rules_breakdown["rule_6_1_da_mrp"] = True
                else:
                    violations.append({
                        "rule_id": "RULE_6_1_DA_TAX_SUFFIX_MISSING",
                        "rule_name": "Rule 6(1)(da) - Missing Statutory Tax Suffix",
                        "severity": "HIGH",
                        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(da)",
                        "description": "Price declared without mandatory 'Inclusive of all taxes' statutory clause.",
                        "found_text": f"MRP: ₹ {mrp_val} (Missing Tax Suffix)",
                        "remediation": "Print 'MRP ₹ [Price] (Inclusive of all taxes)' on the Principal Display Panel."
                    })
                    rules_breakdown["rule_6_1_da_mrp"] = False

            # 3. Net Quantity & Approved Metric Unit Override
            if "net_quantity" in manual_overrides and manual_overrides["net_quantity"] is not None:
                qty_val = str(manual_overrides["net_quantity"]).strip()
                unit_val = str(manual_overrides.get("unit_of_measure", "")).strip().lower()
                extracted_metadata["net_quantity"] = qty_val
                if unit_val:
                    extracted_metadata["unit_of_measure"] = unit_val

                violations = [v for v in violations if not v.get("rule_id", "").startswith("RULE_11_12")]
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_11_12_NET_QUANTITY"]

                # Check if unit is prohibited imperial
                is_prohibited = unit_val in self.UNAMBIGUOUS_IMPERIAL_UNITS or any(unit_val == k for k in self.UNAMBIGUOUS_IMPERIAL_UNITS)
                if is_prohibited:
                    violations.append({
                        "rule_id": "RULE_11_12_PROHIBITED_IMPERIAL",
                        "rule_name": "Rule 11 & 12 - Prohibited Non-Standard Unit",
                        "severity": "HIGH",
                        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & 12",
                        "description": f"Prohibited imperial unit '{unit_val}' declared.",
                        "found_text": f"{qty_val} {unit_val}",
                        "remediation": "Declare net quantity exclusively in approved SI metric units (e.g., g, kg, ml, l)."
                    })
                    rules_breakdown["rule_11_12_net_quantity"] = False
                else:
                    passed_checks.append({
                        "rule_id": "RULE_11_12_NET_QUANTITY",
                        "rule_name": "Rule 11 & 12 - Approved Metric SI Units",
                        "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & 12",
                        "description": "Net quantity is declared in approved standard SI units.",
                        "evidence": f"Declared Net Quantity: {qty_val} {unit_val or 'Units'} [Inspector Verified]"
                    })
                    rules_breakdown["rule_11_12_net_quantity"] = True

            # 4. Consumer Care Email & Phone Override
            if manual_overrides.get("consumer_care_email") or manual_overrides.get("consumer_care_phone"):
                email_val = manual_overrides.get("consumer_care_email")
                phone_val = manual_overrides.get("consumer_care_phone")
                if email_val:
                    extracted_metadata["consumer_care_email"] = str(email_val).strip()
                if phone_val:
                    extracted_metadata["consumer_care_phone"] = str(phone_val).strip()

                violations = [v for v in violations if not v.get("rule_id", "").startswith("RULE_6_1_G")]
                warnings = [w for w in warnings if not w.get("rule_id", "").startswith("RULE_6_1_G")]
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_6_1_G_CARE"]

                ev_parts = []
                if extracted_metadata["consumer_care_email"]:
                    ev_parts.append(f"Email: {extracted_metadata['consumer_care_email']}")
                if extracted_metadata["consumer_care_phone"]:
                    ev_parts.append(f"Phone: {extracted_metadata['consumer_care_phone']}")

                passed_checks.append({
                    "rule_id": "RULE_6_1_G_CARE",
                    "rule_name": "Rule 6(1)(g) - Consumer Care & Redressal Helpline",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(g)",
                    "description": "Consumer grievance redressal channel verified.",
                    "evidence": f"{' | '.join(ev_parts)} [Inspector Verified]"
                })
                rules_breakdown["rule_6_1_g_consumer_care"] = True

            # 5. Manufacturing / Packaging Date Override
            if manual_overrides.get("manufacturing_date"):
                mfg_val = str(manual_overrides["manufacturing_date"]).strip()
                extracted_metadata["manufacturing_date"] = mfg_val
                violations = [v for v in violations if not v.get("rule_id", "").startswith("RULE_6_1_C")]
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_6_1_C"]

                passed_checks.append({
                    "rule_id": "RULE_6_1_C",
                    "rule_name": "Rule 6(1)(c) - Manufacturing / Packaging Timeline",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(c)",
                    "description": "Month and Year of manufacture/packaging is verified.",
                    "evidence": f"Declared Timeline: {mfg_val} [Inspector Verified]"
                })
                rules_breakdown["rule_6_1_c_mfg_date"] = True

            # 6. Country of Origin Override
            if manual_overrides.get("country_of_origin"):
                origin_val = str(manual_overrides["country_of_origin"]).strip()
                extracted_metadata["country_of_origin"] = origin_val
                warnings = [w for w in warnings if w.get("rule_id") != "RULE_6_10_ORIGIN_ADVISORY"]
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_6_10_ORIGIN"]

                passed_checks.append({
                    "rule_id": "RULE_6_10_ORIGIN",
                    "rule_name": "Rule 6(10) - Country of Origin",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(10)",
                    "description": "Country of origin verified.",
                    "evidence": f"Declared Origin: {origin_val} [Inspector Verified]"
                })

            # 7. Manufacturer / Packer Name & Address Override
            if manual_overrides.get("manufacturer_name"):
                mfg_name = str(manual_overrides["manufacturer_name"]).strip()
                extracted_metadata["manufacturer_name"] = mfg_name
                passed_checks = [c for c in passed_checks if c.get("rule_id") != "RULE_6_1_A_MFG_NAME"]
                passed_checks.append({
                    "rule_id": "RULE_6_1_A_MFG_NAME",
                    "rule_name": "Rule 6(1)(a) - Name & Address of Manufacturer / Packer",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(a)",
                    "description": "Name of Manufacturer/Packer identified and verified.",
                    "evidence": f"Manufacturer/Packer: {mfg_name} [Inspector Verified]"
                })

        extracted_metadata["manual_fields"] = manual_fields_applied

        # Compute Overall Score and Verdict
        failed_critical_count = sum(1 for v in violations if v.get("severity") == "HIGH")
        failed_medium_count = sum(1 for v in violations if v.get("severity") == "MEDIUM")

        base_score = 100
        score_deductions = (failed_critical_count * 25) + (failed_medium_count * 15) + (len(warnings) * 3)
        overall_score = max(0, min(100, base_score - score_deductions))

        status = "COMPLIANT" if len(violations) == 0 else "NON_COMPLIANT"

        return {
            "status": status,
            "overall_score": overall_score,
            "timestamp": datetime.now().isoformat(),
            "is_manually_verified": len(manual_fields_applied) > 0,
            "manual_fields_applied": manual_fields_applied,
            "total_segments_analyzed": len(segments),
            "multilingual_profile": multilingual_profile,
            "violations": violations,
            "passed_checks": passed_checks,
            "warnings": warnings,
            "extracted_metadata": extracted_metadata,
            "rules_breakdown": rules_breakdown
        }

    # =========================================================================
    # PIPELINE 1: Rule 6(1)(da) - MRP & Statutory Tax Suffix (Curvature Resilient)
    # =========================================================================
    def _check_rule_mrp(
        self,
        segments: List[Dict[str, Any]],
        full_text: str,
        full_text_lower: str,
        normalized_condensed: str
    ) -> Dict[str, Any]:
        violations = []
        found_mrp = None

        has_tax_suffix = bool(self.tax_suffix_regex.search(full_text)) or bool(
            re.search(r"inc[l1i]?(?:of)?all(?:tax|ta|taxes)?", normalized_condensed) or
            re.search(r"alltax(?:es)?inc", normalized_condensed)
        )

        has_mrp_keyword = bool(
            re.search(r"\b(m\.?r\.?p\.?|mr\.?p|m\.?r\.?|max(?:imum)?\s+retail\s+price|retail\s+price|अधिकतम\s*खुदरा\s*मूल्य|अ\.?खु\.?मू\.?|एमआरपी|कमाल\s*किरकोळ\s*किंमत|గరిష్ట\s*రిటైల్\s*ధర|ధర|সর্বোচ্চ\s*খুচরা\s*মূল্য|ਵੱਧ\s*ਤੋਂ\s*ਵੱਧ\s*ਪ੍ਰਚੂਨ\s*ਮੁੱਲ|زیادہ\s*سے\s*زیادہ\s*خوردہ\s*قیمت|அதிகபட்ச\s*சில்லறை\s*விலை|કિંમત|ಬೆಲೆ|വില)\b", full_text, flags=re.IGNORECASE)
        )

        price_matches = self.price_regex.findall(full_text)
        if not price_matches:
            price_matches = self.standalone_price_regex.findall(full_text)

        if price_matches:
            found_mrp = price_matches[0]
            if isinstance(found_mrp, tuple):
                found_mrp = found_mrp[0]

        # Case 1: No MRP keyword or price found at all
        if not has_mrp_keyword and not found_mrp:
            violations.append({
                "rule_id": "RULE_6_1_DA_MISSING",
                "rule_name": "Rule 6(1)(da) - Mandatory MRP Declaration",
                "severity": "HIGH",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(da)",
                "description": "Maximum Retail Price (MRP) declaration is missing from the package display.",
                "found_text": "None detected",
                "remediation": "Print Maximum Retail Price clearly as 'MRP ₹ [Amount] (Inclusive of all taxes)' on the Principal Display Panel."
            })
            return {"passed": False, "violations": violations, "data": {"mrp": None, "taxes_included": False}}

        # Case 2: Price detected but missing mandatory tax inclusion suffix
        if not has_tax_suffix:
            violations.append({
                "rule_id": "RULE_6_1_DA_TAX_SUFFIX_MISSING",
                "rule_name": "Rule 6(1)(da) - Statutory Tax Inclusion Suffix",
                "severity": "HIGH",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(da)",
                "description": "MRP is stated without the mandatory statutory phrase 'Inclusive of all taxes' or 'Incl. of all taxes'.",
                "found_text": f"MRP: {found_mrp or 'Detected'} (Missing Tax Suffix)",
                "remediation": "Append the mandatory statutory text 'Inclusive of all taxes' or 'Incl. of all taxes' immediately adjacent to the price."
            })
            return {"passed": False, "violations": violations, "data": {"mrp": found_mrp, "taxes_included": False}}

        return {
            "passed": True,
            "check": {
                "rule_id": "RULE_6_1_DA",
                "rule_name": "Rule 6(1)(da) - Maximum Retail Price (MRP) & Tax Suffix",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(da)",
                "description": "Validated Maximum Retail Price format and mandatory statutory tax inclusion clause.",
                "evidence": f"Found MRP: ₹ {found_mrp or 'Declared'} with confirmed statutory tax suffix."
            },
            "data": {"mrp": found_mrp, "taxes_included": True}
        }

    # =========================================================================
    # PIPELINE 2: Rule 11 & 12 - Net Quantity Standards & Approved Metric Units
    # =========================================================================
    def _check_rule_net_quantity(
        self,
        segments: List[Dict[str, Any]],
        full_text: str,
        full_text_lower: str
    ) -> Dict[str, Any]:
        violations = []

        # 1. Prepare Sanitized Text for Imperial & Metric Unit Verification
        sanitized_text = self.sanitize_text_for_metric_scan(full_text)
        sanitized_lower = sanitized_text.lower()

        # 2. Check for Unambiguous Prohibited Imperial Units (oz, fl oz, lbs, gallon, quart, yard, inch)
        for imperial_unit, unit_desc in self.unambiguous_imperial_units.items():
            pattern = r"\b\d+(?:\.\d+)?\s*" + re.escape(imperial_unit) + r"\b"
            match = re.search(pattern, sanitized_lower)
            if match:
                violations.append({
                    "rule_id": "RULE_11_12_PROHIBITED_UNIT",
                    "rule_name": "Rule 11 & 12 - Prohibited Imperial Units Detected",
                    "severity": "HIGH",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & Rule 12",
                    "description": f"Found non-standard imperial measurement '{match.group(0)}'. {unit_desc}.",
                    "found_text": match.group(0),
                    "remediation": "Remove imperial units (oz, fl oz, lbs, etc.). All net quantities must be expressed strictly in standard SI metric units (g, kg, ml, l, N/units, cm)."
                })

        # 3. Context-Aware Evaluation of Ambiguous Imperial Abbreviations ('in', 'pt', 'ft')
        in_match_candidates = re.finditer(r"\b(\d+(?:\.\d+)?)\s*in\b", sanitized_lower)
        for cand in in_match_candidates:
            start_pos = cand.start()
            end_pos = cand.end()

            preceding_str = sanitized_lower[max(0, start_pos - 30):start_pos].strip()
            following_str = sanitized_lower[end_pos:min(len(sanitized_lower), end_pos + 30)].strip()
            following_first_word = following_str.split()[0].rstrip(".,;:") if following_str else ""

            is_preceded_by_phrase = any(verb in preceding_str for verb in self.IN_PRECEDING_VERBS)
            is_followed_by_target = (
                following_first_word in self.IN_PREPOSITION_FOLLOWERS or
                re.match(r"^(?:19|20)\d{2}\b", following_first_word) is not None or
                following_first_word.isdigit()
            )

            is_explicit_dimension = bool(
                re.search(r"\b(?:size|length|width|height|depth|dia|diameter|screen|display|dimensions?)\s*[\.:=-]*\s*$", preceding_str) or
                re.match(r"^[x×]\s*\d+", following_str)
            )

            if not is_preceded_by_phrase and not is_followed_by_target and is_explicit_dimension:
                violations.append({
                    "rule_id": "RULE_11_12_PROHIBITED_UNIT",
                    "rule_name": "Rule 11 & 12 - Prohibited Imperial Units Detected",
                    "severity": "HIGH",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & Rule 12",
                    "description": f"Found non-standard imperial measurement '{cand.group(0)}'. Inch (Imperial Unit - Non-standard under Rule 11).",
                    "found_text": cand.group(0),
                    "remediation": "Express linear dimensions and sizes strictly in standard metric units (mm, cm, m) rather than inches."
                })

        # 4. Context-Aware Evaluation of Ambiguous 'pt' (Pint vs Point/Part)
        pt_match_candidates = re.finditer(r"\b(\d+(?:\.\d+)?)\s*pt\b", sanitized_lower)
        for cand in pt_match_candidates:
            start_pos = cand.start()
            preceding_str = sanitized_lower[max(0, start_pos - 30):start_pos].strip()
            is_volume_context = any(kw in preceding_str for kw in ["vol", "volume", "capacity", "net qty", "liquid"])
            is_part_no = any(kw in preceding_str for kw in ["part", "pt", "font", "point", "ref"])
            if is_volume_context and not is_part_no:
                violations.append({
                    "rule_id": "RULE_11_12_PROHIBITED_UNIT",
                    "rule_name": "Rule 11 & 12 - Prohibited Imperial Units Detected",
                    "severity": "HIGH",
                    "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & Rule 12",
                    "description": f"Found non-standard imperial measurement '{cand.group(0)}'. Pint (Imperial Unit - Prohibited under Rule 11).",
                    "found_text": cand.group(0),
                    "remediation": "Express liquid volumes strictly in millilitres (ml) or litres (l) rather than pints."
                })

        # 5. Extract Approved SI Metric Units & Dimensions (with Bottle Curvature & Partial Word Tolerance)
        detected_metric_unit = None
        detected_qty_val = None
        detected_dimensions = None

        # Check for Dimensions (e.g. Size: 20 x 28 cm, 140 mm x 10 mm)
        size_match = re.search(
            r"(?:size|dimensions?|dim)[\s.:=-]*(\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?(?:\s*(?:x|×)\s*\d+(?:\.\d+)?)?\s*(?:cm|mm|m)?)",
            full_text_lower
        )
        if size_match:
            detected_dimensions = size_match.group(1).strip()

        # Check for Tip Size / Writing Instrument Dimensions (e.g. 0.5 mm tip, 1.0 mm)
        tip_match = re.search(
            r"(\d+(?:\.\d+)?\s*mm)\s*(?:tip|ball\s*tip|gel\s*tip|point|nib|line\s*width)?",
            full_text_lower
        )
        if tip_match and not detected_dimensions:
            detected_dimensions = f"Tip Size: {tip_match.group(1).strip()}"

        # Check for Stationery / Paper Pages & Sheets (e.g. 428 Pages, 160 Sheets)
        pages_match = re.search(
            r"(?:pages?|sheets?|leaves|nos?|count)[\s.:=-]*(\d+)",
            full_text_lower
        )
        if pages_match:
            detected_qty_val = pages_match.group(1).strip()
            detected_metric_unit = "Pages / Units"

        # Check for Stationery / Pens / Writing Instruments count (e.g. 1 N, 2 N, 1 Pen, 5 Pens, 1 Pc)
        pen_qty_match = re.search(
            r"(?:(?:net\s*(?:qty|quantity|content|wt|weight)?\s*[\.:=-]*\s*)?(\d+(?:\.\d+)?)\s*(n|pens?|refills?|pencils?|markers?|units?|u|pcs?|pieces?|sets?))\b",
            full_text_lower
        )
        if pen_qty_match and not detected_qty_val:
            detected_qty_val = pen_qty_match.group(1).strip()
            detected_metric_unit = pen_qty_match.group(2).strip().upper()

        # Check for Liquid Volume / Weight with Curvature Partial Tolerance (e.g. '200 ml', '500ml', '100g', '250 gm')
        if not detected_qty_val:
            cylinder_metric_pattern = re.compile(
                r"(?:(?:net\s*(?:qty|quantity|content|wt|weight|vol|volume|cont|w|v)?\s*[\.:=-]*\s*)?(\d+(?:\.\d+)?)\s*(ml|mls|millilitre|millilitres|l|ltr|ltrs|litre|litres|g|gm|gms|gram|grams|kg|kgs|kilogram|n|units?|pcs?|pieces?|tab|tablet|tablets|cap|capsule|capsules))\b",
                re.IGNORECASE
            )
            for match in cylinder_metric_pattern.finditer(sanitized_text):
                val = match.group(1)
                unit_candidate = match.group(2).strip().lower().rstrip(".,")
                if unit_candidate in self.APPROVED_METRIC_UNITS:
                    detected_qty_val = val
                    detected_metric_unit = unit_candidate
                    break

        # Check for Regional Script Metric Quantity (Hindi, Marathi, Telugu, Bengali, Punjabi, Urdu, Tamil, Gujarati, Kannada)
        if not detected_qty_val:
            regional_units_regex = (
                r"(?:(?:शुद्ध\s*मात्रा|निव्वळ\s*वजन|పరిమాణం|నెట్\s*క్వాంటిటీ|నిట్\s*পরিমাণ|ਸ਼ੁੱਧ\s*ਮਾਤਰਾ|خالص\s*مقدار|నెం|వాల్యూమ్)?\s*[\.:=-]*\s*)?"
                r"(\d+(?:\.\d+)?)\s*"
                r"(ग्राम|किग्रा|कि\.ग्रा\.|कि\.ग्रॅ\.|किग्रॅ|ग्रॅम|ग्रॅ\.|मिली|मि\.ली\.|लीटर|ली\.|नग|संख्या|"
                r"గ్రాములు|గ్రా|మి\.లీ|మిలీ|లీటర్|కేజీ|కిలో|కిలోలు|సంఖ్య|"
                r"গ্রাম|কেজি|মিলি|লিটার|সংখ্যা|"
                r"ਗ੍ਰਾਮ|ਕਿਲੋ|ਮਿਲੀ|ਲਿਟਰ|ਨੰਬਰ|"
                r"گرام|کلو|ملی|لیٹر|"
                r"கிராம்|கிலோ|மில்லி|லிட்டர்|"
                r"ગ્રામ|કિલો|મિલી|લીટર|"
                r"ಗ್ರಾಂ|ಕೆಜಿ|ಮಿಲಿ|ಲೀಟರ್)"
            )
            reg_match = re.search(regional_units_regex, full_text, flags=re.UNICODE | re.IGNORECASE)
            if reg_match:
                detected_qty_val = reg_match.group(1).strip()
                detected_metric_unit = reg_match.group(2).strip()

        if violations:
            return {
                "passed": False,
                "violations": violations,
                "data": {"net_quantity": detected_qty_val, "unit": detected_metric_unit, "dimensions": detected_dimensions}
            }

        if not detected_metric_unit and not detected_dimensions:
            violations.append({
                "rule_id": "RULE_11_12_NO_VALID_METRIC",
                "rule_name": "Rule 11 & 12 - Net Quantity Declaration",
                "severity": "HIGH",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & Rule 12",
                "description": "Standard net quantity in approved SI units (g, kg, ml, l, N/units/pcs/pages/pens) was not identified.",
                "found_text": "Missing valid metric quantity statement",
                "remediation": "Provide net quantity clearly in standard units: grams (g), kilograms (kg), millilitres (ml), litres (l), or count (N / Units / Pens / Pcs / Pages)."
            })
            return {
                "passed": False,
                "violations": violations,
                "data": {"net_quantity": None, "unit": None, "dimensions": None}
            }

        evidence_str = f"Declared Quantity: {detected_qty_val or ''} {detected_metric_unit or ''}".strip()
        if detected_dimensions:
            if evidence_str:
                evidence_str += f" | Dimensions: {detected_dimensions}"
            else:
                evidence_str = f"Dimensions: {detected_dimensions}"

        return {
            "passed": True,
            "check": {
                "rule_id": "RULE_11_12",
                "rule_name": "Rule 11 & 12 - Net Quantity & Metric Standards",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 11 & Rule 12",
                "description": "Net quantity and dimensions declared in standard statutory metric units.",
                "evidence": evidence_str.strip()
            },
            "data": {"net_quantity": detected_qty_val, "unit": detected_metric_unit, "dimensions": detected_dimensions}
        }

    # =========================================================================
    # PIPELINE 3: Rule 6(1)(g) - Consumer Redressal Mechanism (Fuzzy & Resilient)
    # =========================================================================
    def _check_rule_consumer_care(
        self,
        segments: List[Dict[str, Any]],
        full_text: str,
        full_text_lower: str
    ) -> Dict[str, Any]:
        """
        Validates Consumer Care Grievance Redressal under Rule 6(1)(g).
        Fuzzy-Matching Policy:
        - Stitches fragmented tokens ('customer', 'care', '@', 'domain.com').
        - DO NOT declare 'Consumer Care Missing' if any email (e.g. care@, help@, support@)
          or a 10-digit phone number / helpline is present near manufacturing details.
        - If at least one redressal channel (Email or Phone) is present, the rule PASSES.
        - If one sub-channel is absent, raise a Low Severity Advisory instead of a High Severity Infringement.
        """
        violations = []
        warnings = []

        has_care_keyword = any(kw in full_text_lower for kw in self.consumer_care_keywords)
        emails = self.email_regex.findall(full_text)
        valid_email = emails[0] if emails else None

        phones = self.phone_regex.findall(full_text)
        clean_phones = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 8]
        valid_phone = clean_phones[0] if clean_phones else None

        has_web = bool(re.search(r"\b[a-zA-Z0-9.-]+\.(?:co\.in|com|in|org|net)\b", full_text_lower))

        has_any_contact = bool(valid_email or valid_phone or has_web or has_care_keyword)

        # Case 1: Absolutely NO contact information or grievance mechanism detected
        if not has_any_contact:
            violations.append({
                "rule_id": "RULE_6_1_G_MISSING_ALL",
                "rule_name": "Rule 6(1)(g) - Consumer Care Mechanism Missing",
                "severity": "HIGH",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(g)",
                "description": "No consumer care or grievance redressal contact information was detected on the package.",
                "found_text": "None detected",
                "remediation": "Provide name, address, valid telephone helpline number, and email address of the consumer grievance redressal officer."
            })
            return {
                "passed": False,
                "violations": violations,
                "warnings": warnings,
                "data": {"email": None, "phone": None}
            }

        # Case 2: Contact channel detected (e.g. care@ email or phone number)
        if not valid_email and valid_phone:
            warnings.append({
                "rule_id": "RULE_6_1_G_EMAIL_ADVISORY",
                "rule_name": "Rule 6(1)(g) - Consumer Grievance Email Channel Advisory",
                "severity": "LOW",
                "description": f"Telephonic helpline ({valid_phone}) verified. Dedicating an explicit consumer grievance email address (e.g. care@company.in) is recommended under Rule 6(1)(g).",
                "recommendation": "Mention a dedicated consumer care email address prominently on the label."
            })
        elif valid_email and not valid_phone:
            warnings.append({
                "rule_id": "RULE_6_1_G_HELPLINE_ADVISORY",
                "rule_name": "Rule 6(1)(g) - Consumer Helpline Number Advisory",
                "severity": "LOW",
                "description": f"Consumer care email ({valid_email}) verified. Providing a dedicated telephonic helpline / toll-free number is recommended under Rule 6(1)(g).",
                "recommendation": "Provide a telephonic helpline number (e.g. 1800-XXX-XXXX or local office phone) for consumer queries."
            })

        evidence_parts = []
        if valid_email:
            evidence_parts.append(f"Email: {valid_email}")
        if valid_phone:
            evidence_parts.append(f"Helpline: {valid_phone}")
        if not evidence_parts and has_web:
            evidence_parts.append("Web Portal Declared")

        return {
            "passed": True,
            "check": {
                "rule_id": "RULE_6_1_G",
                "rule_name": "Rule 6(1)(g) - Consumer Grievance Redressal",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(g)",
                "description": "Consumer grievance redressal channel verified on package.",
                "evidence": " | ".join(evidence_parts) if evidence_parts else "Consumer Redressal Declared"
            },
            "warnings": warnings,
            "violations": violations,
            "data": {"email": valid_email, "phone": valid_phone}
        }

    # =========================================================================
    # PIPELINE 4: Rule 6(1)(c) - Manufacturing & Packaging Timeline
    # =========================================================================
    def _check_rule_mfg_date(
        self,
        segments: List[Dict[str, Any]],
        full_text: str,
        full_text_lower: str
    ) -> Dict[str, Any]:
        violations = []

        date_patterns = [
            r"(?:mfd\.?\s*on|mfg\.?\s*on|pkd\.?\s*on|mfd|mfg|pkd|packed|pkg|exp|use\s*before|best\s*before)[\s.:=-]*((?:0[1-9]|1[0-2])[\/\.-](?:20\d{2}|\d{2})|(?:[a-zA-Z]{3,9})[\s,.-]+(?:20\d{2}|\d{2}))",
            r"\b(?:0[1-9]|1[0-2])[\/\.-](?:20\d{2}|\d{2})\b",
            r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[\s,.-]+(?:20\d{2}|\d{2})\b"
        ]

        found_date_str = None
        for pat in date_patterns:
            match = re.search(pat, full_text, re.IGNORECASE)
            if match:
                found_date_str = match.group(1) if match.lastindex else match.group(0)
                break

        has_mfg_keyword = any(kw in full_text_lower for kw in self.mfg_keywords)

        if not found_date_str and not has_mfg_keyword:
            violations.append({
                "rule_id": "RULE_6_1_C_MISSING_DATE",
                "rule_name": "Rule 6(1)(c) - Manufacturing / Packaging Date Missing",
                "severity": "HIGH",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(c)",
                "description": "Month and Year of manufacture, packaging, or import is not declared on the package.",
                "found_text": "None detected",
                "remediation": "Print Month and Year of manufacture / packaging clearly (e.g., 'Mfd. on : 04/2025' or 'Mfg Date: 03/2026')."
            })
            return {
                "passed": False,
                "violations": violations,
                "data": {"date": None}
            }

        return {
            "passed": True,
            "check": {
                "rule_id": "RULE_6_1_C",
                "rule_name": "Rule 6(1)(c) - Manufacturing / Packaging Timeline",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(c)",
                "description": "Month and Year of manufacture/packaging is verified.",
                "evidence": f"Declared Timeline: {found_date_str or 'Declared on package'}"
            },
            "data": {"date": found_date_str}
        }

    # =========================================================================
    # PIPELINE 5: Font Size & Aspect Ratio Estimation (Rule 9 & Schedule II)
    # =========================================================================
    def _check_font_and_aspect(
        self,
        segments: List[Dict[str, Any]],
        image_dimensions: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        warnings = []
        violations = []

        if not segments:
            return {"passed": True, "check": {"rule_id": "RULE_9", "rule_name": "Rule 9 - Font Size & Layout", "evidence": "No segments to calculate."}, "warnings": []}

        img_h = image_dimensions[0] if (image_dimensions and image_dimensions[0] > 0) else 1000
        heights = []
        small_text_segments = []

        for seg in segments:
            box = seg.get("box", [])
            text = seg.get("text", "")
            if len(box) >= 4:
                y_coords = [pt[1] for pt in box]
                box_h = max(y_coords) - min(y_coords)
                height_ratio = box_h / float(img_h)
                heights.append((text, box_h, height_ratio))

                is_key_clause = any(k in text.lower() for k in ["mrp", "rs.", "₹", "net", "qty", "customer", "care", "mfg", "mfd", "pkd", "pages", "art"])
                if is_key_clause and height_ratio < 0.012 and len(text.strip()) > 3:
                    small_text_segments.append(text)

        avg_box_height = sum([h[1] for h in heights]) / max(1, len(heights))

        if small_text_segments:
            warnings.append({
                "rule_id": "RULE_9_FONT_SIZE_WARNING",
                "rule_name": "Rule 9 & Schedule II - Minimum Font Height Advisory",
                "severity": "LOW",
                "description": f"Text size for statutory declarations appears below recommended height threshold ({len(small_text_segments)} declarations found in micro-font).",
                "affected_declarations": small_text_segments[:3],
                "recommendation": "Ensure numeral and letter heights meet statutory minimums (1.0mm to 6.0mm depending on package size/weight under Schedule II)."
            })

        return {
            "passed": True,
            "check": {
                "rule_id": "RULE_9_LAYOUT",
                "rule_name": "Rule 9 & Schedule II - Display Area & Font Legibility",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 9",
                "description": "Principal Display Panel layout and font height aspect ratio estimated.",
                "evidence": f"Estimated Average Font Box Height: {avg_box_height:.1f}px across {len(segments)} segments."
            },
            "warnings": warnings,
            "violations": violations
        }

    # =========================================================================
    # SUPPLEMENTARY CLAUSES: Rule 6(10) Country of Origin & Manufacturer Scan
    # =========================================================================
    def _check_supplementary_clauses(
        self,
        full_text: str,
        full_text_lower: str,
        extracted_metadata: Dict[str, Any],
        passed_checks: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]]
    ):
        """
        Validates Country of Origin under Rule 6(10).
        Fuzzy & Inference Logic:
        - If explicit 'Country of Origin: India' / 'Made in India' -> PASS cleanly.
        - If Indian state (e.g. Gujarat, Maharashtra, MH) or 6-digit PIN code is detected,
          infer Country as India, mark as PASSED, and raise ONLY a 'Low Severity Advisory'
          recommending explicit addition of 'India' for strict compliance.
        """
        origin_match = re.search(
            r"(?:country\s+of\s+origin|made\s+in|product\s+of|origin\s*:)[\s.:=-]+([a-zA-Z\s]+)",
            full_text_lower
        )

        has_explicit_india = (
            "india" in full_text_lower or
            "bharat" in full_text_lower or
            "भारत" in full_text or
            "భారతదేశం" in full_text or
            "భారత్" in full_text or
            "ভারত" in full_text or
            "ਭਾਰਤ" in full_text or
            "ہندوستان" in full_text or
            "இந்தியா" in full_text or
            "ભારત" in full_text or
            "ಭಾರತ" in full_text or
            ".co.in" in full_text_lower or
            ".gov.in" in full_text_lower
        )

        detected_state_or_city = None
        for loc in self.INDIAN_STATES_AND_UTS:
            if re.search(r"\b" + re.escape(loc) + r"\b", full_text_lower):
                detected_state_or_city = loc.title()
                break

        pincode_match = self.pincode_regex.search(full_text)
        detected_pincode = pincode_match.group(0) if pincode_match else None

        if origin_match and not has_explicit_india:
            origin_country = origin_match.group(1).split("\n")[0].strip().title()
            extracted_metadata["country_of_origin"] = origin_country
            passed_checks.append({
                "rule_id": "RULE_6_10_ORIGIN",
                "rule_name": "Rule 6(10) - Country of Origin",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(10)",
                "description": "Country of Origin declared clearly.",
                "evidence": f"Declared Origin: {origin_country}"
            })
        elif has_explicit_india:
            extracted_metadata["country_of_origin"] = "India"
            passed_checks.append({
                "rule_id": "RULE_6_10_ORIGIN",
                "rule_name": "Rule 6(10) - Country of Origin",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(10)",
                "description": "Country of Origin identified.",
                "evidence": "Declared Origin: India"
            })
        elif detected_state_or_city or detected_pincode:
            extracted_metadata["country_of_origin"] = "India (Inferred from Address & PIN Code)"
            location_desc = []
            if detected_state_or_city:
                location_desc.append(f"State/City: {detected_state_or_city}")
            if detected_pincode:
                location_desc.append(f"PIN Code: {detected_pincode}")

            passed_checks.append({
                "rule_id": "RULE_6_10_ORIGIN",
                "rule_name": "Rule 6(10) - Country of Origin",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(10)",
                "description": "Country of Origin inferred as India from domestic manufacturer address.",
                "evidence": f"Inferred Origin: India ({', '.join(location_desc)})"
            })

            warnings.append({
                "rule_id": "RULE_6_10_ORIGIN_ADVISORY",
                "rule_name": "Rule 6(10) - Country of Origin Advisory",
                "severity": "LOW",
                "description": f"Country of origin inferred as 'India' from domestic manufacturer address ({', '.join(location_desc)}).",
                "recommendation": "Print explicit statutory phrase 'Country of Origin: India' on the Principal Display Panel as per Rule 6(10) for strict compliance."
            })
        else:
            warnings.append({
                "rule_id": "RULE_6_10_ORIGIN_ADVISORY",
                "rule_name": "Rule 6(10) - Country of Origin Advisory",
                "severity": "LOW",
                "description": "Explicit 'Country of Origin' declaration keyword was not detected on the panel.",
                "recommendation": "Mention 'Country of Origin: India' or originating nation as per Rule 6(10)."
            })

        # Manufacturer / Packer
        mfg_name_match = re.search(
            r"(?:mfd\s+by|manufactured\s+by|packed\s+by|marketed\s+by|pkg\s+by|industries)[\s.:=-]+([^\n\r,]+)",
            full_text_lower
        )
        if mfg_name_match:
            extracted_metadata["manufacturer_name"] = mfg_name_match.group(0).strip().title()
            passed_checks.append({
                "rule_id": "RULE_6_1_A_MFG_NAME",
                "rule_name": "Rule 6(1)(a) - Name & Address of Manufacturer / Packer",
                "legal_reference": "Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)(a)",
                "description": "Name of Manufacturer/Packer identified on package.",
                "evidence": f"Manufacturer/Packer: {extracted_metadata['manufacturer_name']}"
            })
