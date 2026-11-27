"""
Tests for the first-login tour (the small card on Home that points at each part of the app).

What this covers:
  T1  a guest: the tour starts by itself after the quiz, each step points at the right thing, the card never covers it,
      and finishing it is remembered
  T2  an account: the tour starts after the quiz, finishing it is saved online (user data) and on the device,
      a second device does not show it again, and a brand new account does
  T3  Skip, Escape and leaving Home all end the tour for good
  T4  an organizer, a parent and an admin get their own wording and steps
  T5  looks: phone, small phone, tablet and computer, light and dark (the card inside the screen, not on top of its target)
  T6  keyboard and window changes: focus on the buttons, Enter, Back, a resized window
  T7  when the tour must NOT show: before the quiz, before the account data has loaded, on other tabs; and the Settings button that plays it again
  T8  an account that has no tour record online, or only on this device

It runs the real page in headless Chromium against the pretend Supabase in fake_sb.py (with fake.tour=True so the pretend
accounts really start without the tour record). Run it from the repo folder:
    python3 tools/test/test_tour.py
"""
import json, os, re, subprocess, sys, time
from subprocess import DEVNULL
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fake_sb import Fake, SBRE, KEY

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.environ.get('BL_SHOTS', '/tmp/bulletin-test-shots'); os.makedirs(SP + '/shots', exist_ok=True)
PORT = 8778
URL = f'http://127.0.0.1:{PORT}/index.html'
LOCAL = f'http://127.0.0.1:{PORT}/local.html'
HTML = open(REPO + '/index.html', encoding='utf-8').read()
HTML_LOCAL = re.sub(r'const SB_URL="[^"]*"', 'const SB_URL=""', HTML, count=1)
assert HTML_LOCAL != HTML
srv = subprocess.Popen(['python3', '-I', '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=REPO, stdout=DEVNULL, stderr=DEVNULL)
time.sleep(1.0)

results = []; all_errs = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' | ' + str(detail)[:300]) if (detail != '' and not ok) else ''), flush=True)

ANS = {'grade': '10th grade', 'school': 'The Village School', 'zip': '77095', 'learn': 'biology and chemistry', 'want': ['Join a club'], 'why': ['Trying new things'], 'time': '3-5 hours'}
# a guest who already took the quiz and has not seen the tour, sitting on Home
GUEST = {'stage': 'app', 'tab': 'Home', 'seen': True, 'done': True, 'theme': 'light', 'ans': ANS}
# a guest who has not taken the quiz: the app sends them to the account step
APP0 = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': False, 'theme': 'light', 'ans': {}}
FILL = """(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='zip'?'77095':q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""
PW = 'secret1'
D = {'width': 1440, 'height': 900}
P = {'width': 390, 'height': 844}
SP5 = {'width': 375, 'height': 667}
TAB = {'width': 800, 'height': 1000}
ROLE_TXT = {'Student': 'I’m a student', 'Parent': 'parent or guardian', 'Teacher': 'I’m a teacher', 'Organizer': 'run a club'}
RING = 'rgb(214, 69, 47)'   # Pin Red, the colour of the ring around what the card points at

# what the card and its target look like right now, measured in the browser
GEO = """(()=>{
 const c=document.getElementById('tour'); if(!c) return null;
 const r=c.getBoundingClientRect(), all=document.querySelectorAll('.tour-hl'), t=all[0]||null;
 const tr=t?t.getBoundingClientRect():null, hd=document.querySelector('.hd').getBoundingClientRect().bottom, cs=t?getComputedStyle(t):null;
 const bn=document.getElementById('bn'), bnTop=bn&&bn.getClientRects().length?bn.getBoundingClientRect().top:innerHeight;
 return {c:[r.left,r.top,r.right,r.bottom], t:tr?[tr.left,tr.top,tr.right,tr.bottom]:null, rings:all.length, vw:document.documentElement.clientWidth, vh:innerHeight, hd, bnTop,
  ow:cs?cs.outlineWidth:null, oc:cs?cs.outlineColor:null, clip:c.scrollHeight>c.clientHeight+1,
  title:(c.querySelector('h2')||{}).textContent||'', n:(c.querySelector('.tour-n')||{}).textContent||'', text:c.innerText,
  btns:[...c.querySelectorAll('button')].map(b=>b.textContent.trim()), role:c.getAttribute('role'), focus:document.activeElement?document.activeElement.textContent.trim():'',
  tsel:t?(t.id?'#'+t.id:'.'+[...t.classList].filter(x=>x!=='tour-hl').join('.')):null}})()"""

def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def newpage(b, vp, fake, state=None, sb=None, users=None, visit=True, scheme='light', local=False):
    """A page seeded exactly as asked (nothing is pre-marked as toured here, unlike the other suites)."""
    mob = vp['width'] < 500
    ctx = b.new_context(viewport=vp, is_mobile=mob, has_touch=mob, color_scheme=scheme)
    js = "try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    if state is not None: js += "localStorage.setItem('bl.state',%s);" % json.dumps(json.dumps(state))
    if sb is not None: js += "localStorage.setItem('bl.sb',%s);" % json.dumps(json.dumps(sb))
    if users is not None: js += "localStorage.setItem('bl.users',%s);" % json.dumps(json.dumps(users))
    if visit: js += "sessionStorage.setItem('bl.visit','1');"
    ctx.add_init_script(js + "}}catch(e){}")
    ctx.route(SBRE, fake.handler)
    if local:
        ctx.route('**/local.html', lambda route, request: route.fulfill(status=200, content_type='text/html', body=HTML_LOCAL))
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_' not in m.text else None)
    pg.on('dialog', lambda d: d.accept())
    all_errs.append(errs)
    pg.goto(LOCAL if local else URL); pg.wait_for_timeout(500)
    return ctx, pg, errs

w = lambda pg, ms=250: pg.wait_for_timeout(ms)
def geo(pg): return pg.evaluate(GEO)
def card(pg): return pg.locator('#tour')
def has_card(pg): return pg.locator('#tour').count() == 1
def step_n(pg):
    g = geo(pg); return g['n'] if g else None
def tab(pg, name):
    pg.locator(f'button[data-tab="{name}"]:visible').first.click(); w(pg)
def titles(pg, press='[data-act="tournext"]'):
    """Walk the whole tour with Next, return the title of every step, stopping on the last one (Done is not pressed)."""
    out = []
    while True:
        g = geo(pg); out.append(g['title'])
        if 'Done' in g['btns']: break
        pg.click(press); w(pg, 120)
        if len(out) > 14: break
    return out
def fill_signup(pg, name, email, role='Student', org=None):
    pg.fill('#a_name', name); pg.fill('#a_email', email); pg.fill('#a_pw', PW)
    pg.locator('.role', has_text=ROLE_TXT[role]).click()
    if org is not None: pg.fill('#a_org', org)
def do_quiz(pg):
    pg.click('#full [data-act="quiz"]'); w(pg, 200)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 500)
def sign_up(b, vp, fake, name, email, role='Student', org=None, scheme='light', quiz=True):
    """From a guest at the account step: create the account through the page, then (if asked) take the quiz and land on Home."""
    ctx, pg, errs = newpage(b, vp, fake, APP0, scheme=scheme)
    pg.click('#full [data-act="signup"]'); w(pg)
    fill_signup(pg, name, email, role, org)
    pg.click('[data-act="dosignup"]'); w(pg, 900)
    if quiz and role != 'Organizer': do_quiz(pg)
    else: w(pg, 400)
    return ctx, pg, errs
def logged_in_page(b, vp, fake, email, state=None, role='Student', toured_here=None, answers=ANS, **kw):
    """A seeded login for an account the pretend project already has (it has NO tour record unless the test gives one)."""
    if email not in fake.users:
        fake.add_user(email, PW, {'name': email.split('@')[0].title(), 'role': role, 'provider': role == 'Organizer', 'org': 'Robot Club' if role == 'Organizer' else ''})
    uid = fake.users[email]['id']
    if answers is not None: fake.profiles[uid]['quiz_answers'] = answers
    seed = fake.sb_seed(fake.session(uid, None))
    st = dict(state if state is not None else GUEST, me=email, done=answers is not None and role != 'Organizer')
    if answers is not None: st['ans'] = answers
    u = {'name': fake.profiles[uid]['name'], 'email': email, 'role': role, 'provider': role == 'Organizer', 'org': 'Robot Club' if role == 'Organizer' else '', 'friends': [], 'sb': 1}
    if toured_here is not None: u['toured'] = toured_here
    ctx, pg, errs = newpage(b, vp, fake, state=st, sb=seed, users={email: u}, **kw)
    return ctx, pg, errs, uid

def section(fn):
    try:
        fn()
    except Exception as e:
        check(f'{fn.__name__} CRASHED', False, repr(e)[:400])


def check_step(label, pg, want_ring=True):
    """The card is fully on screen, readable and not on top of what it points at; the ring is the right colour."""
    g = geo(pg)
    if not g: check(f'{label}: the card is on the page', False); return None
    c = g['c']
    check(f'{label}: the card is inside the screen', c[0] >= -0.5 and c[2] <= g['vw'] + 0.5 and c[1] >= -0.5 and c[3] <= g['vh'] + 0.5, [c, g['vw'], g['vh']])
    check(f'{label}: nothing in the card is cut off', not g['clip'])
    if want_ring:
        check(f'{label}: exactly one thing has the red ring', g['rings'] == 1, g['rings'])
        if g['t']:
            check(f'{label}: the ring is {RING} and 3px', g['oc'] == RING and g['ow'] == '3px', [g['oc'], g['ow']])
            check(f'{label}: the card does not cover what it points at', not overlap(c, g['t']), [c, g['t'], g['tsel']])
            t = g['t']; fixed = g['tsel'] in ('#bn', '#nav', '#q', '.gb', '#hadm')
            check(f'{label}: what it points at is on screen' + ('' if fixed else ' and not hidden under the header'), t[0] >= -0.5 and t[2] <= g['vw'] + 0.5 and t[3] <= g['vh'] + 0.5 and t[1] >= -0.5 and (fixed or t[1] >= g['hd'] - 1), [t, g['hd'], g['vh'], g['tsel']])
    else:
        check(f'{label}: no ring on the welcome step', g['rings'] == 0, g['rings'])
    return g


def run(b):
    # ---------- T1: a guest ----------
    def t1_guest():
        for label, vp, ring_tabs in (('phone', P, '#bn'), ('desktop', D, '#nav')):
            fake = Fake(); fake.tour = True
            ctx, pg, errs = newpage(b, vp, fake, APP0)
            # the real path: account step, continue as a guest, take the quiz, land on Home
            pg.click('#full [data-act="guest"]'); w(pg)
            check(f'T1 {label}: nothing about the tour before the quiz', not has_card(pg))
            do_quiz(pg)
            check(f'T1 {label}: the tour starts by itself on the first visit to Home', has_card(pg) and pg.evaluate("[S.stage,S.tab,TOUR]") == ['app', 'Home', 0], pg.evaluate("[S.stage,S.tab,TOUR]"))
            g = geo(pg)
            check(f'T1 {label}: the first card says Welcome to Bulletin and 1 of 8', g['title'] == 'Welcome to Bulletin.' and g['n'] == '1 of 8', [g['title'], g['n']])
            check(f'T1 {label}: the first card has Start and Skip tour, no Back', g['btns'] == ['Skip tour', 'Start'], g['btns'])
            check(f'T1 {label}: the card is a dialog with a label', g['role'] == 'dialog' and pg.evaluate("document.getElementById('tour').getAttribute('aria-labelledby')") == 'tour-t')
            check(f'T1 {label}: the first card says what Home is', 'This is your Home' in g['text'] and 'about a minute' in g['text'], g['text'][:200])
            check_step(f'T1 {label} step 1', pg, want_ring=False)
            want = ['Welcome to Bulletin.', 'Make a free account', 'The tabs', 'Your counts', 'Your top matches', 'Save what you like', 'Search', 'Settings']
            got = [g['title']]
            ring_of = {}
            for i in range(1, 8):
                pg.click('#tour .btn.pri'); w(pg, 150)
                g = check_step(f'T1 {label} step {i + 1}', pg)
                got.append(g['title']); ring_of[g['title']] = g['tsel']
                check(f'T1 {label} step {i + 1}: the counter says {i + 1} of 8', g['n'] == f'{i + 1} of 8', g['n'])
            check(f'T1 {label}: the eight steps, in order', got == want, got)
            check(f'T1 {label}: each step points at the right thing', ring_of == {'Make a free account': '.qb', 'The tabs': ring_tabs, 'Your counts': '.hts', 'Your top matches': '.hr', 'Save what you like': '.bm', 'Search': '#q', 'Settings': '.gb'}, ring_of)
            g = geo(pg)
            check(f'T1 {label}: the last step has Back and Done and no Skip', g['btns'] == ['Back', 'Done'], g['btns'])
            # Back goes to the step before, Next comes forward again
            pg.click('[data-act="tourback"]'); w(pg, 150)
            check(f'T1 {label}: Back goes to the step before', geo(pg)['title'] == 'Search', geo(pg)['title'])
            pg.click('[data-act="tournext"]'); w(pg, 150)
            pg.click('[data-act="tourdone"]'); w(pg, 250)
            check(f'T1 {label}: Done takes the card and the ring away', not has_card(pg) and pg.locator('.tour-hl').count() == 0)
            check(f'T1 {label}: the guest is marked as having seen it', pg.evaluate("[S.toured,TOUR]") == [True, None], pg.evaluate("[S.toured,TOUR]"))
            check(f'T1 {label}: a guest finishing the tour sends nothing online', fake.calls('PUT') == [] and fake.meta_puts == [])
            pg.reload(); w(pg, 700)
            check(f'T1 {label}: after a reload the tour does not come back', not has_card(pg))
            # Settings plays it again
            tab(pg, 'Settings')
            check(f'T1 {label}: Settings has a Show the tour button', pg.locator('#main [data-act="tour"]').count() == 1)
            pg.click('#main [data-act="tour"]'); w(pg, 300)
            check(f'T1 {label}: Show the tour goes Home and starts at step 1', pg.evaluate("[S.tab,TOUR]") == ['Home', 0] and geo(pg)['n'] == '1 of 8', pg.evaluate("[S.tab,TOUR]"))
            pg.click('[data-act="tourskip"]'); w(pg, 200)
            check(f'T1 {label}: and it can be skipped again', not has_card(pg))
            check(f'T1 {label}: no page errors', errs == [], errs[:3])
            ctx.close()
    section(t1_guest)

    # ---------- T2: an account ----------
    def t2_account():
        fake = Fake(); fake.tour = True
        ctx, pg, errs = sign_up(b, P, fake, 'Pat Student', 'pat@example.com')
        check('T2 a new account sees the tour after its quiz', has_card(pg) and pg.evaluate("TOUR") == 0)
        g = geo(pg)
        check('T2 the welcome says the person’s first name', g['title'] == 'Welcome to Bulletin, Pat.' and g['n'] == '1 of 7', [g['title'], g['n']])
        check('T2 an account has no “make a free account” step', 'Make a free account' not in titles(pg), '')
        pg.click('[data-act="tourdone"]'); w(pg, 700)
        check('T2 finishing it is saved online as user data (toured: true)', fake.meta_puts == [('pat@example.com', {'toured': True})], fake.meta_puts)
        check('T2 the pretend project now has it in the account’s user data', fake.users['pat@example.com']['meta'].get('toured') is True, fake.users['pat@example.com']['meta'])
        check('T2 the sign-up details in the user data were kept', fake.users['pat@example.com']['meta'].get('name') == 'Pat Student' and fake.users['pat@example.com']['meta'].get('role') == 'Student')
        check('T2 the send used the person’s login and no password change was recorded', fake.pw_changes == [] and fake.violations == [], [fake.pw_changes, fake.violations])
        us = json.loads(pg.evaluate("localStorage.getItem('bl.users')"))
        check('T2 this device remembers it too', us['pat@example.com'].get('toured') is True, us)
        check('T2 the device copy still holds no password or quiz answers', 'pw' not in us['pat@example.com'] and 'ans' not in us['pat@example.com'])
        pg.reload(); w(pg, 800)
        check('T2 after a reload there is no tour', not has_card(pg))
        # log out, log in again on the same device: still no tour
        tab(pg, 'Settings'); pg.click('#main [data-act="logout"]'); w(pg, 600)
        pg.click('#full [data-act="login"]'); w(pg)
        pg.fill('#a_email', 'pat@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 1000)
        check('T2 logging in again on this device: Home, and no tour', pg.evaluate("[S.stage,S.tab]") == ['app', 'Home'] and not has_card(pg), pg.evaluate("[S.stage,S.tab]"))
        ctx.close()
        # a second device (a new browser profile): the login brings the user data, which says the tour was seen
        ctx2, pg2, errs2 = newpage(b, P, fake, APP0)
        pg2.click('#full [data-act="login"]'); w(pg2)
        pg2.fill('#a_email', 'pat@example.com'); pg2.fill('#a_pw', PW); pg2.click('[data-act="dologin"]'); w(pg2, 1200)
        check('T2 a second device: Home with the quiz answers, and no tour', pg2.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True] and not has_card(pg2), pg2.evaluate("[S.stage,S.tab,S.done]"))
        check('T2 a second device does not send the tour record again', len(fake.meta_puts) == 1, fake.meta_puts)
        ctx2.close()
        # a different new account starts its own tour
        ctx3, pg3, errs3 = sign_up(b, P, fake, 'Quinn Student', 'quinn@example.com')
        check('T2 a different new account gets its own tour', has_card(pg3) and geo(pg3)['title'] == 'Welcome to Bulletin, Quinn.', geo(pg3) and geo(pg3)['title'])
        ctx3.close()
        check('T2 no page errors', all(e == [] for e in all_errs[-4:]), [e[:2] for e in all_errs[-4:]])
    section(t2_account)

    # ---------- T3: skip, Escape and leaving Home ----------
    def t3_ending():
        for label, how in (('Skip on the first card', 'skip'), ('Escape in the middle', 'esc'), ('tapping a tab in the middle', 'tab'), ('the browser Back button', 'back'), ('typing in the search box', 'search')):
            fake = Fake(); fake.tour = True
            ctx, pg, errs, uid = logged_in_page(b, P, fake, 'sam@example.com', state=dict(GUEST, tab='School') if how == 'back' else None)
            if how == 'back': tab(pg, 'Home'); w(pg, 300)
            check(f'T3 {label}: the tour starts for an account with no tour record', has_card(pg) and geo(pg)['n'] == '1 of 7', geo(pg) and geo(pg)['n'])
            if how == 'skip':
                pg.click('[data-act="tourskip"]')
            elif how == 'esc':
                pg.click('[data-act="tournext"]'); w(pg, 120); pg.click('[data-act="tournext"]'); w(pg, 120); pg.keyboard.press('Escape')
            elif how == 'tab':
                pg.click('[data-act="tournext"]'); w(pg, 120)
                pg.locator('#bn button[data-tab="School"]').click()
            elif how == 'back':
                pg.click('[data-act="tournext"]'); w(pg, 120)
                pg.go_back()
            else:
                pg.evaluate("TOUR=5;tourDraw()"); w(pg, 150)
                check('T3 typing in the search box: the card was on the Search step', geo(pg)['title'] == 'Search', geo(pg)['title'])
                pg.fill('#q', 'robot')
            w(pg, 700)
            check(f'T3 {label}: the tour is gone', not has_card(pg) and pg.locator('.tour-hl').count() == 0 and pg.evaluate("TOUR") is None)
            check(f'T3 {label}: and counted as seen, on the device and online', json.loads(pg.evaluate("localStorage.getItem('bl.users')"))['sam@example.com'].get('toured') is True and fake.meta_puts == [('sam@example.com', {'toured': True})], fake.meta_puts)
            # coming back to Home does not start it again
            tab(pg, 'Home'); w(pg, 300)
            check(f'T3 {label}: coming back to Home does not start it again', not has_card(pg))
            check(f'T3 {label}: no page errors', errs == [], errs[:3])
            ctx.close()
    section(t3_ending)

    # ---------- T4: organizer, parent, admin ----------
    def t4_roles():
        # an organizer: no quiz, own wording, a step for the Post button
        fake = Fake(); fake.tour = True
        ctx, pg, errs = sign_up(b, D, fake, 'Olive Organizer', 'olive@example.com', role='Organizer', org='Houston Robotics Club')
        check('T4 an organizer’s tour starts on Home with no quiz', has_card(pg) and pg.evaluate("[S.tab,S.done]") == ['Home', False], pg.evaluate("[S.tab,S.done]"))
        g = geo(pg)
        check('T4 the organizer welcome says they post for students and has 6 steps', g['title'] == 'Welcome to Bulletin, Olive.' and 'You post opportunities for students to find' in g['text'] and g['n'] == '1 of 6', [g['title'], g['n']])
        got = titles(pg)
        check('T4 the organizer steps', got == ['Welcome to Bulletin, Olive.', 'The tabs', 'Your numbers', 'Post an opportunity', 'Search', 'Settings'], got)
        g = geo(pg)
        check('T4 the last organizer step does not mention the quiz', 'quiz' not in g['text'].lower() and 'log out' in g['text'], g['text'])
        pg.click('[data-act="tourback"]'); w(pg, 150); pg.click('[data-act="tourback"]'); w(pg, 150)
        g = check_step('T4 organizer Post step', pg)
        check('T4 the Post step points at the Post an opportunity button', g['title'] == 'Post an opportunity' and g['tsel'].startswith('.btn'), [g['title'], g['tsel']])
        pg.click('[data-act="tourskip"]'); w(pg, 300)
        ctx.close()
        # a parent: everything is about their child
        fake = Fake(); fake.tour = True
        ctx, pg, errs = sign_up(b, P, fake, 'Paula Parent', 'paula@example.com', role='Parent')
        g = geo(pg)
        check('T4 a parent’s welcome says the matches are for their child', 'Everything here is matched to your child’s answers' in g['text'], g['text'][:240])
        pg.click('#tour .btn.pri'); w(pg, 150)
        check('T4 a parent’s tabs step says the school is their child’s', 'Clubs at your child’s school' in geo(pg)['text'], geo(pg)['text'])
        pg.click('#tour .btn.pri'); w(pg, 150); pg.click('#tour .btn.pri'); w(pg, 150)
        check('T4 a parent’s matches step says the match levels are for their child', 'for your child' in geo(pg)['text'], geo(pg)['text'])
        pg.click('[data-act="tourskip"]'); w(pg, 200); ctx.close()
        # a teacher
        fake = Fake(); fake.tour = True
        ctx, pg, errs = sign_up(b, P, fake, 'Terry Teacher', 'terry@example.com', role='Teacher')
        check('T4 a teacher’s welcome says the matches are for the student', 'Everything here is matched to the student’s answers' in geo(pg)['text'], geo(pg)['text'][:240])
        pg.click('[data-act="tourskip"]'); w(pg, 200); ctx.close()
        # an admin gets one extra step, pointing at the Admin button
        fake = Fake(); fake.tour = True; fake.sql = True
        fake.add_user('boss@example.com', PW, {'name': 'Boss Person', 'role': 'Teacher', 'provider': False, 'org': ''}); fake.make_admin('boss@example.com')
        ctx, pg, errs = newpage(b, D, fake, APP0)
        pg.click('#full [data-act="login"]'); w(pg)
        pg.fill('#a_email', 'boss@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 1200)
        check('T4 an admin lands on the Admin page, and the tour waits (it belongs to Home)', pg.evaluate("S.tab") == 'Admin' and not has_card(pg), pg.evaluate("S.tab"))
        tab(pg, 'Home'); w(pg, 400)
        check('T4 the admin’s tour starts when they open Home', has_card(pg))
        got = titles(pg)
        check('T4 the admin steps include Admin, just before Settings', 'Admin' in got and got[-2:] == ['Admin', 'Settings'] and got[0] == 'Welcome to Bulletin, Boss.', got)
        pg.click('[data-act="tourback"]'); w(pg, 150)
        g = check_step('T4 admin step', pg)
        check('T4 the Admin step points at the Admin button in the header', g['title'] == 'Admin' and g['tsel'] == '#hadm', g['tsel'])
        pg.click('[data-act="tourskip"]'); w(pg, 200); ctx.close()
    section(t4_roles)

    # ---------- T5: looks ----------
    def t5_looks():
        shots = {0: 'welcome', 1: 'tabs', 4: 'bookmark', 6: 'settings'}
        for label, vp in (('phone', P), ('small-phone', SP5), ('tablet', TAB), ('desktop', D), ('short-desktop', {'width': 1100, 'height': 560})):
            for scheme in ('light', 'dark'):
                fake = Fake(); fake.tour = True
                ctx, pg, errs, uid = logged_in_page(b, vp, fake, 'lee@example.com', state=dict(GUEST, theme='auto' if scheme == 'dark' else 'light'), scheme=scheme)
                bad = []
                g = geo(pg); total = int(g['n'].split(' of ')[1])
                for i in range(total):
                    g = geo(pg); c = g['c']
                    ok = c[0] >= -0.5 and c[2] <= g['vw'] + 0.5 and c[1] >= -0.5 and c[3] <= g['vh'] + 0.5 and not g['clip'] and (not g['t'] or not overlap(c, g['t'])) and (i == 0 or g['rings'] == 1)
                    if not ok: bad.append((i + 1, g['title'], g['c'], g['t'], g['clip']))
                    if i in shots and scheme in ('light', 'dark'): pg.screenshot(path=f'{SP}/shots/tour-{label}-{scheme}-{shots[i]}.png')
                    pg.click('#tour .btn.pri'); w(pg, 120)
                check(f'T5 {label} {scheme}: all {total} steps keep the card on screen, readable, and off its target', bad == [], bad)
                check(f'T5 {label} {scheme}: the page does not scroll sideways during the tour', True if not has_card(pg) else pg.evaluate("document.documentElement.scrollWidth<=innerWidth"))
                check(f'T5 {label} {scheme}: no page errors', errs == [], errs[:3])
                ctx.close()
    section(t5_looks)

    # ---------- T6: keyboard and window changes ----------
    def t6_keys():
        fake = Fake(); fake.tour = True
        ctx, pg, errs, uid = logged_in_page(b, D, fake, 'kay@example.com')
        g = geo(pg)
        check('T6 the Start button has the focus when the tour opens', g['focus'] == 'Start', g['focus'])
        pg.keyboard.press('Enter'); w(pg, 200)
        g = geo(pg)
        check('T6 Enter on the focused button goes to the next step', g['n'] == '2 of 7' and g['focus'] == 'Next', [g['n'], g['focus']])
        pg.keyboard.press('Shift+Tab'); w(pg, 50)
        check('T6 Shift+Tab moves to the Back button inside the card', pg.evaluate("document.activeElement.closest('#tour')!==null&&document.activeElement.textContent.trim()==='Back'"), pg.evaluate("document.activeElement.textContent"))
        pg.keyboard.press('Escape'); w(pg, 250)
        check('T6 Escape closes the card', not has_card(pg))
        # the tour reopens from Settings and works on a window that is resized part way through
        tab(pg, 'Settings'); pg.click('#main [data-act="tour"]'); w(pg, 300)
        pg.click('#tour .btn.pri'); w(pg, 150)
        check('T6 on a wide screen the tabs step points at the tab bar in the header', geo(pg)['tsel'] == '#nav', geo(pg)['tsel'])
        pg.set_viewport_size(P); w(pg, 400)
        g = geo(pg)
        check('T6 shrinking the window to a phone keeps the card on screen and moves the ring to the bottom bar', g is not None and g['tsel'] == '#bn' and g['c'][2] <= g['vw'] + 0.5 and not overlap(g['c'], g['t']), g and [g['tsel'], g['c'], g['t']])
        pg.set_viewport_size(D); w(pg, 400)
        g = geo(pg)
        check('T6 growing it back puts the ring on the tab bar again', g is not None and g['tsel'] == '#nav' and not overlap(g['c'], g['t']), g and [g['tsel'], g['c'], g['t']])
        # a redraw while the tour is open (for example after saving a bookmark) keeps the same step and does not steal the focus
        pg.click('#tour .btn.pri'); w(pg, 150); pg.click('#tour .btn.pri'); w(pg, 150); pg.click('#tour .btn.pri'); w(pg, 200)
        check('T6 on the bookmark step', geo(pg)['title'] == 'Save what you like', geo(pg)['title'])
        pg.click('#main .hs .bm'); w(pg, 300)
        g = geo(pg)
        check('T6 tapping the highlighted bookmark saves it and the tour stays on that step with the ring', g is not None and g['title'] == 'Save what you like' and g['rings'] == 1 and pg.evaluate("Object.values(S.saved).filter(Boolean).length") == 1, g and [g['title'], g['rings']])
        pg.evaluate("render()"); w(pg, 200)
        check('T6 another redraw changes nothing', geo(pg)['title'] == 'Save what you like')
        check('T6 no page errors', errs == [], errs[:3])
        ctx.close()
    section(t6_keys)

    # ---------- T7: when the tour must not show ----------
    def t7_not_shown():
        # before the quiz: a guest at the account step, the quiz step, the quiz itself, and a signed-in account at the quiz step
        fake = Fake(); fake.tour = True
        ctx, pg, errs = newpage(b, P, fake, APP0)
        check('T7 account step: no tour', pg.evaluate("S.stage") == 'auth' and not has_card(pg))
        pg.click('#full [data-act="guest"]'); w(pg)
        check('T7 quiz step: no tour', pg.evaluate("S.stage") == 'prompt' and not has_card(pg))
        pg.click('#full [data-act="quiz"]'); w(pg)
        check('T7 in the quiz: no tour', pg.evaluate("S.stage") == 'quiz' and not has_card(pg))
        ctx.close()
        # a guest on another tab: no tour until they open Home
        fake = Fake(); fake.tour = True
        ctx, pg, errs = newpage(b, D, fake, dict(GUEST, tab='School'))
        check('T7 a guest who opens the app on School sees no tour there', pg.evaluate("S.tab") == 'School' and not has_card(pg))
        tab(pg, 'Home'); w(pg, 300)
        check('T7 it starts when they open Home', has_card(pg) and geo(pg)['n'] == '1 of 8', geo(pg) and geo(pg)['n'])
        tab(pg, 'Explore'); w(pg, 300)
        check('T7 and goes away on another tab', not has_card(pg))
        ctx.close()
        # the welcome screens and the forms never show it
        fake = Fake(); fake.tour = True
        ctx, pg, errs = newpage(b, P, fake, dict(GUEST), visit=False)
        check('T7 the welcome screens come first and show no tour', pg.evaluate("S.stage") == 'intro' and not has_card(pg))
        ctx.close()
        # the account data has not loaded (the server is unreachable): the app opens, with no tour yet
        fake = Fake(); fake.tour = True
        fake.add_user('dee@example.com', PW, {'name': 'Dee', 'role': 'Student', 'provider': False, 'org': ''})
        uid = fake.users['dee@example.com']['id']; fake.profiles[uid]['quiz_answers'] = ANS
        sess = fake.session(uid, None); fake.fail = 'net'
        u = {'dee@example.com': {'name': 'Dee', 'email': 'dee@example.com', 'role': 'Student', 'provider': False, 'org': '', 'friends': [], 'sb': 1}}
        ctx, pg, errs = newpage(b, P, fake, dict(GUEST, me='dee@example.com', done=False, ans={}), sb=fake.sb_seed(sess), users=u)
        w(pg, 1200)
        check('T7 the server is unreachable: the app opens on Home but the tour waits', pg.evaluate("[S.stage,S.tab,sbNeedPull]") == ['app', 'Home', True] and not has_card(pg), pg.evaluate("[S.stage,S.tab,sbNeedPull]"))
        fake.fail = None
        pg.evaluate("dispatchEvent(new Event('online'))"); w(pg, 1500)
        check('T7 when the data arrives, the tour starts', pg.evaluate("[S.stage,S.tab,sbNeedPull]") == ['app', 'Home', False] and has_card(pg), pg.evaluate("[S.stage,S.tab,sbNeedPull,S.done]"))
        check('T7 no page errors', all(e == [] for e in all_errs[-4:]), [e[:2] for e in all_errs[-4:]])
        ctx.close()
    section(t7_not_shown)

    # ---------- T8: accounts whose record is only on the device, or only online ----------
    def t8_records():
        # the account has no record online and none here: tour shows, and Done writes both
        fake = Fake(); fake.tour = True
        ctx, pg, errs, uid = logged_in_page(b, P, fake, 'ann@example.com')
        check('T8 no record anywhere: the tour shows', has_card(pg))
        ctx.close()
        # this device says it was seen: no tour
        fake = Fake(); fake.tour = True
        ctx, pg, errs, uid = logged_in_page(b, P, fake, 'bob@example.com', toured_here=True)
        check('T8 the device says seen: no tour', not has_card(pg))
        ctx.close()
        # this device says seen but the account does not (an earlier send failed): logging in tells the account
        fake = Fake(); fake.tour = True
        fake.add_user('cy@example.com', PW, {'name': 'Cy', 'role': 'Student', 'provider': False, 'org': ''})
        fake.profiles[fake.users['cy@example.com']['id']]['quiz_answers'] = ANS
        us = {'cy@example.com': {'name': 'Cy', 'email': 'cy@example.com', 'role': 'Student', 'provider': False, 'org': '', 'friends': [], 'sb': 1, 'toured': True}}
        ctx, pg, errs = newpage(b, P, fake, APP0, users=us)
        pg.click('#full [data-act="login"]'); w(pg)
        pg.fill('#a_email', 'cy@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 1200)
        check('T8 this device knew, the account did not: no tour, and the account is told now', not has_card(pg) and fake.meta_puts == [('cy@example.com', {'toured': True})], [has_card(pg), fake.meta_puts])
        ctx.close()
        # the account knows, the device does not (a new device): no tour, and nothing is sent
        fake = Fake(); fake.tour = True
        fake.add_user('di@example.com', PW, {'name': 'Di', 'role': 'Student', 'provider': False, 'org': '', 'toured': True})
        fake.profiles[fake.users['di@example.com']['id']]['quiz_answers'] = ANS
        ctx, pg, errs = newpage(b, P, fake, APP0)
        pg.click('#full [data-act="login"]'); w(pg)
        pg.fill('#a_email', 'di@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 1200)
        check('T8 the account knew, this device did not: no tour and nothing sent', not has_card(pg) and fake.meta_puts == [] and json.loads(pg.evaluate("localStorage.getItem('bl.users')"))['di@example.com'].get('toured') is True, [has_card(pg), fake.meta_puts])
        ctx.close()
        # the send fails (offline): the tour is still finished here, and no error shows
        fake = Fake(); fake.tour = True
        ctx, pg, errs, uid = logged_in_page(b, P, fake, 'ed@example.com')
        fake.fail = 'net'
        pg.click('[data-act="tourskip"]'); w(pg, 800)
        check('T8 offline: Skip still ends the tour here, with no error on screen', not has_card(pg) and pg.evaluate("me().toured") is True and 'went wrong' not in pg.locator('body').inner_text().lower(), pg.evaluate("me().toured"))
        ctx.close()
        # a device-only account (no Supabase): the record is kept on the device
        ctx, pg, errs = newpage(b, P, Fake(), APP0, local=True)
        pg.click('#full [data-act="signup"]'); w(pg)
        fill_signup(pg, 'Dev Only', 'dev@example.com'); pg.click('[data-act="dosignup"]'); w(pg, 700)
        do_quiz(pg)
        check('T8 device-only: a new account gets the tour', has_card(pg) and geo(pg)['title'] == 'Welcome to Bulletin, Dev.', geo(pg) and geo(pg)['title'])
        pg.click('[data-act="tourskip"]'); w(pg, 300)
        us = json.loads(pg.evaluate("localStorage.getItem('bl.users')"))
        check('T8 device-only: skipping is saved on the device', us['dev@example.com'].get('toured') is True, us)
        pg.reload(); w(pg, 700)
        check('T8 device-only: no tour after a reload', not has_card(pg))
        check('T8 no page errors', all(e == [] for e in all_errs[-6:]), [e[:2] for e in all_errs[-6:]])
        ctx.close()
    section(t8_records)


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        run(b)
        b.close()
finally:
    srv.terminate()

bad = [r for r in results if not r[1]]
errs_flat = [e for lst_ in all_errs for e in lst_]
print('\n==== %d checks, %d failed, %d page errors' % (len(results), len(bad), len(errs_flat)))
for r in bad: print('FAILED:', r[0], '|', str(r[2])[:300])
for e in errs_flat[:10]: print('ERR:', e[:200])
