"""Joint Desk API (FastAPI).

    uvicorn backend.main:app --reload

Env: DATABASE_URL (Postgres, e.g. Supabase; default SQLite backend/joint_desk.db; never logged), DEMO_MODE
(1 = cached LLM results only, never the API), UPLOAD_PASSCODE (uploads and imports need it in the X-Upload-Passcode
header; unset = open, for local use), LLM_DAILY_CAP (new LLM reads a day, default 20), ALLOWED_ORIGINS
(comma-separated; default the Vercel site and localhost), ANTHROPIC_API_KEY (only read when DEMO_MODE is off).
There are no user accounts yet: "by" on a decision is the name the client sends.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import json

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Path as PathParam, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend import services as S
from backend.db import Patient, backend_name, get_session, init_db
from kneedss import importer as I
from kneedss.results import build_results

PathwayKey = Literal["surgery", "physio", "weight_physio", "non_surgical", "review"]

# The Vercel site and local development only.
DEFAULT_ORIGINS = "https://frontend-wine-ten-82.vercel.app,http://localhost:5173,http://localhost:4173"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 5
MAX_SHEET_BYTES = 5 * 1024 * 1024
SIGNATURES = {".pdf": (b"%PDF-",), ".docx": (b"PK\x03\x04",)}

PatientId = Annotated[str, PathParam(pattern=r"^[A-Za-z0-9_-]{1,32}$")]
DB = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_dotenv()                                    # once, before the database is chosen (never overrides real env)
    os.environ.setdefault("DEMO_MODE", "1")          # spending API credit has to be switched on deliberately
    init_db()
    yield


app = FastAPI(title="Joint Desk API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Upload-Passcode"],
)


def passcode_needed() -> bool:
    return bool(os.environ.get("UPLOAD_PASSCODE"))


def passcode_ok(given: str | None) -> bool:
    expected = os.environ.get("UPLOAD_PASSCODE") or ""
    return not expected or hmac.compare_digest((given or "").encode(), expected.encode())


async def require_passcode(x_upload_passcode: Annotated[str | None, Header()] = None) -> None:
    """Uploads and imports can spend API credit: on the live site they need the passcode."""
    if not passcode_ok(x_upload_passcode):
        await asyncio.sleep(1)                          # slows guessing
        raise HTTPException(401, "Passcode needed")


Passcode = Depends(require_passcode)


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
def health(session: DB) -> dict:
    """Up, and how: demo mode, which database (never its URL), passcode on, today's new LLM reads and the cap."""
    return {"ok": True, "demo_mode": os.environ.get("DEMO_MODE") == "1", "database": backend_name(),
            "passcode": passcode_needed(), "llm_reads_today": S.reads_today(session), "llm_daily_cap": S.daily_cap()}


class PasscodeIn(BaseModel):
    passcode: str = Field(max_length=200)


@app.post("/passcode")
async def check_passcode(body: PasscodeIn) -> dict:
    """The app checks the passcode once and keeps it for the session."""
    if not passcode_ok(body.passcode):
        await asyncio.sleep(1)
        raise HTTPException(401, "Wrong passcode")
    return {"ok": True}


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


class BookIn(BaseModel):
    by: str = Field("clinician", min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    confirm: bool = False           # set after seeing who over 52 weeks the booking pushes out


class UnbookIn(BaseModel):
    by: str = Field("clinician", min_length=1, max_length=80)
    reason: str | None = Field(None, max_length=500)


@app.post("/patients/{pid}/book")
def book(pid: PatientId, body: BookIn, session: DB) -> dict:
    """Book into this week (always in, counts against capacity). Returns needs_confirm with the over-52s it would
    push out, and stores nothing, unless confirm is true."""
    try:
        return S.book(session, get_patient(session, pid), body.by, body.reason.strip(), body.confirm)
    except S.NoSlotLeft as e:
        raise HTTPException(409, str(e)) from None


@app.post("/patients/{pid}/unbook")
def unbook(pid: PatientId, body: UnbookIn, session: DB) -> dict:
    return S.unbook(session, get_patient(session, pid), body.by, body.reason)


@app.post("/letters", dependencies=[Passcode])
async def upload_letters(session: DB, files: Annotated[list[UploadFile], File()]) -> list[dict]:
    """Read one or many letters. Each file gets its own result, so one bad file doesn't stop the rest."""
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"At most {MAX_FILES} files at once")
    out = []
    for f in files:
        name = Path(f.filename or "letter").name
        data = await f.read(MAX_FILE_BYTES + 1)
        problem = file_problem(name, data)
        if problem:
            out.append({"file": name, "ok": False, "message": problem})
            continue
        try:
            out.append(S.read_letter(session, name, data))
        except Exception:                                # one file's surprise never fails the others
            S.log.exception("Upload %s failed", name)
            session.rollback()
            out.append({"file": name, "ok": False, "message": "Couldn't read file"})
    return out


# ---------------------------------------------------------------------------- spreadsheet import

async def read_sheet(file: UploadFile) -> tuple[str, bytes]:
    """A .csv or .xlsx upload, at most 5 MB, whose content matches its type."""
    name = Path(file.filename or "import").name
    suffix = Path(name).suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(415, "Only .csv or .xlsx")
    data = await file.read(MAX_SHEET_BYTES + 1)
    if len(data) > MAX_SHEET_BYTES:
        raise HTTPException(413, "File too large (max 5 MB)")
    if not data:
        raise HTTPException(422, "Empty file")
    if suffix == ".xlsx" and not data.startswith(b"PK\x03\x04"):
        raise HTTPException(415, "Not a real .xlsx file")
    if suffix == ".csv":
        try:
            if "\x00" in data.decode("utf-8-sig"):
                raise HTTPException(415, "Not a text CSV file")
        except UnicodeDecodeError:
            raise HTTPException(415, "CSV is not UTF-8") from None
    return name, data


def parse_mapping(raw: str | None) -> dict[str, str | None] | None:
    if raw is None:
        return None
    try:
        m = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(422, "Mapping is not JSON") from None
    if not isinstance(m, dict) or not all(isinstance(k, str) and (v is None or v in I.FIELDS) for k, v in m.items()):
        raise HTTPException(422, "Mapping must be {column header: field name or null}")
    return m


@app.post("/import/preview", dependencies=[Passcode])
async def import_preview(file: Annotated[UploadFile, File()], mapping: Annotated[str | None, Form()] = None) -> dict:
    """Detected (or given) column mapping, the first 10 rows, problems, and how many rows would import."""
    name, data = await read_sheet(file)
    try:
        return I.preview(name, data, parse_mapping(mapping))
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"Couldn't read the spreadsheet: {e}") from None


@app.post("/import/commit", dependencies=[Passcode])
async def import_commit(session: DB, file: Annotated[UploadFile, File()], mapping: Annotated[str, Form()],
                        by: Annotated[str, Form(max_length=80)] = "clinician") -> dict:
    """Import with the confirmed mapping: added / updated / skipped (with reasons). Recorded in the database."""
    name, data = await read_sheet(file)
    try:
        return S.import_commit(session, name, data, parse_mapping(mapping) or {}, by or "clinician")
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e)) from None


@app.post("/week/build")
def week(session: DB) -> dict:
    try:
        return S.build_week(session)
    except S.NoSlotLeft as e:
        raise HTTPException(409, str(e)) from None


@app.get("/results")
def results() -> dict:
    return build_results()
