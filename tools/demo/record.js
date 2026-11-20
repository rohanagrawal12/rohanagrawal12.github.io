// Records the Bulletin demo from the live index.html in full HD (1280x720 page at a real 1.5x device scale = 1920x1080).
// Frames are Chrome screenshots with their real timestamps; compose.py builds the video, cut.py makes the short versions.
// Usage (from the repo folder):  node tools/demo/record.js /path/to/new-frames-folder
const { chromium } = require('playwright');
const fs = require('fs');
const { spawn } = require('child_process');

const REPO = process.env.REPO || process.cwd(); // the folder that holds index.html
const OUT = process.argv[2];
const TEST = process.env.TEST === '1';
const PORT = 8767;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const now = () => Date.now() / 1000;

const ANS = {
  learn: 'Biology and how the human body works',
  learn2: 'How doctors use research to help people',
  free: 'Chess, drawing and walking my dog',
  make: 'Helping people, I like organizing events',
  self: 'Curious and kind. I want to find a club where I belong',
};

const CURSOR_INIT = () => {
  const mk = () => {
    if (document.getElementById('__cur') || !document.documentElement) return;
    const d = document.createElement('div');
    d.id = '__cur';
    d.style.cssText = 'position:fixed;left:0;top:0;width:24px;height:24px;z-index:2147483647;pointer-events:none;will-change:transform;';
    d.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" style="display:block;transform-origin:2px 2px;transition:transform .09s"><path d="M2 2 L2 19.5 L6.6 15.3 L9.8 22.4 L12.8 21 L9.6 14.1 L16 14.1 Z" fill="#111113" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(d);
    const p = window.__curPos || { x: 980, y: 430 };
    d.style.transform = `translate(${p.x - 2}px,${p.y - 2}px)`;
  };
  window.__curPos = window.__curPos || { x: 980, y: 430 };
  window.__curSet = (x, y) => {
    mk();
    window.__curPos = { x, y };
    const d = document.getElementById('__cur');
    if (d) d.style.transform = `translate(${x - 2}px,${y - 2}px)`;
  };
  window.__curMove = (x, y, ms) => new Promise(res => {
    mk();
    const x0 = window.__curPos.x, y0 = window.__curPos.y, t0 = performance.now();
    const dx = x - x0, dy = y - y0, dist = Math.hypot(dx, dy) || 1;
    const px = -dy / dist, py = dx / dist, amp = Math.min(40, dist * 0.07);
    const ease = t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
    const f = now => {
      const t = Math.min(1, (now - t0) / ms), k = ease(t), bow = Math.sin(Math.PI * k) * amp;
      window.__curSet(x0 + dx * k + px * bow, y0 + dy * k + py * bow);
      if (t < 1) requestAnimationFrame(f); else res();
    };
    requestAnimationFrame(f);
  });
  window.__curPress = down => {
    mk();
    const s = document.querySelector('#__cur svg');
    if (s) s.style.transform = down ? 'scale(.86)' : 'scale(1)';
  };
  document.addEventListener('DOMContentLoaded', mk);
  mk();
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const srv = spawn('python3', ['-I', '-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: REPO, stdio: 'ignore' });
  await sleep(900);
  const browser = await chromium.launch({ args: ['--force-device-scale-factor=1.5', '--window-size=1280,720', '--hide-scrollbars'] });
  const ctx = await browser.newContext({ viewport: null, colorScheme: 'light' });
  await ctx.addInitScript("try{if(!sessionStorage.getItem('__s')){sessionStorage.setItem('__s','1');localStorage.clear()}}catch(e){}");
  await ctx.addInitScript(CURSOR_INIT);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|ERR_/.test(m.text())) errors.push('console: ' + m.text()); });
  await page.goto(`http://127.0.0.1:${PORT}/index.html`);
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await sleep(500);

  const client = await ctx.newCDPSession(page);
  // ---- frame capture loop (CDP screenshots at 1.5x = true 1920x1080, with timestamps)
  let n = 0;
  const stamps = [];
  let running = true;
  const marks = [];
  const mark = name => { marks.push({ name, t: now() }); };
  const loop = (async () => {
    while (running) {
      const t0 = now();
      let r;
      try { r = await client.send('Page.captureScreenshot', { format: 'jpeg', quality: 90, optimizeForSpeed: true }); } catch (e) { break; }
      const t1 = now();
      fs.writeFileSync(`${OUT}/f${String(n).padStart(5, '0')}.jpg`, Buffer.from(r.data, 'base64'));
      stamps.push((t0 + t1) / 2);
      n++;
    }
  })();
  await sleep(300);
  mark('start');

  // ---- helpers
  const VH = 720;
  async function ensureVisible(loc, top = 100, bottom = 64) {
    // scroll only when the element is really out of view, and put it near the middle
    const b = await loc.boundingBox();
    if (b.y >= top && b.y + b.height <= VH - bottom) return;
    const d = b.y + b.height / 2 - VH * 0.5;
    await page.evaluate(d => window.scrollBy({ top: d, behavior: 'smooth' }), d);
    await sleep(Math.min(1100, 380 + Math.abs(d) * 0.9));
  }
  async function moveTo(x, y, ms) {
    await page.evaluate(([x, y, ms]) => window.__curMove(x, y, ms), [x, y, ms]);
    await page.mouse.move(x, y);
  }
  async function click(loc, { ms = 650, left = false, scroll = true, real = true } = {}) {
    if (scroll) await ensureVisible(loc);
    const b = await loc.boundingBox();
    const x = left ? b.x + Math.min(24, b.width / 2) : b.x + b.width / 2;
    const y = b.y + b.height / 2;
    await moveTo(x, y, ms);
    await page.evaluate(() => window.__curPress(true));
    if (real) await page.mouse.down();
    await sleep(90);
    if (real) await page.mouse.up();
    await page.evaluate(() => window.__curPress(false));
    await sleep(140);
  }
  async function type(loc, text, delay = 32) {
    await click(loc);
    await page.keyboard.type(text, { delay });
    await sleep(260);
  }
  async function smoothScrollTo(y, ms) {
    await page.evaluate(y => window.scrollTo({ top: y, behavior: 'smooth' }), y);
    await sleep(ms);
  }
  const tab = name => page.locator(`button[data-tab="${name}"]:visible`).first();
  const act = (name, extra = '') => page.locator(`[data-act="${name}"]${extra}:visible`).first();

  if (TEST) {
    await moveTo(300, 300, 700); await sleep(500); await moveTo(800, 500, 700); await sleep(800);
    mark('end');
  } else {
    // ---- A. welcome screen with the video box
    mark('welcome');
    await sleep(2200);
    await click(act('quiz'), { ms: 900, scroll: false });
    await sleep(500);

    // ---- B. quiz page 1
    mark('quiz1');
    await sleep(900);
    const sels = page.locator('select');
    await click(sels.nth(0), { ms: 800, real: false }); await sleep(200); await sels.nth(0).selectOption('10th grade'); await sleep(450);
    await click(sels.nth(1), { ms: 600, real: false }); await sleep(200); await sels.nth(1).selectOption('The Village School'); await sleep(500);
    await click(act('next'), { ms: 700 });
    await sleep(500);

    // ---- quiz page 2
    mark('quiz2');
    await sleep(700);
    const ta = page.locator('textarea');
    await type(ta.nth(0), ANS.learn);
    await type(ta.nth(1), ANS.learn2);
    await type(ta.nth(2), ANS.free);
    await type(ta.nth(3), ANS.make);
    await type(ta.nth(4), ANS.self);
    await sleep(500);
    await click(act('next'), { ms: 700 });
    await sleep(500);

    // ---- quiz page 3
    mark('quiz3');
    await sleep(700);
    for (const t of ['Join a club', 'Research']) await click(page.locator('label.opt', { hasText: new RegExp('^' + t + '$') }).first(), { ms: 600, left: true });
    for (const t of ['Exploring careers or majors', 'Trying new things']) await click(page.locator('label.opt', { hasText: new RegExp('^' + t + '$') }).first(), { ms: 600, left: true });
    await click(page.locator('label.opt', { hasText: /^3-5 hours/ }).first(), { ms: 600, left: true });
    await sleep(500);
    await click(act('next'), { ms: 700 });
    await sleep(500);

    // ---- quiz page 4
    mark('quiz4');
    await sleep(800);
    const sk = (k, w, nn) => page.locator(`button[data-act="sk"][data-k="${k}"][data-w="${w}"][data-n="${nn}"]`).first();
    await click(sk('Health & medicine', 'g', 4), { ms: 650 });
    await click(sk('Health & medicine', 'i', 5), { ms: 450 });
    await click(sk('Science', 'g', 4), { ms: 500 });
    await click(sk('Science', 'i', 5), { ms: 450 });
    await click(sk('Leading & organizing', 'g', 4), { ms: 500 });
    await click(sk('Leading & organizing', 'i', 4), { ms: 450 });
    await sleep(400);
    mark('see_matches_click');
    await click(act('next'), { ms: 700 });

    // ---- C. loading, then results
    mark('loading');
    await page.waitForFunction(() => S.stage === 'app', null, { timeout: 15000 });
    mark('results');
    await sleep(900);
    // clubs, then volunteer spots, then programs, then back to the clubs with their match levels
    mark('community');
    await click(tab('Community'), { ms: 800, scroll: false });
    await sleep(1300);
    mark('explore_tab');
    await click(tab('Explore'), { ms: 650, scroll: false });
    await sleep(1300);
    mark('school_again');
    await click(tab('School'), { ms: 650, scroll: false });
    await sleep(500);
    mark('scroll_down');
    await smoothScrollTo(340, 1600);
    await sleep(700);
    mark('scroll_up');
    await smoothScrollTo(0, 1000);
    await sleep(400);

    // ---- E. open a card
    mark('card_explore_click');
    const firstExplore = page.locator('button[data-act="explore"]:visible').first();
    await click(firstExplore, { ms: 800 });
    await sleep(600);
    mark('card_open');
    // bring the open card into view so details are readable
    await page.evaluate(() => { const a = document.querySelector('.it2.open'); if (a) window.scrollTo({ top: a.getBoundingClientRect().top + window.scrollY - 120, behavior: 'smooth' }); });
    await sleep(1000);
    // point at "Meets" and "How to join" while the card is open
    const openCard = page.locator('.it2.open').first();
    for (const label of ['Meets:', 'How to join:']) {
      const bb = await openCard.locator('b', { hasText: label }).first().boundingBox();
      await moveTo(bb.x + bb.width + 150, bb.y + bb.height / 2, 850);
      await sleep(label === 'Meets:' ? 800 : 950);
    }

    // ---- F. save it, go to My Activities
    mark('save_click');
    await click(page.locator('.it2.open button[data-act="save"]').first(), { ms: 700 });
    await sleep(1000);
    mark('myact_click');
    await click(tab('My Activities'), { ms: 900, scroll: false });
    await sleep(500);
    mark('myact');
    await sleep(3600);
    mark('end');
  }

  running = false;
  await loop;
  const info = await page.evaluate(() => ({ stage: S.stage, tab: S.tab, saved: Object.keys(S.saved || {}) }));
  fs.writeFileSync(`${OUT}/stamps.json`, JSON.stringify({ stamps, marks, info, errors, frames: n }));
  console.log(JSON.stringify({ frames: n, firstStamp: stamps[0], nowAtEnd: now(), marks: marks.length, info, errors }));
  await browser.close();
  srv.kill();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
