#!/usr/bin/env python3
"""
check_es3.py - Catch modern JavaScript in InDesign ExtendScript (.jsx) files.

InDesign runs ExtendScript, which is ECMAScript 3 (1999). Code written as
modern JavaScript fails, often with an unhelpful error. Run this on every
script before giving it to the user:

    python3 check_es3.py my_script.jsx [more.jsx ...]

Exit code 0 = no errors (warnings may still be printed), 1 = errors found.
Strings, regex literals and comments are blanked before checking, so text
inside them does not trigger false alarms.
"""

import re
import sys

ERRORS = [
    (r"\blet\s+[A-Za-z_$\[{]", "'let' is not ES3: use 'var'"),
    (r"\bconst\s+[A-Za-z_$\[{]", "'const' is not ES3: use 'var'"),
    (r"=>", "arrow functions are not ES3: use 'function () { ... }'"),
    (r"`", "template literals are not ES3: concatenate strings with +"),
    (r"\bclass\s+[A-Za-z_$]", "'class' is not ES3: use constructor functions"),
    (r"\b(async|await)\b", "async/await is not available in ExtendScript"),
    (r"\.\.\.[A-Za-z_$\[]", "spread/rest syntax is not ES3"),
    (r"\b(var|let|const)\s*[\[{]", "destructuring is not ES3"),
    (r"function\s*[A-Za-z_$]*\s*\([^)]*=", "default parameters are not ES3"),
    (r"\.(forEach|map|filter|reduce|some|every|find|findIndex|includes)\s*\(",
     "Array/String method not in ES3: use a for loop"),
    (r"\bJSON\s*\.", "JSON is not built into ExtendScript: avoid it or include json2.js"),
    (r"\bObject\s*\.\s*(keys|values|entries|assign|create|freeze)\b",
     "Object.* helper not in ES3: use for...in with hasOwnProperty"),
    (r"\.(trim|startsWith|endsWith|padStart|padEnd|repeat)\s*\(",
     "String method not in ES3: use a regex instead"),
    (r"\b(Map|Set|WeakMap|Symbol|Promise)\s*[\.(]", "ES6 built-in not available"),
    (r"\bfor\s*\(\s*(var\s+)?[A-Za-z_$]+\s+of\b", "for...of is not ES3: use a for loop"),
]

WARNINGS = [
    (r"\.indexOf\s*\(", "Array.indexOf is not ES3 (String.indexOf is fine): check the receiver"),
    (r",\s*[\]}]", "trailing comma in array/object literal: breaks older ExtendScript"),
    (r"\bArray\.isArray\b", "Array.isArray is not ES3: use 'instanceof Array'"),
]


def blank_literals(source):
    """Replace comments, strings and regex literals with spaces (keep newlines)."""
    out = []
    i, n = 0, len(source)
    prev_significant = ""
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = source.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue
        if ch == "/" and nxt == "*":
            j = source.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(re.sub(r"[^\n]", " ", source[i:j]))
            i = j
            continue
        if ch in "'\"":
            j = i + 1
            while j < n and source[j] != ch and source[j] != "\n":
                j += 2 if source[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(ch + " " * (j - i - 2) + ch if j - i >= 2 else ch)
            i = j
            prev_significant = "x"
            continue
        if ch == "/" and (prev_significant == "" or prev_significant in "(,=:[!&|?{};+-*%<>~^"):
            # Regex literal.
            j = i + 1
            in_class = False
            while j < n and source[j] != "\n":
                c = source[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and source[j].isalpha():
                j += 1
            out.append("/" + " " * max(j - i - 2, 0) + "/")
            i = j
            prev_significant = "x"
            continue
        out.append(ch)
        if not ch.isspace():
            prev_significant = ch
        i += 1
    return "".join(out)


def check_file(path):
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    code = blank_literals(source)
    lines = code.split("\n")
    errors, warnings = [], []
    for number, text in enumerate(lines, start=1):
        if text.lstrip().startswith("#"):  # #target, #include preprocessor lines
            continue
        for pattern, message in ERRORS:
            if re.search(pattern, text):
                errors.append((number, message))
        for pattern, message in WARNINGS:
            if re.search(pattern, text):
                warnings.append((number, message))
    # ExtendScript may read files without a BOM in the system encoding, so
    # accented letters and symbols in code break. Use \uXXXX escapes.
    for number, text in enumerate(source.split("\n"), start=1):
        stripped = text.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if re.search(r"[^\x00-\x7F]", text):
            warnings.append((number, "non-ASCII character in code or string: "
                                     "use a \\uXXXX escape (e.g. \\u00ED for i-acute)"))
    # Trailing commas can span lines.
    for match in re.finditer(r",\s*\n\s*[\]}]", code):
        number = code.count("\n", 0, match.start()) + 1
        warnings.append((number, "trailing comma in array/object literal"))
    return errors, warnings


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    failed = False
    for path in argv:
        errors, warnings = check_file(path)
        for number, message in errors:
            print("%s:%d: error: %s" % (path, number, message))
        for number, message in warnings:
            print("%s:%d: warning: %s" % (path, number, message))
        if errors:
            failed = True
        else:
            print("%s: OK (ES3)%s" % (path, " with %d warning(s)" % len(warnings)
                                      if warnings else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
