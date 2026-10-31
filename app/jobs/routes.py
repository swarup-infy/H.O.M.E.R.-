"""Local-first job-search API routes for HOMER."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.jobs import service

router = APIRouter(prefix="/jobs", tags=["job search"])
JobStatus = Literal["saved", "to_apply", "applied", "interview", "offer", "rejected", "withdrawn"]

# Search links open the source's own results page. HOMER does not scrape,
# log in to, or bypass restrictions on these services.
JOB_SEARCH_SOURCES: dict[str, tuple[str, str]] = {
    "google_jobs": ("Google Jobs", "https://www.google.com/search"),
    "linkedin": ("LinkedIn Jobs", "https://www.linkedin.com/jobs/search/"),
    "indeed": ("Indeed", "https://www.indeed.com/jobs"),
    "naukri": ("Naukri", "https://www.naukri.com/"),
    "foundit": ("Foundit", "https://www.foundit.in/srp/results"),
    "wellfound": ("Wellfound", "https://wellfound.com/jobs"),
    "glassdoor": ("Glassdoor", "https://www.glassdoor.com/Job/"),
    "greenhouse": ("Greenhouse job boards", "https://www.google.com/search"),
    "lever": ("Lever job boards", "https://www.google.com/search"),
}


def _search_url(source_id: str, query: str, location: str) -> str:
    """Build a public search URL without sending requests to the job site."""
    title, base_url = JOB_SEARCH_SOURCES[source_id]
    terms = " ".join(part for part in (query.strip(), location.strip()) if part)
    if source_id == "google_jobs":
        return base_url + "?" + urlencode({"q": f"jobs {terms}"})
    if source_id == "linkedin":
        params = {"keywords": query.strip()}
        if location.strip():
            params["location"] = location.strip()
        return base_url + "?" + urlencode(params)
    if source_id == "indeed":
        params = {"q": query.strip()}
        if location.strip():
            params["l"] = location.strip()
        return base_url + "?" + urlencode(params)
    if source_id == "naukri":
        # Naukri's public site uses query-friendly paths; use its homepage
        # with the requested terms preserved in the returned metadata.
        return base_url + "?" + urlencode({"k": query.strip(), "l": location.strip()})
    if source_id == "foundit":
        return base_url + "?" + urlencode({"query": query.strip(), "locations": location.strip()})
    if source_id == "wellfound":
        return "https://wellfound.com/jobs?" + urlencode({"query": terms})
    if source_id == "glassdoor":
        return base_url + "?" + urlencode({"sc.keyword": query.strip(), "locT": "C", "locKeyword": location.strip()})
    site = "greenhouse.io" if source_id == "greenhouse" else "jobs.lever.co"
    return "https://www.google.com/search?" + urlencode({"q": f"{terms} site:{site}"})


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


@router.get("/search")
async def search_jobs(
    q: str = Query(min_length=1, max_length=200, description="Job title or skills"),
    location: str = Query(default="", max_length=200, description="City, country, or Remote"),
    sources: list[str] | None = Query(default=None, description="Optional source IDs"),
) -> dict:
    """Return search links across job sites; does not scrape or log in."""
    query = q.strip()
    place = location.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a job title or skills.")
    selected = sources or list(JOB_SEARCH_SOURCES)
    unknown = sorted(set(selected) - JOB_SEARCH_SOURCES.keys())
    if unknown:
        raise HTTPException(status_code=422, detail={"unknown_sources": unknown, "available_sources": sorted(JOB_SEARCH_SOURCES)})
    results = [
        {
            "source_id": source_id,
            "source": JOB_SEARCH_SOURCES[source_id][0],
            "search_url": _search_url(source_id, query, place),
            "query": query,
            "location": place,
            "mode": "external_search_link",
        }
        for source_id in dict.fromkeys(selected)
    ]
    return {
        "query": query,
        "location": place,
        "count": len(results),
        "results": results,
        "note": "These links open each site's own search. Live listings are not yet aggregated inside HOMER.",
    }


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
