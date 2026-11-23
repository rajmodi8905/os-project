const { chromium } = require('playwright'); const out = process.argv[2];
(async () => { const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage(); await p.goto('file:///workspace/os-project/docs/course/index.html');
  await p.addStyleTag({ content: 'html{scroll-behavior:auto!important} .animate-in{opacity:1!important;transform:none!important}' });
  async function at(sel, name, off) { await p.evaluate(([s, o]) => { const e = document.querySelector(s); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - (o || 80)); }, [sel, off]); await p.waitForTimeout(300); await p.screenshot({ path: out + '/c3_' + name + '.png' }); }
  await p.screenshot({ path: out + '/c3_top.png' });
  await at('#module-1 .screen:nth-of-type(3)', 'assign'); await at('.layer-demo', 'layer', 150); await at('#dnd-brief', 'dnd', 120); await at('#module-1 .screen:nth-of-type(7)', 'timeline', 70);
  await b.close(); })();
