"""SQLite database (SQLModel): patients, letters read, and the clinician's decisions.

On first start the database is filled from what the repo already holds, with no API calls: the cleaned waiting list
(data/output/waiting_list.csv) and the 250 letters already read and checked (the demo export in
frontend/public/demo/patients/, which came from the extraction cache).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

from kneedss.extract import text_key
from kneedss.rules import decide, priority_breakdown, priority_score

ROOT = Path(__file__).resolve().parent.parent
WAITING_LIST = ROOT / "data" / "output" / "waiting_list.csv"
DEMO_PATIENTS = ROOT / "frontend" / "public" / "demo" / "patients"
DEFAULT_DB = ROOT / "backend" / "joint_desk.db"


def now() -> datetime:
    return datetime.now(timezone.utc)


def nhs_digits(n) -> str:
    return re.sub(r"\D", "", str(n or ""))


class Patient(SQLModel, table=True):
    id: str = Field(primary_key=True)
    nhs_number: str
    nhs_digits: str = Field(index=True, unique=True)
    name: str
    age: int | None = None
    sex: str | None = None
    side: str | None = None
    weeks_waiting: int = 0
    on_waiting_list: bool = True
    # the rules' decision on the latest information: the newest letter if there is one, else the GP record
    pathway: str
    rule: int
    priority: int
    weight_support: bool = False
    reasons: list = Field(default_factory=list, sa_column=Column(JSON))
    priority_parts: dict = Field(default_factory=dict, sa_column=Column(JSON))
    facts: dict = Field(default_factory=dict, sa_column=Column(JSON))
    letter_id: str | None = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=now)


class Letter(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    letter_id: str = Field(index=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    filename: str
    source: str                                  # "dev", "test" (seeded) or "upload"
    text: str
    text_key: str = Field(index=True)
    model: str | None = None                     # which model read it (traceability; never sent to the app)
    facts: dict = Field(default_factory=dict, sa_column=Column(JSON))
    quotes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    spans: list = Field(default_factory=list, sa_column=Column(JSON))
    dropped: list = Field(default_factory=list, sa_column=Column(JSON))
    read_at: datetime = Field(default_factory=now)


class Decision(SQLModel, table=True):
    """Every confirm and override is kept: who, when, the pathway before and after, and why."""
    id: int | None = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    kind: str                                    # "confirmed" or "overridden"
    rules_pathway: str
    old_pathway: str
    new_pathway: str
    reason: str | None = None
    by: str
    at: datetime = Field(default_factory=now)


@lru_cache(maxsize=None)
def engine_for(url: str):
    return create_engine(url, connect_args={"check_same_thread": False})


def get_engine():
    return engine_for(os.environ.get("DATABASE_URL") or f"sqlite:///{DEFAULT_DB}")


def record_facts(r) -> dict:
    """Rules inputs from a waiting-list row (the GP record)."""
    val = lambda v: None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
    return {"oks": val(r.oks), "oks_before": val(r.oks_before), "kl": val(r.kl_grade),
            "physio_weeks": val(r.physio_weeks), "bmi": val(r.bmi), "weeks_waiting": int(r.weeks_waiting),
            "night_pain": bool(r.night_pain), "lives_alone_or_carer": bool(r.lives_alone_or_carer)}


def cached_model(letter_id: str) -> str | None:
    """The model that read a seeded letter, from its cache file when the cache is here (not on the server)."""
    for path in (ROOT / "data" / "cache").glob(f"*/{letter_id}.json"):
        try:
            return json.loads(path.read_text()).get("model")
        except (OSError, json.JSONDecodeError):
            return None
    return None


def seed(session: Session) -> None:
    """Fill an empty database: the cleaned waiting list, then the letters already read."""
    wl = pd.read_csv(WAITING_LIST, dtype={"nhs_number": str})
    for r in wl.itertuples():
        f = record_facts(r)
        d = decide(f)
        session.add(Patient(
            id=r.patient_id, nhs_number=r.nhs_number, nhs_digits=nhs_digits(r.nhs_number),
            name=f"{r.first_name} {r.surname}", age=int(r.age), sex=r.sex, side=r.laterality,
            weeks_waiting=int(r.weeks_waiting), on_waiting_list=True,
            pathway=d["pathway"], rule=d["rule"], priority=priority_score(f), weight_support=d["weight_support"],
            reasons=d["reasons"], priority_parts=priority_breakdown(f), facts=f))
    session.commit()

    for path in sorted(DEMO_PATIENTS.glob("*.json")):
        p = json.loads(path.read_text())
        patient = session.get(Patient, p["id"])
        if patient is None:
            continue
        session.add(Letter(letter_id=p["letter_id"], patient_id=p["id"], filename=f"{p['letter_id']}.txt",
                           source=p["set"], text=p["letter_text"], text_key=text_key(p["letter_text"]),
                           model=cached_model(p["letter_id"]), facts=p["facts"], quotes=p["quotes"], spans=p["spans"],
                           dropped=p["dropped"]))
        patient.pathway, patient.rule, patient.priority = p["pathway"], p["rule"], p["priority"]
        patient.weight_support, patient.reasons, patient.priority_parts = p["weight_support"], p["reasons"], p["priority_parts"]
        patient.letter_id = p["letter_id"]
        session.add(patient)
    session.commit()


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if s.exec(select(Patient).limit(1)).first() is None:
            seed(s)


def get_session():
    with Session(get_engine()) as s:
        yield s
