"""Web backend for the Jeopardy Trainer.

Serves a small REST API plus the static frontend in web/, so the whole
app is one process, one port, and works identically from a desktop
browser or an iPhone's Safari -- no native app needed on any platform.

Run with:
    uvicorn api.app:app --host 0.0.0.0 --port 8000
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import Config
from db.connection import run_schema_script
from db.loader import load_opentdb_results
from sources.opentdb_client import OpenTDBClient
from study.quiz import (
    list_subjects,
    get_quiz_clues,
    get_clue,
    record_attempt,
    weak_subjects,
    check_answer,
)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Jeopardy Trainer API")

# Permissive by default since this is an open-source template people will
# fork and may host frontend/backend separately. Tighten this if you
# deploy publicly with a fixed frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_schema() -> None:
    """Create the SQLite file/tables on first run so a fresh clone just works."""
    if not os.path.exists(Config.SQLITE_DB_PATH):
        run_schema_script()
    else:
        # Table-level CREATE IF NOT EXISTS is safe to re-run on an existing db.
        run_schema_script()


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate write-triggering endpoints (opentdb pulls) behind a shared-secret
    header. Disabled by default so a public deployment doesn't silently let
    anyone burn your opentdb rate limit on your behalf."""
    expected = Config.ADMIN_TOKEN
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Admin actions are disabled. Set ADMIN_TOKEN in .env to enable them.",
        )
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token.")


# ---------------------------------------------------------------------
# Read-only endpoints -- no auth needed
# ---------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/subjects")
def api_list_subjects():
    return list_subjects()


@app.get("/api/quiz")
def api_get_quiz(
    subject: str | None = None,
    difficulty: str | None = None,
    round: str | None = None,
    only_missed: bool = False,
    limit: int = 10,
):
    clues = get_quiz_clues(
        subject=subject,
        difficulty=difficulty,
        round_name=round,
        only_missed=only_missed,
        limit=limit,
    )
    # Never send the correct response to the client before they answer.
    return [
        {
            "clue_id": c["ClueId"],
            "clue_text": c["ClueText"],
            "difficulty": c["Difficulty"],
            "category_name": c["CategoryName"],
        }
        for c in clues
    ]


class AttemptRequest(BaseModel):
    clue_id: int
    user_answer: str


@app.post("/api/quiz/attempt")
def api_submit_attempt(req: AttemptRequest):
    clue = get_clue(req.clue_id)
    if clue is None:
        raise HTTPException(status_code=404, detail="Clue not found.")

    was_correct = check_answer(req.user_answer, clue["CorrectResponse"])
    record_attempt(req.clue_id, req.user_answer, was_correct)

    return {
        "is_correct": was_correct,
        "correct_response": clue["CorrectResponse"],
    }


@app.get("/api/weak-subjects")
def api_weak_subjects(limit: int = 10):
    return weak_subjects(limit=limit)


# ---------------------------------------------------------------------
# Admin endpoints -- gated behind ADMIN_TOKEN, see require_admin() above
# ---------------------------------------------------------------------

class PullOpenTDBRequest(BaseModel):
    subject: str
    category_id: int | None = None
    difficulty: str | None = None
    count: int = 50


@app.post("/api/admin/pull-opentdb", dependencies=[])
def api_pull_opentdb(req: PullOpenTDBRequest, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)

    client = OpenTDBClient()
    if req.category_id:
        results = client.fetch_all_for_category(req.category_id, target_count=req.count)
    else:
        results, _ = client.fetch_questions(amount=min(req.count, 50), difficulty=req.difficulty)

    category_name_to_id = {c["name"]: c["id"] for c in client.get_categories()}
    n = load_opentdb_results(results, subject_name=req.subject, category_name_to_id=category_name_to_id)
    return {"loaded": n}


# ---------------------------------------------------------------------
# Static frontend -- mounted last so it doesn't shadow the /api routes
# ---------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
