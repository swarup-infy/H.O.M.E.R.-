# HOMER job-search toolkit

## Multi-site search

The GET /jobs/search endpoint creates public search links for Google Jobs, LinkedIn Jobs, Indeed, Naukri, Foundit, Wellfound, Glassdoor, Greenhouse-hosted postings, and Lever-hosted postings.

Example: GET /jobs/search?q=Python%20AI%20Engineer&location=Remote%2C%20India

Optional repeated sources parameters select sources, e.g. GET /jobs/search?q=FastAPI&sources=linkedin&sources=indeed.

This first step returns links to the sites' own search pages. It does not scrape websites, authenticate to accounts, or aggregate live job listings inside HOMER yet. Some sites may interpret search parameters differently or change their URLs; check the opened search before relying on it.

## Job fit and application tracking

- Score a job from the skills, role and location terms you provide.
- Show which required skills match and which are missing.
- Save a job in a local JSON tracker.
- Track status: saved, to apply, applied, interview, offer, rejected or withdrawn.
- Update a saved job's status later.

The feature does not submit applications or contact employers. The score is a transparent keyword estimate, not a prediction of whether an employer will hire you.

## Privacy

Scoring runs locally in the HOMER backend and does not call the Groq API. The tracker is saved to Windows: %USERPROFILE%\\.homer\\job_search\\applications.json.

You can override the tracker file location by setting HOMER_JOB_TRACKER_PATH before starting HOMER. Keep the file private because it may contain your job-search notes.
