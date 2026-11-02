"""Role-based access control: which roles may see which record classifications."""
from __future__ import annotations

from fastapi import HTTPException

# Ordered from least to most sensitive.
CLASSIFICATIONS: dict[str, dict] = {
    "public": {
        "label": "Public",
        "description": "Releasable under public-records law without redaction (inspections, adopted policies).",
    },
    "internal": {
        "label": "Internal",
        "description": "Operational records for department staff (SOPs, incident reports, maintenance).",
    },
    "restricted": {
        "label": "Restricted",
        "description": "Open investigations and pre-incident security details. Officers and above.",
    },
    "confidential": {
        "label": "Confidential",
        "description": "Personnel and medical exposure records. Records administrators only.",
    },
}

ROLES: dict[str, dict] = {
    "public_info": {
        "label": "Public Information Officer",
        "classifications": ["public"],
        "permissions": [],
    },
    "firefighter": {
        "label": "Firefighter",
        "classifications": ["public", "internal"],
        "permissions": [],
    },
    "fire_officer": {
        "label": "Fire Officer",
        "classifications": ["public", "internal", "restricted"],
        "permissions": ["ingest"],
    },
    "records_admin": {
        "label": "Records Administrator",
        "classifications": ["public", "internal", "restricted", "confidential"],
        "permissions": ["ingest", "audit:read", "users:manage"],
    },
}

DEFAULT_ROLE = "firefighter"


def role_info(role: str) -> dict:
    return ROLES.get(role) or ROLES[DEFAULT_ROLE]


def allowed_classifications(role: str) -> list[str]:
    return list(role_info(role)["classifications"])


def can(role: str, permission: str) -> bool:
    return permission in role_info(role)["permissions"]


def can_view(role: str, classification: str) -> bool:
    return classification in allowed_classifications(role)


def require_permission(user: dict, permission: str) -> None:
    if not can(user.get("role", DEFAULT_ROLE), permission):
        raise HTTPException(status_code=403, detail="Your role does not permit this action.")


def access_policy() -> dict:
    return {
        "classifications": [{"id": key, **value} for key, value in CLASSIFICATIONS.items()],
        "roles": [{"id": key, **value} for key, value in ROLES.items()],
    }
