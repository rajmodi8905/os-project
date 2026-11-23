/* Project-specific interactive widgets for the xv6 course (kept apart from main.js).
   Each widget attaches to ids in the lessons and does nothing if its ids are absent. */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function hex(n, w) { var s = (n >>> 0).toString(16).toUpperCase(); while (s.length < w) s = '0' + s; return '0x' + s; }
  function bin(n, w) { var s = (n >>> 0).toString(2); while (s.length < w) s = '0' + s; return s; }
  function parseNum(s) {
    s = String(s).trim(); var neg = false, v;
    if (s.charAt(0) === '-') { neg = true; s = s.slice(1).trim(); }
    if (/^0x[0-9a-f]+$/i.test(s)) v = parseInt(s.slice(2), 16);
    else if (/^\d+$/.test(s)) v = parseInt(s, 10);
    else return NaN;
    return neg ? -v : v;
  }
  var KEY = 'xv6course:v2', state = { ex: {}, cards: {}, pre: {} };
  try { var raw = localStorage.getItem(KEY); if (raw) { var o = JSON.parse(raw); for (var k in o) state[k] = o[k]; } } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }

  /* ---------- module 3: address splitter ---------- */
  (function () {
    var inp = $('#addr-in'), out = $('#addr-out'); if (!inp) return;
    function go() {
      var v = parseNum(inp.value);
      if (isNaN(v) || v < 0 || v > 0xFFFFFFFF) { out.innerHTML = '<div class="x-verdict bad">Enter a hex address like 0x00404010 (up to 32 bits).</div>'; return; }
      var a = v >>> 0, b = bin(a, 32), pdx = (a >>> 22) & 0x3ff, ptx = (a >>> 12) & 0x3ff, off = a & 0xfff;
      out.innerHTML = '<div class="x-segs"><div class="x-seg a"><div class="bin">' + b.slice(0, 10) + '</div><div class="nm">PDX (floor)</div><div class="v">' + pdx + '</div></div>' +
        '<div class="x-seg b"><div class="bin">' + b.slice(10, 20) + '</div><div class="nm">PTX (room)</div><div class="v">' + ptx + '</div></div>' +
        '<div class="x-seg c"><div class="bin">' + b.slice(20) + '</div><div class="nm">offset (spot)</div><div class="v">' + hex(off, 3) + '</div></div></div>' +
        '<dl class="x-kv"><dt>page number</dt><dd>' + hex(a >>> 12, 5) + ' (' + (a >>> 12) + ')  = address / 4096</dd><dt>page starts at</dt><dd>' + hex(a & ~0xfff, 8) + '  (PGROUNDDOWN)</dd>' +
        '<dt>page-aligned?</dt><dd>' + (off === 0 ? '<span class="x-pill ok">yes</span>' : '<span class="x-pill warn">no: mprotect would return -1</span>') + '</dd>' +
        '<dt>region</dt><dd>' + (a >= 0x80000000 ? '<span class="x-pill bad">kernel address: rejected by our helper</span>' : '<span class="x-pill info">user address</span>') + '</dd></dl>';
    }
    inp.addEventListener('input', go);
    $$('button[data-a]', $('#addr-sim')).forEach(function (b) { b.addEventListener('click', function () { inp.value = b.getAttribute('data-a'); go(); }); });
    go();
  })();

  /* ---------- module 3: PTE lab ---------- */
  (function () {
    var P = $('#pte-p'), W = $('#pte-w'), U = $('#pte-u'), WP = $('#pte-wp'), op = $('#pte-op'); if (!P) return;
    function pte() { return ((0x123 << 12) | (U.checked ? 4 : 0) | (W.checked ? 2 : 0) | (P.checked ? 1 : 0)) >>> 0; }
    function pill(ok, msg) { return '<span class="x-pill ' + (ok === 'warn' ? 'warn' : ok ? 'ok' : 'bad') + '">' + msg + '</span>'; }
    function draw() {
      var v = pte(), h = '';
      for (var i = 31; i >= 0; i--) {
        var on = (v >>> i) & 1;
        if (i >= 12) h += '<span class="addr">' + on + '</span>';
        else h += '<span class="' + (on ? 'on' : '') + (i === 1 ? ' w' : '') + '" title="bit ' + i + '">' + on + '</span>';
      }
      $('#pte-bits').innerHTML = h; $('#pte-hex').textContent = hex(v, 8);
      var p = P.checked, w = W.checked, u = U.checked, wp = WP.checked;
      function res(rid, eid, ok, msg, err) { $(rid).innerHTML = pill(ok, msg); $(eid).textContent = err; }
      if (!p) res('#r-ur', '#e-ur', false, 'page fault', 'trap 14 err 4 (not present, read, user)');
      else if (!u) res('#r-ur', '#e-ur', false, 'page fault', 'trap 14 err 5 (present, user mode, supervisor-only page)');
      else res('#r-ur', '#e-ur', true, 'reads the value', 'nothing: no fault');
      if (!p) res('#r-uw', '#e-uw', false, 'page fault', 'trap 14 err 6 (not present, write, user)');
      else if (!u || !w) res('#r-uw', '#e-uw', false, 'page fault: process killed', 'trap 14 err 7 (present + write + user)');
      else res('#r-uw', '#e-uw', true, 'write succeeds', 'nothing: no fault');
      if (!p) res('#r-kw', '#e-kw', false, 'kernel fault: panic', 'trap 14 in kernel mode');
      else if (!w && wp) res('#r-kw', '#e-kw', false, 'kernel fault: panic', 'trap 14 in kernel mode (the Module 6 crash)');
      else if (!w && !wp) res('#r-kw', '#e-kw', 'warn', 'write goes through', 'WP is off, so read-only is ignored in kernel mode');
      else res('#r-kw', '#e-kw', true, 'write succeeds', 'nothing: no fault');
    }
    [P, W, U, WP].forEach(function (c) { c.addEventListener('change', function () { op.textContent = 'flag changed by hand'; draw(); }); });
    $('#pte-mp').addEventListener('click', function () { W.checked = false; op.textContent = '*pte &= ~PTE_W  →  ' + hex(pte(), 8); draw(); });
    $('#pte-mu').addEventListener('click', function () { W.checked = true; op.textContent = '*pte |= PTE_W  →  ' + hex(pte(), 8); draw(); });
    draw();
  })();

  /* ---------- module 3: error decoder ---------- */
  (function () {
    var p = $('#err-p'), w = $('#err-w'), u = $('#err-u'), eo = $('#err-out'); if (!p) return;
    function ed() {
      var e = (p.checked ? 1 : 0) | (w.checked ? 2 : 0) | (u.checked ? 4 : 0), t = [];
      t.push(u.checked ? 'a user-mode' : 'a kernel-mode'); t.push(w.checked ? 'write' : 'read');
      t.push(p.checked ? 'to a present page that refused it (a protection violation)' : 'to a page that is not present');
      var cls = '', extra = '';
      if (e === 7) { cls = 'ok'; extra = ' This is our protection firing.'; } else if (!u.checked) { cls = 'bad'; extra = ' A fault in kernel mode makes xv6 call panic.'; }
      eo.className = 'x-verdict ' + cls; eo.innerHTML = '<span class="x-pill info">err ' + e + '</span><span>trap 14 err ' + e + ': ' + t.join(' ') + '.' + extra + '</span>';
    }
    [p, w, u].forEach(function (c) { c.addEventListener('change', ed); }); ed();
  })();

  /* ---------- module 4: TLB stepper ---------- */
  (function () {
    var fl = $('#tlb-flush'), flow = $('#tlb-flow'), say = $('#tlb-say'); if (!fl) return;
    var step = 0;
    function draw() {
      var flush = fl.checked, cached = step >= 1 && !(step >= 3 && flush), pw = step < 2, msg, cls = '';
      var cpu = '<div class="x-box on"><h5>CPU</h5><small>' + (step === 1 ? 'writes page 0x4000' : step === 4 ? 'writes page 0x4000 again' : 'idle') + '</small></div>';
      var tlb = '<div class="x-box ' + (cached ? (step >= 2 ? 'warn' : 'good') : 'dim') + '"><h5>Sticky note (TLB)</h5><small>' + (cached ? '0x4000 → writable' : 'empty') + (cached && step >= 2 ? '  (STALE)' : '') + '</small></div>';
      var pt = '<div class="x-box ' + (pw ? 'good' : 'bad') + '"><h5>Real record (page table)</h5><small>PTE_W = ' + (pw ? 1 : 0) + '</small></div>';
      flow.innerHTML = cpu + '<div class="x-ar">→</div>' + tlb + '<div class="x-ar">→</div>' + pt;
      var m = ['Start: the page is writable and the TLB is empty.', 'The process writes the page. The CPU jots down 0x4000 → writable on its sticky note.',
        'mprotect clears PTE_W in the real record. The sticky note still says writable: it is now stale.',
        flush ? 'setuvmwrite reloads CR3, which throws the sticky note away.' : 'No reload: the stale note stays.', null];
      if (step < 4) msg = m[step];
      else if (flush) { msg = 'The CPU finds no note, reads the real record, sees PTE_W = 0 and raises trap 14 err 7. Protected.'; cls = 'ok'; }
      else { msg = 'The note says "writable", so the write goes through. The page is not protected. This is the bug our test catches.'; cls = 'bad'; }
      say.className = 'x-verdict ' + cls; say.textContent = msg; $('#tlb-next').disabled = step >= 4;
    }
    $('#tlb-next').addEventListener('click', function () { if (step < 4) { step++; draw(); } });
    $('#tlb-reset').addEventListener('click', function () { step = 0; draw(); });
    fl.addEventListener('change', function () { if (step >= 3) step = 3; draw(); });
    draw();
  })();

  /* ---------- module 4: overflow calculator and two-pass simulator ---------- */
  (function () {
    var va = $('#o-va'), np = $('#o-np'), sz = $('#o-sz'), out = $('#o-out'); if (!va) return;
    function go() {
      var a = parseNum(va.value), n = parseNum(np.value), s = parseNum(sz.value);
      if ([a, n, s].some(isNaN)) { out.innerHTML = '<div class="x-verdict bad">Use hex (0x1000), decimal, or a negative number.</div>'; return; }
      a = a >>> 0; s = s >>> 0; var ni = n | 0, nu = ni >>> 0;
      var prod = Math.imul(ni, 4096) >>> 0, end = (a + prod) >>> 0, naive = end <= s, ours, why;
      if (a % 4096 !== 0) { ours = false; why = 'start is not page-aligned'; }
      else if (ni <= 0) { ours = false; why = 'count is zero or negative'; }
      else if (a >= s) { ours = false; why = 'start is outside the process'; }
      else if (nu > Math.floor((s - a) / 4096)) { ours = false; why = 'count ' + nu + ' is more than the ' + Math.floor((s - a) / 4096) + ' pages that fit'; }
      else { ours = true; why = 'count fits: ' + nu + ' ≤ ' + Math.floor((s - a) / 4096); }
      var wrong = naive && !ours;
      out.innerHTML = '<dl class="x-kv"><dt>npages × 4096</dt><dd>' + hex(prod, 8) + (ni > 0 && prod / 4096 !== ni ? '  <span class="x-pill bad">wrapped past 2^32</span>' : '') + '</dd>' +
        '<dt>end = va + product</dt><dd>' + hex(end, 8) + '</dd><dt>naive: end ≤ sz ?</dt><dd>' + (naive ? '<span class="x-pill ' + (wrong ? 'bad' : 'ok') + '">accepts' + (wrong ? ' (WRONG)' : '') + '</span>' : '<span class="x-pill ok">rejects</span>') + '</dd>' +
        '<dt>ours: compare counts</dt><dd><span class="x-pill ok">' + (ours ? 'accepts' : 'rejects') + '</span> — ' + esc(why) + '</dd></dl>' +
        (wrong ? '<div class="x-verdict bad">The naive check accepts a request far larger than the process. Comparing counts rejects it.</div>' : '');
    }
    [va, np, sz].forEach(function (i) { i.addEventListener('input', go); });
    $$('button[data-p]', $('#ovf-sim')).forEach(function (b) { b.addEventListener('click', function () { var p = b.getAttribute('data-p').split('|'); va.value = p[0]; np.value = p[1]; sz.value = p[2]; go(); }); });
    go();
  })();
  (function () {
    var box = $('#two-pages'), res = $('#two-out'); if (!box) return;
    var pages = [], bad = 4;
    function draw() {
      box.innerHTML = '';
      for (var i = 0; i < 5; i++) (function (i) {
        var b = document.createElement('button'); b.type = 'button'; b.className = 'x-pg' + (pages[i] ? ' ro' : '') + (i === bad ? ' inv' : '');
        b.innerHTML = 'page ' + i + '<b>' + (i === bad ? 'invalid' : pages[i] ? 'read-only' : 'writable') + '</b>';
        b.addEventListener('click', function () { bad = (bad === i) ? -1 : i; reset(); }); box.appendChild(b);
      })(i);
    }
    function reset() { pages = [0, 0, 0, 0, 0]; res.className = 'x-verdict'; res.textContent = 'Choose a mode and run it.'; draw(); }
    $('#two-reset').addEventListener('click', reset);
    $('#two-run').addEventListener('click', function () {
      var mode = $('input[name=two-mode]:checked').value;
      if (mode === 'one') {
        var changed = 0; for (var i = 0; i < 5; i++) { if (i === bad) break; pages[i] = 1; changed++; }
        draw();
        if (bad >= 0) { res.className = 'x-verdict bad'; res.innerHTML = '<span class="x-pill bad">returned -1</span> <span>but pages 0–' + (changed - 1) + ' are now read-only. The call failed and still changed things.</span>'; }
        else { res.className = 'x-verdict ok'; res.textContent = 'All five pages protected, returned 0.'; }
      } else if (bad >= 0) { draw(); res.className = 'x-verdict ok'; res.innerHTML = '<span class="x-pill ok">returned -1</span> <span>Pass one found the bad page before changing anything. Nothing was touched.</span>'; }
      else { pages = [1, 1, 1, 1, 1]; draw(); res.className = 'x-verdict ok'; res.textContent = 'Pass one accepted all five, pass two protected them, returned 0.'; }
    });
    reset();
  })();

  /* ---------- module 5: syscall simulator ---------- */
  (function () {
    var call = $('#kb-call'), pg = $('#kb-page'), fix = $('#kb-fix'), out = $('#kb-out'); if (!call) return;
    function go() {
      var c = call.value, ro = pg.value === 'ro', f = fix.checked, writes = c !== 'write', cls, html;
      if (!writes) { cls = 'ok'; html = '<span class="x-pill ok">works</span><span>The kernel only reads the buffer, so a protected page is a valid source. This is why <code>sys_write</code> keeps plain <code>argptr</code>.</span>'; }
      else if (!ro) { cls = 'ok'; html = '<span class="x-pill ok">works</span><span>The buffer is writable, so the kernel writes into it normally.</span>'; }
      else if (f) { cls = 'ok'; html = '<span class="x-pill ok">returns -1</span><span><code>argptrw</code> calls <code>checkuvmwrite</code>, sees the read-only page and refuses before any write. The page is untouched and the kernel keeps running.</span>'; }
      else { cls = 'bad'; html = '<span class="x-pill bad">KERNEL PANIC</span><span><code>unexpected trap 14 from cpu 0 eip 80103743 (cr2=0x5000)</code> then <code>panic: trap</code>. The kernel wrote into a read-only page with CR0.WP set: the crash we reproduced before the fix.</span>'; }
      out.className = 'x-verdict ' + cls; out.innerHTML = html;
    }
    [call, pg, fix].forEach(function (e) { e.addEventListener('change', go); }); go();
  })();

  /* ---------- module 6: mutation lab ---------- */
  (function () {
    var tabs = $('#mut-tabs'), out = $('#mut-out'); if (!tabs) return;
    var MUT = [
      { n: 'Delete the lcr3 line', code: 'vm.c line 351:  lcr3(V2P(pgdir));   // deleted', status: 'ok', st: 'Verified by running it',
        res: '$ ./scripts/xv6 smoke\nPASS: xv6 boot, shell command and upstream forktest\nFAIL: vmtest reported a failure; inspect artifacts/*.log\n\n$ grep FAIL artifacts/smoke.log\nvmtest: FAIL mprotect takes effect immediately (TLB refreshed)\nvmtest: 1 FAILED',
        why: 'Only the immediate-effect test notices. Every other protected write happens in a freshly forked child, and a context switch reloads CR3 for it. We added this test because the first version of the suite missed the bug.' },
      { n: 'Merge the two passes', code: 'Change the PTE inside the pass-1 loop and drop pass 2', status: 'ok', st: 'Verified by running it',
        res: 'FAIL: vmtest reported a failure; inspect artifacts/*.log\n(the rejected guard-page range left the page before it read-only, and the test program was then killed)',
        why: 'The atomic-rejection tests catch it. A range that ends in the guard page must change nothing, and here it changed the earlier pages.' },
      { n: 'Use argptr in sys_read', code: 'sysfile.c line 76:  argptr(1, &p, n)   // instead of argptrw', status: 'ok', st: 'Verified: this was the original bug',
        res: 'unexpected trap 14 from cpu 0 eip 80103743 (cr2=0x5000)\nlapicid 0: panic: trap',
        why: 'The kernel-buffer test reproduces the crash. Read into a protected page makes the kernel itself fault.' },
      { n: 'Drop the PTE_U check', code: 'vm.c line 337:  remove  || (*pte & PTE_U) == 0', status: 'warn', st: 'Predicted, not run',
        res: 'Expected: the "stack guard page rejected" checks in the invalid group fail,\nbecause the guard page is no longer refused.',
        why: 'The guard page has PTE_U cleared by exec. Without the user-bit check, our helper would accept it. Try it yourself and confirm.' }];
    MUT.forEach(function (m, i) { var b = document.createElement('button'); b.type = 'button'; b.textContent = m.n; b.addEventListener('click', function () { show(i); }); tabs.appendChild(b); });
    function show(i) {
      var m = MUT[i]; $$('button', tabs).forEach(function (b, j) { b.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
      out.innerHTML = '<p><b>Change:</b> <code>' + esc(m.code) + '</code></p><p><span class="x-pill ' + m.status + '">' + m.st + '</span></p><div class="x-term"><pre>' + esc(m.res) + '</pre></div><p>' + esc(m.why) + '</p>';
    }
    show(0);
  })();

  /* ---------- module 6: terminal replay ---------- */
  (function () {
    var term = $('#demo-term'), say = $('#demo-say'); if (!term) return;
    var G = window.__GUEST || null;
    var src = $('#guest-data'); if (src) { try { G = JSON.parse(src.textContent); } catch (e) {} }
    if (!G) return;
    function idx(s, from) { for (var i = from || 0; i < G.length; i++) if (G[i].indexOf(s) >= 0) return i; return G.length - 1; }
    var end = idx('vmdemo done'), i1 = idx('[1]'), i1e = idx('stored and read back'), i2 = idx('protected read still works'),
      f = idx('STOPPED by page fault', i2), pa = idx('parent still alive'), i3 = idx('inherited child write'),
      i4 = idx('[4]'), i4e = idx('after rejected munprotect'), i5 = idx('[5]'), i5e = idx('child write of 507');
    var S = [
      { upto: i1e + 1, hl: [i1, i1e], say: 'Scene 1: a writable control. Three pages starting at 0x4000 hold the values 7, 8 and 9.' },
      { upto: i2 + 1, hl: [i2 - 2, i2], say: 'Scene 2: mprotect returned 0 and the page is still readable. Say: only the write bit changed.' },
      { upto: pa + 1, hl: [f - 1, f], say: 'A child writes and dies. Point at trap 14 err 7 and the word STOPPED. Then say: the parent is still alive and its value did not change.' },
      { upto: i3 + 1, hl: [i3 - 1, i3], say: 'Scene 3: a brand-new child inherits the read-only page, so it faults too. copyuvm copies the flags.' },
      { upto: i4e + 1, hl: [i4 + 1, i4 + 2, i4 + 3, i4e - 1, i4e], say: 'Scene 4: bad requests return -1, and the rejected munprotect changed nothing. The next child still faults.' },
      { upto: end + 1, hl: [i5, i5e - 1, i5e], say: 'Scene 5: after munprotect, the parent and a child can both write. The shell is still running.' }];
    var n = 0;
    function draw() {
      var s = n > 0 ? S[n - 1] : null, up = s ? s.upto : 2, h = '';
      for (var i = 0; i < up && i < G.length; i++) {
        var l = G[i], c = '';
        if (l.indexOf('trap 14') >= 0) c = 'x-fault'; else if (l.indexOf('SUCCEEDED') >= 0) c = 'x-ok'; else if (l.indexOf('STOPPED') >= 0) c = 'x-stop'; else if (l.indexOf('vmdemo 7 3') === 0) c = 'x-cmd';
        h += '<span class="' + c + (s && s.hl.indexOf(i) >= 0 ? ' x-hl' : '') + '">' + (i === 0 ? '$ ' : '') + esc(l || ' ') + '</span>';
      }
      term.innerHTML = h; say.className = 'x-verdict' + (n === S.length ? ' ok' : ''); say.textContent = s ? s.say : 'Press Next scene to run the demo one step at a time.';
      $('#demo-next').disabled = n >= S.length;
    }
    $('#demo-next').addEventListener('click', function () { if (n < S.length) { n++; draw(); } });
    $('#demo-reset').addEventListener('click', function () { n = 0; draw(); });
    draw();
  })();

  /* ---------- module 7: exercises, checklist, flashcards ---------- */
  (function () {
    $$('button[data-done]').forEach(function (b) {
      var id = b.getAttribute('data-done');
      function paint() { b.textContent = state.ex[id] ? 'Done ✓' : 'I did this one'; b.className = 'btn' + (state.ex[id] ? ' x-done' : ''); }
      paint(); b.addEventListener('click', function () { state.ex[id] = !state.ex[id]; save(); paint(); });
    });
    $$('#pre-list input').forEach(function (c, i) { c.checked = !!state.pre[i]; c.addEventListener('change', function () { state.pre[i] = c.checked; save(); }); });
    var fc = $('#fc'), dots = $('#fc-dots'); if (!fc) return;
    var C = [
      ['Why must the address be page-aligned, and the length in pages?', 'Permissions apply to whole pages, so an address in the middle of a page has no meaning.'],
      ['Why two passes over the pages?', 'A failed call must change nothing. Pass one validates every page, so pass two cannot fail halfway.'],
      ['What happens without the CR3 reload?', 'The TLB may keep a writable translation, so a write can still succeed. Only the immediate-effect test notices.'],
      ['Why does only the child die, and what does trap 14 err 7 mean?', 'The fault happens in the child’s user mode, so only it is killed. Page fault: present + write + user.'],
      ['Why did read() into a protected buffer panic, and why is write() still allowed?', 'CR0.WP makes kernel writes obey read-only pages, and a kernel-mode fault panics. We check output buffers first. write() only reads.'],
      ['Why does fork keep the protection?', 'copyuvm copies the flag bits into the child’s own new page. The two pages are independent copies.'],
      ['Can a process protect its own code at address 0?', 'Yes: code is a user page. The project does not change null-pointer behaviour.'],
      ['What happens to protected pages after exec, or after sbrk shrinks the heap?', 'Exec builds a fresh address space. Shrinking frees pages normally. New heap pages are writable.'],
      ['Is check-then-write safe with several CPUs and threads?', 'No: you would need locking or fault handling. Here there is one CPU and no threads, so nothing changes between check and write.'],
      ['Why do the tests use a pipe instead of wait()?', 'xv6’s wait() returns no exit status, so a marker byte through a pipe shows whether the write succeeded.'],
      ['What would error code 6 mean instead of 7?', 'A user write to a page that is not present.'],
      ['Walk me from mprotect in C to the PTE change, naming every file.', 'user.h, usys.S stub (EAX = 22), syscall.h and the table in syscall.c, sysproc.c changeprotection, vm.c setuvmwrite: validate, clear PTE_W, lcr3. The result returns in EAX.']];
    var order = C.map(function (_, i) { return i; }), pos = 0, shown = false;
    function known() { return Object.keys(state.cards).filter(function (k) { return state.cards[k]; }).length; }
    function draw() {
      var i = order[pos];
      fc.innerHTML = '<div class="n">Card ' + (pos + 1) + ' of ' + C.length + '</div><p class="q">' + esc(C[i][0]) + '</p>' +
        (shown ? '<div class="a">' + esc(C[i][1]) + '</div><div class="bar"><button class="btn btn-primary" type="button" id="fc-k">Knew it</button><button class="btn" type="button" id="fc-r">Review again</button></div>' :
          '<div class="bar"><button class="btn btn-primary" type="button" id="fc-s">Show answer</button><button class="btn" type="button" id="fc-skip">Skip</button></div>');
      dots.innerHTML = order.map(function (c, p) { return '<i class="' + (state.cards[c] ? 'got' : '') + (p === pos ? ' cur' : '') + '"></i>'; }).join('');
      $('#fc-stat').textContent = known() + ' of ' + C.length + ' marked "knew it"';
      var s = $('#fc-s'); if (s) s.addEventListener('click', function () { shown = true; draw(); });
      var sk = $('#fc-skip'); if (sk) sk.addEventListener('click', next);
      var k = $('#fc-k'); if (k) k.addEventListener('click', function () { state.cards[i] = true; save(); next(); });
      var r = $('#fc-r'); if (r) r.addEventListener('click', function () { state.cards[i] = false; save(); next(); });
    }
    function next() { shown = false; pos = (pos + 1) % order.length; draw(); }
    $('#fc-shuffle').addEventListener('click', function () { for (var i = order.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = order[i]; order[i] = order[j]; order[j] = t; } pos = 0; shown = false; draw(); });
    draw();
  })();
})();
