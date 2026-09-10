"""Pydantic request/response schemas and the role vocabulary."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #

class Role(str, Enum):
    INSPECTOR = "INSPECTOR"
    SENIOR_OFFICER = "SENIOR_OFFICER"
    ADMIN = "ADMIN"


#: Rank order used by `require_role`. A higher rank satisfies every lower one.
ROLE_RANK: Dict[str, int] = {
    Role.INSPECTOR.value: 1,
    Role.SENIOR_OFFICER.value: 2,
    Role.ADMIN.value: 3,
}

ROLE_LABELS: Dict[str, str] = {
    Role.INSPECTOR.value: "Legal Metrology Inspector",
    Role.SENIOR_OFFICER.value: "Senior Enforcement Officer",
    Role.ADMIN.value: "System Administrator",
}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

#: Rejected outright regardless of length. These are what a credential-stuffing
#: list tries first, and an enforcement portal is a public-facing target.
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "letmein", "welcome1", "admin123", "iloveyou", "abc12345",
    "legalmetrology", "consumeraffairs",
}


def validate_password_strength(password: str) -> str:
    """
    Requires length plus variety, and rejects the obvious guesses.

    Length alone is a weak rule: "password" clears an 8-character minimum, and it
    is the first thing any attacker tries.
    """
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")

    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS or lowered.strip("0123456789!@#$") in _COMMON_PASSWORDS:
        raise ValueError("That password is too common. Choose something less guessable.")

    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 3:
        raise ValueError(
            "Use at least three of: lower case, upper case, digits, symbols."
        )
    return password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    full_name: str = Field(min_length=2, max_length=120)
    designation: str = Field(default="", max_length=120)
    jurisdiction: str = Field(default="", max_length=120)
    role: Role = Role.INSPECTOR

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    role_label: str = ""
    designation: str = ""
    jurisdiction: str = ""
    is_active: bool = True
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserPublic


# --------------------------------------------------------------------------- #
# Enforcement case lifecycle
# --------------------------------------------------------------------------- #

class CaseStatus(str, Enum):
    """
    Where an inspection sits in the enforcement process.

    A scan by itself is a finding, not an outcome. The problem statement asks for a
    dashboard monitoring "inspections, violations and enforcement activities" -
    activities means what happened next, which requires tracking it.
    """
    OPEN = "OPEN"                      # recorded, no action taken yet
    NOTICE_ISSUED = "NOTICE_ISSUED"    # statutory notice served on the packer/seller
    COMPLIED = "COMPLIED"              # re-inspected and found corrected
    ESCALATED = "ESCALATED"            # referred for prosecution / compounding
    CLOSED = "CLOSED"                  # no further action (incl. false positives)


#: Transitions an officer may make. Anything not listed is refused, so a case
#: cannot jump from OPEN straight to COMPLIED without a notice, and a closed case
#: cannot be quietly reopened into an active state.
CASE_TRANSITIONS: Dict[str, List[str]] = {
    CaseStatus.OPEN.value: [CaseStatus.NOTICE_ISSUED.value, CaseStatus.CLOSED.value],
    CaseStatus.NOTICE_ISSUED.value: [
        CaseStatus.COMPLIED.value, CaseStatus.ESCALATED.value, CaseStatus.CLOSED.value,
    ],
    CaseStatus.COMPLIED.value: [CaseStatus.CLOSED.value],
    CaseStatus.ESCALATED.value: [CaseStatus.CLOSED.value],
    CaseStatus.CLOSED.value: [],
}

CASE_STATUS_LABELS: Dict[str, str] = {
    CaseStatus.OPEN.value: "Open",
    CaseStatus.NOTICE_ISSUED.value: "Notice issued",
    CaseStatus.COMPLIED.value: "Complied",
    CaseStatus.ESCALATED.value: "Escalated",
    CaseStatus.CLOSED.value: "Closed",
}


class PremisesType(str, Enum):
    RETAIL = "RETAIL"
    SUPERMARKET = "SUPERMARKET"
    WHOLESALE = "WHOLESALE"
    WAREHOUSE = "WAREHOUSE"
    ECOMMERCE = "ECOMMERCE"
    OTHER = "OTHER"


class InspectionContext(BaseModel):
    """
    Where and in what circumstances the package was found.

    A compliance finding with no record of the premises is evidentially thin: a
    notice under the Act is served on a person at a place, and "this pack was
    non-compliant" does not say whose pack, in whose shop, on what date. This is
    submitted alongside a scan.
    """
    premises_name: str = Field(default="", max_length=200)
    premises_address: str = Field(default="", max_length=400)
    premises_type: PremisesType = PremisesType.RETAIL
    premises_licence: str = Field(default="", max_length=80, description="Trade/GST/Legal Metrology licence, if shown")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    location_accuracy_m: Optional[float] = Field(default=None, ge=0)
    remarks: str = Field(default="", max_length=2000)


class CaseUpdateRequest(BaseModel):
    case_status: CaseStatus
    note: str = Field(default="", max_length=2000)
    notice_reference: str = Field(default="", max_length=120)


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #

class SegmentModel(BaseModel):
    text: str
    confidence: float = 0.0
    box: Optional[List[List[float]]] = None
    height_ratio: Optional[float] = None


class TextAnalysisRequest(BaseModel):
    """Used by the browser-OCR fallback: the client extracts text, the server rules on it."""
    raw_text: str = ""
    segments: Optional[List[Dict[str, Any]]] = None
    filename: str = "manual_entry.txt"
    image_dimensions: Optional[List[int]] = None
    source: str = "manual"
    persist: bool = True
    #: Where the package was found. Typing a label by hand still happens in a
    #: shop, so this route needs the premises as much as a photo scan does.
    context: Optional["InspectionContext"] = None


class ListingAnalysisRequest(BaseModel):
    """
    E-commerce product listing ingestion.

    Accepts pasted listing text or raw HTML. The server deliberately does NOT
    fetch a user-supplied URL: that would be a server-side request forgery hole,
    and a marketplace page is JS-rendered anyway. `source_url` is recorded as
    provenance metadata only.
    """
    listing_text: str = ""
    listing_html: str = ""
    source_url: str = ""
    platform: str = ""
    product_title: str = ""
    persist: bool = True
    context: Optional["InspectionContext"] = None


class ReAuditRequest(BaseModel):
    """Inspector correction pass: re-run the rules with human-verified field values."""
    inspection_id: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None
    image_dimensions: Optional[List[int]] = None
    manual_overrides: Dict[str, Any] = Field(default_factory=dict)


class InspectionSummary(BaseModel):
    id: str
    created_at: str
    status: str
    overall_score: int
    product_name: str = ""
    brand: str = ""
    violations_count: int = 0
    violation_rule_ids: List[str] = Field(default_factory=list)
    officer_id: str = ""
    officer_name: str = ""
    source: str = "image"
    evidence_ids: List[str] = Field(default_factory=list)
    is_manually_verified: bool = False
    case_number: str = ""
    case_status: str = ""
    premises_name: str = ""


class PaginatedInspections(BaseModel):
    items: List[InspectionSummary]
    total: int
    page: int
    page_size: int
    pages: int
