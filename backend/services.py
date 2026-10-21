"""What the API does, kept apart from the HTTP layer.

Reading a letter: text -> extract (cache; DEMO_MODE=1 never calls the API) -> quote check -> rules -> match on NHS
number. A letter whose text is already in the database reuses the stored result, so the same letter is never
paid for twice and the seeded demo letters can be uploaded on a server that has no cache.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlmodel import Session, col, select

from backend.db import Decision, Letter, Patient, nhs_digits, now
from kneedss import extract as X
from kneedss import llm
from kneedss import optimise as O
from kneedss.rules import PATHWAYS, PRIORITY_MAX

# A demo letter's ID at the start of a file name: L0001.txt, T0042.pdf, "L0001 (1).pdf"
LETTER_ID = re.compile(r"^([LT]\d{4})(?!\d)")


# ---------------------------------------------------------------------------- decisions

def latest_decision(session: Session, pid: str) -> Decision | None:
    return session.exec(select(Decision).where(Decision.patient_id == pid)
                        .order_by(col(Decision.at).desc(), col(Decision.id).desc())).first()


def latest_decisions(session: Session) -> dict[str, Decision]:
    """Each patient's newest decision, in one query."""
    out: dict[str, Decision] = {}
    for d in session.exec(select(Decision).order_by(col(Decision.at), col(Decision.id))).all():
        out[d.patient_id] = d
    return out


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


def record_decision(session: Session, p: Patient, new_pathway: str, by: str, reason: str | None, kind: str) -> Decision:
    old = effective_pathway(p, latest_decision(session, p.id))
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
    return {"id": p.id, "letter_id": letter.letter_id if letter else None, "set": letter.source if letter else None,
            "name": p.name, "nhs_number": p.nhs_number, "filename": letter.filename if letter else None,
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
            "model": letter.model if letter else None, "letter_text": letter.text if letter else ""}


def queue(session: Session, pathways: list[str] | None = None) -> list[dict]:
    """Referrals: patients with a letter, highest priority first."""
    rows, decisions, letters = [], latest_decisions(session), latest_letters(session)
    for p in session.exec(select(Patient).where(col(Patient.letter_id).is_not(None))).all():
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

    try:
        ex = X.extract(text, letter_id)
    except X.DemoCacheMiss:
        return fail("Couldn't read file · demo mode")
    except (llm.LLMError, ValueError):
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


# ---------------------------------------------------------------------------- week

def next_monday(today: date | None = None) -> str:
    today = today or date.today()
    return (today + timedelta(days=(7 - today.weekday()) % 7 or 7)).isoformat()


def build_week(session: Session) -> dict:
    """The optimiser on the current database, overrides included."""
    rows, decisions = [], latest_decisions(session)
    for p in session.exec(select(Patient)).all():
        rows.append({"patient_id": p.id, "pathway": effective_pathway(p, decisions.get(p.id)),
                     "priority_score": p.priority, "weeks_waiting": p.weeks_waiting, "has_letter": p.letter_id is not None,
                     "name": p.name})
    df = pd.DataFrame(rows)
    plan = O.optimise(df)
    return O.plan_to_json(plan, df, dict(zip(df.patient_id, df.name)), set(df.patient_id[df.has_letter]), next_monday())
