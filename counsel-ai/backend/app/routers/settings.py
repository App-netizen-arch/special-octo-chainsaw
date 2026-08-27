"""Settings router: onboarding data, jurisdictions, firm policy, data wipe."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import (
    DEFAULT_FIRM_SETTINGS,
    firm_settings,
    record_audit,
    session_scope,
    set_firm_setting,
    wipe_all_data,
)
from ..deps import current_user, require_admin
from ..models.db import User
from ..utils.encryption import secure_wipe_dir
from ..utils.domain_whitelist import LEGAL_ORG_ALLOWLIST, is_legitimate_source

log = logging.getLogger("counsel.settings")
router = APIRouter(prefix="/api/settings", tags=["settings"])

JURISDICTIONS: dict[str, list[str]] = {
    "United States": [
        "California", "New York", "Texas", "Florida", "Illinois",
        "Washington", "Massachusetts", "Delaware", "Georgia", "Virginia",
    ],
    "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
    "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba"],
    "India": ["Maharashtra", "Delhi NCT", "Karnataka", "Tamil Nadu", "Uttar Pradesh", "West Bengal"],
    "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia"],
    "Germany": ["Berlin", "Bavaria", "Hesse", "North Rhine-Westphalia"],
}


class JurisdictionsOut(BaseModel):
    countries: list[str]
    provinces: dict[str, list[str]]


@router.get("/jurisdictions", response_model=JurisdictionsOut)
async def jurisdictions() -> JurisdictionsOut:
    return JurisdictionsOut(countries=list(JURISDICTIONS), provinces=JURISDICTIONS)


class SettingsOut(BaseModel):
    country: str
    province: str
    city: str
    privacy_preference: str
    domain_whitelist: list[str]
    default_whitelist: list[str]
    disclaimer_text: str


@router.get("", response_model=SettingsOut)
async def get_settings(user: User = Depends(current_user)) -> SettingsOut:
    s = json.loads(user.settings_json or "{}")
    extra = s.get("domain_whitelist_json") or ""
    firm = firm_settings()
    return SettingsOut(
        country=s.get("country", ""),
        province=s.get("province", ""),
        city=s.get("city", ""),
        privacy_preference=s.get("privacy_preference", "local-first"),
        domain_whitelist=[d for d in extra.split(",") if d],
        default_whitelist=sorted(LEGAL_ORG_ALLOWLIST),
        disclaimer_text=firm["disclaimer_text"],
    )


class SettingsPatch(BaseModel):
    country: str | None = None
    province: str | None = None
    city: str | None = None
    privacy_preference: str | None = None
    practice_areas: list[str] | None = None
    jurisdictions: list[str] | None = None


@router.patch("")
async def patch_settings(patch: SettingsPatch,
                         user: User = Depends(current_user)) -> dict:
    from ..database import get_session_factory

    data = patch.model_dump(exclude_none=True)
    with session_scope() as s:
        u = s.get(User, user.id)
        if u is None:
            return {"ok": False}
        settings_map = json.loads(u.settings_json or "{}")
        for key in ("country", "province", "city", "privacy_preference"):
            if key in data:
                settings_map[key] = str(data.pop(key))[:200]
        if "jurisdictions" in data:
            u.jurisdictions_json = json.dumps(data.pop("jurisdictions")[:20])
        if "practice_areas" in data:
            u.practice_areas_json = json.dumps(data.pop("practice_areas")[:30])
        u.settings_json = json.dumps(settings_map)
    record_audit(user.id, "settings.updated", detail={"keys": list(data.keys())})
    return {"ok": True}


# ------------------------------------------------------------- firm (admin)


class FirmSettingsOut(BaseModel):
    allowed_domains: list[str]
    model_policy: str
    audit_access_roles: str
    disclaimer_text: str


@router.get("/firm", response_model=FirmSettingsOut)
async def get_firm_settings(admin: User = Depends(require_admin)) -> FirmSettingsOut:
    f = firm_settings()
    return FirmSettingsOut(
        allowed_domains=json.loads(f["allowed_domains_json"]),
        model_policy=f["model_policy"],
        audit_access_roles=f["audit_access_roles"],
        disclaimer_text=f["disclaimer_text"],
    )


class FirmPatch(BaseModel):
    allowed_domains: list[str] | None = None
    model_policy: str | None = None
    disclaimer_text: str | None = None


@router.patch("/firm")
async def patch_firm(patch: FirmPatch, admin: User = Depends(require_admin)) -> dict:
    if patch.allowed_domains is not None:
        hosts = [h.strip().lower() for h in patch.allowed_domains if h.strip()]
        bad = [h for h in hosts if not is_legitimate_source(h)]
        set_firm_setting("allowed_domains_json", json.dumps(hosts), admin.id)
        if bad:
            return {"ok": True,
                    "warning": f"Entries not recognised as legitimate sources (kept anyway): {', '.join(bad)}"}
    if patch.model_policy is not None:
        if patch.model_policy not in ("local-only", "local-first", "api-allowed"):
            return {"ok": False, "error": "model_policy must be local-only|local-first|api-allowed"}
        set_firm_setting("model_policy", patch.model_policy, admin.id)
    if patch.disclaimer_text is not None and patch.disclaimer_text.strip():
        set_firm_setting("disclaimer_text", patch.disclaimer_text.strip()[:500], admin.id)
    record_audit(admin.id, "admin.firm_settings_updated")
    return {"ok": True}


# --------------------------------------------------------------- data wipe


@router.post("/wipe-all-data")
async def wipe_data(admin: User = Depends(require_admin),
                    keep_users: bool = True) -> dict:
    """Securely wipes DB rows + encrypted uploads + vector index + outputs."""
    counts = wipe_all_data(keep_users=keep_users)
    files = 0
    from ..config import settings as cfg

    for directory in (cfg.docs_dir, cfg.outputs_dir, cfg.index_dir):
        files += secure_wipe_dir(directory)
    record_audit(admin.id, "admin.wipe_all_data",
                 detail={"rows": counts, "files": files})
    log.warning("WIPE ALL DATA executed by %s — %d files removed", admin.email, files)
    return {"ok": True, "tables": counts, "files_removed": files}
