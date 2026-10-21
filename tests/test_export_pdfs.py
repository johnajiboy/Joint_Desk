import importlib.util
import io
import json
from pathlib import Path

from pypdf import PdfReader

from kneedss.extract import quote_in_letter, read_letter

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("export_pdfs", ROOT / "scripts" / "export_pdfs.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def key_and_text(base: Path, lid: str):
    key = next(k for k in map(json.loads, open(base / "answer_key.jsonl")) if k["letter_id"] == lid)
    return key, (base / "letters" / f"{lid}.txt").read_text()


def test_letter_meta_reads_practice_date_and_ubrn():
    _, text = key_and_text(P.OUT, "L0001")
    m = P.letter_meta(text)
    assert m == {"code": "Y99006", "practice": "North Ormesby Family Practice",
                 "address": "17 North Ormesby Square, Middlesbrough TS3", "date": "25/04/2026", "ubrn": "0000 4111 4025"}


def test_pdf_text_is_selectable_with_letterhead_and_footer_on_every_page():
    _, text = key_and_text(P.OUT / "test", "T0002")              # scanned-style: two pages
    pdf = P.letter_pdf(text, P.letter_meta(text))
    pages = PdfReader(io.BytesIO(pdf)).pages
    assert len(pages) == 2
    assert all(P.FOOTER in page.extract_text() for page in pages)
    first = pages[0].extract_text()
    assert "Marton Park Health Centre" in first and "Practice code Y99004" in first and "e-RS UBRN: 0000 2013 6328" in first
    assert "NHS logo" not in first


def test_every_quote_survives_pdf_and_docx(tmp_path):
    for base, lid in [(P.OUT, "L0001"), (P.OUT, "L0011"), (P.OUT / "test", "T0002"), (P.OUT / "test", "T0050")]:
        key, text = key_and_text(base, lid)
        meta = P.letter_meta(text)
        for name, data in [(f"{lid}.pdf", P.letter_pdf(text, meta)), (f"{lid}.docx", P.letter_docx(text, meta))]:
            r = P.check(name, data, key)
            assert r["missing"] == [] and r["found"] == r["quotes"] > 0, (name, r["missing"])
            assert all(quote_in_letter(q, read_letter(name, data)) for q in key["evidence"].values())
