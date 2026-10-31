# HOMER local job-search toolkit

This first version adds local job-fit scoring and an application tracker to HOMER.

## What it can do

- Score a job from the skills, role and location terms you provide.
- Show which required skills match and which are missing.
- Save a job in a local JSON tracker.
- Track status: saved, to apply, applied, interview, offer, rejected or withdrawn.
- Update a saved job's status later.

It does **not** scrape job portals, send applications, contact employers, or generate CVs/cover letters yet. It never submits anything. The score is a transparent keyword estimate, not a prediction of whether an employer will hire you.

## Privacy

Scoring runs locally in the HOMER backend and does not call the Groq API. The tracker is saved to:

- Windows: %USERPROFILE%\.homer\job_search\applications.json

You can override the tracker file location by setting HOMER_JOB_TRACKER_PATH before starting HOMER. Keep the file private because it may contain your job-search notes.

## API examples

Open http://127.0.0.1:8000/docs while HOMER is running.

### Score a job

POST /jobs/score

```json
{
  "profile_skills": ["Python", "FastAPI", "Git"],
  "target_roles": ["AI Engineer"],
  "preferred_locations": ["Remote", "India"],
  "job_title": "AI Engineer",
  "job_location": "Remote, India",
  "required_skills": ["Python", "FastAPI", "SQL"],
  "preferred_skills": ["Git", "Docker"]
}
```

### Save a job

POST /jobs/applications

```json
{
  "company": "Example Ltd",
  "job_title": "Junior Python Developer",
  "job_url": "https://example.com/jobs/123",
  "location": "Remote, India",
  "notes": "Review required skills before applying",
  "status": "saved"
}
```

### List tracked jobs

GET /jobs/applications

### Update a job's status

PATCH /jobs/applications/{application_id}

```json
{"status": "applied"}
```

Allowed statuses: saved, to_apply, applied, interview, offer, rejected, withdrawn.

## Safety rules

- Review every CV, cover letter and application yourself.
- Never claim a skill or experience you do not have.
- Do not paste passwords, API keys or private account credentials into job descriptions or notes.
- Applying and sending messages remain manual actions under your control.
