"""Pydantic request/response schemas and the role vocabulary."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


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

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(min_length=2, max_length=120)
    designation: str = Field(default="", max_length=120)
    jurisdiction: str = Field(default="", max_length=120)
    role: Role = Role.INSPECTOR


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


class PaginatedInspections(BaseModel):
    items: List[InspectionSummary]
    total: int
    page: int
    page_size: int
    pages: int
