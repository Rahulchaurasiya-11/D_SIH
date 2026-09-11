"""
Statutory rule catalogue.

The rule set lives in CSV files under `app/data/`, not in code, so a Legal Metrology
officer can amend a penalty band or add a regional keyword without a developer and
without a redeploy. `POST /rules/reload` re-reads them into the running engine.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.db import repositories as repo
from app.db.db_manager import db_manager
from app.db.store import backend_name
from app.deps import get_current_user, require_role
from app.models import Role

router = APIRouter(prefix="/rules", tags=["Statutory rules"])


@router.get("/database")
def get_rules_database(_: Dict[str, Any] = Depends(get_current_user)):
    """The full statutory knowledge base backing the compliance engine."""
    return {
        "success": True,
        "master_rules": db_manager.master_rules,
        "approved_units": db_manager.approved_units_list,
        "approved_units_count": len(db_manager.approved_units_set),
        "prohibited_units": db_manager.prohibited_units_dict,
        "prohibited_units_count": len(db_manager.prohibited_units_dict),
        "tax_suffix_patterns_count": len(db_manager.tax_suffix_patterns),
        "consumer_care_keywords_count": len(db_manager.consumer_care_keywords),
        "mfg_keywords_count": len(db_manager.mfg_keywords),
        "storage_mode": backend_name(),
    }


@router.post("/reload")
def reload_rules(user: Dict[str, Any] = Depends(require_role(Role.ADMIN))):
    """
    Hot-reloads the CSV knowledge base into the running engine. Admin only: changing
    the rule set changes what counts as a contravention.
    """
    from app.api.v1.inspections import engine

    summary = engine.reload_rules()
    repo.audit_log.record(user["id"], user.get("full_name", ""), "RULES_RELOADED",
                          detail="rules=%s" % summary.get("loaded_rules_count", "?"))
    return {
        "success": True,
        "message": "Statutory rules and metric datasets reloaded from CSV.",
        "reload_summary": summary,
        "database_status": db_manager.get_database_status(),
    }


@router.get("/audit-log")
def audit_trail(limit: int = 100, _: Dict[str, Any] = Depends(require_role(Role.SENIOR_OFFICER))):
    """System audit trail: who scanned, revised, exported or changed what."""
    entries = repo.audit_log.recent(limit=limit)
    return {"success": True, "count": len(entries), "entries": entries}
