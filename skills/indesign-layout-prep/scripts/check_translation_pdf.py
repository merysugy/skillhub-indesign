#!/usr/bin/env python3
"""
check_translation_pdf.py - Check a translations JSON against the PDFs of an
InDesign document. Needs pdfplumber.

Before building the script, against the SOURCE PDF:

    python3 check_translation_pdf.py source translations.json original.pdf

  - every source text ("es") exists in the PDF (spacing and case ignored);
  - every **marked** run really has a different font or colour from the rest
    of its paragraph, and is uniform (catches bold boundaries read wrong);
  - prints, per page, the PDF text that no entry covers, so nothing is left
    out (page numbers, e-mails and names usually remain: that is fine).

After the designer runs the script, against the TRANSLATED PDF:

    python3 check_translation_pdf.py result translations.json translated.pdf

  - source texts still present (not translated);
  - target texts ("en") not found. Paragraphs split across columns or pages
    can show up here as "not found in one piece": check them by eye.

Exit code 1 when a check fails.
"""
import json, re, sys
import pdfplumber


def key(s):
    s = s.replace("**", "").replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", "", s).lower()


def chars_of(pdf):
    out = []
    for pno, page in enumerate(pdf.pages, 1):
        for c in page.chars:
            if not c["text"].strip():
                continue
            for ch in c["text"]:
                out.append((ch.replace("\u2019", "'").replace("\u2018", "'"),
                            c["fontname"].split("+")[-1], str(c.get("non_stroking_color")), pno))
    return out


def source(entries, pdf):
    chars = chars_of(pdf)
    low = "".join(c[0] for c in chars).lower()
    bad = 0
    for e in entries:
        es = e["es"]
        k = key(es)
        idx = low.find(k)
        if idx < 0:
            bad += 1
            print("NOT IN PDF:", es.replace("**", "")[:90])
            continue
        mask, marked, i = [], False, 0
        while i < len(es):
            if es.startswith("**", i):
                marked = not marked; i += 2; continue
            if not es[i].isspace():
                mask.append(marked)
            i += 1
        if any(mask):
            seg = chars[idx: idx + len(k)]
            m = {(c[1], c[2]) for c, x in zip(seg, mask) if x}
            u = {(c[1], c[2]) for c, x in zip(seg, mask) if not x}
            if len(m) != 1 or (m & u):
                bad += 1
                print("MARKED RUN DOES NOT MATCH THE FORMATTING:", es[:70])
                print("   marked:", sorted(m), "\n   rest:  ", sorted(u))
    keys = sorted({key(e["es"]) for e in entries}, key=len, reverse=True)
    print("\nPDF text not covered by any entry, per page:")
    for pno, page in enumerate(pdf.pages, 1):
        s = re.sub(r"\s+", "", "".join(c["text"] for c in page.chars)).lower()
        for k in keys:
            s = s.replace(k, "|")
        s = re.sub(r"\|+", "|", s).strip("|")
        if s:
            print("  p%d: %s" % (pno, s[:300]))
    print("\n%d entries, %d problems" % (len(entries), bad))
    return bad


def result(entries, pdf):
    pages = [key("".join(c["text"] for c in p.chars)) for p in pdf.pages]
    alltext = "".join(pages)
    bad = 0
    for e in entries:
        k = key(e["es"])
        hits = [i + 1 for i, s in enumerate(pages) if k in s]
        if hits and len(k) >= 8:
            bad += 1
            print("STILL IN SOURCE LANGUAGE (p. %s): %s" % (",".join(map(str, hits)), e["es"].replace("**", "")[:80]))
    for e in entries:
        for en in (e["en"] if isinstance(e["en"], list) else [e["en"]]):
            k = key(en)
            if k not in alltext and k.replace("-", "") not in alltext.replace("-", ""):
                print("TARGET NOT FOUND IN ONE PIECE (check by eye):", en.replace("**", "")[:80])
    print("\n%d source texts still present" % bad)
    return bad


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("source", "result"):
        print(__doc__); sys.exit(2)
    entries = json.load(open(sys.argv[2], encoding="utf-8"))
    with pdfplumber.open(sys.argv[3]) as pdf:
        bad = (source if sys.argv[1] == "source" else result)(entries, pdf)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
