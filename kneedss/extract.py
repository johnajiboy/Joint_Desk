"""Read a referral letter into facts, check every quote, and apply the pathway rules.

Flow: letter text -> llm.complete_json (cached per model) -> quote check -> rules.decide / priority_score.
The LLM only reads; rules.py decides. Cache: data/cache/<model>/<letter_id>.json holds the raw LLM answer,
so the quote check can change without paying for new calls, plus the call's token usage and cost.
DEMO_MODE=1 (the default in .env) never calls the API.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from kneedss import llm
from kneedss.rules import PATHWAYS, decide, priority_breakdown, priority_score
from kneedss.schemas import FALSE_WITHOUT_QUOTE, FIELDS, RANGES, VALUE_IS_QUOTE, LetterFacts

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"

SYSTEM = """You read NHS GP referral letters for knee osteoarthritis and record the facts they state.

For every field give the value and the quote: the exact words copied from the letter that state it, character
for character (keep the letter's spelling, capitals and abbreviations). Use the shortest span that shows the value.
If the letter doesn't state a fact, set both value and quote to null. Never guess and never use outside knowledge.

Reading rules:
- Read the whole letter, including the record block at the top (problems, medication, observations).
- When a fact appears more than once with different values, use the most recent dated value and quote that one.
- Negations count: "denies night pain" or "sleeps well" means night_pain is false.
- Oxford Knee Score (OKS) runs 0-48, lower is worse. oks is the current score; oks_before an earlier one.
- Kellgren-Lawrence (KL) grade: use the grade if stated. Otherwise grade the X-ray report wording:
  0 no features of osteoarthritis; 1 doubtful narrowing, possible osteophytic lipping;
  2 definite osteophytes, possible narrowing (mild); 3 moderate osteophytes, definite narrowing, some sclerosis
  (moderate or established); 4 large osteophytes, marked narrowing, bone on bone, severe sclerosis or deformity
  (severe, advanced or end-stage). When you grade from the wording, quote that wording as the kl quote.
  If an X-ray is only requested or not mentioned, kl and xray_finding are null.
- physio_weeks: convert words and shorthand to a number of weeks ("six weeks", "x6/52" = 6). If physiotherapy is
  mentioned without a length ("some physio"), physio_weeks is null. "No physiotherapy yet" is 0.
- lives_alone_or_carer: true if they live alone or care for someone; false if they live with others and no caring
  role is mentioned.
- diabetes: true if diabetes appears anywhere in the letter, otherwise false (quote null).
- weeks_waiting: only when the letter says how long they have been on the orthopaedic waiting list.
- Dates: letter_date is the letter or referral date; give dates as dd/mm/yyyy, quoting the letter."""

PROMPT = "Record the facts from this referral letter.\n\n<letter>\n{text}\n</letter>"


TITLE = re.compile(r"^\s*(?:(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof)\.?\s+)+", re.IGNORECASE)


class DemoCacheMiss(RuntimeError):
    """DEMO_MODE is on and there is no saved result for this letter."""


class Extraction(BaseModel):
    letter_id: str
    model: str
    facts: dict[str, object]           # value per field after the quote check (None = not known)
    quotes: dict[str, str]             # quote per kept fact, for highlighting in the letter
    dropped: list[dict[str, object]]   # facts removed by the quote check, with the reason
    from_cache: bool
    usage: dict | None = None          # tokens and cost of the call that read it (None in older cache files)


# ---------------------------------------------------------------------------- letter files

def read_letter(name: str, data: bytes) -> str:
    """Text of an uploaded letter: PDF, DOCX or TXT."""
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if suffix == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    if suffix == ".txt":
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {suffix or name}")


# ---------------------------------------------------------------------------- cache

def cache_path(letter_id: str, model: str | None = None) -> Path:
    return CACHE_DIR / (model or llm.model_name()) / f"{letter_id}.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _prompt_sha() -> str:
    """Changes when the prompt or schema changes, so old answers aren't reused."""
    return _sha(SYSTEM + PROMPT + json.dumps(LetterFacts.model_json_schema(), sort_keys=True))


def _load_cached(path: Path, text: str) -> dict | None:
    try:
        saved = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    fresh = saved.get("text_sha256") == _sha(text) and saved.get("prompt_sha256") == _prompt_sha()
    return saved if fresh else None


def is_cached(text: str, letter_id: str) -> bool:
    """A saved answer for this exact letter text, prompt and model: reading it costs nothing."""
    load_dotenv()
    return _load_cached(cache_path(letter_id), text) is not None


def read_facts(text: str, letter_id: str, refresh: bool = False) -> tuple[dict, str, bool, dict | None]:
    """Raw LLM answer for a letter: (facts, model, from_cache, usage). Uses the cache unless refresh."""
    load_dotenv()
    model = llm.model_name()
    path = cache_path(letter_id, model)
    saved = None if refresh else _load_cached(path, text)
    if saved:
        return saved["raw"], model, True, saved.get("usage")
    if os.environ.get("DEMO_MODE") == "1":
        raise DemoCacheMiss(f"No saved result for {letter_id} ({model})")

    usage: dict = {}
    raw = llm.complete_json(SYSTEM, PROMPT.format(text=text), LetterFacts.model_json_schema(), usage=usage)
    raw = LetterFacts.model_validate(raw).model_dump()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "letter_id": letter_id,
        "model": model,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "text_sha256": _sha(text),
        "prompt_sha256": _prompt_sha(),
        "usage": usage,
        "raw": raw,
    }, indent=1))
    return raw, model, False, usage


# ---------------------------------------------------------------------------- quote check

def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def quote_in_letter(quote: str | None, text: str) -> bool:
    """True if the quote appears in the letter (ignoring differences in spacing and curly quotes)."""
    return bool(quote and quote.strip()) and _norm(quote) in _norm(text)


def check_quotes(raw: dict, text: str) -> tuple[dict, dict, list]:
    """Keep a fact only if its quote is in the letter and its value is in range."""
    facts, quotes, dropped = {}, {}, []
    for field in FIELDS:
        value, quote = raw[field]["value"], raw[field]["quote"]
        reason = None
        if value is None:
            pass
        elif value is False and field in FALSE_WITHOUT_QUOTE and not quote:
            pass
        elif not quote_in_letter(quote, text):
            reason = "quote not in letter"
        elif field in RANGES and not (RANGES[field][0] <= value <= RANGES[field][1]):
            reason = "out of range"
        if reason:
            dropped.append({"field": field, "value": value, "quote": quote, "reason": reason})
            value = None
        elif value is not None and field in VALUE_IS_QUOTE:
            value = quote
        elif value is not None and field == "name":
            value = TITLE.sub("", value)
        facts[field] = value
        if value is not None and quote:
            quotes[field] = quote
    if facts["age"] is None:
        facts["age"] = age_on(facts["date_of_birth"], facts["letter_date"])
        if facts["age"] is not None:
            quotes["age"] = quotes["date_of_birth"]
    return facts, quotes, dropped


def _parse_date(s: str | None) -> date | None:
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    try:
        return date(int(m[3]), int(m[2]), int(m[1])) if m else None
    except ValueError:
        return None


def age_on(dob: str | None, on: str | None) -> int | None:
    """Age in whole years on a date, both written dd/mm/yyyy."""
    b, d = _parse_date(dob), _parse_date(on)
    if not (b and d) or b > d:
        return None
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def extract(text: str, letter_id: str, refresh: bool = False) -> Extraction:
    raw, model, from_cache, usage = read_facts(text, letter_id, refresh)
    facts, quotes, dropped = check_quotes(raw, text)
    return Extraction(letter_id=letter_id, model=model, facts=facts, quotes=quotes, dropped=dropped,
                      from_cache=from_cache, usage=usage)


# ---------------------------------------------------------------------------- for the app

def text_key(text: str) -> str:
    """Fingerprint used to recognise an uploaded copy of a demo letter (spacing ignored)."""
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


def quote_spans(text: str, quotes: dict[str, str]) -> list[dict]:
    """Where each quote sits in the letter. The quote check ignores spacing, so the search does too."""
    spans = []
    for field, q in quotes.items():
        m = re.search(r"\s+".join(map(re.escape, q.split())), text)
        if m:
            spans.append({"field": field, "start": m.start(), "end": m.end()})
    return sorted(spans, key=lambda s: (s["start"], -s["end"]))


# ---------------------------------------------------------------------------- rules

def decide_letter(facts: dict, weeks_waiting: int | None = None) -> dict:
    """Pathway and priority from the checked facts. Weeks waiting comes from the waiting list (the RTT clock)
    when the patient is already on it, otherwise from the letter."""
    f = {k: facts.get(k) for k in ("oks", "oks_before", "kl", "physio_weeks", "bmi", "night_pain",
                                    "lives_alone_or_carer")}
    f["weeks_waiting"] = weeks_waiting if weeks_waiting is not None else facts.get("weeks_waiting")
    d = decide(f)
    return {**d, "label": PATHWAYS[d["pathway"]], "priority": priority_score(f),
            "priority_parts": priority_breakdown(f), "facts_used": f}
