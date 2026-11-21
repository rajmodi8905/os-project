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

LONG = "--long" in sys.argv
CHAPTERS = ["Problem", "Background", "Solution", "Tests & demo", "Modify it", "Viva Q&A", "Live proof"]
ORDER = [0, 1, 2, 3, 6, 4, 5] if LONG else [0, 1, 2, 3, 4, 5]   # chip order on screen
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


def S(ch, main, text=None, silence=None, say=None, long=False):
    if long and not LONG:
        return
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
.cap.small{font-size:29px;line-height:1.3;padding:0 100px}
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
    pos = ORDER.index(ch)
    chips = "".join(
        f'<div class="chip {"on" if k == pos else "done" if k < pos else ""}">{html.escape(CHAPTERS[i])}</div>'
        for k, i in enumerate(ORDER))
    cap = html.escape(caption) if caption else ""
    capcls = "cap small" if len(caption or "") > 170 else "cap"
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body>'
            f'<div class="top"><div class="brand">Read-only page protection in <span>xv6</span></div>'
            f'<div class="chips">{chips}</div></div>'
            f'<div class="prog"><i style="width:{frac * 100:.2f}%"></i></div>'
            f'<div class="main">{main}</div><div class="{capcls}">{cap}</div></body>')


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
    show = lines[max(0, upto - 21):upto]
    base = max(0, upto - 21)
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
agenda = [CHAPTERS[i] for i in ORDER]


def title_card(lit):
    ag = "".join(box(a, "on" if i < lit else "dim") for i, a in enumerate(agenda))
    return ('<div class="title"><h1>Read-only page protection<br>in x86 xv6</h1>'
            '<p>Viva walkthrough: problem, solution, real code, tests, and how to change it</p>'
            f'<div class="agenda">{ag}</div></div>')


S(0, title_card(0), "This video prepares you for the viva on read-only page protection in xv6.")
S(0, title_card(3), "We go from the problem, through the background and our solution, to the code block by block, and then the tests and a live demo.")
S(0, title_card(6), "At the end you get three example changes an examiner might ask for, and rapid-fire viva questions.")
S(0, title_card(7), "This longer version also walks through every file we wrote, all the tests, the demo program and the runner, and ends with a step by step guide to proving it live in front of the examiner.", long=True)
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

# ---- long only: the rest of the code we wrote (chapter 2)
S(2, code_view("user.h", (14, 28), (26, 27), ours=(26, 27), note="<p>Prototypes so user programs can call the two new system calls.</p>", head="user.h"),
  "Now the rest of the code we wrote, file by file. In user.h, two prototypes let user programs call mprotect and munprotect.", long=True)
S(2, code_view("defs.h", (176, 190), (186, 187), ours=(186, 187), note="<p>Kernel-internal declarations. <code>argptrw</code> is declared at line 154.</p>", head="defs.h"),
  "defs.h declares setuvmwrite and checkuvmwrite, and argptrw, so sysproc.c, syscall.c and sysfile.c can call them.", long=True)
S(2, code_view("Makefile", (168, 187), (184, 185), ours=(184, 185), note="<p>Without these two lines the programs are not built or copied into the guest's disk, and the guest says <code>not found</code>.</p>", head="Makefile"),
  "The Makefile lists vmtest and vmdemo as user programs, so they are compiled and copied into the guest's disk image. Forget this, and the guest says: not found.", long=True)
S(2, code_view("vm.c", (35, 54), (41, 46), note="<p>Returns the address of the PTE for an address. With <code>alloc</code> = 0 it returns 0 instead of building a page table.</p>", head="walkpgdir (existing)"),
  "Two existing pieces you must know. walkpgdir finds the directory entry, then the page table, and returns a pointer to the PTE. With alloc zero it gives up instead of building a page table, which both our helpers rely on.", long=True)
S(2, code_view("exec.c", (62, 69), (68, 68), note="<p>The lower of the two new pages loses <code>PTE_U</code>: the <b>guard page</b>. Our validation rejects it.</p>", head="Guard page (existing)"),
  "And exec allocates two pages and clears the user bit on the lower one. That is the guard page, and our validation rejects any page without the user bit.", long=True)
RW = [
    "Reject: unaligned, count ≤ 0, start ≥ <code>sz</code>",
    "Reject: <code>npages</code> &gt; <code>(sz - va) / PGSIZE</code>",
    "Pass 1: each page present, user (no allocating)",
    "Pass 2: set or clear <b>only</b> <code>PTE_W</code>",
    "<code>lcr3(V2P(pgdir))</code>, then return 0",
]
S(2, bullets("Rewrite setuvmwrite from memory", RW, 5, dim_prev=False),
  "A good test of ownership: close the video and rewrite setuvmwrite from these five steps. Reject bad arguments. Compare counts. Validate every page. Change only the write bit. Then reload CR3.", long=True)


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

TR = [
    "<code>mprotect(p, 2)</code> declared in <code>user.h</code>",
    "<code>usys.S</code> stub: <code>eax = 22</code>, <code>int T_SYSCALL</code>",
    "<code>trap()</code> → <code>syscall()</code> looks up slot 22 in <code>syscall.c</code>",
    "<code>sys_mprotect</code> → <code>changeprotection(0)</code> in <code>sysproc.c</code>",
    "<code>setuvmwrite</code> in <code>vm.c</code>: validate, clear <code>PTE_W</code>, <code>lcr3</code>",
    "Result returns in <code>eax</code> to the program",
]
for k in range(1, 7):
    S(2, bullets("One mprotect call, end to end", TR, k),
      ["A very likely question: walk me from mprotect in C to the page table entry, naming every file. In the program, mprotect is declared in user.h.",
       "The stub in usys.S puts twenty-two in EAX and executes int T underscore SYSCALL.",
       "The trap handler calls syscall, which looks up slot twenty-two in the table in syscall.c.",
       "That slot is sys mprotect in sysproc.c, which calls change protection with writable equals zero.",
       "Which calls setuvmwrite in vm.c: validate, clear the write bit, and reload CR3.",
       "The result goes back in EAX, and that is what the program sees."][k - 1], long=True)

# ---- long only: the full vmtest tour (chapter 3)
V = (1, 400)
S(3, code_view("vmtest.c", (1, 20), (8, 19), ours=V, note="<p><code>check</code> prints ok or FAIL and counts failures. <code>faults</code> counts children stopped by a fault.</p>", head="vmtest.c: the helpers"),
  "Now vmtest.c from top to bottom. check prints ok or FAIL and counts failures. The faults counter counts children stopped by a fault, and the runner compares it with the kernel.", long=True)
S(3, code_view("vmtest.c", (22, 40), (24, 33), ours=V, note="<p>Whole fresh pages: the tests never protect the stack or <code>malloc</code>'s own data.</p>", head="allocpages"),
  "allocpages grows the heap with sbrk, rounds up to a page boundary, and returns whole fresh pages, so a test never protects the stack or malloc's own data.", long=True)
S(3, code_view("vmtest.c", (125, 137), (131, 134), ours=V, note="<p>Calling a protection twice must be harmless and give the same state.</p>", head="repeated"),
  "The repeated test calls mprotect twice, then munprotect twice. Doing the same thing again must be harmless.", long=True)
S(3, code_view("vmtest.c", (141, 160), (148, 155), ours=V, note="<p>Pages 1–3 of 5 protected. Every page in the range must fault; pages 0 and 4 must stay writable.</p>", head="multiple"),
  "The multiple test protects the middle three of five pages. Every page in the range must fault, while the page before and the page after stay writable.", long=True)
S(3, code_view("vmtest.c", (163, 182), (169, 171), ours=V, note="<p>A forked child inherits the read-only page, so it faults.</p>", head="forking: inheritance"),
  "The forking test first protects a page. A freshly forked child must fault when it writes, so protection is inherited.", long=True)
S(3, code_view("vmtest.c", (172, 191), (176, 191), ours=V, note="<p>The child unprotects and writes <b>its own copy</b>; the parent's copy must be unchanged and still protected.</p>", head="forking: independence"),
  "Then a child unprotects and writes its own copy, and reports back through a pipe. The parent checks that its copy is unchanged and still protected.", long=True)
S(3, code_view("vmtest.c", (185, 204), (193, 202), ours=V, note="<p>And the reverse: a child protecting <b>its</b> copy must not protect the parent's.</p>", head="forking: the reverse"),
  "And the reverse: a child that protects its copy must not protect the parent's. So the two are independent in both directions.", long=True)
S(3, code_view("vmtest.c", (206, 225), (214, 224), ours=V, note="<p>Every bad request must return <code>-1</code>.</p>", head="invalid arguments"),
  "The invalid test lists every bad request: unaligned, zero, negative, overflowing, wrapping, past the heap, a kernel address, and the guard page. Each must return minus one.", long=True)
S(3, code_view("vmtest.c", (221, 240), (226, 239), ours=V, note="<p>A range that runs into an invalid page must fail <b>and leave earlier pages as they were</b>. This test caught our merged-passes mutation.</p>", head="atomic rejection"),
  "Then the atomicity cases. A range that runs into an invalid page must fail, and the earlier pages must stay exactly as they were. A child write checks it after every rejection.", long=True)
S(3, code_view("vmtest.c", (245, 264), (254, 260), ours=V, note="<p><code>read()</code> into a protected page must return <code>-1</code> and leave the page alone. Before our fix this panicked the kernel.</p>", head="kernel buffers: read"),
  "The kernel buffer tests protect a page and ask read to fill it. Read must return minus one and leave the page alone. Before our fix, this exact test panicked the kernel.", long=True)
S(3, code_view("vmtest.c", (262, 281), (264, 280), ours=V, note="<p>A buffer starting in a writable page and running into a protected one is also rejected. <code>write()</code> from a protected page still works.</p>", head="kernel buffers: spanning, write"),
  "A buffer that starts in a writable page and runs into a protected one is also rejected, and neither page changes. And write from a protected page still works.", long=True)
S(3, code_view("vmtest.c", (284, 303), (287, 291), ours=V, note="<p><code>fstat</code> and <code>pipe</code> destinations are checked the same way.</p>", head="kernel buffers: fstat, pipe"),
  "The fstat and pipe destinations are rejected in the same way when the page is protected.", long=True)
S(3, code_view("vmtest.c", (295, 311), (305, 309), ours=V, note="<p>The printed fault count is what the runner compares with the kernel's <code>trap 14</code> lines.</p>", head="main"),
  "main runs the groups in order, prints how many faults it saw, and prints ALL PASSED only if no check failed. That printed count is what the runner compares with the kernel messages.", long=True)
D = (1, 100)
S(3, code_view("vmdemo.c", (21, 40), (28, 39), ours=D, note="<p>Same idea as the test helper, with friendly output.</p>", head="vmdemo.c: trywrite"),
  "vmdemo is the friendly version of the same idea. trywrite forks a child that writes, and the parent prints whether the write succeeded or was stopped by a page fault.", long=True)
S(3, code_view("vmdemo.c", (42, 61), (48, 56), ours=D, note="<p><code>vmdemo [value] [pages]</code>: the examiner can choose both. 1 to 16 pages.</p>", head="vmdemo.c: arguments"),
  "main reads an optional value and page count, so the examiner can choose them, from one to sixteen pages.", long=True)
S(3, code_view("vmdemo.c", (61, 80), (61, 71), ours=D, note="<p>Scene 1: writable control. Scene 2: protect, read still works, child write is stopped.</p>", head="vmdemo.c: scenes 1 and 2"),
  "Scene one is the writable control. Scene two protects the pages, shows a protected read still works, and a child write must be stopped.", long=True)
S(3, code_view("vmdemo.c", (73, 89), (73, 87), ours=D, note="<p>Scene 3: fork inheritance. Scene 4: bad requests change nothing. Scene 5: restore.</p>", head="vmdemo.c: scenes 3 to 5"),
  "Scenes three to five: fork inheritance, invalid requests that change nothing, and munprotect followed by a successful write.", long=True)


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

# ---- long only: the runner, then the live proof (chapters 3 and 6)
S(3, code_view("scripts/smoke.py", (16, 33), (22, 28), ours=(1, 130), note="<p>Fails on any <code>FAIL</code> line, and requires vmtest's fault count to equal the kernel's <code>trap 14</code> lines.</p>", head="The runner"),
  "The runner, scripts slash smoke dot py, starts vmtest and fails on any FAIL line. It also requires vmtest's fault count to equal the kernel's trap fourteen messages.", long=True)
S(3, code_view("scripts/smoke.py", (89, 104), (90, 104), ours=(1, 130), note="<p>Boot, an echo, <code>forktest</code>, our <code>vmtest</code>, and for <code>check</code> the original <code>usertests</code>.</p>", head="The sequence"),
  "Around that, it checks boot, an echo command, forktest, our vmtest, and for check, the original xv6 user tests.", long=True)
S(3, code_view("scripts/xv6", (51, 66), (57, 65), ours=(1, 80), note="<p><code>build</code>, <code>run</code>, <code>smoke</code>, <code>check</code>, <code>clean</code>: the only commands you need.</p>", head="scripts/xv6"),
  "scripts slash x v 6 is the command you type: build, run, smoke, check, and clean. Check runs the whole sequence including the original tests.", long=True)
S(3, code_view(".github/workflows/baseline.yml", (12, 31), (23, 24), ours=(1, 40), note="<p>GitHub Actions runs <code>check</code> on every push: repeatable evidence.</p>", head="CI"),
  "And GitHub Actions runs the same check on every push, so the evidence is repeatable and not just on your laptop.", long=True)

# ---- long only: chapter 6, show it live in front of the examiner
GLOG = ["$ git log --oneline xv6-baseline..HEAD"] + [l for l in (ROOT / "video/assets/git_log.txt").read_text().split("\n") if l.strip()]
GDIFF = ["$ git diff --stat xv6-baseline -- '*.c' '*.h' '*.S' Makefile"] + [l for l in (ROOT / "video/assets/git_diff_stat.txt").read_text().split("\n") if l.strip()]
LS = (ROOT / "video/assets/live_session.txt").read_text().replace("\r", "").split("\n")
ls_cmd = LS.index("$ ls") if "$ ls" in LS else next(i for i, l in enumerate(LS) if l.startswith("$ ls"))
demo_cmd = next(i for i, l in enumerate(LS) if l.startswith("$ vmdemo"))
BOOT = ["$ ./scripts/xv6 run", "Exit QEMU: Ctrl-A, then X. Guest disks are fs.img and xv6.img."] + LS[:ls_cmd]
LSOUT = LS[ls_cmd:demo_cmd]
DEMO2 = LS[demo_cmd:]
while DEMO2 and DEMO2[-1] == "":
    DEMO2.pop()

PRE = [
    "Charge the laptop; <b>test it on the presentation machine</b>",
    "<code>git pull</code> so you have the latest <code>main</code>",
    "<code>./scripts/xv6 clean</code> then <code>check</code>: three PASS lines",
    "Close every other QEMU window: one guest at a time",
    "Keep a screen recording of a passing run as a backup",
]
S(6, bullets("Before the viva", PRE, 5, dim_prev=False),
  "Now the part most people forget: how to prove it live. The day before, charge the laptop and test it on the presentation machine. Pull the latest code, run clean and then check, and expect three pass lines. Close other QEMU windows, and keep a recording as a backup.", long=True)
S(6, term_view(GLOG, len(GLOG), (1, len(GLOG) - 1), head="Terminal: the project folder", note="<p>Start with the history: each checkpoint is one commit.</p>", noteh="Show the work"),
  "Start by showing the work. git log shows each checkpoint as a commit, from the syscalls to the tests, the demo and the documentation.", long=True)
S(6, term_view(GDIFF, len(GDIFF), (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13), head="Terminal: what changed", note="<p>Only these files differ from original xv6. The kernel part is <code>vm.c</code>, <code>sysproc.c</code>, <code>syscall.c</code>, <code>sysfile.c</code> and a few wiring lines.</p>", noteh="Ours vs xv6"),
  "Then git diff stat against the xv6 baseline. Only these files differ from original xv6. The kernel part is vm.c, sysproc.c, syscall.c, sysfile.c, and a few wiring lines. Everything else is untouched.", long=True)
S(6, term_view(TL, len(TL), (3, 4, 5), head="Terminal: the proof", note="<p>About 40 seconds. While it runs, explain what the three PASS lines mean.</p>", noteh="Run check"),
  "Now run clean and check. It takes about forty seconds. While it runs, explain the three pass lines: the boot test, our vm test suite with ten expected faults, and the original xv6 tests.", long=True)
S(6, term_view(BOOT, len(BOOT), (len(BOOT) - 1,), head="Terminal: start the guest", note="<p><code>./scripts/xv6 run</code> boots xv6 in QEMU. Exit later with <b>Ctrl-A, then X</b>.</p>", noteh="Run it"),
  "Then run the project. The run command boots xv6 in QEMU. When you see the dollar prompt, you are inside the guest. Exit later with control A, then X.", long=True)
LSE = BOOT + LSOUT
S(6, term_view(LSE, len(LSE), tuple(i for i, l in enumerate(LSE) if l.startswith(("vmtest", "vmdemo"))), head="Terminal: inside xv6", note="<p><code>ls</code> shows our two programs next to the original ones.</p>", noteh="Our programs"),
  "Type ls. Our two programs, vmtest and vmdemo, sit next to the original xv6 programs. That is how you know the Makefile change worked.", long=True)
dN = len(DEMO2)
S(6, term_view(DEMO2, dN, (1, 2, 3), head="Terminal: inside xv6", note="<p>Let the examiner choose: <code>vmdemo 1000 4</code> means value 1000, four pages. Real output.</p>", noteh="Examiner's numbers"),
  "Now the demo. Ask the examiner for a value and a page count. Here we use one thousand and four pages. Scene one shows the writable control with their numbers.", long=True)
fi = next(i for i, l in enumerate(DEMO2) if "STOPPED" in l)
S(6, term_view(DEMO2, fi + 3, (fi - 1, fi), head="Terminal: inside xv6", note="<p>Point at <code>trap 14 err 7</code> and the word <b>STOPPED</b>. Then at <i>parent still alive</i>.</p>", noteh="Point here"),
  "Point at two things. The kernel line, trap fourteen error seven, and the word stopped. Then say: the parent is still alive and its value did not change.", long=True)
S(6, term_view(DEMO2, dN, (dN - 4, dN - 3), head="Terminal: inside xv6", note="<p>After <code>munprotect</code> writes work again; the shell is still running.</p>", noteh="Finish"),
  "Finish with the last scene: after munprotect, writes work again, and the shell is still running. Then run vm test and an echo command to show the whole system survived.", long=True)
MUTL = [
    "$ # open vm.c and delete the line  lcr3(V2P(pgdir));",
    "$ ./scripts/xv6 smoke",
    "PASS: xv6 boot, shell command and upstream forktest",
    "FAIL: vmtest reported a failure; inspect artifacts/*.log",
    "$ grep FAIL artifacts/smoke.log",
    "vmtest: FAIL mprotect takes effect immediately (TLB refreshed)",
    "vmtest: 1 FAILED",
    "$ git checkout -- vm.c      # restore the line",
]
S(6, term_view(MUTL, len(MUTL), (3, 5), head="Terminal: break it live", note="<p>Optional but impressive: delete the TLB flush, run the smoke test, see exactly one failure, then restore. This is real output from our earlier run.</p>", noteh="Prove the tests matter"),
  "If you want a stronger proof, break it live. Delete the C R 3 reload line, run the smoke test, and watch the immediate effect test fail. Then restore the file with git checkout. This shows the tests really detect the bug.", long=True)
MODL = [("$ " + l if i == 0 else l) for i, l in enumerate((ROOT / "video/assets/modify_output.txt").read_text().replace("\r", "").split("\n")) if l.strip() and l.strip() != "$"]
S(6, term_view(MODL, 3, (1, 2), head="Terminal: a live change", note="<p>If the examiner asks for a change: edit, <code>./scripts/xv6 build</code>, <code>run</code>, show. Real output: all three examples applied to a scratch copy.</p>", noteh="Live change"),
  "If the examiner asks for a change, make it, rebuild, run, and show it. This is real output with all three example changes applied to a scratch copy. getprot says one before. Then mprotect with five thousand bytes returns zero.", long=True)
S(6, term_view(MODL, 5, (3, 4), head="Terminal: a live change", note="<p>5000 bytes rounds up to <b>two</b> pages. A kernel address gives <code>-1</code>.</p>", noteh="Bytes, rounded up"),
  "Both pages now read as protected, because five thousand bytes rounds up to two pages. A kernel address gives minus one.", long=True)
S(6, term_view(MODL, 7, (5, 6), head="Terminal: a live change", note="<p><code>munprotect(p, 1)</code> restores only the first page.</p>", noteh="Restore"),
  "Unprotecting one byte restores only the first page.", long=True)
S(6, term_view(MODL, len(MODL), (len(MODL) - 4, len(MODL) - 3), head="Terminal: a live change", note="<p>Our clearer message appears before the usual trap line; the parent keeps running.</p>", noteh="Clearer message"),
  "And a write to a read-only page now prints our clearer message before the usual trap line, while the parent keeps running.", long=True)
CHK2 = [
    "Edit the <b>one</b> function that controls it",
    "<code>./scripts/xv6 build</code> then <code>run</code>",
    "Show the result, then explain <b>why</b> it works",
    "Restore with <code>git checkout -- .</code>",
    "Never edit anything you cannot explain",
]
S(6, bullets("Live change checklist", CHK2, 5, dim_prev=False),
  "For any live change: edit the one function that controls it, rebuild, run, show the result, and explain why it works. Restore with git checkout. Never edit something you cannot explain.", long=True)
TRB = [
    "Guest hangs or <code>check</code> times out → close other QEMU, then <code>clean</code>",
    "<code>vmdemo: not found</code> → <code>./scripts/xv6 clean</code> and run again",
    "Mac is slow → QEMU emulates x86; be patient",
    "Stuck in QEMU → <b>Ctrl-A</b>, then <b>X</b>",
    "Total failure → play the backup recording",
]
S(6, bullets("If something goes wrong", TRB, 5, dim_prev=False),
  "If something goes wrong: a hang means another QEMU is running, so close it and clean. Not found means an old disk image, so clean and run again. A slow Mac is normal. Control A then X leaves QEMU. And if all fails, play your backup recording.", long=True)
OPEN = [
    "I added two system calls, <code>mprotect</code> and <code>munprotect</code>",
    "They clear or set <b>one bit</b>, <code>PTE_W</code>, on a range of pages",
    "Hardware enforces it; I validate first, change second, then flush the TLB",
    "I also made the kernel's own writes respect it",
    "Let me show it, then I can walk through any block",
]
S(6, bullets("Your opening, 30 seconds", OPEN, 5, dim_prev=False),
  "Finally, your opening. Say: I added two system calls that clear or set one bit on a range of pages. The hardware enforces it. I validate first, change second, then flush the TLB, and I made the kernel's own writes respect it. Let me show it, and then I can walk through any block.", long=True)


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
E4 = "video/examples/limits_solution.c"
LIM = [("$ " + l if i == 0 else l) for i, l in enumerate((ROOT / "video/assets/limits_output.txt").read_text().replace("\r", "").split("\n")) if l.strip() and l.strip() != "$"]
S(4, code_view(E4, (5, 14), (9, 11), ours=(1, 14), note="<p>Example 4: refuse page 0 and cap each call at 16 pages. One condition in the <b>first check</b> of the shared helper.</p>", head="Refuse page 0, cap the length"),
  "Example four: refuse page zero and allow at most sixteen pages per call. It is one condition in the first check of the shared helper.", long=True)
S(4, code_view(E4, (5, 14), (13, 14), ours=(1, 14), note="<p>Because both calls share the helper, both rules apply to <code>mprotect</code> <b>and</b> <code>munprotect</code>.</p>", head="Why one place is enough"),
  "Because mprotect and munprotect share the helper, both rules apply to both calls. Only a range that starts at zero can include page zero.", long=True)
S(4, term_view(LIM, len(LIM), (1, 3, 5), head="Terminal: tested in the guest", note="<p>Real output from a scratch copy with the change applied. 16 pages work; 17 and page 0 return <code>-1</code>.</p>", noteh="It works"),
  "We tested it in a scratch copy. Page zero is refused, sixteen pages work, seventeen returns minus one, and munprotect obeys the same cap.", long=True)
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


if LONG:
    QA += [
        ("Can a process protect its own code at address 0?",
         "Yes, code is a user page. Our project does not change null-pointer behaviour."),
        ("What happens to protected pages after exec, or after sbrk shrinks the heap?",
         "Exec builds a fresh address space. Shrinking frees the pages normally. New heap pages are writable."),
        ("Is check-then-write safe with several CPUs and threads?",
         "No: you would need locking or fault handling. Here there is one CPU and no threads, so nothing changes between the check and the write."),
        ("Why do the tests use a pipe instead of wait?",
         "xv6's wait returns no exit status, so a marker byte through a pipe shows whether the write succeeded."),
        ("What would error code 6 mean instead of 7?",
         "A user write to a page that is not present."),
        ("What do mprotect and munprotect return?",
         "0 on success and -1 on an invalid request, and an invalid request changes nothing."),
    ]
    SPOKEN_A += [
        "Yes, code is a user page. Our project does not change null-pointer behaviour.",
        "Exec builds a fresh address space. Shrinking frees the pages normally. New heap pages are writable.",
        "No. You would need locking or fault handling. Here there is one CPU and no threads, so nothing changes between the check and the write.",
        "xv6's wait returns no exit status, so a marker byte through a pipe shows whether the write succeeded.",
        "A user write to a page that is not present.",
        "Zero on success and minus one on an invalid request, and an invalid request changes nothing.",
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
    cap = 30 * 60 if LONG else 15 * 60 + 30
    if total > cap:
        print(f"WARNING: longer than the cap ({fmt(cap)})")

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
    out = OUT / ("viva_full.mp4" if LONG else "viva.mp4")
    run(["ffmpeg", "-y", "-i", str(BUILD / "video.mp4"), "-i", str(BUILD / "full.wav"),
         "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-ac", "1",
         "-shortest", "-movflags", "+faststart", str(out)])

    # chapter timestamps and readable script
    md = ["# Narration script and chapter times" + (" (full 30-minute version)" if LONG else "") + "\n"]
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
    (ROOT / "video" / ("narration_full.md" if LONG else "narration.md")).write_text("\n".join(md) + "\n")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB), {fmt(total)}")
    print("chapters:", {CHAPTERS[k]: fmt(chap_start[k]) for k in ORDER if k in chap_start})


if __name__ == "__main__":
    main()
