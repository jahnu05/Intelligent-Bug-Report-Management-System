# Issue Assignment System Documentation

## 1. Purpose

This subsystem assigns GitHub issues to the most suitable contributor using:

1. Issue context (title, body, labels, state)
2. Contributor summaries generated from commit history
3. An LLM assignment strategy with deterministic fallback

It stores fetched issues and generated assignments in MongoDB so assignment history is queryable and reproducible.

## 2. High-level architecture

The issue-assignment flow follows the same layered architecture used in contributor profiling:

- API layer: endpoint orchestration in [app/main.py](app/main.py)
- Service layer: issue fetch and assignment orchestration in [app/services.py](app/services.py)
- Adapter layer: GitHub issues integration in [app/github_api.py](app/github_api.py), LLM assignment prompts in [app/gemini_api.py](app/gemini_api.py)
- Persistence layer: issue and assignment stores in [app/repositories.py](app/repositories.py)
- Webhook layer: real-time issue synchronization via GitHub Webhooks
- Event layer: instant UI updates via Server-Sent Events (SSE)

## 3. Workflow

### 3.1 Random issue fetch and storage

1. API calls `POST /repositories/{owner}/{repo}/issues/random/fetch`
2. Service asks GitHub client for a random issue from selected pages
3. Pull requests are excluded
4. Issue is upserted into `issues` collection

### 3.3 Webhook-based synchronization

1. GitHub sends a POST request to `/webhooks/github` (via ngrok in local development).
2. Service validates the signature (if configured).
3. Service parses the payload for `opened`, `edited`, or `closed` actions.
4. Issue is upserted into MongoDB.
5. `issue_updated` event is broadcasted via SSE to notify the local dashboard.

### 3.2 Assignment generation

1. API calls `POST /repositories/{owner}/{repo}/assignments/generate`
2. Service loads issue (specific issue or random fetched issue)
3. Service loads contributor summaries from `contributors`
4. Service constructs assignment payload and calls `LLMProviderStrategy.assign_issue(...)`
5. Selected contributor and rationale are persisted to `assignments`

## 4. Design patterns and architectural decisions

### 4.1 Layered architecture

Why:

- Keeps FastAPI handlers thin
- Consolidates business logic in service methods
- Makes persistence and external integrations replaceable

### 4.2 Adapter pattern

Used for external API boundaries:

- GitHub issue retrieval in `GitHubClient`
- Gemini assignment generation in `GeminiProviderStrategy`

Why:

- Encapsulates provider protocol and payload details
- Reduces coupling to third-party API structures

### 4.3 Strategy pattern for assignment generation

`LLMProviderStrategy` now has two operations:

- `summarize_contributor(...)`
- `assign_issue(...)`

Implementations:

- `GeminiProviderStrategy`
- `DeterministicProviderStrategy`

Why:

- Assignment behavior can be swapped independently
- Supports resilient fallback when model output is unavailable

### 4.4 Repository pattern

MongoDB access is encapsulated in:

- `IssueStore`
- `AssignmentStore`

Why:

- Query/update details stay out of service and API layers
- Enables schema-level consistency and centralized indexing

## 5. External APIs used

### 5.1 GitHub REST API

Used endpoints:

- `GET /repos/{owner}/{repo}/issues`
- `GET /repos/{owner}/{repo}/issues/{issue_number}`

Notes:

- Pull requests are filtered out from issue lists
- Random selection is sampled from fetched issue pages

### 5.2 Gemini API

Used through `google-generativeai` SDK for assignment reasoning.

Prompt output schema (strict JSON):

- `assigned_contributor_key`
- `assigned_github_login`
- `rationale`
- `confidence`
- `alternatives`

## 6. Database schema

## 6.1 `issues` collection

Purpose:

- Stores fetched issue snapshots for assignment workflows

Fields:

- `repository_full_name`
- `issue_number`
- `title`
- `body`
- `state`
- `labels`
- `html_url`
- `author_login`
- `created_at`
- `updated_at`
- `fetched_at`

Indexes:

- Unique: `repository_full_name + issue_number`

## 6.2 `assignments` collection

Purpose:

- Stores latest assignment result per issue

Fields:

- `repository_full_name`
- `issue_number`
- `issue_title`
- `issue_url`
- `issue_state`
- `assigned_contributor_key`
- `assigned_github_login`
- `rationale`
- `confidence`
- `alternatives`
- `source_contributor_count`
- `generated_with`
- `generated_at`

Indexes:

- Unique: `repository_full_name + issue_number`
- Query index: `repository_full_name + generated_at`

## 7. API reference

### 7.1 Fetch random issue

POST `/repositories/{owner}/{repo}/issues/random/fetch`

Body:

- `state` default `open`
- `max_pages` default `2`
- `per_page` default `100`

Returns:

- persisted issue record

### 7.2 List issues

GET `/repositories/{owner}/{repo}/issues`

Query:

- `limit` default `50`

### 7.3 Get issue

GET `/repositories/{owner}/{repo}/issues/{issue_number}`

### 7.4 Generate assignment

POST `/repositories/{owner}/{repo}/assignments/generate`

Body:

- `issue_number` optional
- `issue_state` default `open`
- `fetch_if_missing` default `true`

Behavior:

- If `issue_number` is omitted, uses a random issue
- If issue is missing and `fetch_if_missing=true`, pulls from GitHub then stores

### 7.5 List assignments

GET `/repositories/{owner}/{repo}/assignments`

Query:

- `limit` default `50`

### 7.6 Get assignment by issue

GET `/repositories/{owner}/{repo}/assignments/{issue_number}`

## 8. Error handling

- If no issues are found for random fetch, GitHub adapter raises explicit error
- If no contributor summaries are present, assignment generation fails with clear message
- If LLM output is unparsable, deterministic strategy fallback produces assignment

## 9. Operational notes

- For better assignment quality, run contributor sync before assignment generation
- Use `recent_n_commits` in sync when repository history is very large
- Current implementation keeps latest assignment per issue (upsert model)

## 10. Environment and defaults

Current default target repository:

- owner: `pandas-dev`
- repo: `pandas`
- url: `https://github.com/pandas-dev/pandas`
