#!/usr/bin/env python3
"""Build the viva video: styled slides + real code + offline narration + captions.

    python3 video/make_video.py            # full build -> video/out/viva.mp4
    python3 video/make_video.py --frames   # only render frames (no audio), quick check

Needs: python3, pygments, ffmpeg, espeak-ng (+ mbrola voices for a smoother
voice), Node with Playwright (or any Chromium-based screenshot via Playwright).
No internet is needed: the voice is local and slides are drawn from HTML.

Everything shown comes from the committed files: code is read from the real
source files, and the terminal scenes use real output captured from the guest
(video/assets). Line ranges are validated; a wrong range stops the build.
"""
import concurrent.futures as cf
import html
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "video" / "out"
BUILD = Path(os.environ.get("VIDEO_BUILD", "/tmp/viva_build"))
VOICE = os.environ.get("VOICE", "mb-us2")          # falls back to en-us if mbrola is missing
SPEED = os.environ.get("SPEED", "150")
GAP = 0.35                                          # seconds of silence after each sentence

CHAPTERS = ["Problem", "Background", "Solution", "Tests & demo", "Modify it", "Viva Q&A"]
steps = []

# --------------------------------------------------------------------------- text to speech
SAY = [
    ("changeprotection", "change protection"), ("checkuvmwrite", "check u v m write"),
    ("setuvmwrite", "set u v m write"), ("getuvmprot", "get u v m prot"),
    ("copyuvm", "copy u v m"), ("copyout", "copy out"), ("argptrw", "arg ptr w"),
    ("argptr", "arg ptr"), ("argint", "arg int"), ("walkpgdir", "walk page dir"),
    ("PGROUNDDOWN", "page round down"), ("PGSIZE", "page size"), ("PTE_W", "P T E W"),
    ("PTE_U", "P T E U"), ("PTE_P", "P T E P"), ("munprotect", "m unprotect"),
    ("mprotect", "m protect"), ("getprot", "get prot"), ("vmtest", "v m test"),
    ("vmdemo", "v m demo"), ("lcr3", "l c r 3"), ("rcr2", "r c r 2"), ("fstat", "f stat"),
    ("sbrk", "s break"), ("xv6", "x v 6"), ("PTEs", "P T Es"), ("PTE", "P T E"),
    ("TLB", "T L B"), ("CR3", "C R 3"), ("CR0", "C R 0"), ("EAX", "E A X"),
    ("OSTEP", "O S T E P"), ("usys.S", "usys dot S"), ("sysfile.c", "sysfile dot c"),
    ("sysproc.c", "sysproc dot c"), ("syscall.c", "syscall dot c"), ("syscall.h", "syscall dot h"),
    ("trap.c", "trap dot c"), ("vm.c", "vm dot c"), ("entry.S", "entry dot S"),
    ("mmu.h", "mmu dot h"), ("defs.h", "defs dot h"), ("user.h", "user dot h"),
    ("VIVA.md", "viva dot m d"), ("WP", "W P"), ("0x1000", "hex one thousand"),
    ("0x100000", "hex one hundred thousand"), ("2^32", "two to the thirty second"),
]


def spoken(text):
    t = text
    for a, b in sorted(SAY, key=lambda p: -len(p[0])):
        t = t.replace(a, b)
    t = t.replace("_", " ").replace("`", "")
    return " ".join(t.split())


def S(ch, main, text=None, silence=None, say=None):
    steps.append(dict(ch=ch, main=main, text=text, silence=silence, say=say))


# --------------------------------------------------------------------------- html pieces
CSS = """
*{box-sizing:border-box}
body{width:1920px;height:1080px;margin:0;background:#0d1117;color:#e6edf3;
 font-family:Inter,'DejaVu Sans',sans-serif;display:flex;flex-direction:column;overflow:hidden}
.top{height:76px;display:flex;align-items:center;padding:0 48px;gap:24px;border-bottom:1px solid #30363d;flex:none}
.brand{font-weight:700;font-size:26px;letter-spacing:.2px}
.brand span{color:#58a6ff}
.chips{display:flex;gap:10px;margin-left:auto}
.chip{padding:7px 18px;border-radius:20px;font-size:20px;color:#8b949e;border:1px solid #30363d}
.chip.on{color:#0d1117;background:#58a6ff;border-color:#58a6ff;font-weight:700}
.chip.done{color:#3fb950;border-color:#238636}
.prog{height:5px;background:#21262d;flex:none}.prog i{display:block;height:100%;background:#58a6ff}
.main{flex:1;padding:26px 48px;display:flex;gap:30px;min-height:0}
.cap{height:150px;flex:none;background:#010409;border-top:1px solid #30363d;display:flex;align-items:center;
 justify-content:center;padding:0 140px;font-size:35px;line-height:1.35;text-align:center;color:#f0f6fc}
h1{font-size:64px;margin:0 0 14px}h2{font-size:48px;margin:0 0 22px}
.col{display:flex;flex-direction:column;min-width:0}
.mono{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace}
/* code */
.codewrap{flex:1;display:flex;flex-direction:column;min-width:0}
.fileb{font-family:'DejaVu Sans Mono',monospace;font-size:24px;color:#8b949e;padding:0 0 12px}
.fileb b{color:#e6edf3}
.code{background:#0d1117;border:1px solid #30363d;border-radius:12px;padding:14px 0;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:25px;line-height:35px;overflow:hidden}
.ln{display:flex;white-space:pre;height:35px;transition:none}
.ln .no{width:78px;text-align:right;color:#6e7681;padding-right:16px;flex:none}
.ln .bar{width:6px;flex:none;margin-right:16px;border-radius:3px}
.ln .bar.ours{background:#3fb950}.ln .bar.old{background:#30363d}
.ln.dim{opacity:.5}
.ln.focus{background:#1c2b44;box-shadow:inset 4px 0 0 #58a6ff}
.side{width:520px;flex:none;display:flex;flex-direction:column;gap:20px}
.card{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:22px 26px;font-size:28px;line-height:1.4}
.card h3{margin:0 0 10px;font-size:22px;letter-spacing:1.5px;text-transform:uppercase;color:#58a6ff}
.card code,.card .m{font-family:'DejaVu Sans Mono',monospace;color:#ffa657;font-size:26px}
.legend{font-size:21px;color:#8b949e;display:flex;gap:22px;align-items:center}
.legend i{display:inline-block;width:6px;height:20px;border-radius:3px;margin-right:8px;vertical-align:middle}
/* pygments */
.k,.kd,.kr,.kn,.kp{color:#ff7b72}.kt{color:#ffa657}.nf{color:#d2a8ff}.c1,.cm,.c,.cs{color:#8b949e;font-style:italic}
.cp,.cpf{color:#ff7b72}.s,.s1,.s2,.sc{color:#a5d6ff}.mi,.mh,.m,.mf{color:#79c0ff}.o{color:#ff7b72}.nb{color:#ffa657}
.nl,.nc{color:#7ee787}.na{color:#79c0ff}.nv,.nx{color:#e6edf3}
/* diagrams */
.diag{flex:1;display:flex;flex-direction:column;justify-content:center;gap:34px}
.row{display:flex;align-items:center;gap:18px}
.box{background:#161b22;border:2px solid #30363d;border-radius:16px;padding:20px 26px;font-size:30px;text-align:center;line-height:1.25}
.box small{display:block;font-size:21px;color:#8b949e;margin-top:6px;font-family:'DejaVu Sans Mono',monospace}
.box.on{border-color:#58a6ff;background:#0f2a4a}
.box.good{border-color:#3fb950;background:#0f2d1a}
.box.bad{border-color:#f85149;background:#3a1216}
.box.warn{border-color:#d29922;background:#3a2a08}
.box.dim{opacity:.3}
.arr{font-size:42px;color:#6e7681}
.seg{border:2px solid #30363d;border-radius:12px;padding:16px 10px;text-align:center;font-size:30px;background:#161b22}
.seg small{display:block;font-size:22px;color:#8b949e;margin-top:4px}
.seg.on{border-color:#58a6ff;background:#0f2a4a}
.pill{display:inline-block;padding:4px 14px;border-radius:14px;font-size:22px;margin-left:12px;font-weight:700}
.pill.red{background:#f85149;color:#0d1117}.pill.green{background:#3fb950;color:#0d1117}.pill.amber{background:#d29922;color:#0d1117}
ul.bul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:22px}
ul.bul li{font-size:40px;line-height:1.3;padding-left:46px;position:relative}
ul.bul li:before{content:'';position:absolute;left:6px;top:17px;width:16px;height:16px;border-radius:50%;background:#58a6ff}
ul.bul li.hide{visibility:hidden}ul.bul li.dim{opacity:.4}
ul.bul code{font-family:'DejaVu Sans Mono',monospace;color:#ffa657;font-size:36px}
.term{flex:1;background:#010409;border:1px solid #30363d;border-radius:14px;display:flex;flex-direction:column;min-width:0}
.term .bar{height:44px;background:#161b22;border-radius:14px 14px 0 0;display:flex;align-items:center;padding:0 18px;gap:9px;color:#8b949e;font-size:21px}
.term .bar i{width:14px;height:14px;border-radius:50%;display:inline-block}
.term pre{margin:0;padding:16px 22px;font-family:'DejaVu Sans Mono',monospace;font-size:24px;line-height:33px;overflow:hidden;flex:1}
.tl{display:block;height:33px;white-space:pre}
.tl.fault{color:#ff7b72;background:#3a1216}.tl.ok{color:#7ee787}.tl.stop{color:#ffa657}.tl.cmd{color:#58a6ff;font-weight:700}
.tl.hl{background:#1c2b44;box-shadow:inset 4px 0 0 #58a6ff}.tl.fault.hl{background:#4a1a1f}
.qcard{flex:1;display:flex;flex-direction:column;justify-content:center;gap:34px}
.q{font-size:54px;line-height:1.25;font-weight:700}
.a{font-size:40px;line-height:1.4;color:#7ee787;border-left:6px solid #3fb950;padding-left:28px}
.think{font-size:34px;color:#d29922}
.title{flex:1;display:flex;flex-direction:column;justify-content:center;gap:26px}
.title h1{font-size:86px;line-height:1.1}.title p{font-size:38px;color:#8b949e;margin:0}
.agenda{display:flex;gap:18px;margin-top:20px}
.agenda .box{font-size:28px;min-width:230px}
.big{font-size:44px}
.eq{font-family:'DejaVu Sans Mono',monospace;font-size:38px;line-height:1.7}
.eq b.r{color:#f85149}.eq b.g{color:#3fb950}.eq b.y{color:#ffa657}.eq b.b{color:#58a6ff}
"""

_lex_cache = {}
_lines_cache = {}


def src_lines(path):
    if path not in _lines_cache:
        _lines_cache[path] = (ROOT / path).read_text().split("\n")
    return _lines_cache[path]


def hl_line(path, text):
    key = path
    if key not in _lex_cache:
        try:
            _lex_cache[key] = get_lexer_for_filename(path)
        except Exception:
            _lex_cache[key] = TextLexer()
    fmt = HtmlFormatter(nowrap=True)
    return highlight(text, _lex_cache[key], fmt).rstrip("\n") or " "


def page(ch, main, caption, frac):
    chips = "".join(
        f'<div class="chip {"on" if i == ch else "done" if i < ch else ""}">{html.escape(c)}</div>'
        for i, c in enumerate(CHAPTERS))
    cap = html.escape(caption) if caption else ""
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body>'
            f'<div class="top"><div class="brand">Read-only page protection in <span>xv6</span></div>'
            f'<div class="chips">{chips}</div></div>'
            f'<div class="prog"><i style="width:{frac * 100:.2f}%"></i></div>'
            f'<div class="main">{main}</div><div class="cap">{cap}</div></body>')


def code_view(path, show, focus=None, ours=None, note="", head=None):
    lines = src_lines(path)
    a, b = show
    assert b - a + 1 <= 20, f"window too tall for {path} {show}"
    assert 1 <= a <= b <= len(lines), f"bad range {path} {show}"
    if focus:
        assert a <= focus[0] <= focus[1] <= b, f"focus outside window {path} {focus} {show}"
    rows = []
    for n in range(a, b + 1):
        cls = "ln"
        if focus:
            cls += " focus" if focus[0] <= n <= focus[1] else " dim"
        bar = "ours" if ours and ours[0] <= n <= ours[1] else "old"
        rows.append(f'<div class="{cls}"><span class="no">{n}</span><span class="bar {bar}"></span>'
                    f'<span>{hl_line(path, lines[n - 1].expandtabs(2))}</span></div>')
    fl = f"{path}  ·  lines {focus[0]}–{focus[1]}" if focus else f"{path}  ·  lines {a}–{b}"
    title = head or ""
    side = (f'<div class="card"><h3>{html.escape(title or "What it does")}</h3>{note}</div>'
            if note else "")
    legend = ('<div class="legend"><span><i style="background:#3fb950"></i>project addition</span>'
              '<span><i style="background:#30363d"></i>existing xv6</span></div>')
    return (f'<div class="codewrap"><div class="fileb"><b>{html.escape(fl)}</b></div>'
            f'<div class="code">{"".join(rows)}</div></div>'
            f'<div class="side">{side}{legend}</div>')


def bullets(title, items, shown, dim_prev=True):
    lis = []
    for i, it in enumerate(items):
        cls = "hide" if i >= shown else ("dim" if dim_prev and i < shown - 1 else "")
        lis.append(f'<li class="{cls}">{it}</li>')
    return f'<div class="col" style="flex:1;justify-content:center"><h2>{title}</h2><ul class="bul">{"".join(lis)}</ul></div>'


def box(txt, cls="", sub=""):
    s = f"<small>{sub}</small>" if sub else ""
    return f'<div class="box {cls}">{txt}{s}</div>'


ARR = '<div class="arr">→</div>'


def chain(items):
    out = []
    for i, (t, c, s) in enumerate(items):
        if i:
            out.append(ARR)
        out.append(box(t, c, s))
    return f'<div class="row" style="justify-content:center;flex-wrap:nowrap">{"".join(out)}</div>'


def term_view(lines, upto, hl=(), head="xv6 guest · QEMU serial console", note="", noteh="Look at"):
    show = lines[max(0, upto - 24):upto]
    base = max(0, upto - 24)
    out = []
    for i, l in enumerate(show):
        idx = base + i
        cls = "tl"
        if "trap 14" in l:
            cls += " fault"
        elif "SUCCEEDED" in l or "PASS" in l or "ALL PASSED" in l or l.strip().startswith("vmtest: ok"):
            cls += " ok"
        elif "STOPPED" in l:
            cls += " stop"
        elif l.startswith("$ "):
            cls += " cmd"
        if idx in hl:
            cls += " hl"
        out.append(f'<span class="{cls}">{html.escape(l)}</span>')
    side = f'<div class="side"><div class="card"><h3>{noteh}</h3>{note}</div></div>' if note else ""
    return (f'<div class="term"><div class="bar"><i style="background:#f85149"></i><i style="background:#d29922"></i>'
            f'<i style="background:#3fb950"></i>&nbsp;{html.escape(head)}</div><pre>{"".join(out)}</pre></div>{side}')


# --------------------------------------------------------------------------- content
# ---- chapter 0: problem
agenda = ["Problem", "Background", "Solution", "Tests & demo", "Modify it", "Viva Q&A"]


def title_card(lit):
    ag = "".join(box(a, "on" if i < lit else "dim") for i, a in enumerate(agenda))
    return ('<div class="title"><h1>Read-only page protection<br>in x86 xv6</h1>'
            '<p>Viva walkthrough: problem, solution, real code, tests, and how to change it</p>'
            f'<div class="agenda">{ag}</div></div>')


S(0, title_card(0), "This video prepares you for the viva on read-only page protection in xv6.")
S(0, title_card(3), "We go from the problem, through the background and our solution, to the code block by block, and then the tests and a live demo.")
S(0, title_card(6), "At the end you get three example changes an examiner might ask for, and rapid-fire viva questions.")
S(0, title_card(6), "Pause often, and try to rewrite each function yourself. You must own every line.")

PROB = [
    "Add two system calls to xv6:",
    "<code>mprotect(addr, len)</code> makes pages read-only; <code>munprotect</code> restores them",
    "<code>addr</code> page-aligned, <code>len</code> counts <b>pages</b>, not bytes",
    "Reads still work. A write kills <b>only that process</b>",
    "A failed call changes <b>nothing</b>; effect is immediate",
    "Permissions survive <code>fork()</code>, then stay independent",
]
S(0, bullets("The problem", PROB, 1), "The task, from the OSTEP virtual memory project: add two system calls to xv6.")
S(0, bullets("The problem", PROB, 2), "mprotect makes a range of pages read-only. munprotect makes them writable again.")
S(0, bullets("The problem", PROB, 3), "The address must be page aligned, and the length counts pages, not bytes.")
S(0, bullets("The problem", PROB, 4), "Reads must still work, but a write to a protected page must kill that process, and only that process.")
S(0, bullets("The problem", PROB, 6), "A failed call must change nothing. The change must be immediate. And fork must keep the protection.")

# ---- chapter 1: background
def addr_view(segs=(), chain_on=(), formula=False):
    def seg(i, w, t, s):
        return f'<div class="seg {"on" if i in segs else ""}" style="flex:{w}">{t}<small>{s}</small></div>'
    bar = ('<div class="row" style="gap:10px">' + seg(0, 10, "Page directory index", "PDX · 10 bits") +
           seg(1, 10, "Page table index", "PTX · 10 bits") + seg(2, 12, "Offset in page", "12 bits") + "</div>")
    names = [("CR3", "register", "points to directory"), ("Page directory", "", "PDX picks an entry"),
             ("Page table", "", "PTX picks the PTE"), ("PTE", "", "physical page + flags"),
             ("Physical page", "", "+ offset")]
    ch = chain([(n, "on" if i in chain_on else "", s) for i, (n, _, s) in enumerate(names)])
    f = ""
    if formula:
        f = ('<div class="card big" style="text-align:center">page number = address / 4096 &nbsp;&nbsp;·&nbsp;&nbsp; '
             'offset = address % 4096</div>')
    return (f'<div class="diag"><div class="mono" style="font-size:26px;color:#8b949e;text-align:center">'
            f'32-bit virtual address</div>{bar}{ch}{f}</div>')


S(1, addr_view(), "Background. A page is four thousand ninety-six bytes, and a thirty-two bit address splits into three fields.")
S(1, addr_view(segs=(0,), chain_on=(1,)), "The top ten bits index the page directory.")
S(1, addr_view(segs=(1,), chain_on=(2,)), "The next ten bits index a page table.")
S(1, addr_view(segs=(2,), chain_on=(4,)), "The low twelve bits are the offset inside the page.")
S(1, addr_view(chain_on=(0, 3)), "The register CR3 points at the directory, and the entry that names the physical page is the PTE.")
S(1, addr_view(formula=True), "Page number is the address divided by 4096, and the offset is the remainder.")

PTEN = ('<p>Three bit operations to know:</p>'
        '<p><code>*pte &amp;= ~PTE_W</code> clears</p><p><code>*pte |= PTE_W</code> sets</p>'
        '<p><code>*pte &amp; PTE_W</code> tests</p>')
S(1, code_view("mmu.h", (85, 101), (99, 101), note="<p>The PTE keeps the physical page in its top 20 bits and flags in the low 12.</p>", head="PTE layout"),
  "The PTE stores the physical page and permission bits.")
S(1, code_view("mmu.h", (85, 101), (94, 96), note="<p><code>PTE_W</code> is the bit this whole project toggles.</p>", head="The three flags"),
  "PTE_P means present, PTE_W means writable, and PTE_U means user accessible.")
S(1, code_view("mmu.h", (85, 101), (94, 96), note=PTEN, head="Bit operations"),
  "To clear the writable bit we AND with the inverse mask. To set it we OR. To test it we AND and compare.")


def tlb_view(state):
    cpu = box("CPU writes<br>to page 0x4000", "on")
    if state == 1:
        tlb = box("TLB (cache)", "good", "0x4000 → writable ✓")
        pt = box("Page table", "", "PTE_W = 1")
        msg = "Permissions are cached together with the translation."
    elif state == 2:
        tlb = box('TLB (cache)<span class="pill amber">STALE</span>', "warn", "0x4000 → writable ✓")
        pt = box("Page table", "bad", "PTE_W = 0 (just cleared)")
        msg = "The cache still says writable, so a write could slip through."
    else:
        tlb = box("TLB (cache)", "dim", "flushed: empty")
        pt = box("Page table", "bad", "PTE_W = 0")
        msg = "<code>lcr3</code> flushes the cache; the next write checks the real PTE and faults."
    return (f'<div class="diag">'
            f'<div class="row" style="justify-content:center">{cpu}{ARR}{tlb}{ARR}{pt}</div>'
            f'<div class="card big" style="text-align:center">{msg}</div></div>')


S(1, tlb_view(1), "Two hardware facts matter. First, the TLB caches translations together with their permissions.")
S(1, tlb_view(2), "If we clear the writable bit in the PTE, the cached copy may still say writable.")
S(1, tlb_view(3), "Reloading CR3 flushes the cache, so the next write sees the real permission. That is why our code reloads CR3.")
S(1, code_view("entry.S", (48, 56), (55, 55), note="<p>With <code>CR0_WP</code> set, even <b>kernel</b> writes obey read-only pages. It matters later.</p>", head="Second fact"),
  "Second, entry.S sets CR0 WP, so even the kernel obeys read-only pages. Remember this; it matters later.")

S(1, code_view("trap.c", (82, 95), (89, 93), note="<p>User-mode fault: print, then mark <b>this process</b> killed.</p>", head="The fault handler"),
  "When user code writes a read-only page, the processor raises trap fourteen, a page fault, and this existing handler runs.")
S(1, code_view("trap.c", (82, 95), (94, 94), note="<p>Only the faulting process dies. Its parent keeps running.</p>", head="Why the parent lives"),
  "If the fault came from user mode, only that process is marked killed. The parent carries on.")
ERR = ('<p>Error code 7 =</p><p><span class="m">1</span> page was present</p>'
       '<p><span class="m">2</span> it was a write</p><p><span class="m">4</span> user mode</p>'
       '<p>So <code>trap 14 err 7</code> is a user write to a read-only page.</p>')
S(1, code_view("trap.c", (82, 95), (90, 93), note=ERR, head="Decode err 7"),
  "Decode the message: error seven is one for present, two for write, and four for user mode. That is our protection firing.")
S(1, code_view("trap.c", (82, 95), (83, 87), note="<p>A fault in <b>kernel</b> mode is treated as a kernel bug: <code>panic</code> stops the machine.</p>", head="Kernel-mode fault"),
  "A fault from kernel mode is different. The branch above calls panic, and the whole machine stops.")

# ---- chapter 2: solution
def flow_view(on, extra=False):
    names = [("mprotect(addr, len)", "user.h · usys.S"), ("int T_SYSCALL", "trap into kernel"),
             ("syscall() table", "syscall.c"), ("sys_mprotect", "sysproc.c"), ("setuvmwrite", "vm.c")]
    ch = chain([(n, "on" if i in on else "", s) for i, (n, s) in enumerate(names)])
    res = ""
    if 5 in on:
        res = ('<div class="row" style="justify-content:center">' +
               box("Pass 1", "good", "validate every page") + ARR + box("Pass 2", "good", "change only PTE_W") + ARR +
               box("lcr3", "good", "flush the TLB") + "</div>")
    ex = ""
    if extra:
        ex = ('<div class="row" style="justify-content:center">' +
              box("read · fstat · pipe", "warn", "output buffer must be writable") + ARR +
              box("argptrw → checkuvmwrite", "good", "else return -1, no kernel fault") + "</div>")
    return f'<div class="diag">{ch}{res}{ex}</div>'


S(2, flow_view({0}), "Our solution in one picture. The program calls mprotect.")
S(2, flow_view({0, 1, 2, 3}), "A tiny assembly stub traps into the kernel, and the dispatch table finds sys mprotect.")
S(2, flow_view({0, 1, 2, 3, 4}), "That calls one shared helper, setuvmwrite, in vm.c.")
S(2, flow_view({0, 1, 2, 3, 4, 5}), "The helper validates every page first, then changes only the writable bit, then reloads CR3.")
S(2, flow_view({0, 1, 2, 3, 4, 5}, extra=True), "A second part makes read, fstat and pipe check their output buffers, so the kernel can never fault on protected memory.")

S(2, code_view("usys.S", (14, 33), (31, 33), ours=(32, 33), note="<p>Same one-line pattern as <code>uptime</code>: load the call number, trap, return.</p>", head="User side"),
  "On the user side we copied the pattern of uptime. Each call is one line in usys.S that loads the call number and traps.")
S(2, code_view("syscall.h", (5, 24), (23, 24), ours=(23, 24), note="<p>Unique numbers <b>22</b> and <b>23</b>.</p>", head="Call numbers"),
  "In syscall.h, our calls are numbered twenty-two and twenty-three.")
S(2, code_view("syscall.c", (125, 143), (141, 142), ours=(141, 142), note="<p>Table entries map the number to the handler. The <code>extern</code> lines at 116–117 declare them.</p>", head="Dispatch table"),
  "In syscall.c, an extern declaration and a table entry connect each number to its handler.")

S(2, code_view("sysproc.c", (94, 113), (99, 104), ours=(93, 117), note="<p><code>argint</code> reads each argument from the user stack.</p>", head="Front end"),
  "In sysproc.c, changeprotection fetches the address and the length with argint, and passes them to setuvmwrite.")
S(2, code_view("sysproc.c", (98, 117), (107, 117), ours=(93, 117), note="<p><code>mprotect</code> → writable = 0<br><code>munprotect</code> → writable = 1</p><p>One helper, two thin wrappers.</p>", head="Two wrappers"),
  "mprotect passes writable equals zero, and munprotect passes one. One helper, two thin wrappers.")

VM = (313, 378)
S(2, code_view("vm.c", (313, 332), (319, 320), ours=VM, note="<p>The heart of the project. Returns <b>0</b> on success, <b>-1</b> on an invalid request.</p>", head="setuvmwrite"),
  "Now the heart of the project, setuvmwrite in vm.c.")
S(2, code_view("vm.c", (313, 332), (325, 326), ours=VM, note="<p>Rejects: unaligned address, count ≤ 0 (also negatives), start outside the process.</p>", head="Check 1"),
  "The first check rejects an unaligned address, a count of zero or less, and a start outside the process.")
S(2, code_view("vm.c", (313, 332), (327, 330), ours=VM, note="<p>Compare page <b>counts</b>. Never multiply first: the product can overflow.</p>", head="Check 2"),
  "The second check compares the count with how many whole pages fit. We never multiply first, because the product could overflow.")
S(2, code_view("vm.c", (321, 340), (331, 331), ours=VM, note="<p>Safe now: this end address is known to be inside the process.</p>", head="End address"),
  "Only then is the end address safe to compute.")
S(2, code_view("vm.c", (321, 340), (333, 339), ours=VM, note="<p><b>Pass 1</b>: each page must exist, be present and be a user page. <code>walkpgdir(…, 0)</code> never allocates. The stack guard page has no <code>PTE_U</code>, so it fails.</p>", head="Pass 1: validate"),
  "Pass one walks every page without allocating. Each must be present and a user page, so the stack guard page is rejected here.")
S(2, code_view("vm.c", (334, 353), (341, 348), ours=VM, note="<p><b>Pass 2</b> runs only if pass 1 passed for every page, so it cannot fail halfway. Only <code>PTE_W</code> changes.</p>", head="Pass 2: update"),
  "Pass two runs only when pass one succeeded, so it cannot fail halfway. It sets or clears only the writable bit.")
S(2, code_view("vm.c", (334, 353), (350, 351), ours=VM, note="<p><code>V2P</code> because <code>CR3</code> holds a <b>physical</b> address. Reloading it flushes the TLB.</p>", head="Flush the TLB"),
  "Finally, reloading CR3 flushes the TLB, so the change takes effect immediately.")


def math_view(stage):
    l = ['<div class="eq">start = <b class="b">0x1000</b> &nbsp; count = <b class="b">0x100000</b> &nbsp;(2^20 pages)</div>']
    if stage >= 1:
        l.append('<div class="eq">count × 4096 = 2^20 × 2^12 = 2^32 → wraps to <b class="r">0</b> in 32 bits</div>')
    if stage >= 2:
        l.append('<div class="eq">naive: end = start + 0 = 0x1000 → <b class="r">looks valid ✗</b></div>')
        l.append('<div class="eq">ours: count &gt; (sz − va) / 4096 → <b class="g">rejected ✓</b></div>')
    return f'<div class="col" style="flex:1;justify-content:center"><h2>Why compare counts?</h2>{"".join(l)}</div>'


S(2, math_view(0), "Why compare counts? Take a start of hex one thousand and a count of hex one hundred thousand.", say="Why compare counts? Take a start of hex one thousand and a count of hex one hundred thousand, two to the twentieth pages.")
S(2, math_view(1), "Count times 4096 is two to the thirty-second, which wraps around to zero in thirty-two bit arithmetic.", say="Count times four thousand ninety-six is two to the thirty-second, which wraps around to zero in thirty-two bit arithmetic.")
S(2, math_view(2), "A naive check would see an end of 0x1000 and accept it. Ours compares counts, and correctly rejects it.", say="A naive check would see an end of hex one thousand and accept it. Ours compares counts, and correctly rejects it.")


def pass_view(mode):
    def pg(n, cls, sub=""):
        return box(f"page {n}", cls, sub)
    wrong = ""
    right = ""
    if mode >= 1:
        wrong = ('<div class="card"><h3>One pass (wrong)</h3><div class="row">' + pg(1, "warn", "changed") +
                 pg(2, "warn", "changed") + pg(3, "bad", "invalid") +
                 '<div style="font-size:30px;margin-left:20px">returns -1, but pages 1–2 <b style="color:#f85149">stay modified</b></div></div></div>')
    if mode >= 2:
        right = ('<div class="card"><h3>Two passes (ours)</h3><div class="row">' + pg(1, "good", "ok") +
                 pg(2, "good", "ok") + pg(3, "bad", "invalid") +
                 '<div style="font-size:30px;margin-left:20px">pass 1 fails → <b style="color:#3fb950">nothing was touched</b></div></div></div>')
    head = '<h2>A failed call must change nothing</h2>'
    return f'<div class="col" style="flex:1;justify-content:center;gap:28px">{head}{wrong}{right}</div>'


S(2, pass_view(0), "Why two passes? The specification says a failed call must change nothing.")
S(2, pass_view(1), "If we changed pages while validating, an invalid third page would leave the first two already modified.")
S(2, pass_view(2), "With two passes, validation fails first, so nothing is touched. We tested this by merging the passes and watching the test fail.")

S(2, code_view("vm.c", (390, 407), (397, 402), note="<p>Flags are copied with the page, so <code>PTE_W</code> = 0 is inherited. The child gets its <b>own</b> physical page.</p>", head="fork: copyuvm"),
  "Fork needed no change. copyuvm reads each page's flags, allocates a new physical page, copies the contents, and maps it with the same flags.")
S(2, code_view("vm.c", (390, 407), (402, 402), note="<p>Read-only stays read-only in the child, but the two pages are separate copies: changes never cross over.</p>", head="Independent copies"),
  "So a read-only page stays read-only in the child, yet the two are separate copies. A change in one never affects the other.")


def kbuf_view(stage):
    if stage == 0:
        items = [("read(fd, buf, n)", "on", ""), ("kernel copies data into buf", "", "inside the kernel")]
    elif stage == 1:
        items = [("read(fd, buf, n)", "on", ""), ("kernel writes into buf", "warn", "buf's page is read-only"),
                 ("CR0.WP is set", "warn", "kernel obeys read-only"), ("kernel-mode fault", "bad", "trap() → panic!")]
    elif stage == 2:
        items = [("read(fd, buf, n)", "on", ""), ("argptrw checks buf", "good", "every page writable?"),
                 ("not writable", "good", "return -1, no write")]
    else:
        items = [("write(fd, buf, n)", "on", ""), ("kernel only READS buf", "good", "protected page is fine")]
    return f'<div class="diag">{chain(items)}</div>'


S(2, kbuf_view(0), "Now the bug we found by testing. What if the kernel itself writes into a protected page, for example in read?")
S(2, kbuf_view(1), "Because CR0 WP is set, that is a page fault in kernel mode, and the trap handler panics. We reproduced exactly this crash.")
S(2, kbuf_view(2), "The rule: if the kernel will write into a user buffer, check that every page is writable first, and return minus one if not.")
S(2, kbuf_view(3), "But write only reads the buffer, so a protected page is perfectly fine there.")
S(2, code_view("vm.c", (361, 378), (369, 376), ours=VM, note="<p>Loops over <b>every</b> page the buffer touches, including a writable page followed by a read-only one.</p>", head="checkuvmwrite"),
  "checkuvmwrite loops over every page the buffer touches, so buffers that span several pages are covered.")
S(2, code_view("vm.c", (361, 378), (372, 373), ours=VM, note="<p>All three bits needed: present, user, writable. Anything less returns -1.</p>", head="The test"),
  "Each page needs present, user and writable all set. Anything less returns minus one.")
S(2, code_view("syscall.c", (66, 80), (72, 80), ours=(72, 80), note="<p>Old bounds check first, then the new writable check.</p>", head="argptrw"),
  "argptrw calls the old bounds check, then this check.")
S(2, code_view("sysfile.c", (69, 82), (76, 76), ours=(76, 76), note="<p><code>argptr</code> became <code>argptrw</code>. Same one-word change in <code>sys_fstat</code> and <code>sys_pipe</code>. <code>sys_write</code> is untouched.</p>", head="The callers"),
  "In sys read, argptr became argptrw. sys fstat and sys pipe changed the same way, but sys write is untouched.")
S(2, code_view("vm.c", (433, 452), (441, 445), ours=(444, 445), note="<p><code>copyout</code> writes through the kernel's own always-writable alias, so it needed the same check.</p>", head="copyout"),
  "copyout writes through the kernel's own always-writable mapping, so it got the same check.")

# ---- chapter 3: tests and demo
S(3, code_view("vmtest.c", (41, 60), (48, 58), ours=(1, 400), note="<p>A child does the risky write, so a fault kills the child, not the test.</p>", head="vmtest.c"),
  "To test this from user code, vmtest uses a child process, because a faulting write kills only its own process.")
S(3, code_view("vmtest.c", (41, 60), (57, 58), ours=(1, 400), note="<p>The marker is written <b>only if</b> the store succeeded.</p>", head="The marker"),
  "The child writes, and only if the write succeeds does it write a marker byte into a pipe.")
S(3, code_view("vmtest.c", (49, 68), (62, 67), ours=(1, 400), note="<p>EOF on the pipe means the child died before the marker, so the write faulted. xv6's <code>wait()</code> has no exit status, hence the pipe.</p>", head="Detecting the fault"),
  "The parent reads the pipe. End of file means the child died before the marker, so the write faulted.")
S(3, code_view("vmtest.c", (92, 111), (101, 104), ours=(1, 400), note="<p>The first write caches a writable TLB entry. <code>mprotect</code> then <code>write</code> again, with no context switch.</p>", head="The TLB test"),
  "One test deserves special mention. The child writes the page first, caching a writable translation, then calls mprotect and writes again.")
S(3, code_view("vmtest.c", (92, 111), (103, 104), ours=(1, 400), note="<p>No <code>lcr3</code> → the second write succeeds → the marker arrives → test fails. We deleted the line to prove it.</p>", head="Why it matters"),
  "Without the CR3 reload, that second write would succeed. We proved it by deleting the line: this test failed. Then we restored it.")

G = [l.rstrip("\n") for l in (ROOT / "video/assets/guest_output.txt").read_text().replace("\r", "").split("\n")]


def gi(sub, start=0):
    for i in range(start, len(G)):
        if sub in G[i]:
            return i
    raise SystemExit(f"marker not found in guest output: {sub}")


i1 = gi("[1]"); i1e = gi("stored and read back"); i2 = gi("protected read still works")
i2f = gi("STOPPED by page fault", i2); i2p = gi("parent still alive"); i3 = gi("inherited child write")
i4 = gi("[4]"); i4e = gi("after rejected munprotect"); i5 = gi("[5]"); i5e = gi("child write of 507"); iend = gi("vmdemo done")
demo_hl = lambda *a: tuple(a)
S(3, term_view(G, i1e + 1, (i1, i1e), note="<p><code>vmdemo 7 3</code>: three pages, value 7. Real output from the xv6 guest.</p>", noteh="Writable control"),
  "Now the live demo. We run vmdemo with seven and three: three pages, value seven. First a writable control.")
S(3, term_view(G, i2 + 1, (i2 - 2, i2), note="<p><code>mprotect</code> returned 0 and the page is still readable.</p>", noteh="Protect"),
  "After mprotect returns zero, reading still works.")
S(3, term_view(G, i2p + 1, (i2f - 1, i2f), note="<p><code>trap 14 err 7</code>: page fault, write, user mode. The parent is alive, value unchanged.</p>", noteh="The fault"),
  "A child writes to the last page and dies. The kernel line says trap fourteen error seven, a page fault from a user write. The parent is alive and its value is unchanged.")
S(3, term_view(G, i3 + 1, (i3 - 1, i3), note="<p>A brand-new child inherits the read-only page and faults too.</p>", noteh="Fork"),
  "A fresh child inherits the read-only page, so it faults too.")
S(3, term_view(G, i4e + 1, (i4 + 1, i4 + 2, i4 + 3, i4e - 1, i4e), note="<p>Bad requests return <code>-1</code>. The rejected <code>munprotect</code> changed nothing: the next child still faults.</p>", noteh="Rejections"),
  "Invalid requests return minus one, and the rejected munprotect changed nothing: the next child still faults.")
S(3, term_view(G, iend + 1, (i5, i5e - 1, i5e), note="<p>After <code>munprotect</code> the parent and a child can both write.</p>", noteh="Restore"),
  "After munprotect, writes work again, for the parent and for a child.")

CHK = [l for l in (ROOT / "video/assets/check_output.txt").read_text().split("\n") if l.strip()]
TL = ["$ ./scripts/xv6 clean", "$ ./scripts/xv6 check", ""] + CHK
S(3, term_view(TL, len(TL), (3, 4, 5), head="Laptop terminal", note="<p>Passed in a Linux cloud container, GitHub Actions, and on the Pop!_OS laptop.</p><p>10 faults seen by <code>vmtest</code> = 10 kernel fault messages.</p>", noteh="The evidence"),
  "The full check prints three pass lines. It passed in a Linux container, in GitHub Actions, and on your Pop O S laptop. The ten faults vmtest counted match ten kernel messages.")
MUT = ('<p>We also <b>broke the code on purpose</b>:</p><p>no <code>lcr3</code> → TLB test fails</p>'
       '<p>merged passes → atomic tests fail</p><p><code>argptr</code> in read → kernel panic</p>'
       '<p style="color:#d29922">The Mac passed only the baseline so far. Run <code>check</code> there before relying on it.</p>')
S(3, term_view(TL, len(TL), (4,), head="Laptop terminal", note=MUT, noteh="Mutation checks"),
  "We also broke the code on purpose. Deleting the CR3 reload, or merging the two passes, made tests fail. The Mac has passed only the baseline so far, so run check there first.")

# ---- chapter 4: modify
M = [
    "Name the <b>files and function</b> that control the behaviour",
    "Make the <b>smallest</b> change",
    "<code>./scripts/xv6 build</code>, then <code>run</code> and test",
    "Explain <b>why</b> it works and what else it affects",
]
S(4, bullets("If the examiner says: change this", M, 1), "Part four. The examiner may ask you to change the code. The method is always the same.")
S(4, bullets("If the examiner says: change this", M, 4), "Name the files and the function. Make the smallest change. Rebuild and test. Then explain why it works.")
E1 = "video/examples/getprot_solution.c"
S(4, code_view(E1, (5, 24), (11, 16), ours=(1, 35), note="<p>Example 1: <code>getprot(addr)</code> returns 1 if writable, 0 if read-only, -1 if invalid.</p>", head="Add getprot"),
  "Example one: add a getprot call that reports whether a page is writable. The helper walks the page table without allocating, requires a present user page, and returns the writable bit.")
S(4, code_view(E1, (17, 35), (25, 35), ours=(1, 35), note="<p>Wiring, same as mprotect: number 24, <code>extern</code> + table entry, stub, two prototypes.</p>", head="Wire it up"),
  "The wrapper fetches one argument and calls the helper. Then the wiring is exactly like mprotect: a number, an extern and table entry, a stub, and two prototypes.")
E2 = "video/examples/bytes_solution.c"
S(4, code_view(E2, (4, 23), (14, 16), ours=(1, 23), note="<p>Example 2: <code>len</code> in <b>bytes</b>, rounded up to pages.</p>", head="Bytes, not pages"),
  "Example two: make the length a count of bytes. Only changeprotection changes. Reject non-positive lengths, then convert to pages, rounding up.")
S(4, code_view(E2, (4, 23), (16, 17), ours=(1, 23), note="<p>Subtract first so we never add 4095 and overflow. Some <code>vmtest</code> cases assume page counts and would need updating.</p>", head="Why this form"),
  "Subtract one before dividing, so we never add four thousand ninety-five and overflow. Mention that some vmtest cases assume page counts.")
E3 = "video/examples/fault_message_solution.c"
S(4, code_view(E3, (1, 18), (7, 7), ours=(1, 18), note="<p>Example 3: a clearer message on a write fault, in <code>trap.c</code>.</p>", head="Clearer message"),
  "Example three: print a clearer message on a write fault. In trap.c, in the user branch, check for a page fault with the error bits present, write and user.")
S(4, code_view(E3, (1, 18), (8, 9), ours=(1, 18), note="<p><code>PGROUNDDOWN</code> is already available through <code>mmu.h</code>. Put it <b>before</b> the existing message.</p>", head="Print the page"),
  "Print the faulting page with PGROUNDDOWN of rcr2, before the existing message. PGROUNDDOWN is already included through mmu.h.")
IDEAS = [
    "Kill the caller instead of returning an error",
    "Refuse page <b>0</b>",
    "Cap the length",
    "Return how many pages changed",
    "For each: which <b>file</b>, which <b>line</b>, which <b>test</b>?",
]
S(4, bullets("Other likely requests", IDEAS, 5), "Other likely requests: kill the caller instead of returning an error, refuse page zero, cap the length, or return how many pages changed. For each, name the file, the line and the test.")
EXP = [
    "Delete <code>lcr3</code> → the immediate-effect test fails",
    "Merge the passes → a rejected range leaves a page read-only",
    "Drop the <code>PTE_U</code> check → the guard page is accepted",
    "<code>argptr</code> in <code>sys_read</code> → kernel panic",
]
S(4, bullets("Predict before you run", EXP, 4, dim_prev=False), "Predict before you run: deleting lcr3 fails the immediate-effect test. Merging the passes leaves a page read-only after a rejection. Dropping the user check accepts the guard page. And argptr in sys read panics the kernel.")

# ---- chapter 5: Q&A
QA = [
    ("Why must the address be page-aligned, and the length in pages?",
     "Permissions apply to whole pages, so a mid-page address has no meaning."),
    ("Why two passes?", "So a failed call changes nothing. Pass two cannot fail halfway."),
    ("What happens without the CR3 reload?",
     "The TLB may keep a writable translation, so a write could still succeed."),
    ("Why does only the child die, and what is trap 14 err 7?",
     "The fault is in the child's user mode, so only it is killed. Page fault: present, write, user."),
    ("Why did read into a protected buffer panic, and why is write still allowed?",
     "CR0.WP makes kernel writes obey read-only pages, and a kernel fault panics. We check output buffers. Write only reads."),
    ("Why does fork keep protection?",
     "copyuvm copies the flag bits into the child's own separate page."),
]
SPOKEN_A = [
    "Permissions apply to whole pages, so a mid-page address has no meaning.",
    "So a failed call changes nothing. Pass two cannot fail halfway.",
    "The TLB may keep a writable translation, so a write could still succeed.",
    "The fault is in the child's user mode, so only it is killed. Page fault: present, write, user.",
    "CR0 WP makes kernel writes obey read-only pages, and a kernel fault panics. We check output buffers. Write only reads.",
    "copyuvm copies the flag bits into the child's own separate page.",
]


def qa_view(i, stage):
    q, a = QA[i]
    body = f'<div class="q">Q{i + 1}. {html.escape(q)}</div>'
    if stage == 1:
        body += '<div class="think">⏸ Pause the video and answer aloud…</div>'
    if stage == 2:
        body += f'<div class="a">{html.escape(a)}</div>'
    return f'<div class="qcard">{body}</div>'


S(5, bullets("Viva questions", ["Answer each one <b>aloud</b> before listening", "Short answers are fine; examiners follow up"], 2),
  "Now rapid-fire viva questions. Answer each one aloud before you listen to the answer.")
for i, (q, a) in enumerate(QA):
    S(5, qa_view(i, 0), q)
    S(5, qa_view(i, 1), None, silence=3.2)
    S(5, qa_view(i, 2), SPOKEN_A[i])

SUM = [
    "A process can toggle <code>PTE_W</code> on its own pages <b>safely</b>",
    "Hardware enforces it; the kernel can neither crash nor bypass it",
    "Do <b>VIVA.md</b> exercises 1–3 with no AI help",
    "Rehearse <b>DEMO.md</b> on the presentation machine",
    "Deadline: end-sem exam + 3 days",
]
S(5, bullets("Summary", SUM, 2), "In one sentence: a process can switch the write bit of its own pages off and on, safely. The hardware enforces it, and the kernel can neither crash nor bypass it.")
S(5, bullets("Summary", SUM, 5), "Now do the three exercises in VIVA.md without any help, answer the questions aloud, and rehearse the demo on your presentation machine. When you can rewrite setuvmwrite from memory and explain every line, you own it. Good luck.")

# --------------------------------------------------------------------------- build
def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def make_audio(i, st):
    wav = BUILD / f"a{i:03d}.wav"
    raw = BUILD / f"r{i:03d}.wav"
    if st["silence"]:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(st["silence"]),
             "-c:a", "pcm_s16le", str(wav)])
    else:
        text = spoken(st["say"] or st["text"])
        voice = VOICE
        try:
            run(["espeak-ng", "-v", voice, "-s", SPEED, "-w", str(raw), text])
        except subprocess.CalledProcessError:
            run(["espeak-ng", "-v", "en-us", "-s", SPEED, "-w", str(raw), text])
        run(["ffmpeg", "-y", "-i", str(raw), "-ar", "44100", "-ac", "1",
             "-af", f"apad=pad_dur={GAP}", "-c:a", "pcm_s16le", str(wav)])
        raw.unlink()
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def fmt(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def main():
    frames_only = "--frames" in sys.argv
    shutil.rmtree(BUILD, ignore_errors=True)
    BUILD.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    n = len(steps)

    if frames_only:
        durs = [5.0] * n
    else:
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            durs = list(ex.map(lambda p: make_audio(*p), enumerate(steps)))
    total = sum(durs)
    print(f"{n} steps, {fmt(total)} total")
    if total > 15 * 60 + 30:
        print("WARNING: longer than 15 minutes")

    t = 0.0
    chap_start = {}
    for i, st in enumerate(steps):
        chap_start.setdefault(st["ch"], t)
        cap = st["text"] if st["text"] else ""
        (BUILD / f"s{i:03d}.html").write_text(page(st["ch"], st["main"], cap, t / total))
        t += durs[i]

    shoot = BUILD / "shoot.js"
    shoot.write_text("""
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const dir = process.argv[2];
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.html')).sort();
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const f of files) {
    await p.goto('file://' + path.resolve(dir, f));
    await p.screenshot({ path: path.resolve(dir, f.replace('.html', '.png')) });
  }
  await b.close();
})();
""")
    r = subprocess.run(["node", str(shoot), str(BUILD)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("screenshot step failed:\n" + r.stderr[-1500:])
    print("frames rendered")
    if frames_only:
        print(f"frames in {BUILD}")
        return

    (BUILD / "audio.txt").write_text("".join(f"file 'a{i:03d}.wav'\n" for i in range(n)))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(BUILD / "audio.txt"), "-c", "copy", str(BUILD / "full.wav")])
    lines = []
    for i in range(n):
        lines.append(f"file 's{i:03d}.png'\nduration {durs[i]:.3f}\n")
    lines.append(f"file 's{n - 1:03d}.png'\n")
    (BUILD / "images.txt").write_text("".join(lines))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(BUILD / "images.txt"),
         "-vf", "fps=10,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
         "-tune", "stillimage", str(BUILD / "video.mp4")])
    out = OUT / "viva.mp4"
    run(["ffmpeg", "-y", "-i", str(BUILD / "video.mp4"), "-i", str(BUILD / "full.wav"),
         "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-shortest", "-movflags", "+faststart", str(out)])

    # chapter timestamps and readable script
    md = ["# Narration script and chapter times\n"]
    md.append("Spoken with a local offline voice; re-record in your own voice if you prefer.\n")
    cur = -1
    t = 0.0
    for i, st in enumerate(steps):
        if st["ch"] != cur:
            cur = st["ch"]
            md.append(f"\n## {fmt(chap_start[cur])}  {CHAPTERS[cur]}\n")
        if st["text"]:
            md.append(f"- {st['text']}")
        t += durs[i]
    (ROOT / "video" / "narration.md").write_text("\n".join(md) + "\n")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB), {fmt(total)}")
    print("chapters:", {CHAPTERS[k]: fmt(v) for k, v in chap_start.items()})


if __name__ == "__main__":
    main()
