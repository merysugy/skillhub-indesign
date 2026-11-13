#!/usr/bin/env python3
"""
build_translation_jsx.py - Build the InDesign translation script from a JSON file.

    python3 build_translation_jsx.py translations.json -o Translate-EN.jsx

translations.json is a list of paragraphs, in document order:

    [
      {"es": "Texto **en negrita** del original", "en": "Text **in bold** from the original"},
      {"es": "Subtitulo repetido", "en": ["First occurrence", "Second occurrence"]}
    ]

- "es": source text exactly as in the layout (case, line breaks and special
  spaces do not matter). "en": target text. Any language pair works.
- **...** marks the run with different formatting (bold, colour) inside the
  paragraph. The script copies that run's formatting from the source.
- A list in "en" assigns translations by page order to a source text that
  appears several times.
- Write intentional multiple spaces in "en" as they must appear (they are
  kept); in "es" spacing does not matter.

Checks: balanced ** marks, no duplicate source texts, no empty texts. Every
non-ASCII character is written as a \\uXXXX escape (ExtendScript may read the
file in the system encoding). Exit code 1 on error.
"""
import argparse, json, os, re, sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "translate_document.jsx")
MARKER = "// @@TRANSLATIONS@@"


def escape_non_ascii(text):
    out = []
    for ch in text:
        cp = ord(ch)
        if cp < 128:
            out.append(ch)
        elif cp <= 0xFFFF:
            out.append("\\u%04X" % cp)
        else:  # surrogate pair
            cp -= 0x10000
            out.append("\\u%04X\\u%04X" % (0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)))
    return "".join(out)


def js_string(s):
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return '"' + escape_non_ascii(s) + '"'


def norm(s):
    s = s.replace("**", "").lower()
    s = re.sub(r"[\u00AD\uFEFF\u200B-\u200D]", "", s)
    s = re.sub(r"[\s\u00A0\u2000-\u200A\u202F]+", " ", s).strip()
    return s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--template", default=TEMPLATE)
    a = ap.parse_args()

    data = json.load(open(a.json, encoding="utf-8"))
    errors, seen, lines = [], {}, []
    for n, e in enumerate(data, 1):
        es, en = e.get("es"), e.get("en")
        ens = en if isinstance(en, list) else [en]
        if not es or not all(ens):
            errors.append("entry %d: empty 'es' or 'en'" % n)
            continue
        for label, s in [("es", es)] + [("en", x) for x in ens]:
            if s.count("**") % 2:
                errors.append("entry %d: unbalanced ** in %s: %s" % (n, label, s[:60]))
        k = norm(es)
        if k in seen:
            errors.append("entry %d: same source text as entry %d: %s" % (n, seen[k], es[:60]))
        seen[k] = n
        en_js = "[" + ", ".join(js_string(x) for x in ens) + "]" if isinstance(en, list) else js_string(en)
        lines.append("  { es: %s,\n    en: %s }" % (js_string(es), en_js))
    if errors:
        print("\n".join("ERROR " + x for x in errors))
        sys.exit(1)

    tpl = open(a.template, encoding="utf-8").read()
    if MARKER not in tpl:
        sys.exit("ERROR template has no %s marker" % MARKER)
    block = "var TRANSLATIONS = [\n" + ",\n".join(lines) + "\n];"
    out = escape_non_ascii(tpl.replace(MARKER, block))
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(out)
    print("%s: %d paragraphs, %d with variants by page" %
          (a.output, len(data), sum(isinstance(e["en"], list) for e in data)))


if __name__ == "__main__":
    main()
