"""NHS standards used across the project.

Everything here is either an NHS / clinical coding standard or a clearly marked project convention.
All identifiers produced are SYNTHETIC: NHS numbers come from the 999 test range, practices are
fictional, and postcodes are outward codes only (no full address can be reconstructed).
"""
from __future__ import annotations
import random

# ---------------------------------------------------------------------------
# NHS number: 10 digits, modulus 11 check digit. Test numbers start with 999.
# Weights 10..2 on the first nine digits; check = 11 - (sum mod 11); 11 -> 0; 10 -> invalid.
# ---------------------------------------------------------------------------
def nhs_check_digit(first9: str) -> int | None:
    total = sum(int(d) * w for d, w in zip(first9, range(10, 1, -1)))
    check = 11 - (total % 11)
    if check == 11:
        return 0
    if check == 10:
        return None
    return check


def is_valid_nhs_number(n: str) -> bool:
    n = n.replace(" ", "")
    if len(n) != 10 or not n.isdigit():
        return False
    c = nhs_check_digit(n[:9])
    return c is not None and c == int(n[9])


def synthetic_nhs_number(rng: random.Random, used: set) -> str:
    """A valid NHS number in the 999 test range, formatted 3-3-4 as on NHS letters."""
    while True:
        first9 = "999" + "".join(str(rng.randint(0, 9)) for _ in range(6))
        c = nhs_check_digit(first9)
        if c is None:
            continue
        n = first9 + str(c)
        if n not in used:
            used.add(n)
            return f"{n[:3]} {n[3:6]} {n[6:]}"


# ---------------------------------------------------------------------------
# NHS Data Dictionary codes
# ---------------------------------------------------------------------------
PERSON_STATED_GENDER = {"1": "Male", "2": "Female", "9": "Indeterminate", "X": "Not known"}
PRIORITY_TYPE = {"1": "Routine", "2": "Urgent", "3": "Two week wait"}
SOURCE_OF_REFERRAL_OP = {"03": "Referral from a General Medical Practitioner"}
TREATMENT_FUNCTION = {"110": "Trauma and Orthopaedics"}
RTT_PERIOD_STATUS = {"10": "First activity", "20": "Subsequent activity", "30": "Start of first definitive treatment"}

# ---------------------------------------------------------------------------
# Clinical terminologies
# ---------------------------------------------------------------------------
ICD10 = {
    "M17.0": "Primary gonarthrosis, bilateral",
    "M17.1": "Other primary gonarthrosis",          # used for unilateral primary knee OA
    "M17.9": "Gonarthrosis, unspecified",
}
SNOMED_KNEE_OA = ("239873007", "Osteoarthritis of knee")
OPCS4_TKR = ("W40.1", "Primary total prosthetic replacement of knee joint using cement")

COMORBIDITY_SNOMED = {
    "Type 2 diabetes mellitus": "44054006",
    "Essential hypertension": "59621000",
    "Chronic kidney disease": "709044004",
    "Asthma": "195967001",
    "Depressive disorder": "35489007",
}

# ---------------------------------------------------------------------------
# Scores and gradings
# ---------------------------------------------------------------------------
# Oxford Knee Score: 12 items, total 0 (worst) to 48 (best).
OKS_BANDS = [(0, 19, "severe"), (20, 29, "moderate to severe"), (30, 39, "mild to moderate"), (40, 48, "satisfactory")]

def oks_band(score: int | None) -> str | None:
    if score is None:
        return None
    for lo, hi, name in OKS_BANDS:
        if lo <= score <= hi:
            return name
    return None

# Kellgren-Lawrence grade (0-4) with radiology report wording, several ways each is written.
KL_REPORT_WORDING = {
    0: ["No radiographic evidence of osteoarthritis.",
        "Joint spaces preserved. No osteophytes."],
    1: ["Doubtful joint space narrowing with possible early osteophytic lipping.",
        "Minimal changes only, of doubtful significance."],
    # KL 2 avoids "early", which also fits KL 1. Replaced in place (same count) so the random draws don't shift.
    2: ["Definite small osteophytes with possible joint space narrowing, in keeping with mild osteoarthritis.",
        "Mild degenerative change with definite small osteophytes and possible medial joint space narrowing.",
        "Mild osteoarthritis with definite osteophytes, predominantly medial compartment."],
    3: ["Moderate osteophytes with definite joint space narrowing and some subchondral sclerosis, in keeping with moderate osteoarthritis.",
        "Moderate tricompartmental degenerative change with definite medial joint space loss.",
        "Established osteoarthritis with joint space narrowing, osteophytes and sclerosis."],
    4: ["Large osteophytes, marked joint space narrowing with bone-on-bone contact, severe sclerosis and varus deformity.",
        "Advanced osteoarthritis with complete loss of the medial joint space and bone-on-bone appearance.",
        "Severe end-stage degenerative change with marked joint space loss and subchondral cysts."],
}

# ---------------------------------------------------------------------------
# Project conventions (synthetic, not real organisations)
# ---------------------------------------------------------------------------
# Fictional GP practices. Codes use a 'Y99' prefix so they cannot be mistaken for real ODS codes.
PRACTICES = [
    ("Y99001", "Riverside Medical Centre"), ("Y99002", "Linthorpe Lane Surgery"),
    ("Y99003", "Acklam Green Practice"), ("Y99004", "Marton Park Health Centre"),
    ("Y99005", "Coulby Fields Surgery"), ("Y99006", "North Ormesby Family Practice"),
    ("Y99007", "Teesway Medical Group"), ("Y99008", "Eston Hills Surgery"),
    ("Y99009", "Thornaby Bridge Practice"), ("Y99010", "Stockton Quay Health Centre"),
]
GP_NAMES = ["Dr A. Patel", "Dr S. Byrne", "Dr R. Hughes", "Dr L. Okonkwo", "Dr M. Clarke", "Dr K. Ahmed",
            "Dr J. Fenwick", "Dr P. Sharma", "Dr E. Lowther", "Dr T. Adeyemi", "Dr H. Robson", "Dr N. Iqbal"]

# Outward codes only, Middlesbrough / Stockton / Redcar, with a rough deprivation tilt (IMD decile range).
# IMD 1 = most deprived 10% of areas in England. Middlesbrough has a high share of decile 1 areas.
POSTCODE_OUTWARD = [
    ("TS1", (1, 2)), ("TS3", (1, 3)), ("TS4", (2, 5)), ("TS5", (3, 8)), ("TS6", (1, 4)),
    ("TS7", (6, 10)), ("TS8", (5, 10)), ("TS10", (1, 6)), ("TS17", (4, 9)), ("TS18", (1, 6)),
]

FIRST_NAMES_F = ["Margaret", "Susan", "Linda", "Patricia", "Christine", "Jean", "Elizabeth", "Janet", "Ann", "Carol",
                 "Barbara", "Pauline", "Sandra", "Julie", "Karen", "Gillian", "Maureen", "Lesley", "Aisha", "Fatima",
                 "Joan", "Valerie", "Dorothy", "Shirley", "Brenda", "Irene", "Sheila", "Hazel", "Priya", "Grace"]
FIRST_NAMES_M = ["David", "John", "Robert", "Peter", "Michael", "Alan", "Brian", "Keith", "Stephen", "Ian",
                 "Paul", "Kevin", "Gary", "Colin", "Graham", "Trevor", "Raymond", "Derek", "Imran", "Tariq",
                 "James", "William", "George", "Kenneth", "Barry", "Malcolm", "Neil", "Tony", "Samuel", "Chidi"]
SURNAMES = ["Smith", "Robson", "Wilson", "Taylor", "Brown", "Walker", "Thompson", "Hall", "Wood", "Jackson",
            "Harrison", "Bell", "Dixon", "Graham", "Watson", "Moore", "Atkinson", "Hutchinson", "Pearson", "Lister",
            "Hussain", "Khan", "Ali", "Okafor", "Mensah", "Kowalski", "Nowak", "Shaw", "Carr", "Fletcher",
            "Ellison", "Hart", "Pike", "Walsh", "Carter", "Rahman", "Ellis", "Brennan", "Lowe", "Dawson"]
