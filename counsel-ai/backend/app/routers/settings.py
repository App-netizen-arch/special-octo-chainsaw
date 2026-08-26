"""Settings router: onboarding data, jurisdiction, whitelist configuration."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..database import all_settings, set_setting
from ..models.schemas import SettingsPatch
from ..utils.domain_whitelist import LEGAL_ORG_ALLOWLIST, is_legitimate_source

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsOut(BaseModel):
    onboarded: bool
    country: str
    province: str
    city: str
    privacy_preference: str
    domain_whitelist: list[str]
    default_whitelist: list[str]


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


@router.get("", response_model=SettingsOut)
async def get_settings() -> SettingsOut:
    s = all_settings()
    extra = s.get("domain_whitelist_json") or ""
    return SettingsOut(
        onboarded=s["onboarded"] == "true",
        country=s["country"],
        province=s["province"],
        city=s["city"],
        privacy_preference=s["privacy_preference"],
        domain_whitelist=[d for d in extra.split(",") if d],
        default_whitelist=sorted(LEGAL_ORG_ALLOWLIST),
    )


@router.patch("")
async def patch_settings(patch: SettingsPatch) -> dict:
    mapping = {
        "onboarded": lambda v: "true" if v else "false",
        "country": str,
        "province": str,
        "city": str,
        "privacy_preference": str,
    }
    data = patch.model_dump(exclude_none=True)
    if "domain_whitelist" in data and data["domain_whitelist"] is not None:
        hosts = [h.strip().lower() for h in data.pop("domain_whitelist") if h.strip()]
        bad = [h for h in hosts if not is_legitimate_source(h)]
        set_setting("domain_whitelist_json", ",".join(hosts))
        if bad:
            return {"ok": True, "warning": f"These entries are already covered or not recognisable: {', '.join(bad)}"}
    for key, value in data.items():
        if key in mapping:
            set_setting(key, mapping[key](value))
    return {"ok": True}
