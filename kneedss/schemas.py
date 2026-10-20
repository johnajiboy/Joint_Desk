"""Pydantic models for what the LLM reads from a referral letter.

Every fact is {value, quote}: value is null when the letter doesn't state it, and quote is the exact
words copied from the letter. The JSON schema of LetterFacts becomes the strict tool in llm.py.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str | None = Field(description="Exact words copied from the letter that state the value; null if value is null.")


class TextFact(_Fact):
    value: str | None


class IntFact(_Fact):
    value: int | None


class NumberFact(_Fact):
    value: float | None


class BoolFact(_Fact):
    value: bool | None


class SexFact(_Fact):
    value: Literal["Male", "Female"] | None


class SideFact(_Fact):
    value: Literal["Right", "Left", "Bilateral"] | None


class SmokingFact(_Fact):
    value: Literal["Never smoked", "Ex-smoker", "Current smoker"] | None


class LetterFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nhs_number: TextFact = Field(description="NHS number, 10 digits, as written (e.g. '999 123 4567').")
    name: TextFact = Field(description="Patient's first name and surname, without a title (no Mr, Mrs, Ms, Dr).")
    letter_date: TextFact = Field(description="Date of the letter or referral, dd/mm/yyyy as written.")
    date_of_birth: TextFact = Field(description="Date of birth, dd/mm/yyyy as written.")
    age: IntFact = Field(description="Age in years, only if the letter states it (code works it out from the dates).")
    sex: SexFact
    side: SideFact = Field(description="Which knee is referred.")
    oks: IntFact = Field(description="Current Oxford Knee Score, 0 (worst) to 48 (best).")
    oks_before: IntFact = Field(description="An earlier Oxford Knee Score, if one is given for comparison.")
    kl: IntFact = Field(
        description="Kellgren-Lawrence grade 0-4: the stated grade, or graded from the X-ray report wording."
    )
    xray_finding: TextFact = Field(description="The X-ray report's finding, word for word.")
    physio_weeks: IntFact = Field(description="Weeks of physiotherapy completed (0 if none). Null if vague or not stated.")
    injections: IntFact = Field(description="Number of steroid injections into the knee.")
    bmi: NumberFact = Field(description="Body mass index in kg/m2; the most recent dated value if there are several.")
    night_pain: BoolFact
    lives_alone_or_carer: BoolFact = Field(description="True if the patient lives alone or is a carer for someone.")
    walking_aid: BoolFact = Field(description="True if the patient uses a stick, crutch, frame or other walking aid.")
    diabetes: BoolFact = Field(description="True if diabetes is listed or mentioned; false if it is not.")
    smoking: SmokingFact
    weeks_waiting: IntFact = Field(description="Weeks already on the orthopaedic waiting list, only if the letter states it.")


FIELDS = list(LetterFacts.model_fields)

# Fields the answer key scores (the rest are used for matching and working out age).
SCORED_FIELDS = [f for f in FIELDS if f not in ("nhs_number", "letter_date", "date_of_birth")]

# Plausible ranges; a value outside its range is dropped like a fact with a bad quote.
RANGES: dict[str, tuple[float, float]] = {
    "age": (16, 110), "oks": (0, 48), "oks_before": (0, 48), "kl": (0, 4), "physio_weeks": (0, 104),
    "injections": (0, 20), "bmi": (12, 80), "weeks_waiting": (0, 260),
}

# Text facts whose value is the letter's own words: the checked quote becomes the value.
VALUE_IS_QUOTE = {"xray_finding"}

# Facts that may be false without a quote: diabetes not on the problem list means no diabetes.
FALSE_WITHOUT_QUOTE = {"diabetes"}
