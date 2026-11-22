#!/usr/bin/env python3
"""Build the interactive course page from course.template.html.

    python3 docs/course/build.py            # writes docs/course/index.html

The template holds the lessons and the interactive widgets. This script fills in
the real code and real captured output, so nothing in the course is retyped:

  @@CODE:path:first:last@@            numbered, highlighted lines of a source file
  @@CODE:path:first:last:HL=3-4,9@@   the same, with some lines marked
  @@RAW:path@@                        a text file, escaped, for a terminal block
  @@JSON:path@@                       a text file as a JSON array of lines

Every range is checked against the file, so a stale line number stops the build.
Needs: pygments (pip install pygments). Open index.html in any browser, no server.
"""
import html
import json
import re
import sys
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FMT = HtmlFormatter(nowrap=True)


def lexer(path):
    try:
        return get_lexer_for_filename(path)
    except Exception:
        return TextLexer()


def code_block(path, a, b, hl):
    lines = (ROOT / path).read_text().split("\n")
    if not (1 <= a <= b <= len(lines)):
        sys.exit(f"bad range {path}:{a}-{b} (file has {len(lines)} lines)")
    lx = lexer(path)
    rows = []
    for n in range(a, b + 1):
        src = lines[n - 1].expandtabs(2)
        body = highlight(src, lx, FMT).rstrip("\n") or "&nbsp;"
        mark = " hl" if n in hl else ""
        rows.append(f'<span class="l{mark}"><i>{n}</i><b>{body}</b></span>')
    cap = f'{html.escape(path)} · lines {a}–{b}'
    return (f'<figure class="code"><figcaption>{cap}</figcaption>'
            f'<pre tabindex="0"><code>{"".join(rows)}</code></pre></figure>')


def parse_hl(spec):
    out = set()
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            x, y = part.split("-")
            out.update(range(int(x), int(y) + 1))
        else:
            out.add(int(part))
    return out


def expand(text):
    def code(m):
        parts = m.group(1).split(":")
        path, a, b = parts[0], int(parts[1]), int(parts[2])
        hl = set()
        for extra in parts[3:]:
            if extra.startswith("HL="):
                hl = parse_hl(extra[3:])
        return code_block(path, a, b, hl)

    def raw(m):
        return html.escape((ROOT / m.group(1)).read_text().replace("\r", "").rstrip("\n"))

    def js(m):
        lines = (ROOT / m.group(1)).read_text().replace("\r", "").rstrip("\n").split("\n")
        return json.dumps(lines)

    text = re.sub(r"@@CODE:([^@]+)@@", code, text)
    text = re.sub(r"@@RAW:([^@]+)@@", raw, text)
    text = re.sub(r"@@JSON:([^@]+)@@", js, text)
    return text


def main():
    tpl = (HERE / "course.template.html").read_text()
    page = expand(tpl)
    head, body = page.split("<!--BODY-->", 1)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            f'{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    (HERE / "index.html").write_text(full)
    fragment = head + body       # for the artifact: it adds its own document skeleton
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out:
        out.write_text(fragment)
    print(f"wrote {HERE / 'index.html'} ({len(full) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
