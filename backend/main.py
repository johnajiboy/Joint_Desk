"""Joint Desk API (FastAPI).

    uvicorn backend.main:app --reload

Env: DATABASE_URL (default sqlite backend/joint_desk.db), DEMO_MODE (1 = cached LLM results only, never the API),
ALLOWED_ORIGINS (comma-separated; default the Vercel site and localhost), ANTHROPIC_API_KEY (only read when
DEMO_MODE is off). There are no user accounts yet: "by" on a decision is the name the client sends.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Path as PathParam, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend import services as S
from backend.db import Patient, get_session, init_db
from kneedss.results import build_results

PathwayKey = Literal["surgery", "physio", "weight_physio", "non_surgical", "review"]

# The Vercel site (its production addresses) and local development only.
DEFAULT_ORIGINS = ("https://frontend-wine-ten-82.vercel.app,https://frontend-johnajiboys-projects.vercel.app,"
                   "https://frontend-git-main-johnajiboys-projects.vercel.app,http://localhost:5173,http://localhost:4173")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 20
SIGNATURES = {".pdf": (b"%PDF-",), ".docx": (b"PK\x03\x04",)}

PatientId = Annotated[str, PathParam(pattern=r"^[A-Za-z0-9_-]{1,32}$")]
DB = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.environ.setdefault("DEMO_MODE", "1")          # spending API credit has to be switched on deliberately
    init_db()
    yield


app = FastAPI(title="Joint Desk API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def file_problem(name: str, data: bytes) -> str | None:
    """Why a file can't be read, or None. Checks the extension, the size and that the content matches the type."""
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".docx", ".txt"):
        return "Only PDF, DOCX or TXT"
    if len(data) > MAX_FILE_BYTES:
        return f"File too large (max {MAX_FILE_BYTES // (1024 * 1024)} MB)"
    if not data:
        return "Empty file"
    if suffix in SIGNATURES and not data.startswith(SIGNATURES[suffix]):
        return f"Not a real {suffix[1:].upper()} file"
    if suffix == ".txt":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return "Text file is not UTF-8"
        if "\x00" in text:
            return "Not a text file"
    return None


def get_patient(session: Session, pid: str) -> Patient:
    p = session.get(Patient, pid)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return p


class ConfirmIn(BaseModel):
    by: str = Field("clinician", min_length=1, max_length=80)
    reason: str | None = Field(None, max_length=500)


class OverrideIn(ConfirmIn):
    pathway: PathwayKey


@app.get("/health")
def health() -> dict:
    return {"ok": True, "demo_mode": os.environ.get("DEMO_MODE") == "1"}


@app.get("/queue")
def get_queue(session: DB, pathway: Annotated[list[PathwayKey] | None, Query()] = None) -> list[dict]:
    """Referrals (patients with a letter). Repeat ?pathway= to filter by the pathway that counts (overrides included)."""
    return S.queue(session, pathway)


@app.get("/patients/{pid}")
def get_one(pid: PatientId, session: DB) -> dict:
    return S.patient_out(session, get_patient(session, pid))


@app.post("/patients/{pid}/confirm")
def confirm(pid: PatientId, body: ConfirmIn, session: DB) -> dict:
    p = get_patient(session, pid)
    current = S.effective_pathway(p, S.latest_decision(session, pid))
    return S.decision_out(S.record_decision(session, p, current, body.by, body.reason, "confirmed"))


@app.post("/patients/{pid}/override")
def override(pid: PatientId, body: OverrideIn, session: DB) -> dict:
    p = get_patient(session, pid)
    kind = "confirmed" if body.pathway == p.pathway else "overridden"
    return S.decision_out(S.record_decision(session, p, body.pathway, body.by, body.reason, kind))


@app.post("/letters")
async def upload_letters(session: DB, files: Annotated[list[UploadFile], File()]) -> list[dict]:
    """Read one or many letters. Each file gets its own result, so one bad file doesn't stop the rest."""
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"At most {MAX_FILES} files at once")
    out = []
    for f in files:
        name = Path(f.filename or "letter").name
        data = await f.read(MAX_FILE_BYTES + 1)
        problem = file_problem(name, data)
        out.append({"file": name, "ok": False, "message": problem} if problem else S.read_letter(session, name, data))
    return out


@app.post("/week/build")
def week(session: DB) -> dict:
    return S.build_week(session)


@app.get("/results")
def results() -> dict:
    return build_results()
