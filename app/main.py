from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from connect_atlas import get_mongo_database

from .config import settings
from .context_optimizer import CommitContextOptimizer
from .events import stream_events
from .gemini_api import ProviderFactory
from .github_api import GitHubClient
from .repositories import (
    AssignmentStore,
    CommitStore,
    ContributorStore,
    DatabaseInitializer,
    IssueStore,
    RepositoryStore,
    SyncRunStore,
)
from .schemas import (
    ApiMessage,
    AssignmentGenerateRequest,
    AssignmentRecord,
    BulkIssueFetchRequest,
    CommitRecord,
    ContributorSummary,
    IssueRecord,
    OverrideRequest,
    RandomIssueFetchRequest,
    RepositorySummary,
    SyncRequest,
    SyncRunResult,
)
from .services import ContributorPipelineService

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


app = FastAPI(
    title="Intelligent Bug Report Management System - Contributor Intelligence API",
    version="1.0.0",
    description="Collects GitHub commit history, profiles contributors with Gemini, and stores summaries in MongoDB Atlas.",
)


def build_pipeline() -> ContributorPipelineService:
    db = get_mongo_database(settings.mongodb_db_name)
    DatabaseInitializer(db).ensure_indexes()
    github_client = GitHubClient(settings.github_api_base_url, settings.github_token)
    summarizer = ProviderFactory.create(settings.llm_provider)
    context_optimizer = CommitContextOptimizer(
        char_budget=settings.llm_prompt_char_budget,
        max_evidence_items=settings.llm_max_evidence_items,
        recent_messages_limit=settings.llm_recent_messages_limit,
    )
    return ContributorPipelineService(
        github_client=github_client,
        summarizer=summarizer,
        context_optimizer=context_optimizer,
        repository_store=RepositoryStore(db),
        commit_store=CommitStore(db),
        contributor_store=ContributorStore(db),
        issue_store=IssueStore(db),
        assignment_store=AssignmentStore(db),
        sync_run_store=SyncRunStore(db),
    )


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.on_event("startup")
def startup_event() -> None:
    app.state.pipeline = build_pipeline()


def get_pipeline() -> ContributorPipelineService:
    return app.state.pipeline


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.get("/stream", include_in_schema=False)
async def sse_stream(request: Request, last_event_id: int = Query(default=0)) -> StreamingResponse:
    async def generate():
        async for chunk in stream_events(last_event_id):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health", response_model=ApiMessage)
def health() -> ApiMessage:
    return ApiMessage(message="ok", data={"service": app.title, "status": "healthy"})


@app.post("/repositories/{owner}/{repo}/sync", response_model=SyncRunResult)
def sync_repository(
    owner: str,
    repo: str,
    request: SyncRequest,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> SyncRunResult:
    max_pages = request.max_pages or settings.default_sync_pages
    per_page = request.per_page or settings.default_page_size
    result = pipeline.sync_repository(
        owner,
        repo,
        max_pages=max_pages,
        per_page=per_page,
        recent_n_commits=request.recent_n_commits,
    )
    return SyncRunResult(**result)


@app.get("/repositories/{owner}/{repo}", response_model=RepositorySummary)
def get_repository(
    owner: str,
    repo: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> RepositorySummary:
    document = pipeline.get_repository_summary(owner, repo)
    if not document:
        raise HTTPException(status_code=404, detail="Repository not found. Run sync first.")
    return RepositorySummary(**document)


@app.get("/repositories/{owner}/{repo}/contributors", response_model=list[ContributorSummary])
def list_contributors(
    owner: str,
    repo: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> list[ContributorSummary]:
    return [ContributorSummary(**item) for item in pipeline.list_contributors(owner, repo)]


@app.get("/repositories/{owner}/{repo}/contributors/{contributor_key}", response_model=ContributorSummary)
def get_contributor(
    owner: str,
    repo: str,
    contributor_key: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ContributorSummary:
    document = pipeline.get_contributor_profile(owner, repo, contributor_key)
    if not document:
        raise HTTPException(status_code=404, detail="Contributor profile not found.")
    return ContributorSummary(**document)


@app.post("/repositories/{owner}/{repo}/contributors/{contributor_key}/refresh", response_model=ContributorSummary)
def refresh_contributor(
    owner: str,
    repo: str,
    contributor_key: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ContributorSummary:
    document = pipeline.refresh_contributor_profile(owner, repo, contributor_key)
    if not document:
        raise HTTPException(status_code=404, detail="No commits found for contributor.")
    return ContributorSummary(**document)


@app.post("/repositories/{owner}/{repo}/contributors/force-refresh", response_model=ApiMessage)
def force_refresh_all_contributors(
    owner: str,
    repo: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ApiMessage:
    result = pipeline.force_refresh_all_summaries(owner, repo)
    return ApiMessage(message="force-refresh completed", data=result)


@app.delete("/repositories/{owner}/{repo}/summaries", response_model=ApiMessage)
def clear_repository_summaries(
    owner: str,
    repo: str,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ApiMessage:
    result = pipeline.clear_repository_summaries(owner, repo)
    return ApiMessage(message="repository summaries cleared", data=result)


@app.delete("/summaries", response_model=ApiMessage)
def clear_all_summaries(
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ApiMessage:
    result = pipeline.clear_all_summaries()
    return ApiMessage(message="all summaries cleared", data=result)


@app.get("/repositories/{owner}/{repo}/commits", response_model=list[CommitRecord])
def list_commits(
    owner: str,
    repo: str,
    contributor_key: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> list[CommitRecord]:
    return [CommitRecord(**item) for item in pipeline.list_commits(owner, repo, contributor_key, limit)]


@app.post("/repositories/{owner}/{repo}/issues/random/fetch", response_model=IssueRecord)
def fetch_random_issue(
    owner: str,
    repo: str,
    request: RandomIssueFetchRequest,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> IssueRecord:
    document = pipeline.fetch_random_issue(
        owner,
        repo,
        state=request.state,
        max_pages=request.max_pages,
        per_page=request.per_page,
    )
    return IssueRecord(**document)


@app.get("/repositories/{owner}/{repo}/issues", response_model=list[IssueRecord])
def list_issues(
    owner: str,
    repo: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    state: str | None = Query(default=None),
    search: str | None = Query(default=None),
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> list[IssueRecord]:
    return [IssueRecord(**item) for item in pipeline.list_issues(
        owner, repo, limit=limit, offset=offset, state=state, search=search
    )]


@app.get("/repositories/{owner}/{repo}/issues/count")
def count_issues(
    owner: str,
    repo: str,
    state: str | None = Query(default=None),
    search: str | None = Query(default=None),
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> dict:
    return {"count": pipeline.count_issues(owner, repo, state=state, search=search)}


@app.get("/repositories/{owner}/{repo}/issues/{issue_number}", response_model=IssueRecord)
def get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> IssueRecord:
    document = pipeline.get_issue(owner, repo, issue_number)
    if not document:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return IssueRecord(**document)


@app.post("/repositories/{owner}/{repo}/issues/fetch-all", response_model=ApiMessage)
def fetch_all_issues(
    owner: str,
    repo: str,
    request: BulkIssueFetchRequest,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> ApiMessage:
    try:
        result = pipeline.fetch_and_store_all_issues(owner, repo, state=request.state, max_issues=request.max_issues)
        return ApiMessage(
            message=result["message"],
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/repositories/{owner}/{repo}/assignments/generate", response_model=AssignmentRecord)
def generate_assignment(
    owner: str,
    repo: str,
    request: AssignmentGenerateRequest,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> AssignmentRecord:
    try:
        document = pipeline.generate_issue_assignment(
            owner,
            repo,
            issue_number=request.issue_number,
            issue_state=request.issue_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssignmentRecord(**document)


@app.get("/repositories/{owner}/{repo}/assignments", response_model=list[AssignmentRecord])
def list_assignments(
    owner: str,
    repo: str,
    limit: int = Query(default=50, ge=1, le=200),
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> list[AssignmentRecord]:
    return [AssignmentRecord(**item) for item in pipeline.list_assignments(owner, repo, limit=limit)]


@app.get("/repositories/{owner}/{repo}/assignments/{issue_number}", response_model=AssignmentRecord)
def get_assignment(
    owner: str,
    repo: str,
    issue_number: int,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> AssignmentRecord:
    document = pipeline.get_assignment(owner, repo, issue_number)
    if not document:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return AssignmentRecord(**document)


@app.post("/repositories/{owner}/{repo}/assignments/{issue_number}/approve", response_model=AssignmentRecord)
def approve_assignment(
    owner: str,
    repo: str,
    issue_number: int,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> AssignmentRecord:
    document = pipeline.approve_assignment(owner, repo, issue_number)
    if not document:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return AssignmentRecord(**document)


@app.post("/repositories/{owner}/{repo}/assignments/{issue_number}/override", response_model=AssignmentRecord)
def override_assignment(
    owner: str,
    repo: str,
    issue_number: int,
    request: OverrideRequest,
    pipeline: ContributorPipelineService = Depends(get_pipeline),
) -> AssignmentRecord:
    document = pipeline.override_assignment(owner, repo, issue_number, request.contributor_key)
    if not document:
        raise HTTPException(status_code=404, detail="Assignment or contributor not found.")
    return AssignmentRecord(**document)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
