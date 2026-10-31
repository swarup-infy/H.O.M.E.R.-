"""Tests for HOMER's local-first job-search feature."""
from fastapi.testclient import TestClient

from app import main
from app.jobs import service

client = TestClient(main.app)


def test_job_score_reports_skill_gaps_and_explanation():
    result = service.score_job(
        profile_skills=["Python", "FastAPI", "Git"],
        target_roles=["AI Engineer"],
        preferred_locations=["Remote"],
        job_title="AI Engineer",
        job_location="Remote, India",
        required_skills=["Python", "FastAPI", "SQL"],
        preferred_skills=["Git", "Docker"],
    )
    assert result["fit_score"] == 69
    assert result["matched_required_skills"] == ["fastapi", "python"]
    assert result["missing_required_skills"] == ["sql"]
    assert result["matched_preferred_skills"] == ["git"]
    assert "not a hiring prediction" in result["scoring_note"]


def test_job_score_endpoint_rejects_unknown_fields():
    response = client.post("/jobs/score", json={
        "job_title": "AI Engineer",
        "unexpected": True,
    })
    assert response.status_code == 422


def test_application_tracker_saves_and_updates_locally(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "TRACKER_PATH", tmp_path / "applications.json")
    saved = client.post("/jobs/applications", json={
        "company": "Example Ltd",
        "job_title": "Junior Python Developer",
        "job_url": "https://example.com/jobs/123",
        "status": "saved",
    })
    assert saved.status_code == 201
    record = saved.json()["application"]
    assert record["company"] == "Example Ltd"
    assert "Nothing was submitted" in saved.json()["message"]

    listed = client.get("/jobs/applications")
    assert listed.status_code == 200
    assert len(listed.json()["applications"]) == 1

    updated = client.patch(
        f"/jobs/applications/{record['id']}",
        json={"status": "applied"},
    )
    assert updated.status_code == 200
    assert updated.json()["application"]["status"] == "applied"


def test_application_status_update_returns_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "TRACKER_PATH", tmp_path / "applications.json")
    response = client.patch(
        "/jobs/applications/not-a-real-id",
        json={"status": "applied"},
    )
    assert response.status_code == 404


def test_application_tracker_rejects_invalid_status():
    response = client.post("/jobs/applications", json={
        "company": "Example Ltd",
        "job_title": "Developer",
        "status": "auto_apply",
    })
    assert response.status_code == 422
