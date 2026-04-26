# Contributor Data System Documentation

## 1. Purpose

This subsystem turns Git commit history into contributor intelligence profiles for the Intelligent Bug Report Management System.

The pipeline does three things:

1. Reads GitHub commit history for a repository.
2. Groups commits by contributor identity.
3. Uses an LLM provider strategy (Gemini by default) to generate a structured natural-language profile for each contributor and stores the result in MongoDB Atlas.

The design is intentionally modular so this subsystem can be plugged into a larger bug-management platform without coupling the GitHub, LLM, and database concerns together.

## 2. High-level architecture

The implementation follows a layered architecture:

- API layer: FastAPI endpoints exposed in [app/main.py](app/main.py)
- Service layer: pipeline orchestration in [app/services.py](app/services.py)
- Adapter layer: external API integrations in [app/github_api.py](app/github_api.py) and [app/gemini_api.py](app/gemini_api.py)
- Context optimization layer: bounded prompt payload builder in [app/context_optimizer.py](app/context_optimizer.py)
- Persistence layer: MongoDB repository abstractions in [app/repositories.py](app/repositories.py)
- Event layer: SSE event bus and broadcasting in [app/events.py](app/events.py)
- Webhook layer: GitHub event ingestion in [app/main.py](app/main.py)
- Infrastructure helper: Atlas connection helper in [connect_atlas.py](connect_atlas.py)

This separation supports testability, low coupling, and replaceability of external systems.

## 3. Architectural decisions

### 3.1 Layered architecture

Why it was chosen:

- Keeps API code simple and request-focused.
- Moves business logic into service classes that are easy to test.
- Prevents direct MongoDB or GitHub calls from leaking into endpoint handlers.

Benefit:

- Each layer has one primary responsibility.
- The system can evolve independently at each layer.

### 3.2 Adapter pattern for external APIs

The GitHub and Gemini integrations are isolated behind dedicated client classes:

- [app/github_api.py](app/github_api.py)
- [app/gemini_api.py](app/gemini_api.py)

Why it was chosen:

- External APIs change independently of internal domain logic.
- This makes it easier to swap providers later if needed.
- It centralizes retry, parsing, and response-shaping behavior.

### 3.3 Strategy pattern for LLM providers

The LLM summarization component now uses a strategy abstraction:

- `LLMProviderStrategy` (interface)
- `GeminiProviderStrategy` (Gemini implementation)
- `DeterministicProviderStrategy` (non-LLM fallback)
- `ProviderFactory` (strategy selection by `LLM_PROVIDER`)

Implemented in [app/gemini_api.py](app/gemini_api.py).

Why it was chosen:

- New providers can be added without changing service logic.
- It keeps provider-specific code isolated.
- It supports safe fallback when credentials are unavailable.

### 3.4 Repository pattern for MongoDB

The persistence code is wrapped in repository-like store classes:

- `RepositoryStore`
- `CommitStore`
- `ContributorStore`
- `SyncRunStore`

Why it was chosen:

- Isolates database query logic.
- Makes collections behave like domain stores instead of generic collections.
- Reduces duplication of update and query logic.

### 3.5 Service orchestration pattern

`ContributorPipelineService` coordinates the full sync flow:

1. Load repository metadata from GitHub.
2. Fetch commit history.
3. Persist commit snapshots.
4. Aggregate commits into contributor buckets.
5. Generate contributor summaries with Gemini.
6. Persist contributor profiles and repository statistics.

Why it was chosen:

- The workflow is multi-step and has clear orchestration boundaries.
- Error handling and sync state tracking stay in one place.

### 3.6 Prompt budget and context compression for long histories

Large commit histories can exceed model input limits. To prevent this, `CommitContextOptimizer` compresses contributor history before calling the LLM.

Implemented in [app/context_optimizer.py](app/context_optimizer.py).

Optimization tactics:

- Keep recent commits (high recency signal)
- Keep oldest commits (captures contribution arc)
- Keep deduplicated middle commits (diversity of work)
- Limit evidence lines and total prompt budget via character budget
- Extract top keywords deterministically from sampled messages

Configured through:

- `LLM_PROMPT_CHAR_BUDGET`
- `LLM_MAX_EVIDENCE_ITEMS`
- `LLM_RECENT_MESSAGES_LIMIT`

This keeps LLM calls within bounded size while preserving representative context.

### 3.7 Structured output from Gemini

The Gemini prompt requests strict JSON output.

Why it was chosen:

- Structured output is easier to store in MongoDB.
- It improves consistency for downstream APIs.
- It allows future ranking, filtering, or analytics on profile fields.

If Gemini output cannot be parsed, the system falls back to deterministic summaries so the pipeline remains functional.

## 4. External APIs used

### 4.1 GitHub REST API

Used endpoints:

- GET /repos/{owner}/{repo}
- GET /repos/{owner}/{repo}/commits

Purpose:

- Repository metadata for display and indexing.
- Commit history for contributor profiling.

Notes:

- A GitHub personal access token is supported through the `GITHUB_TOKEN` environment variable.
- If no token is set, public repositories can still be processed, but rate limits are lower.

### 4.2 Gemini API

Used through the `google-generativeai` SDK.

Purpose:

- Turn commit metadata into readable contributor profiles.

Configuration:

- `GEMINI_API_KEY`
- `GEMINI_MODEL` defaults to `gemma-3-27b-it`
- `LLM_PROVIDER` defaults to `gemini`

Prompt strategy:

- Ask for strict JSON.
- Restrict the model to supplied evidence.
- Store only factual commit-derived profile text.

Fallback strategy:

- If `LLM_PROVIDER=gemini` but no `GEMINI_API_KEY` is set, the system automatically falls back to deterministic summaries.

## 5. MongoDB Atlas usage

MongoDB Atlas connection is handled by [connect_atlas.py](connect_atlas.py).

Required environment variables:

- `MONGODB_URI`
- `MONGODB_DB_NAME`

The connection helper:

- creates a cached `MongoClient`
- uses MongoDB Server API v1
- pings the server before returning the database handle

## 6. Database schema

The subsystem uses six collections.

### 6.1 `repositories`

Purpose:

- Stores repository-level metadata and sync state.

Fields:

- `owner`
- `name`
- `full_name`
- `description`
- `default_branch`
- `private`
- `html_url`
- `language`
- `visibility`
- `commit_count`
- `contributor_count`
- `sync_status`
- `sync_error`
- `last_synced_at`

Primary uniqueness:

- Unique index on `full_name`

### 6.2 `commits`

Purpose:

- Stores raw commit snapshots for traceability and later reprocessing.

Fields:

- `repository_full_name`
- `sha`
- `contributor_key`
- `github_login`
- `author_name`
- `author_email`
- `message`
- `html_url`
- `authored_at`
- `committed_at`
- `additions`
- `deletions`
- `files_changed`
- `total_changes`

Primary uniqueness:

- Unique index on `repository_full_name + sha`

### 6.3 `contributors`

Purpose:

- Stores the generated contributor intelligence profile.

Fields:

- `repository_full_name`
- `contributor_key`
- `github_login`
- `display_name`
- `commit_count`
- `first_commit_at`
- `last_commit_at`
- `recent_commit_messages`
- `summary`
- `strengths`
- `collaboration_style`
- `evidence`
- `keywords`
- `confidence`
- `generated_with`
- `source_commit_shas`
- `updated_at`

Primary uniqueness:

- Unique index on `repository_full_name + contributor_key`

### 6.4 `sync_runs`

Purpose:

- Tracks pipeline runs for observability and troubleshooting.

Fields:

- `repository_full_name`
- `triggered_by`
- `status`
- `started_at`
- `finished_at`
- `message`

Index:

- `repository_full_name + started_at`

### 6.5 `issues`

Purpose:

- Stores fetched repository issues used for assignment workflows.

### 6.6 `assignments`

Purpose:

- Stores issue-to-contributor mapping recommendations with rationale.

## 7. Contributor identity strategy

Contributor identity is normalized using the following priority:

1. GitHub login if available
2. Commit author email if available
3. Commit author name if available
4. SHA fallback

This is implemented in [app/github_api.py](app/github_api.py).

Reason:

- GitHub commit data can be incomplete.
- Some commits may not have linked GitHub user accounts.
- The fallback prevents data loss while maintaining stable grouping.

## 8. Endpoints

All endpoints are defined in [app/main.py](app/main.py).

### 8.1 Health

GET `/health`

Returns:

- service status
- basic health message

### 8.2 Sync repository

POST `/repositories/{owner}/{repo}/sync`

Body:

- `max_pages` optional
- `per_page` optional
- `recent_n_commits` optional (sync only the most recent N commits)

What it does:

- fetches repository metadata from GitHub
- fetches commit history
- stores commit snapshots
- generates contributor summaries with Gemini
- updates MongoDB statistics

### 8.3 Get repository summary

GET `/repositories/{owner}/{repo}`

Returns:

- repository metadata
- sync status
- contributor count
- commit count

### 8.4 List contributors

GET `/repositories/{owner}/{repo}/contributors`

Returns:

- all contributor profiles for the repository

### 8.5 Get one contributor profile

GET `/repositories/{owner}/{repo}/contributors/{contributor_key}`

Returns:

- one generated profile

### 8.6 Refresh one contributor profile

POST `/repositories/{owner}/{repo}/contributors/{contributor_key}/refresh`

What it does:

- reloads that contributor’s commit history from MongoDB
- regenerates the profile with Gemini

### 8.7 List commits

GET `/repositories/{owner}/{repo}/commits`

Query params:

- `contributor_key` optional
- `limit` optional

Returns:

- raw commit records stored in MongoDB

### 8.8 Force refresh all contributor summaries

POST `/repositories/{owner}/{repo}/contributors/force-refresh`

What it does:

- uses already stored commit history in MongoDB
- regenerates summaries for every contributor in the repository
- does not call GitHub API again for commits

### 8.9 Clear summaries for one repository

DELETE `/repositories/{owner}/{repo}/summaries`

What it does:

- clears summary-oriented fields (`summary`, `strengths`, `collaboration_style`, `evidence`, `keywords`, `focus_areas`, `work_area_analysis`)
- retains contributor identity and commit metadata

### 8.10 Clear summaries globally

DELETE `/summaries`

What it does:

- clears summary fields for contributors across all repositories
- keeps commit history and repository metadata intact

### 8.11 GitHub Webhook

POST `/webhooks/github`

What it does:
- Receives `issues` events from GitHub.
- Processes `opened`, `edited`, and `closed` actions.
- Automatically persists the new state to the MongoDB `issues` collection.
- Broadcasts an `issue_updated` event to all connected dashboard users via SSE.

### 8.12 SSE Stream

GET `/stream`

What it does:
- Provides a Server-Sent Events (SSE) stream for real-time dashboard updates.
- Emits events for: `repo_synced`, `issues_fetched`, `assignment_generated`, and `issue_updated`.

## 9. Error handling strategy

- GitHub API failures raise explicit `GitHubAPIError` exceptions.
- MongoDB connection issues surface immediately during startup.
- Gemini parsing failures fall back to deterministic summaries.
- Sync state is persisted as `running`, `synced`, or `failed`.

## 10. Design trade-offs

### What was optimized

- Maintainability over compactness.
- Data traceability over minimal storage.
- Structured output over free-form LLM text.

### What was intentionally not included yet

- Background task queueing
- User authentication and access control
- Diff-level semantic analysis

These can be added later without changing the core layering.

## 11. Environment variables

- `MONGODB_URI`: MongoDB Atlas connection string
- `MONGODB_DB_NAME`: database name, default `contributor_data`
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_API_BASE_URL`: defaults to `https://api.github.com`
- `LLM_PROVIDER`: `gemini` or `deterministic`
- `GEMINI_API_KEY`: Gemini API key
- `GEMINI_MODEL`: defaults to `gemma-3-27b-it`
- `LLM_PROMPT_CHAR_BUDGET`: prompt character budget for context optimizer
- `LLM_MAX_EVIDENCE_ITEMS`: max commit evidence lines sent to LLM
- `LLM_RECENT_MESSAGES_LIMIT`: max sampled commit messages sent to LLM
- `DEFAULT_SYNC_PAGES`: default pages of commits to fetch
- `DEFAULT_PAGE_SIZE`: default commits per page

Suggested values for this project:

- default repo owner: `pandas-dev`
- default repo name: `pandas`
- recommended DB name: `contributor_data`

## 12. Operational notes

- The first sync for a large repository may take time because it fetches commit pages and runs LLM summarization.
- For very active repositories, increase `max_pages` gradually.
- Storing raw commit snapshots makes the system auditable and allows profile regeneration without re-pulling GitHub data.
