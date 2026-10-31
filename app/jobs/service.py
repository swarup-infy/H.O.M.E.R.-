"""Local-first job fit scoring and application tracking.

This module never submits applications or contacts employers. Tracker data is
stored on the user's computer as JSON; scoring is deterministic and needs no
AI API call.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACKER_PATH = Path(
    os.environ.get(
        "HOMER_JOB_TRACKER_PATH",
        str(Path.home() / ".homer" / "job_search" / "applications.json"),
    )
)
_TRACKER_LOCK = threading.Lock()
VALID_STATUSES = {
    "saved", "to_apply", "applied", "interview", "offer", "rejected", "withdrawn"
}


def _clean_terms(values: list[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def score_job(
    *,
    profile_skills: list[str],
    target_roles: list[str],
    preferred_locations: list[str],
    job_title: str,
    job_location: str,
    required_skills: list[str],
    preferred_skills: list[str],
) -> dict[str, Any]:
    """Return a transparent 0–100 fit estimate from user-supplied terms."""
    profile = _clean_terms(profile_skills)
    required = _clean_terms(required_skills)
    preferred = _clean_terms(preferred_skills)
    matched_required = sorted(profile & required)
    missing_required = sorted(required - profile)
    matched_preferred = sorted(profile & preferred)
    target_role_terms = _clean_terms(target_roles)
    location_terms = _clean_terms(preferred_locations)

    required_score = (
        len(matched_required) / len(required) * 70 if required else 35.0
    )
    preferred_score = (
        len(matched_preferred) / len(preferred) * 15 if preferred else 7.5
    )
    title = job_title.casefold()
    role_score = 10.0 if any(role in title or title in role for role in target_role_terms) else 0.0
    location = job_location.casefold().strip()
    location_score = 5.0 if not location_terms or any(
        term in location or term in {"remote", "anywhere"} and "remote" in location
        for term in location_terms
    ) else 0.0
    total = round(min(100.0, required_score + preferred_score + role_score + location_score))

    if total >= 75:
        recommendation = "Strong match — review the requirements and consider applying."
    elif total >= 60:
        recommendation = "Possible match — address the gaps before deciding."
    else:
        recommendation = "Lower match — compare the missing requirements with your goals."

    return {
        "fit_score": total,
        "recommendation": recommendation,
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "scoring_note": (
            "This is a transparent keyword-based estimate, not a hiring prediction. "
            "It only evaluates the skills, role and location terms you supplied."
        ),
    }


def _read_tracker() -> list[dict[str, Any]]:
    if not TRACKER_PATH.exists():
        return []
    try:
        payload = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("The local application tracker cannot be read. Back it up before changing it.") from exc
    if not isinstance(payload, list):
        raise RuntimeError("The local application tracker has an unexpected format.")
    return payload


def list_applications() -> list[dict[str, Any]]:
    """List saved job applications without contacting external services."""
    with _TRACKER_LOCK:
        return _read_tracker()


def save_application(
    *,
    company: str,
    job_title: str,
    job_url: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    status: str = "saved",
) -> dict[str, Any]:
    """Save a job to the local tracker; this never applies or sends anything."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "company": company.strip(),
        "job_title": job_title.strip(),
        "job_url": job_url.strip() if job_url else None,
        "location": location.strip() if location else None,
        "notes": notes.strip() if notes else None,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    with _TRACKER_LOCK:
        records = _read_tracker()
        records.append(record)
        TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix="applications-", suffix=".tmp", dir=str(TRACKER_PATH.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temporary_name, TRACKER_PATH)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
    return record


def update_application_status(application_id: str, status: str) -> dict[str, Any] | None:
    """Update only the local status of an existing tracked job."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.")
    with _TRACKER_LOCK:
        records = _read_tracker()
        for record in records:
            if record.get("id") == application_id:
                record["status"] = status
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary_name = tempfile.mkstemp(
                    prefix="applications-", suffix=".tmp", dir=str(TRACKER_PATH.parent)
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(records, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                    os.replace(temporary_name, TRACKER_PATH)
                except Exception:
                    try:
                        os.unlink(temporary_name)
                    except OSError:
                        pass
                    raise
                return record
    return None
