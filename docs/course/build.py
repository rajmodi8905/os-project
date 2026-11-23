#!/usr/bin/env python3
"""Build the course with the codebase-to-course framework.

    python3 docs/course/build.py                  # writes modules/*.html and index.html
    python3 docs/course/build.py --inline OUT     # also writes one self-contained fragment (for an artifact)

Layout (same as the framework): styles.css and main.js are copied verbatim from the
skill and never edited; _base.html is the page shell; modules/NN-*.html hold the
lessons; build.sh-style concatenation produces index.html.

The lessons are written in src/NN-*.html. This script expands three things:

  {{term}} or {{term|shown text}}   glossary tooltip (first use in each module only)
  @@TB:path:first:last@@ ... @@/TB@@   a code/English translation block. The code is read
                                    from the real file, unchanged; the lines between the
                                    markers are the English lines (<p class="tl">...</p>)
  @@TB:path:first:last:plain@@        the same for captured output (no colouring)
  @@JSON:path@@ / @@RAW:path@@        a data file as a JSON array / escaped text

Every line range is checked, so a stale number stops the build. Needs: pip install pygments
"""
import html
import json
import re
import sys
from pathlib import Path

from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, Operator, String

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
GLOSS = json.loads((HERE / "glossary.json").read_text())
used_terms = set()


def code_class(tok):
    if tok in Comment.Preproc or tok in Comment.PreprocFile:
        return "code-keyword"
    if tok in Comment:
        return "code-comment"
    if tok in Keyword:
        return "code-keyword"
    if tok in Name.Function or tok in Name.Builtin:
        return "code-function"
    if tok in String:
        return "code-string"
    if tok in Number:
        return "code-number"
    if tok in Operator:
        return "code-operator"
    return ""


def highlight_line(lexer, text):
    out = []
    for tok, val in lexer.get_tokens(text):
        val = val.rstrip("\n")
        if not val:
            continue
        cls = code_class(tok)
        esc = html.escape(val)
        out.append(f'<span class="{cls}">{esc}</span>' if cls else esc)
    return "".join(out)


def translation_block(path, a, b, plain, english):
    lines = (ROOT / path).read_text().replace("\r", "").split("\n")
    if not (1 <= a <= b <= len(lines)):
        sys.exit(f"bad range {path}:{a}-{b} (file has {len(lines)} lines)")
    try:
        lexer = get_lexer_for_filename(path)
    except Exception:
        lexer = TextLexer()
    rows = []
    for n in range(a, b + 1):
        src = lines[n - 1].expandtabs(2)
        body = html.escape(src) if plain else highlight_line(lexer, src)
        rows.append(f'<span class="code-line">{body or " "}</span>')
    label = f"CODE · {path}" if not plain else f"REAL OUTPUT · {Path(path).name}"
    shown = f"{label} · lines {a}-{b}"
    # drop filler lines such as "(empty line)" or "(the refusal)": they add nothing for the learner
    english = re.sub(r'[ \t]*<p class="tl">\([^<>()]*\)</p>[ \t]*\n?', '', english)
    return ('<div class="translation-block animate-in">\n  <div class="translation-code">\n'
            f'    <span class="translation-label">{html.escape(shown)}</span>\n'
            f'    <pre><code>{chr(10).join(rows)}</code></pre>\n  </div>\n'
            '  <div class="translation-english">\n    <span class="translation-label">PLAIN ENGLISH</span>\n'
            f'    <div class="translation-lines">\n{english.strip()}\n    </div>\n  </div>\n</div>')


def expand_module(text, name):
    seen = set()

    def tb(m):
        path, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        plain = m.group(4) == "plain"
        return translation_block(path, a, b, plain, m.group(5))

    text = re.sub(r"@@TB:([^:@]+):(\d+):(\d+)(?::(plain))?@@(.*?)@@/TB@@", tb, text, flags=re.S)

    def term(m):
        key = m.group(1)
        shown = m.group(2) or key
        if key not in GLOSS:
            sys.exit(f"{name}: unknown glossary term {{{{{key}}}}}")
        used_terms.add(key)
        if key in seen:
            return shown
        seen.add(key)
        return f'<span class="term" data-definition="{html.escape(GLOSS[key], quote=True)}">{shown}</span>'

    text = re.sub(r"\{\{([^}|]+)(?:\|([^}]+))?\}\}", term, text)
    text = re.sub(r"@@JSON:([^@]+)@@",
                  lambda m: json.dumps((ROOT / m.group(1)).read_text().replace("\r", "").rstrip("\n").split("\n")), text)
    text = re.sub(r"@@RAW:([^@]+)@@",
                  lambda m: html.escape((ROOT / m.group(1)).read_text().replace("\r", "").rstrip("\n")), text)
    if "@@" in text:
        sys.exit(f"{name}: unresolved @@ marker left in the module")
    return text


def main():
    (HERE / "modules").mkdir(exist_ok=True)
    for old in (HERE / "modules").glob("*.html"):
        old.unlink()
    names = sorted(p.name for p in (HERE / "src").glob("*.html"))
    for n in names:
        (HERE / "modules" / n).write_text(expand_module((HERE / "src" / n).read_text(), n))
    base = (HERE / "_base.html").read_text()
    footer = (HERE / "_footer.html").read_text()
    mods = "".join((HERE / "modules" / n).read_text() + "\n" for n in names)
    (HERE / "index.html").write_text(base + mods + footer)   # same as: cat _base.html modules/*.html _footer.html
    unused = sorted(set(GLOSS) - used_terms)
    print(f"built {len(names)} modules, {len(used_terms)} glossary terms used"
          + (f" (unused: {', '.join(unused)})" if unused else ""))
    if "--inline" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--inline") + 1])
        css = (HERE / "styles.css").read_text() + "\n" + (HERE / "extras.css").read_text()
        js = (HERE / "main.js").read_text() + "\n" + (HERE / "extras.js").read_text()
        title = re.search(r"<title>(.*?)</title>", base).group(1)
        head_links = "\n".join(re.findall(r"<link[^>]+fonts[^>]+>", base))
        body = re.search(r"<body>(.*)", base + mods + footer, re.S).group(1)
        body = body.replace("</body>", "").replace("</html>", "")
        out.write_text(f"<title>{title}</title>\n{head_links}\n<style>\n{css}\n</style>\n{body}\n<script>\n{js}\n</script>\n")
        print("wrote", out)


if __name__ == "__main__":
    main()
