# Intelligent-Bug-Report-Management-System

## Contributor intelligence subsystem

This repository now includes a contributor profiling pipeline for the larger bug report management system.

### What it does

- Pulls commit history from the GitHub API
- Groups commits by contributor identity
- Generates contributor summaries using an LLM strategy layer (Gemini + deterministic fallback)
- Compresses long commit histories with a bounded context optimizer before LLM calls
- Stores repository, commit, contributor, and sync-run data in MongoDB Atlas
- Fetches random repository issues and stores them for assignment workflows
- Generates issue-to-contributor assignments using issue context + contributor summaries
- Exposes REST endpoints for sync and retrieval

### Main endpoints

- GET `/health`
- POST `/repositories/{owner}/{repo}/sync`
- GET `/repositories/{owner}/{repo}`
- GET `/repositories/{owner}/{repo}/contributors`
- GET `/repositories/{owner}/{repo}/contributors/{contributor_key}`
- POST `/repositories/{owner}/{repo}/contributors/{contributor_key}/refresh`
- POST `/repositories/{owner}/{repo}/contributors/force-refresh`
- DELETE `/repositories/{owner}/{repo}/summaries`
- DELETE `/summaries`
- GET `/repositories/{owner}/{repo}/commits`
- POST `/repositories/{owner}/{repo}/issues/random/fetch`
- GET `/repositories/{owner}/{repo}/issues`
- GET `/repositories/{owner}/{repo}/issues/{issue_number}`
- POST `/repositories/{owner}/{repo}/assignments/generate`
- GET `/repositories/{owner}/{repo}/assignments`
- GET `/repositories/{owner}/{repo}/assignments/{issue_number}`

### Database collections

- `repositories`
- `commits`
- `contributors`
- `sync_runs`
- `issues`
- `assignments`

### Environment variables

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `GITHUB_TOKEN`
- `GITHUB_API_BASE_URL`
- `LLM_PROVIDER`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `LLM_PROMPT_CHAR_BUDGET`
- `LLM_MAX_EVIDENCE_ITEMS`
- `LLM_RECENT_MESSAGES_LIMIT`

### Recommended defaults for current target repo

- Repository: `https://github.com/pandas-dev/pandas`
- Suggested DB name: `contributor_data`
- Gemini model: `gemma-3-27b-it`

### Run commands

```bash
# 1) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Configure environment
cp .env.example .env
# then edit .env and set real values for GITHUB_TOKEN and GEMINI_API_KEY if needed

# 4) Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Alternative startup:

```bash
python3 -m app.main
```

### Test commands

This project currently has API smoke tests via `curl` commands.

```bash
# Health check
curl -s http://localhost:8000/health | jq

# Sync repository data
curl -s -X POST "http://localhost:8000/repositories/pandas-dev/pandas/sync" \
	-H "Content-Type: application/json" \
	-d '{"max_pages": 2, "per_page": 100, "recent_n_commits": 20}' | jq

# Get repository summary
curl -s http://localhost:8000/repositories/pandas-dev/pandas | jq

# List contributor profiles
curl -s http://localhost:8000/repositories/pandas-dev/pandas/contributors | jq

# Force refresh summaries for all contributors in repository
curl -s -X POST "http://localhost:8000/repositories/pandas-dev/pandas/contributors/force-refresh" | jq

# Clear summaries for this repository only
curl -s -X DELETE "http://localhost:8000/repositories/pandas-dev/pandas/summaries" | jq

# Clear summaries for all repositories
curl -s -X DELETE "http://localhost:8000/summaries" | jq

# List latest commits (optionally add ?contributor_key=login:<user>)
curl -s "http://localhost:8000/repositories/pandas-dev/pandas/commits?limit=20" | jq

# Fetch one random issue from GitHub and persist in issues collection
curl -s -X POST "http://localhost:8000/repositories/pandas-dev/pandas/issues/random/fetch" \
	-H "Content-Type: application/json" \
	-d '{"state": "open", "max_pages": 2, "per_page": 100}' | jq

# Generate assignment for a random stored/fetched issue
curl -s -X POST "http://localhost:8000/repositories/pandas-dev/pandas/assignments/generate" \
	-H "Content-Type: application/json" \
	-d '{"issue_state": "open", "fetch_if_missing": true}' | jq

# Generate assignment for a specific issue
curl -s -X POST "http://localhost:8000/repositories/pandas-dev/pandas/assignments/generate" \
	-H "Content-Type: application/json" \
	-d '{"issue_number": 1, "fetch_if_missing": true}' | jq

# List stored issues and assignments
curl -s "http://localhost:8000/repositories/pandas-dev/pandas/issues?limit=20" | jq
curl -s "http://localhost:8000/repositories/pandas-dev/pandas/assignments?limit=20" | jq
```

If `jq` is not installed, run the same commands without piping to `jq`.

For future automated tests, use:

```bash
pytest -q
```

### Documentation

See [controbutor data docs.md](controbutor%20data%20docs.md) for full design notes, API reference, schema details, and architectural decisions.

See [issue assignment docs.md](issue%20assignment%20docs.md) for issue-fetch and issue-to-contributor assignment design details.