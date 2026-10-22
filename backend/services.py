"""What the API does, kept apart from the HTTP layer.

Reading a letter: text -> extract (cache; DEMO_MODE=1 never calls the API) -> quote check -> rules -> match on NHS
number. A letter whose text is already in the database reuses the stored result, so the same letter is never
paid for twice and the seeded demo letters can be uploaded on a server that has no cache.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from backend.db import Decision, ImportRecord, Letter, LlmDay, Patient, nhs_digits, now
from kneedss import importer as I
from kneedss import extract as X
from kneedss import llm
from kneedss import optimise as O
from kneedss.rules import PATHWAYS, PRIORITY_MAX

# A demo letter's ID at the start of a file name: L0001.txt, T0042.pdf, "L0001 (1).pdf"
LETTER_ID = re.compile(r"^([LT]\d{4})(?!\d)")


log = logging.getLogger("uvicorn.error")         # the server log (Render)
LIMIT_REACHED = "Daily limit reached · try tomorrow"
DEFAULT_DAILY_CAP = 20


# ---------------------------------------------------------------------------- daily LLM cap

def daily_cap() -> int:
    try:
        return max(0, int(os.environ.get("LLM_DAILY_CAP", DEFAULT_DAILY_CAP)))
    except ValueError:
        return DEFAULT_DAILY_CAP


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def reads_today(session: Session) -> int:
    row = session.get(LlmDay, today())
    return row.reads if row else 0


def reserve_llm_read(session: Session) -> bool:
    """Take one of today's new LLM reads, or False when the cap is reached. One conditional UPDATE, so two uploads
    at once can't both take the last read."""
    day = today()
    if session.get(LlmDay, day) is None:
        try:
            session.add(LlmDay(day=day, reads=0))
            session.commit()
        except IntegrityError:                           # another request made today's row first
            session.rollback()
    taken = session.execute(update(LlmDay).where(col(LlmDay.day) == day, col(LlmDay.reads) < daily_cap())
                            .values(reads=LlmDay.reads + 1)).rowcount
    session.commit()
    session.expire_all()
    return taken == 1


# ---------------------------------------------------------------------------- decisions

PATHWAY_KINDS = ("confirmed", "overridden")     # decisions that set the pathway
BOOKING_KINDS = ("booked", "unbooked")          # "Book this week" and "Unbook": the pathway stays as it was


def latest_decision(session: Session, pid: str, kinds: tuple[str, ...] = PATHWAY_KINDS) -> Decision | None:
    return session.exec(select(Decision).where(Decision.patient_id == pid, col(Decision.kind).in_(kinds))
                        .order_by(col(Decision.at).desc(), col(Decision.id).desc())).first()


def latest_decisions(session: Session, kinds: tuple[str, ...] = PATHWAY_KINDS) -> dict[str, Decision]:
    """Each patient's newest decision of these kinds, in one query."""
    out: dict[str, Decision] = {}
    for d in session.exec(select(Decision).where(col(Decision.kind).in_(kinds)).order_by(col(Decision.at), col(Decision.id))).all():
        out[d.patient_id] = d
    return out


def bookings(session: Session) -> dict[str, Decision]:
    """Patients booked into this week now (their newest booking decision is "booked")."""
    return {pid: d for pid, d in latest_decisions(session, BOOKING_KINDS).items() if d.kind == "booked"}


def booking_out(d: Decision | None) -> dict | None:
    if d is None or d.kind != "booked":
        return None
    return {"by": d.by, "at": d.at.isoformat(), "reason": d.reason}


def latest_letters(session: Session) -> dict[str, Letter]:
    out: dict[str, Letter] = {}
    for letter in session.exec(select(Letter).order_by(col(Letter.read_at), col(Letter.id))).all():
        out[letter.patient_id] = letter
    return out


def effective_pathway(p: Patient, d: Decision | None) -> str:
    return d.new_pathway if d else p.pathway


def decision_out(d: Decision | None) -> dict | None:
    if d is None:
        return None
    return {"kind": d.kind, "pathway": d.new_pathway, "was": d.rules_pathway, "old_pathway": d.old_pathway,
            "reason": d.reason, "by": d.by, "at": d.at.isoformat()}


def record_decision(session: Session, p: Patient, new_pathway: str | None, by: str, reason: str | None, kind: str) -> Decision:
    """A confirm or override (new_pathway), or a booking (new_pathway None: the pathway is unchanged)."""
    old = effective_pathway(p, latest_decision(session, p.id))
    new_pathway = new_pathway or old
    d = Decision(patient_id=p.id, kind=kind, rules_pathway=p.pathway, old_pathway=old, new_pathway=new_pathway,
                 reason=reason, by=by)
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


# ---------------------------------------------------------------------------- shapes the frontend reads

def latest_letter(session: Session, p: Patient) -> Letter | None:
    if not p.letter_id:
        return None
    return session.exec(select(Letter).where(Letter.patient_id == p.id)
                        .order_by(col(Letter.read_at).desc(), col(Letter.id).desc())).first()


def referral_out(p: Patient, letter: Letter | None, d: Decision | None) -> dict:
    source = letter.source if letter else ("import" if p.imported_from else None)
    return {"id": p.id, "letter_id": letter.letter_id if letter else None, "set": source,
            "name": p.name, "nhs_number": p.nhs_number, "filename": letter.filename if letter else p.imported_from,
            "pathway": p.pathway, "rule": p.rule, "priority": p.priority,
            "weeks_waiting": p.weeks_waiting if p.on_waiting_list else None, "weight_support": p.weight_support,
            "text_key": letter.text_key if letter else None, "decision": decision_out(d)}


def patient_out(session: Session, p: Patient) -> dict:
    letter, d = latest_letter(session, p), latest_decision(session, p.id)
    facts = letter.facts if letter else {**p.facts, "kl": p.facts.get("kl"), "age": p.age, "sex": p.sex, "side": p.side}
    return {**referral_out(p, letter, d), "nhs_number": p.nhs_number, "on_waiting_list": p.on_waiting_list,
            "facts": facts, "quotes": letter.quotes if letter else {}, "spans": letter.spans if letter else [],
            "dropped": letter.dropped if letter else [], "label": PATHWAYS[p.pathway], "reasons": p.reasons,
            "priority_parts": p.priority_parts, "priority_max": PRIORITY_MAX,
            "booking": booking_out(latest_decision(session, p.id, BOOKING_KINDS)),
            "letter_text": letter.text if letter else ""}         # Letter.model is kept in the database only


def queue(session: Session, pathways: list[str] | None = None) -> list[dict]:
    """Referrals: patients with a letter or from a spreadsheet import, highest priority first."""
    rows, decisions, letters = [], latest_decisions(session), latest_letters(session)
    for p in session.exec(select(Patient).where(col(Patient.letter_id).is_not(None) | col(Patient.imported_from).is_not(None))).all():
        d = decisions.get(p.id)
        if pathways and effective_pathway(p, d) not in pathways:
            continue
        rows.append(referral_out(p, letters.get(p.id), d))
    return sorted(rows, key=lambda r: (-r["priority"], -(r["weeks_waiting"] or 0), r["id"]))


# ---------------------------------------------------------------------------- reading letters

def _apply(session: Session, p: Patient, letter: Letter, facts: dict) -> None:
    """The rules on the letter's facts, with weeks waiting from the waiting list when the patient is on it."""
    dec = X.decide_letter(facts, p.weeks_waiting if p.on_waiting_list else None)
    p.pathway, p.rule, p.priority, p.weight_support = dec["pathway"], dec["rule"], dec["priority"], dec["weight_support"]
    p.reasons, p.priority_parts, p.letter_id, p.updated_at = dec["reasons"], dec["priority_parts"], letter.letter_id, now()
    if not p.on_waiting_list and dec["facts_used"]["weeks_waiting"] is not None:
        p.weeks_waiting = int(dec["facts_used"]["weeks_waiting"])
    session.add(p)


def read_letter(session: Session, filename: str, data: bytes) -> dict:
    """One uploaded file -> an UploadResult: {"file", "ok", "referral"} or {"file", "ok": False, "message"}."""
    fail = lambda message: {"file": filename, "ok": False, "message": message}
    try:
        text = X.read_letter(filename, data)
    except Exception:                                    # unreadable PDF/DOCX
        return fail("Couldn't read file")
    if not text.strip():
        return fail("No text in file")
    key = X.text_key(text)

    seen = session.exec(select(Letter).where(Letter.text_key == key)).first()
    if seen:                                             # same letter as before: no new extraction
        p = session.get(Patient, seen.patient_id)
        return {"file": filename, "ok": True, "referral": referral_out(p, seen, latest_decision(session, p.id))}

    named = LETTER_ID.match(Path(filename).stem.strip().upper())
    letter_id = named.group(1) if named else f"U{key[:11].upper()}"

    # Same letter in another format (a PDF or DOCX of a letter already read): reuse its facts only if every quote
    # behind them is in this document, then highlight them in this document's text. No extraction needed.
    stored = session.exec(select(Letter).where(Letter.letter_id == letter_id)
                          .order_by(col(Letter.read_at).desc())).first() if named else None
    if stored and stored.quotes and all(X.quote_in_letter(q, text) for q in stored.quotes.values()):
        p = session.get(Patient, stored.patient_id)
        return _save(session, p, filename, letter_id, text, key, stored.model, stored.facts, stored.quotes, stored.dropped)

    # a new read costs API credit: it needs one of today's reads (DEMO_MODE=1 never calls the API; cached letters are free)
    if os.environ.get("DEMO_MODE") != "1" and not X.is_cached(text, letter_id) and not reserve_llm_read(session):
        return fail(LIMIT_REACHED)
    try:
        ex = X.extract(text, letter_id)
    except X.DemoCacheMiss:
        return fail("Couldn't read file · demo mode")
    except (llm.LLMError, ValueError) as e:
        log.warning("Letter %s not read: %s: %s", letter_id, type(e).__name__, e)     # never the key or the URL
        return fail("Couldn't read file")

    digits = nhs_digits(ex.facts.get("nhs_number"))
    if len(digits) != 10:
        return fail("No NHS number in letter")
    p = session.exec(select(Patient).where(Patient.nhs_digits == digits)).first()
    if p is None:                                        # not on the waiting list yet: a new referral
        p = Patient(id=f"NEW{digits[-6:]}", nhs_number=ex.facts["nhs_number"], nhs_digits=digits,
                    name=str(ex.facts.get("name") or "Unknown"), age=ex.facts.get("age"), sex=ex.facts.get("sex"),
                    side=ex.facts.get("side"), weeks_waiting=0, on_waiting_list=False,
                    pathway="review", rule=1, priority=0)
    return _save(session, p, filename, letter_id, text, key, ex.model, ex.facts, ex.quotes, ex.dropped)


def _save(session: Session, p: Patient, filename: str, letter_id: str, text: str, key: str, model: str,
          facts: dict, quotes: dict, dropped: list) -> dict:
    """Store the letter, apply the rules to the patient, and return the UploadResult."""
    letter = Letter(letter_id=letter_id, patient_id=p.id, filename=filename[:200], source="upload", text=text,
                    text_key=key, model=model, facts=facts, quotes=quotes, spans=X.quote_spans(text, quotes),
                    dropped=dropped)
    session.add(p)
    session.flush()
    session.add(letter)
    _apply(session, p, letter, facts)
    session.commit()
    session.refresh(p)
    return {"file": filename, "ok": True, "referral": referral_out(p, letter, latest_decision(session, p.id))}


# ---------------------------------------------------------------------------- spreadsheet import

def import_commit(session: Session, filename: str, data: bytes, mapping: dict, by: str) -> dict:
    """Import a spreadsheet with a confirmed mapping: update patients matched on NHS number, create the rest.
    Raises ValueError if the file can't be read or the mapping is missing a required field."""
    headers, rows = I.read_table(filename, data)
    mapping = {h: mapping.get(h) for h in headers}
    if problems := I.mapping_problems(mapping):
        raise ValueError("; ".join(problems))
    result = I.plan(headers, rows, mapping)
    added = updated = 0
    touched: list[Patient] = []
    for item in result["valid"]:
        rec, dec = item["record"], item["decision"]
        digits = nhs_digits(rec["nhs_number"])
        p = session.exec(select(Patient).where(Patient.nhs_digits == digits)).first()
        if p:
            updated += 1
        else:
            added += 1
            p = Patient(id=f"IMP{digits}", nhs_number=rec["nhs_number"], nhs_digits=digits, name=rec["name"],
                        pathway=dec["pathway"], rule=dec["rule"], priority=dec["priority"])
        p.name, p.age, p.sex, p.side = rec["name"], rec["age"], rec["sex"], rec["side"]
        p.weeks_waiting, p.on_waiting_list, p.imported_from = rec["weeks_waiting"], True, filename[:200]
        p.pathway, p.rule, p.priority, p.weight_support = dec["pathway"], dec["rule"], dec["priority"], dec["weight_support"]
        p.reasons, p.priority_parts, p.facts, p.updated_at = dec["reasons"], dec["priority_parts"], dec["facts"], now()
        session.add(p)
        touched.append(p)
    record = ImportRecord(filename=filename[:200], by=by, rows=len(rows), added=added, updated=updated,
                          skipped=len(result["skipped"]), mapping=mapping, skipped_rows=result["skipped"])
    session.add(record)
    session.commit()
    decisions, letters = latest_decisions(session), latest_letters(session)
    return {"import_id": record.id, "file": filename, "rows": len(rows), "added": added, "updated": updated,
            "skipped": result["skipped"],
            "referrals": [referral_out(p, letters.get(p.id), decisions.get(p.id)) for p in touched]}


# ---------------------------------------------------------------------------- week

def next_monday(today: date | None = None) -> str:
    today = today or date.today()
    return (today + timedelta(days=(7 - today.weekday()) % 7 or 7)).isoformat()


def week_frame(session: Session) -> pd.DataFrame:
    rows, decisions = [], latest_decisions(session)
    for p in session.exec(select(Patient)).all():
        rows.append({"patient_id": p.id, "pathway": effective_pathway(p, decisions.get(p.id)),
                     "priority_score": p.priority, "weeks_waiting": p.weeks_waiting, "has_letter": p.letter_id is not None,
                     "name": p.name})
    return pd.DataFrame(rows)


class NoSlotLeft(Exception):
    """More patients booked than a slot type has slots."""


def plan_week(df: pd.DataFrame, locked: set[str]) -> O.Plan:
    try:
        return O.optimise(df, locked=locked)
    except RuntimeError as e:
        raise NoSlotLeft("No slot left · all booked") from e


def build_week(session: Session) -> dict:
    """The optimiser on the current database: bookings first, then over-52s, then priority (overrides included)."""
    df = week_frame(session)
    booked = bookings(session)
    plan = plan_week(df, set(booked))
    changes = {pid: {"overridden": True, "booked": False, "was": d.rules_pathway, "by": d.by, "at": d.at.isoformat(),
                     "reason": d.reason, "booking_reason": None}
               for pid, d in latest_decisions(session).items() if d.kind == "overridden"}
    for pid, d in booked.items():
        c = changes.setdefault(pid, {"overridden": False, "was": None})
        c.update(booked=True, by=d.by, at=max(c.get("at") or "", d.at.isoformat()), booking_reason=d.reason)
        c.setdefault("reason", None)
    # the API serves a page for every patient (a letter or the waiting-list record), so every name can link
    return O.plan_to_json(plan, df, dict(zip(df.patient_id, df.name)), set(df.patient_id), next_monday(), changes)


def book(session: Session, p: Patient, by: str, reason: str, confirm: bool) -> dict:
    """Book a patient into this week. If that pushes anyone over 52 weeks out of a slot, nothing is stored until the
    clinician confirms with those names in front of them."""
    pathway = effective_pathway(p, latest_decision(session, p.id))
    if pathway not in O.ALLOWED:
        raise NoSlotLeft("No slot for this pathway")
    df = week_frame(session)
    plan = plan_week(df, set(bookings(session)) | {p.id})
    names = dict(zip(df.patient_id, df.name))
    weeks = dict(zip(df.patient_id, df.weeks_waiting))
    pushed = [{"id": pid, "name": names[pid], "weeks_waiting": int(weeks[pid])} for pid in plan.pushed_out]
    if pushed and not confirm:
        return {"booked": False, "needs_confirm": True, "pushed_out": pushed, "booking": None}
    d = record_decision(session, p, None, by, reason, "booked")
    return {"booked": True, "needs_confirm": False, "pushed_out": pushed, "booking": booking_out(d)}


def unbook(session: Session, p: Patient, by: str, reason: str | None) -> dict:
    if latest_decision(session, p.id, BOOKING_KINDS) is None or p.id not in bookings(session):
        return {"booked": False, "booking": None}
    record_decision(session, p, None, by, reason, "unbooked")
    return {"booked": False, "booking": None}
