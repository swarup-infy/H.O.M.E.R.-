"""Local-first job-search API routes for HOMER."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.jobs import service

router = APIRouter(prefix="/jobs", tags=["job search"])
JobStatus = Literal["saved", "to_apply", "applied", "interview", "offer", "rejected", "withdrawn"]


class JobScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_skills: list[str] = Field(default_factory=list, max_length=100)
    target_roles: list[str] = Field(default_factory=list, max_length=30)
    preferred_locations: list[str] = Field(default_factory=list, max_length=30)
    job_title: str = Field(min_length=1, max_length=200)
    job_location: str = Field(default="", max_length=200)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)


class SaveApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    job_url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    status: JobStatus = "saved"


class UpdateStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: JobStatus


@router.post("/score")
async def score(request: JobScoreRequest) -> dict:
    """Score a job locally; no resume or job data is sent to an AI provider."""
    return service.score_job(
        profile_skills=request.profile_skills,
        target_roles=request.target_roles,
        preferred_locations=request.preferred_locations,
        job_title=request.job_title,
        job_location=request.job_location,
        required_skills=request.required_skills,
        preferred_skills=request.preferred_skills,
    )


@router.get("/applications")
async def applications() -> dict:
    """Return locally saved applications."""
    try:
        return {"applications": service.list_applications()}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/applications", status_code=201)
async def save_application(request: SaveApplicationRequest) -> dict:
    """Save a job to the local tracker. Does not apply or contact anyone."""
    try:
        record = service.save_application(**request.model_dump())
        return {"application": record, "message": "Saved locally. Nothing was submitted."}
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail="Could not save the local application tracker.") from exc


@router.patch("/applications/{application_id}")
async def update_status(application_id: str, request: UpdateStatusRequest) -> dict:
    """Update the status of a locally tracked job."""
    try:
        record = service.update_application_status(application_id, request.status)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail="Could not update the local application tracker.") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return {"application": record}
