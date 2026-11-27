import datetime, json, os, re, subprocess, sys, time
from subprocess import DEVNULL
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fake_sb import Fake, SBRE, KEY

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.environ.get('BL_SHOTS', '/tmp/bulletin-test-shots'); os.makedirs(SP + '/shots', exist_ok=True)
PORT = 8772
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
APP = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': True, 'theme': 'light', 'ans': ANS}
APP0 = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': False, 'theme': 'light', 'ans': {}}
FILL = """(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='zip'?'77095':q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""
PW = 'secret1'
DIALOGS = []; ACCEPT = [True]
# the words on the four account-type cards on the sign-up form
ROLE_TXT = {'Student': 'I’m a student', 'Parent': 'parent or guardian', 'Teacher': 'I’m a teacher', 'Organizer': 'run a club'}

def newpage(b, vp, fake, state=None, sb=None, users=None, visit=True, scheme='light', dsf=1, url=URL, local=False):
    # keep the first-login tour out of the way here (it is covered by test_tour.py): guests and accounts count as having seen it
    if state is not None:
        state = dict(state); state.setdefault('toured', True)
    if users is not None:
        users = {k: dict(v, toured=v.get('toured', True)) for k, v in users.items()}
    mob = vp['width'] < 500
    ctx = b.new_context(viewport=vp, device_scale_factor=dsf, is_mobile=mob, has_touch=mob, color_scheme=scheme)
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
    pg.on('dialog', lambda d: (DIALOGS.append(d.message), d.accept() if ACCEPT[0] else d.dismiss()))
    all_errs.append(errs)
    pg.goto(LOCAL if local else URL); pg.wait_for_timeout(500)
    return ctx, pg, errs

w = lambda pg, ms=250: pg.wait_for_timeout(ms)
def tab(pg, name):
    pg.locator(f'button[data-tab="{name}"]:visible').first.click(); w(pg)
def store(pg):
    return pg.evaluate("Object.fromEntries(Object.keys(localStorage).map(k=>[k,localStorage.getItem(k)]))")
def sbs(pg):
    s = pg.evaluate("localStorage.getItem('bl.sb')"); return json.loads(s) if s else None
def lst(pg, k):
    return pg.evaluate("(k)=>JSON.parse(localStorage.getItem(k)||'null')", k)
def open_form(pg, which):
    """Open the log in or the create account form. A guest who has not taken the quiz can only be at the account step; a guest who has is in the app (Settings)."""
    if pg.evaluate("S.stage") == 'auth': pg.click(f'#full [data-act="{which}"]')
    else:
        tab(pg, 'Settings'); pg.click(f'#main [data-act="{which}"]')
    w(pg)
def fill_signup(pg, name, email, pw=PW, role=None, org=None):
    pg.fill('#a_name', name); pg.fill('#a_email', email); pg.fill('#a_pw', pw)
    if role: pg.locator('.role', has_text=ROLE_TXT[role]).click()
    if org is not None: pg.fill('#a_org', org)
def do_quiz(pg, ms=700):
    """From the required-quiz step: open the quiz, answer the four pages, wait for the app (Home)."""
    pg.click('#full [data-act="quiz"]'); w(pg, 200)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000)
    pg.evaluate("if(TOUR!==null)tourEnd()")   # a guest's first visit to Home starts the tour: close it so it does not cover the page
    w(pg, ms)
def logged_in_page(b, vp, fake, email, state=None, ttl=None, saved=None, known=None, adm=None, **kw):
    if email not in fake.users:
        fake.add_user(email, PW, {'name': email.split('@')[0].title(), 'role': 'Student', 'provider': False, 'org': ''})
    uid = fake.users[email]['id']
    sess = fake.session(uid, ttl)
    seed = fake.sb_seed(sess)
    if known: seed['known'] = known
    if adm is not None: seed['adm'] = adm   # what an earlier visit remembered about this person being an admin
    st = dict(state if state is not None else APP0, me=email)
    if saved: st['saved'] = saved
    u = {email: {'name': fake.profiles[uid]['name'], 'email': email, 'role': 'Student', 'provider': False, 'org': '', 'friends': [], 'sb': 1}}
    ctx, pg, errs = newpage(b, vp, fake, state=st, sb=seed, users=u, **kw)
    return ctx, pg, errs, uid, sess

D = {'width': 1440, 'height': 900}
P = {'width': 390, 'height': 844}

try:
  with sync_playwright() as p:
    b = p.chromium.launch()

    # ---------- S1: a guest never talks to Supabase ----------
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP)
    pg.locator('#main [data-act="save"]').first.click(); w(pg, 900)
    tab(pg, 'Settings'); txt = pg.locator('#main').inner_text()
    check('S1 a guest makes no requests to Supabase', len(fake.log) == 0, fake.log)
    check('S1 guest Settings says to create an account to keep answers on every device', 'Create an account to keep your quiz answers and saved items on every device' in txt, txt[:300])
    check('S1 no login stored for a guest', pg.evaluate("localStorage.getItem('bl.sb')") is None)
    pg.evaluate("act('quiz')"); w(pg)
    check('S1 quiz note for a guest in online mode', 'If you create an account, they’re saved to it.' in pg.locator('.note').inner_text(), pg.locator('.note').inner_text())
    ctx.close()

    # ---------- S2: sign up (a guest who finished the quiz and saved an item makes an account) ----------
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, dict(APP, saved={'school-001': True}))
    tab(pg, 'Settings'); pg.click('#main [data-act="signup"]'); w(pg)
    check('S2 sign-up form is shown', pg.locator('#a_name').count() == 1 and pg.locator('form#af').count() == 1)
    check('S2 autocomplete hints are set', pg.get_attribute('#a_name', 'autocomplete') == 'name' and pg.get_attribute('#a_email', 'autocomplete') == 'email' and pg.get_attribute('#a_pw', 'autocomplete') == 'new-password')
    check('S2 notice on the form says what is stored online', 'stored in your account' in pg.locator('.box').inner_text())
    check('S2 four kinds of account to pick from, Student chosen to begin with, each with a plain sentence about what changes',
          pg.locator('.role').count() == 4 and pg.get_attribute('input[name="a_who"]:checked', 'value') == 'Student' and all(len(pg.locator('.role small').nth(i).inner_text()) > 40 for i in range(4)), pg.locator('.role').count())
    check('S2 the organization box stays hidden until Organizer is picked', not pg.locator('#a_org').is_visible())
    fill_signup(pg, 'Ada Lovelace', 'Ada@Example.com', role='Teacher')
    check('S2 picking Teacher keeps the organization box hidden', not pg.locator('#a_org').is_visible())
    # double click must send one sign-up only, and the button shows it is working
    pg.evaluate("()=>{window.__p=act('dosignup');act('dosignup')}")
    lab = pg.evaluate("(()=>{const e=document.querySelector('[data-act=dosignup]');return e?e.innerText:'(gone)'})()")
    pg.wait_for_function("S.me&&S.stage==='prompt'", timeout=8000); w(pg, 600)
    check('S2 button said "Please wait…" while working', lab == 'Please wait…', lab)
    check('S2 only one sign-up request for a double click', len(fake.calls('POST', '/auth/v1/signup')) == 1, len(fake.calls('POST', '/auth/v1/signup')))
    su = fake.calls('POST', '/auth/v1/signup')[0]
    check('S2 sign-up body carries email, password and the profile details', su['body'] == {'email': 'ada@example.com', 'password': PW, 'data': {'name': 'Ada Lovelace', 'role': 'Teacher', 'provider': False, 'org': ''}}, su['body'])
    check('S2 sign-up request has no Authorization header', su['auth'] is None, su['auth'])
    uid = fake.users['ada@example.com']['id']
    rest = [c for c in fake.log if c['path'].startswith('/rest/')]
    check('S2 every data request carries the signed-in token and never the publishable key', rest and all(c['auth'] and c['auth'].startswith('Bearer at-') for c in rest), [c['auth'] for c in rest])
    check('S2 the fake service saw no rule broken', fake.violations == [], fake.violations)
    prof = fake.profiles.get(uid) or {}
    check('S2 profile row created with name, role and provider flag', (prof.get('name'), prof.get('role'), prof.get('is_provider')) == ('Ada Lovelace', 'Teacher', False) and not prof.get('org'), prof)
    check('S2 a new account starts empty: the quiz answers a guest made earlier do NOT go up with it', not prof.get('quiz_answers'), prof.get('quiz_answers'))
    check('S2 right after sign-up there is nothing matched yet: no answers, quiz not done, and the person is sent to the quiz step', pg.evaluate("[S.stage,S.done,JSON.stringify(S.ans)]") == ['prompt', False, '{}'], pg.evaluate("[S.stage,S.done,JSON.stringify(S.ans)]"))
    pt = pg.locator('#full').inner_text()
    check('S2 the quiz step is about the student (a teacher) and says nothing is matched yet', 'Take the quiz about the student.' in pt and 'Nothing is matched to the student yet.' in pt, pt[:300])
    check('S2 the quiz step has one big Take the quiz button and a Log out link, and no way to skip', pg.locator('#full [data-act="quiz"]').count() == 1 and pg.locator('#full [data-act="logout"]').count() == 1 and 'skip' not in pt.lower() and 'not now' not in pt.lower() and 'open the app' not in pt.lower(), pt)
    pg.click('#full [data-act="quiz"]'); w(pg, 300)
    qt_ = pg.locator('#full').inner_text()
    check('S2 the quiz asks about the student, not about “you”', 'What grade/year is the student in?' in qt_ and 'ZIP code does the student live in' in qt_ and 'TELL US ABOUT THE STUDENT' in qt_, qt_[:400])
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 1500)
    check('S2 finishing the quiz opens Home', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True], pg.evaluate("[S.stage,S.tab,S.done]"))
    check('S2 the answers made after signing up reach the account', (fake.profiles.get(uid) or {}).get('quiz_answers', {}).get('learn') == 'I like robotics, biology and helping people', fake.profiles.get(uid))
    check('S2 the guest saved item went up with the new account', fake.rows(uid, 'saved') == ['school-001'], fake.rows(uid))
    d = store(pg)
    check('S2 password is not stored anywhere in the browser', all(PW not in v for v in d.values()), [k for k, v in d.items() if PW in v])
    s = sbs(pg)
    check('S2 login saved on this device with ids and tokens', s and s['uid'] == uid and s['email'] == 'ada@example.com' and s['access'].startswith('at-') and s['refresh'].startswith('rt-'), s)
    check('S2 sync info up to date (known saved matches, answers clean)', s and s['known']['saved'] == ['school-001'] and s['dirty'] is False, s)
    u = lst(pg, 'bl.users').get('ada@example.com', {})
    check('S2 device copy of the account has no password hash and no quiz answers', 'pw' not in u and 'ans' not in u and u.get('sb') == 1, u)
    check('S2 after the quiz the app is shown (already seen the welcome)', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.me") == 'ada@example.com')
    tab(pg, 'Settings'); st = pg.locator('#main').inner_text()
    check('S2 Settings shows the account and the online-saving note', 'ada@example.com' in st and 'saved to your account' in st and 'Clear data on this device' in st, st[:400])
    pg.evaluate("act('quiz')"); w(pg)
    check('S2 quiz note for a signed-in person', 'saved to your account so they follow you to your other devices' in pg.locator('.note').inner_text(), pg.locator('.note').inner_text())
    pg.evaluate("S.stage='app';S.tab='School';render()"); w(pg)

    # ---------- S3: saving and un-saving goes online ----------
    n0 = len(fake.calls('POST', '/rest/v1/activity'))
    ids = [pg.locator('#main [data-act="save"]').nth(i).get_attribute('data-id') for i in (1, 2)]
    for i in (1, 2): pg.locator('#main [data-act="save"]').nth(i).click()
    w(pg, 1400)
    check('S3 two quick saves go up in one request', len(fake.calls('POST', '/rest/v1/activity')) == n0 + 1, len(fake.calls('POST', '/rest/v1/activity')) - n0)
    check('S3 the two saved items are online', all(i in fake.rows(uid, 'saved') for i in ids), (ids, fake.rows(uid)))
    last = fake.calls('POST', '/rest/v1/activity')[-1]
    check('S3 upsert uses on_conflict and merge-duplicates', 'on_conflict=user_id,opp_id,kind' in last['qs'] and 'resolution=merge-duplicates' in (last['prefer'] or ''), (last['qs'], last['prefer']))
    pg.locator(f'#main [data-act="save"][data-id="{ids[0]}"]').click(); w(pg, 1200)
    dl = fake.calls('DELETE', '/rest/v1/activity')
    check('S3 un-saving removes only that row online', ids[0] not in fake.rows(uid, 'saved') and ids[1] in fake.rows(uid, 'saved') and dl and f'opp_id=in.({ids[0]})' in dl[-1]['qs'] and 'kind=eq.saved' in dl[-1]['qs'], (fake.rows(uid), dl[-1]['qs'] if dl else None))
    first = pg.locator('#main .it2').first
    first.locator('[data-act="explore"]').click(); w(pg, 200)
    first.locator('[data-act="mine"]').click(); w(pg, 1300)
    check('S3 "I’m already in this" goes online as doing', len(fake.rows(uid, 'doing')) == 1, fake.rows(uid, 'doing'))
    s = sbs(pg)
    check('S3 device keeps track of what is online', set(s['known']['saved']) == set(fake.rows(uid, 'saved')) and set(s['known']['doing']) == set(fake.rows(uid, 'doing')), (s['known'], fake.rows(uid)))

    # ---------- S5: reload restores the login and brings in changes from another device ----------
    comm = pg.evaluate("DATA.community[0].id")
    fake.activity.append({'user_id': uid, 'opp_id': comm, 'kind': 'saved'})
    fake.profiles[uid]['quiz_answers'] = dict(ANS, learn='astronomy and rockets')
    nlog = len(fake.log)
    pg.reload(); pg.wait_for_function("S.saved&&S.saved['%s']" % comm, timeout=8000); w(pg, 500)
    check('S5 a saved item added on another device shows up here after reload', pg.evaluate("!!S.saved['%s']" % comm))
    check('S5 quiz answers from the account replace the old ones here', pg.evaluate("S.ans.learn") == 'astronomy and rockets', pg.evaluate("S.ans.learn"))
    check('S5 still signed in with no new login request', pg.evaluate("S.me") == 'ada@example.com' and not [c for c in fake.log[nlog:] if c['path'] == '/auth/v1/signup' or (c['path'] == '/auth/v1/token' and c['q'].get('grant_type') == 'password')])
    check('S5 a valid token is reused (no refresh needed)', not [c for c in fake.log[nlog:] if c['path'] == '/auth/v1/token'], [c['path'] for c in fake.log[nlog:]])
    check('S5 what was un-saved here stays un-saved', not pg.evaluate("!!S.saved['%s']" % ids[0]))

    # ---------- S6: log out wipes this device, not the account ----------
    nlog = len(fake.log)
    tab(pg, 'Settings'); pg.click('[data-act="logout"]'); w(pg, 800)
    lo = [c for c in fake.log[nlog:] if c['path'] == '/auth/v1/logout']
    check('S6 logging out tells Supabase (local scope, with the token)', len(lo) == 1 and lo[0]['q'].get('scope') == 'local' and (lo[0]['auth'] or '').startswith('Bearer at-'), lo)
    check('S6 login removed from this device', pg.evaluate("localStorage.getItem('bl.sb')") is None)
    check('S6 personal data wiped from this device', pg.evaluate("JSON.stringify([S.me,S.ans,S.done,S.saved,S.mine])") == '[null,{},false,{},{}]', pg.evaluate("JSON.stringify([S.me,S.ans,S.done,S.saved,S.mine])"))
    d = store(pg)
    check('S6 quiz text is gone from everything stored here', all('astronomy' not in v and 'biology' not in v for v in d.values()), [k for k, v in d.items() if 'astronomy' in v or 'biology' in v])
    check('S6 the account keeps its data online', len(fake.rows(uid)) >= 3 and fake.profiles[uid]['quiz_answers']['learn'] == 'astronomy and rockets')
    check('S6 after logging out the first screen is the account step, with a way back in', pg.evaluate("S.stage") == 'auth' and pg.locator('#full [data-act="login"]').count() == 1 and pg.locator('#full [data-act="signup"]').count() == 1, pg.evaluate("S.stage"))
    ctx.close()

    # ---------- S4: finishing the quiz while signed in sends the answers ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'quiz@example.com')
    check('S4 a signed-in account that has not taken the quiz is held at the quiz step', pg.evaluate("S.stage") == 'prompt', pg.evaluate("S.stage"))
    pg.click('#full [data-act="quiz"]'); w(pg)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 1500)
    qa = fake.profiles[uid]['quiz_answers']
    check('S4 quiz answers reached the account', qa and qa.get('learn') == 'I like robotics, biology and helping people' and qa.get('grade'), qa)
    check('S4 answers marked clean after sending', sbs(pg)['dirty'] is False, sbs(pg))
    check('S4 no quiz text kept in the device copy of the account', 'ans' not in lst(pg, 'bl.users')['quiz@example.com'], lst(pg, 'bl.users')['quiz@example.com'])
    check('S4 profile name and role not overwritten with blanks', fake.profiles[uid]['name'] == 'Quiz' and fake.profiles[uid]['role'] == 'Student', fake.profiles[uid])
    ctx.close()

    # ---------- S7: log in (wrong password, then right), Enter key ----------
    fake = Fake()
    uid = fake.add_user('grace@example.com', PW, {'name': 'Grace Hopper', 'role': 'Student', 'provider': False, 'org': ''})
    fake.profiles[uid]['quiz_answers'] = ANS
    fake.activity += [{'user_id': uid, 'opp_id': 'school-003', 'kind': 'saved'}, {'user_id': uid, 'opp_id': 'school-004', 'kind': 'doing'}]
    ctx, pg, errs = newpage(b, D, fake, APP0)
    check('S7 a guest who has not taken the quiz starts at the account step', pg.evaluate("S.stage") == 'auth', pg.evaluate("S.stage"))
    pg.click('#full [data-act="login"]'); w(pg)
    check('S7 login form has current-password hint and no name box', pg.get_attribute('#a_pw', 'autocomplete') == 'current-password' and pg.locator('#a_name').count() == 0)
    pg.fill('#a_email', 'Grace@Example.com'); pg.fill('#a_pw', 'wrongpass')
    pg.click('[data-act="dologin"]'); w(pg, 500)
    check('S7 wrong password shows a plain message in place', pg.locator('.err').inner_text() == 'Email or password is incorrect.', pg.locator('.err').inner_text())
    check('S7 typed email and password are still in the boxes after the error', pg.input_value('#a_email') == 'Grace@Example.com' and pg.input_value('#a_pw') == 'wrongpass')
    check('S7 button is usable again after the error', pg.locator('[data-act="dologin"]').is_enabled() and pg.locator('[data-act="dologin"]').inner_text() == 'Log in')
    pg.fill('#a_pw', PW); pg.press('#a_pw', 'Enter')
    pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 500)
    check('S7 Enter key logs in', pg.evaluate("S.me") == 'grace@example.com')
    check('S7 logging in lands on Home, with no quiz asked (the account already has its answers)', pg.evaluate("[S.stage,S.tab]") == ['app', 'Home'], pg.evaluate("[S.stage,S.tab]"))
    check('S7 quiz answers came from the account', pg.evaluate("S.done") is True and pg.evaluate("S.ans.learn") == 'biology and chemistry')
    check('S7 saved and doing items came from the account', pg.evaluate("!!S.saved['school-003']&&!!S.mine['school-004']"))
    check('S7 the error message is gone after logging in', pg.evaluate("S.err") == '')
    tab(pg, 'Settings'); check('S7 Settings shows no old error', pg.locator('#main .err').count() == 0)
    check('S7 login request had no Authorization header', fake.calls('POST', '/auth/v1/token')[-1]['auth'] is None)
    ctx.close()

    # ---------- S7b: a guest's quiz is NOT merged over an account that already has answers; items are combined ----------
    ctx, pg, errs = newpage(b, D, fake, dict(APP, ans=dict(ANS, learn='guest text'), saved={'school-009': True}))
    tab(pg, 'Settings'); pg.click('#main [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'grace@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]')
    pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 1500)
    check('S7b the account quiz answers win over what a guest typed', pg.evaluate("S.ans.learn") == 'biology and chemistry', pg.evaluate("S.ans.learn"))
    check('S7b saved items from both are kept and the guest one goes online', pg.evaluate("!!S.saved['school-003']&&!!S.saved['school-009']") and 'school-009' in fake.rows(uid, 'saved'), fake.rows(uid))
    ctx.close()

    # ---------- S8: error messages and odd cases ----------
    fake = Fake(); fake.add_user('taken@example.com', PW)
    ctx, pg, errs = newpage(b, D, fake, APP0)
    pg.click('#full [data-act="signup"]'); w(pg)
    pg.fill('#a_name', 'Tom'); pg.fill('#a_email', 'taken@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dosignup"]'); w(pg, 600)
    check('S8 existing email gets a friendly message', pg.locator('.err').inner_text() == 'That email already has an account. Try logging in.', pg.locator('.err').inner_text())
    check('S8 typed name, email and password are kept', pg.input_value('#a_name') == 'Tom' and pg.input_value('#a_email') == 'taken@example.com' and pg.input_value('#a_pw') == PW)
    fake.min_pw = 8
    pg.fill('#a_email', 'new@example.com'); pg.click('[data-act="dosignup"]'); w(pg, 600)
    check('S8 a stricter password rule from the server is shown as the server says it', pg.locator('.err').inner_text() == 'Password should be at least 8 characters.', pg.locator('.err').inner_text())
    fake.min_pw = 6
    pg.fill('#a_pw', '123'); pg.click('[data-act="dosignup"]'); w(pg, 300)
    n_before = len(fake.calls('POST', '/auth/v1/signup'))
    check('S8 a too-short password is stopped here without a request', 'password of 6+ characters' in pg.locator('.err').inner_text() and n_before == 2, (pg.locator('.err').inner_text(), n_before))
    pg.fill('#a_pw', PW); fake.fail = 'net'; pg.click('[data-act="dosignup"]'); w(pg, 700)
    check('S8 no internet gives a plain message', pg.locator('.err').inner_text() == 'Can’t reach the server. Check your internet and try again.', pg.locator('.err').inner_text())
    check('S8 form is kept and the button works again after no internet', pg.input_value('#a_name') == 'Tom' and pg.locator('[data-act="dosignup"]').is_enabled() and pg.locator('[data-act="dosignup"]').inner_text() == 'Create account')
    fake.fail = '429'; pg.click('[data-act="dosignup"]'); w(pg, 600)
    check('S8 too many tries gives a plain message', 'Too many tries' in pg.locator('.err').inner_text(), pg.locator('.err').inner_text())
    fake.fail = None
    pg.click('[data-act="login"]'); w(pg)
    check('S8 switching to log in keeps the typed email', pg.input_value('#a_email') == 'new@example.com', pg.input_value('#a_email'))
    ctx.close()

    # confirm-email switched on
    fake = Fake(); fake.confirm = True
    ctx, pg, errs = newpage(b, D, fake, APP0)
    pg.click('#full [data-act="signup"]'); w(pg)
    pg.fill('#a_name', 'Cy'); pg.fill('#a_email', 'cy@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dosignup"]'); w(pg, 800)
    check('S8 when email confirmation is on, the person is told to check email and sent to log in', pg.evaluate("S.stage") == 'login' and 'emailed you a link' in pg.locator('.inf').inner_text() and pg.input_value('#a_email') == 'cy@example.com', pg.locator('.box').inner_text()[:200])
    check('S8 nothing logged in yet when confirmation is needed', pg.evaluate("S.me") is None and pg.evaluate("localStorage.getItem('bl.sb')") is None)
    pg.fill('#a_pw', PW); pg.fill('#a_email', 'nobody@example.com'); pg.click('[data-act="dologin"]'); w(pg, 600)
    check('S8 the notice stays while the person is still trying to log in', pg.locator('.inf').count() == 1 and pg.locator('.err').inner_text() == 'Email or password is incorrect.')
    pg.click('[data-act="signup"]'); w(pg)
    check('S8 the notice goes away when the screen changes', pg.locator('.inf').count() == 0)
    ctx.close()

    # ---------- S9: tokens: refresh when expired, retry once on 401, share one refresh ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'tok@example.com', state=APP, ttl=-100)
    fake.activity.append({'user_id': uid, 'opp_id': 'school-005', 'kind': 'saved'})
    pg.reload(); pg.wait_for_function("S.saved&&S.saved['school-005']", timeout=8000); w(pg, 500)
    tk = fake.calls('POST', '/auth/v1/token')
    check('S9 an expired token is refreshed first (one refresh, no Authorization header)', len(tk) == 1 and tk[0]['q'].get('grant_type') == 'refresh_token' and tk[0]['body'] == {'refresh_token': sess['refresh_token']} and tk[0]['auth'] is None, tk)
    s = sbs(pg)
    check('S9 the new token and the new refresh token are saved', s and s['refresh'] != sess['refresh_token'] and s['access'] != sess['access_token'] and s['exp'] > time.time() + 3000, s)
    rest = [c for c in fake.log if c['path'].startswith('/rest/')]
    check('S9 data requests used the new token', rest and all(c['auth'] == 'Bearer ' + s['access'] for c in rest), [c['auth'] for c in rest])
    check('S9 still the same person after the refresh', pg.evaluate("S.me") == 'tok@example.com')
    n = len(fake.log); fake.expire_now()   # every request that still carries the old token gets 401, in any order
    pg.reload(); w(pg, 1500)
    tk = [c for c in fake.log[n:] if c['path'] == '/auth/v1/token']
    check('S9 two requests that both get 401 share one refresh', len(tk) == 1, len(tk))
    check('S9 after the 401s the data still loads and the person is still signed in', pg.evaluate("S.me") == 'tok@example.com' and pg.evaluate("!!S.saved['school-005']"))
    ctx.close()

    # ---------- S10: a login that can no longer be refreshed ends politely ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'dead@example.com', state=APP, ttl=-100)
    pg.evaluate("(()=>{const s=JSON.parse(localStorage.getItem('bl.sb'));s.exp=1;s.refresh='rt-gone';localStorage.setItem('bl.sb',JSON.stringify(s))})()")
    pg.reload(); w(pg, 1500)
    check('S10 the person is logged out here', pg.evaluate("S.me") is None and pg.evaluate("localStorage.getItem('bl.sb')") is None)
    check('S10 personal data is cleared from this device', pg.evaluate("JSON.stringify([S.ans,S.done,S.saved,S.mine])") == '[{},false,{},{}]', pg.evaluate("JSON.stringify([S.ans,S.done,S.saved,S.mine])"))
    check('S10 they land on the log in screen with a plain message', pg.evaluate("S.stage") == 'login' and pg.locator('.inf').inner_text() == 'Your login ended. Please log in again.', (pg.evaluate("S.stage"), pg.locator('.box').inner_text()[:150]))
    ctx.close()

    # ---------- S10b: a device-only login from before accounts were online is not kept ----------
    fake = Fake()
    old_users = {'legacy@example.com': {'name': 'Old', 'email': 'legacy@example.com', 'pw': 'abc', 'role': 'Student', 'provider': False, 'org': '', 'friends': []}}
    ctx, pg, errs = newpage(b, D, fake, dict(APP, me='legacy@example.com'), users=old_users)
    check('S10b an old device-only login becomes a guest in online mode', pg.evaluate("S.me") is None and len(fake.log) == 0, pg.evaluate("S.me"))
    ctx.close()

    # ---------- S11: offline, then back online ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'off@example.com', state=APP)
    w(pg, 900)
    fake.fail = 'net'
    sid = pg.locator('#main [data-act="save"]').first.get_attribute('data-id')
    pg.locator('#main [data-act="save"]').first.click(); w(pg, 1500)
    check('S11 offline: the save still works here', pg.evaluate("!!S.saved['%s']" % sid))
    check('S11 offline: the device knows it has not been sent', pg.evaluate("sbPending()") is True and sid not in sbs(pg)['known']['saved'])
    check('S11 offline: still signed in', pg.evaluate("S.me") == 'off@example.com')
    tab(pg, 'Settings'); check('S11 offline: Settings says some changes have not reached the account', 'haven’t reached it yet' in pg.locator('#main').inner_text(), pg.locator('#main').inner_text()[-300:])
    pg.reload(); w(pg, 1200)
    check('S11 reload while offline keeps the login and the unsent save', pg.evaluate("S.me") == 'off@example.com' and pg.evaluate("!!S.saved['%s']" % sid) and pg.evaluate("sbPending()") is True)
    fake.fail = None
    pg.evaluate("dispatchEvent(new Event('online'))"); w(pg, 2000)
    check('S11 back online: the pending save goes up', sid in fake.rows(uid, 'saved'), fake.rows(uid))
    check('S11 back online: nothing left pending', pg.evaluate("sbPending()") is False)
    # removed here while offline, still online -> deleted online after reconnect
    fake.activity.append({'user_id': uid, 'opp_id': 'school-007', 'kind': 'saved'})
    pg.evaluate("sbPull()"); w(pg, 1200)
    check('S11 a save made on another device appears here', pg.evaluate("!!S.saved['school-007']"))
    fake.fail = 'net'
    pg.evaluate("S.saved['school-007']=false;sbQueue()"); w(pg, 1500)
    check('S11 un-save while offline is remembered', pg.evaluate("sbPending()") is True and 'school-007' in fake.rows(uid, 'saved'))
    fake.fail = None
    pg.reload(); w(pg, 2200)
    check('S11 after reload the un-save is not undone by the older online copy', not pg.evaluate("!!S.saved['school-007']") and 'school-007' not in fake.rows(uid, 'saved'), (pg.evaluate("S.saved"), fake.rows(uid)))
    ctx.close()

    # ---------- S11b: offline at the moment of logging in ----------
    fake = Fake(); fake.add_user('late@example.com', PW)
    ctx, pg, errs = newpage(b, D, fake, APP0)
    pg.click('#full [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'late@example.com'); pg.fill('#a_pw', PW)
    pg.evaluate("()=>{window.__fn=0}")
    # let the login work but fail the data requests afterwards
    orig = fake.handler
    def flaky(route, request):
        if request.url.endswith('/auth/v1/token?grant_type=password') or request.method == 'OPTIONS' and 'auth' in request.url:
            return orig(route, request)
        if '/rest/' in request.url and request.method != 'OPTIONS':
            return route.abort('failed')
        return orig(route, request)
    ctx.unroute(SBRE); ctx.route(SBRE, flaky)
    pg.click('[data-act="dologin"]'); w(pg, 1500)
    check('S11b login works even if loading the account data fails', pg.evaluate("S.me") == 'late@example.com' and pg.evaluate("S.stage") == 'app')
    check('S11b the device remembers to load the account data later', pg.evaluate("sbNeedPull") is True)
    ht = pg.locator('#main').inner_text()
    check('S11b the person is not pushed into the quiz just because the data did not load: Home says the account has not finished loading', pg.evaluate("S.tab") == 'Home' and 'hasn’t finished loading' in ht and pg.locator('#main [data-act="quiz"]').count() == 0, ht[:300])
    ctx.unroute(SBRE); ctx.route(SBRE, orig)
    pg.evaluate("dispatchEvent(new Event('online'))"); w(pg, 1500)
    check('S11b back online it loads the account data', pg.evaluate("sbNeedPull") is False)
    check('S11b and once it is loaded and the account has no quiz answers, the quiz step comes up', pg.evaluate("S.stage") == 'prompt', pg.evaluate("S.stage"))
    ctx.close()

    # ---------- S12: delete account ----------
    for rpc in (False, True):
        fake = Fake(); fake.rpc = rpc
        ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'del@example.com', state=APP)
        fake.activity += [{'user_id': uid, 'opp_id': 'school-001', 'kind': 'saved'}]
        pg.reload(); w(pg, 1000)
        tab(pg, 'Settings'); DIALOGS.clear(); ACCEPT[0] = False
        pg.click('[data-act="del"]'); w(pg, 500)
        nreq = len(fake.calls(None, '/rpc/delete_my_account')) + len(fake.calls('DELETE'))
        check(f'S12 rpc={rpc} cancelling the question deletes nothing', pg.evaluate("S.me") == 'del@example.com' and nreq == 0 and 'del@example.com' in fake.users and 'delete your account' in DIALOGS[0].lower(), (DIALOGS, nreq))
        ACCEPT[0] = True
        pg.click('[data-act="del"]'); pg.wait_for_function("S.me===null", timeout=8000); w(pg, 600)
        rp = fake.calls('POST', '/rpc/delete_my_account')
        check(f'S12 rpc={rpc} the delete function is called with the token', len(rp) == 1 and (rp[0]['auth'] or '').startswith('Bearer at-'), rp)
        check(f'S12 rpc={rpc} afterwards logged out, data cleared here, and back at the account step', pg.evaluate("S.me") is None and pg.evaluate("localStorage.getItem('bl.sb')") is None and pg.evaluate("S.stage") == 'auth')
        txt = pg.locator('#full .inf').inner_text() if pg.locator('#full .inf').count() else ''
        if rpc:
            check('S12 rpc=True the account is gone online and says so', 'del@example.com' not in fake.users and txt == 'Your account was deleted.', (list(fake.users), txt))
        else:
            check('S12 rpc=False data rows deleted online, login kept, and it says so honestly', uid not in fake.profiles and fake.rows(uid) == [] and 'del@example.com' in fake.users and 'Removing the login itself is not switched on yet' in txt, (fake.profiles.keys(), fake.rows(uid), txt))
        check(f'S12 rpc={rpc} the notice goes away when the person moves on', (lambda: (pg.click('#full [data-act="login"]'), w(pg, 200), pg.locator('.inf').count() == 0)[2])())
        ctx.close()

    # ---------- S13: clear data on this device while signed in ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'clr@example.com', state=APP, saved={'school-002': True}, known={'saved': ['school-002'], 'doing': []})
    fake.activity.append({'user_id': uid, 'opp_id': 'school-002', 'kind': 'saved'})
    tab(pg, 'Settings'); DIALOGS.clear(); ACCEPT[0] = True
    pg.click('[data-act="clear"]'); w(pg, 1500)
    check('S13 clearing asks first and says the account stays online', DIALOGS and 'account and its saved items stay online' in DIALOGS[0], DIALOGS)
    check('S13 the login is gone from this device after clearing', pg.evaluate("localStorage.getItem('bl.sb')") is None and pg.evaluate("S.me") is None)
    check('S13 the account still has its data online', fake.rows(uid) == ['school-002'] and len(fake.calls('POST', '/auth/v1/logout')) == 1, (fake.rows(uid), len(fake.calls('POST', '/auth/v1/logout'))))
    ctx.close()

    # ---------- S14: with no Supabase address everything still works on this device ----------
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP, local=True)
    tab(pg, 'Settings'); st = pg.locator('#main').inner_text()
    check('S14 local mode says everything is saved on this device only', 'Everything is saved on this device only.' in st and 'Create an account to keep' not in st, st[:300])
    ctx.close()
    ctx, pg, errs = newpage(b, D, fake, APP0, local=True)
    check('S14 local mode: a guest who has not taken the quiz starts at the account step, which says accounts are saved on this device', pg.evaluate("S.stage") == 'auth' and 'Guest and email accounts are saved on this device' in pg.locator('#full').inner_text(), pg.evaluate("S.stage"))
    pg.click('#full [data-act="signup"]'); w(pg)
    check('S14 local sign-up page keeps the prototype note', 'Prototype: accounts, friends and messages are saved on this device' in pg.locator('.box').inner_text())
    pg.fill('#a_name', 'Local Lee'); pg.fill('#a_email', 'lee@example.com'); pg.fill('#a_pw', PW); pg.press('#a_pw', 'Enter')
    pg.wait_for_function("S.me==='lee@example.com'", timeout=5000); w(pg, 400)
    u = lst(pg, 'bl.users')['lee@example.com']
    check('S14 Enter key creates a device-only account with a password hash', len(u['pw']) == 64 and 'sb' not in u and PW not in json.dumps(store(pg)))
    check('S14 the new device-only account starts empty and is sent to the quiz step', pg.evaluate("[S.stage,S.done,JSON.stringify(S.ans)]") == ['prompt', False, '{}'], pg.evaluate("[S.stage,S.done,JSON.stringify(S.ans)]"))
    do_quiz(pg)
    check('S14 after the quiz the account lands on Home and keeps its answers on this device', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True] and 'ans' in lst(pg, 'bl.users')['lee@example.com'], pg.evaluate("[S.stage,S.tab,S.done]"))
    check('S14 local mode makes no requests', len(fake.log) == 0, fake.log)
    tab(pg, 'Settings'); pg.click('[data-act="logout"]'); w(pg, 500)
    check('S14 logging out goes back to the account step and clears the answers from memory', pg.evaluate("[S.stage,S.done,JSON.stringify(S.ans)]") == ['auth', False, '{}'], pg.evaluate("[S.stage,S.done]"))
    pg.click('#full [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'lee@example.com'); pg.fill('#a_pw', 'nope'); pg.click('[data-act="dologin"]'); w(pg, 400)
    check('S14 local wrong password shows the message in place and keeps the typed email', pg.locator('.err').inner_text() == 'Email or password is incorrect.' and pg.input_value('#a_email') == 'lee@example.com')
    pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 500)
    check('S14 local log in works, lands on Home and the quiz answers are back (no second quiz)', pg.evaluate("S.me") == 'lee@example.com' and pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True], pg.evaluate("[S.stage,S.tab,S.done]"))
    pg.evaluate("act('quiz')"); w(pg)
    check('S14 local quiz note is the old one', 'not sent to a server' in pg.locator('.note').inner_text())
    ACCEPT[0] = True; DIALOGS.clear()
    pg.evaluate("S.stage='app';S.tab='Settings';render()"); w(pg)
    pg.click('[data-act="del"]'); w(pg, 500)
    check('S14 local delete still asks about this device and removes the account', DIALOGS and 'on this device' in DIALOGS[0] and 'lee@example.com' not in lst(pg, 'bl.users'), (DIALOGS, lst(pg, 'bl.users')))
    check('S14 after deleting, the person is back at the account step', pg.evaluate("S.stage") == 'auth')
    ctx.close()

    # ---------- S15: the Sign up button in the top bar (guests only) ----------
    HDR = """(()=>{const kids=[...document.querySelectorAll('.hd .in > *')].filter(e=>e.getBoundingClientRect().width>0).map(e=>{const b=e.getBoundingClientRect();return{c:e.id||e.className||e.tagName,l:b.left,r:b.right,t:b.top,b:b.bottom}});
      const ov=[];for(let i=0;i<kids.length;i++)for(let j=i+1;j<kids.length;j++){const a=kids[i],c=kids[j];if(a.l<c.r-1&&c.l<a.r-1&&a.t<c.b-1&&c.t<a.b-1)ov.push(a.c+' x '+c.c)}
      return{kids,ov,sw:document.documentElement.scrollWidth,iw:innerWidth,hh:document.querySelector('.hd').getBoundingClientRect().height}})()"""
    fake = Fake()
    for label, vp in (('desktop', D), ('phone', P), ('narrow', {'width': 320, 'height': 700}), ('tablet', {'width': 800, 'height': 900})):
        ctx, pg, errs = newpage(b, vp, fake, dict(APP, tab='Explore'))
        btn = pg.locator('#hacct')
        check(f'S15 {label}: a guest sees a Sign up button in the top bar', btn.is_visible() and btn.inner_text() == 'Sign up' and btn.evaluate("e=>e.tagName") == 'BUTTON', btn.inner_text())
        g = pg.evaluate(HDR)
        hb = {k['c']: k for k in g['kids']}
        gear = hb.get('gb'); ha = hb.get('hacct')
        check(f'S15 {label}: it sits right next to the Settings (theme) button', ha and gear and 0 <= gear['l'] - ha['r'] <= 20 and abs((ha['t'] + ha['b']) / 2 - (gear['t'] + gear['b']) / 2) < 3, (ha, gear))
        check(f'S15 {label}: nothing in the top bar overlaps and the page does not scroll sideways', g['ov'] == [] and g['sw'] <= g['iw'], (g['ov'], g['sw'], g['iw']))
        hh_guest = g['hh']
        ctx.close()
        fake2 = Fake()
        ctx, pg, errs, uid, sess = logged_in_page(b, vp, fake2, f'hdr-{label}@example.com', state=dict(APP, tab='Explore'))
        w(pg, 500)
        g2 = pg.evaluate(HDR)
        check(f'S15 {label}: a signed-in person does not see it', not pg.locator('#hacct').is_visible() and pg.evaluate("document.getElementById('hacct').hidden") is True)
        check(f'S15 {label}: the top bar is the same height with or without the button', abs(g2['hh'] - hh_guest) < 1.5 and g2['ov'] == [], (g2['hh'], hh_guest, g2['ov']))
        ctx.close()

    fake = Fake()
    ctx, pg, errs = newpage(b, P, fake, dict(APP, tab='Explore'))
    pg.click('#hacct'); w(pg)
    check('S15 clicking it opens the Create your account form', pg.evaluate("S.stage") == 'signup' and pg.locator('h1').inner_text() == 'Create your account' and pg.locator('form#af').count() == 1)
    check('S15 the form also offers Log in for people who already have an account', pg.locator('#full [data-act="login"]').count() == 1)
    check('S15 the top bar is hidden while the form is open', not pg.locator('#hacct').is_visible())
    pg.click('#full [data-act="back2"]'); w(pg, 700)
    check('S15 Back from the form returns to the same tab', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.tab") == 'Explore' and pg.locator('#hacct').is_visible(), (pg.evaluate("S.stage"), pg.evaluate("S.tab")))
    pg.click('#hacct'); w(pg)
    pg.go_back(); w(pg, 600)
    check('S15 the browser Back button also returns from the form', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.tab") == 'Explore', (pg.evaluate("S.stage"), pg.evaluate("S.tab")))
    pg.focus('#hacct'); pg.keyboard.press('Enter'); w(pg)
    check('S15 the button works from the keyboard (Tab, then Enter)', pg.evaluate("S.stage") == 'signup')
    pg.fill('#a_name', 'Hedy Lamarr'); pg.fill('#a_email', 'hedy@example.com'); pg.fill('#a_pw', PW)
    pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.me&&S.stage==='prompt'", timeout=8000); w(pg, 600)
    check('S15 after signing up the person is at the quiz step, where there is no top bar', pg.evaluate("S.me") == 'hedy@example.com' and not pg.locator('#hacct').is_visible())
    do_quiz(pg)
    check('S15 once in the app the Sign up button is gone from the top bar', not pg.locator('#hacct').is_visible() and pg.evaluate("document.getElementById('hacct').hidden") is True)
    tab(pg, 'Settings'); pg.click('[data-act="logout"]'); w(pg, 800)
    check('S15 after logging out the person is back at the account step', pg.evaluate("S.stage") == 'auth')
    ctx.close()

    # a guest who just did the quiz can sign up from the top bar and keeps the answers
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP0)
    check('S15 a guest who has not taken the quiz starts at the account step', pg.evaluate("S.stage") == 'auth')
    pg.click('#full [data-act="guest"]'); w(pg)
    check('S15 "Continue as a guest" leads to the required quiz step (still no way to skip it)', pg.evaluate("S.stage") == 'prompt' and pg.locator('#full [data-act="quiz"]').count() == 1)
    do_quiz(pg, 500)
    check('S15 a guest who finished the quiz sees the Sign up button and has made no request', pg.locator('#hacct').is_visible() and len(fake.log) == 0, len(fake.log))
    pg.click('#hacct'); w(pg)
    pg.fill('#a_name', 'Quiz Guest'); pg.fill('#a_email', 'qg@example.com'); pg.fill('#a_pw', PW)
    pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.me&&S.stage==='prompt'", timeout=8000); w(pg, 1500)
    prof = fake.profiles.get(fake.users['qg@example.com']['id']) or {}
    check('S15 the new account starts empty: the guest’s answers are not put into it, and the person is asked to take the quiz', not prof.get('quiz_answers') and pg.evaluate("[S.done,JSON.stringify(S.ans)]") == [False, '{}'], prof)
    ctx.close()

    # with no Supabase address the button still works (device-only accounts)
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP, local=True)
    check('S15 local mode: guests see the button too', pg.locator('#hacct').is_visible())
    pg.click('#hacct'); w(pg)
    check('S15 local mode: it opens the same form with the prototype note', pg.evaluate("S.stage") == 'signup' and 'Prototype: accounts' in pg.locator('.box').inner_text())
    ctx.close()

    # ---------- S17: change password ----------
    NEWPW = 'brand-new-pw'
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'pw@example.com', state=dict(APP, tab='Settings'))
    w(pg, 500)
    check('S17 signed-in Settings has a Change password button', pg.locator('#main [data-act="chpw"]').count() == 1 and pg.locator('#main [data-act="chpw"]').inner_text() == 'Change password')
    ctx.close()
    ctx, pg, errs = newpage(b, D, Fake(), dict(APP, tab='Settings'))
    check('S17 a guest has no Change password button', pg.locator('[data-act="chpw"]').count() == 0)
    pg.evaluate("act('chpw')"); w(pg)
    check('S17 a guest cannot open the screen by calling it directly', pg.evaluate("S.stage") == 'app')
    ctx.close()
    ctx, pg, errs = newpage(b, D, Fake(), dict(APP, tab='Settings'), local=True)
    check('S17 in device-only mode there is no Change password button', pg.locator('[data-act="chpw"]').count() == 0)
    ctx.close()

    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'pw@example.com', state=dict(APP, tab='Settings'))
    w(pg, 500)
    pg.click('#main [data-act="chpw"]'); w(pg)
    check('S17 the button opens the Change your password screen', pg.evaluate("S.stage") == 'chpw' and pg.locator('h1').inner_text() == 'Change your password')
    check('S17 the screen names the account email so the person knows what to log in with', 'pw@example.com' in pg.locator('.box p').first.inner_text(), pg.locator('.box p').first.inner_text())
    check('S17 both boxes are password boxes with the new-password hint for password managers', pg.get_attribute('#p_new', 'type') == 'password' and pg.get_attribute('#p_new2', 'type') == 'password' and pg.get_attribute('#p_new', 'autocomplete') == 'new-password' and pg.get_attribute('#p_new2', 'autocomplete') == 'new-password')
    check('S17 a hidden username field helps password managers update the right login', pg.evaluate("(()=>{const u=document.querySelector('#af input[autocomplete=username]');return !!u&&u.value==='pw@example.com'&&u.hidden})()"))
    check('S17 the top bar is hidden while the screen is open', not pg.locator('#hacct').is_visible() and pg.evaluate("document.body.classList.contains('full')"))
    # Show / Hide
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW)
    pg.click('[data-act="showpw"]'); w(pg, 100)
    check('S17 Show passwords reveals both boxes and keeps what was typed', pg.get_attribute('#p_new', 'type') == 'text' and pg.get_attribute('#p_new2', 'type') == 'text' and pg.input_value('#p_new') == NEWPW and pg.locator('[data-act="showpw"]').inner_text() == 'Hide passwords')
    pg.click('[data-act="showpw"]'); w(pg, 100)
    check('S17 Hide passwords hides them again', pg.get_attribute('#p_new', 'type') == 'password' and pg.locator('[data-act="showpw"]').inner_text() == 'Show passwords' and pg.input_value('#p_new2') == NEWPW)
    # mistakes caught here, with no request
    n0 = len(fake.calls('PUT', '/auth/v1/user'))
    pg.fill('#p_new', 'abc'); pg.fill('#p_new2', 'abc'); pg.click('[data-act="dochpw"]'); w(pg, 200)
    check('S17 a password under 6 characters is stopped here with a plain message', pg.locator('.err').inner_text() == 'Choose a new password of 6+ characters.', pg.locator('.err').inner_text())
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', ''); pg.click('[data-act="dochpw"]'); w(pg, 200)
    check('S17 an empty second box asks to type it again', pg.locator('.err').inner_text() == 'Type the new password again.', pg.locator('.err').inner_text())
    pg.fill('#p_new2', NEWPW + 'x'); pg.click('[data-act="dochpw"]'); w(pg, 200)
    check('S17 two different passwords are stopped here', pg.locator('.err').inner_text() == 'The two passwords don’t match.', pg.locator('.err').inner_text())
    check('S17 typed passwords are kept after a mistake', pg.input_value('#p_new') == NEWPW and pg.input_value('#p_new2') == NEWPW + 'x')
    check('S17 none of those mistakes made a request', len(fake.calls('PUT', '/auth/v1/user')) == n0, len(fake.calls('PUT', '/auth/v1/user')) - n0)
    # same password as now: the server says no
    pg.fill('#p_new', PW); pg.fill('#p_new2', PW); pg.click('[data-act="dochpw"]'); w(pg, 500)
    check('S17 the current password again gets a friendly message from the server', pg.locator('.err').inner_text() == 'That’s already your password. Choose a different one.' and fake.users['pw@example.com']['pw'] == PW, pg.locator('.err').inner_text())
    check('S17 the button works again after an error', pg.locator('[data-act="dochpw"]').is_enabled() and pg.locator('[data-act="dochpw"]').inner_text() == 'Change password')
    # a stricter server rule is shown as the server says it
    fake.min_pw = 10
    pg.fill('#p_new', 'short-ish'); pg.fill('#p_new2', 'short-ish'); pg.click('[data-act="dochpw"]'); w(pg, 500)
    check('S17 a stricter password rule from the server is shown as the server says it', pg.locator('.err').inner_text() == 'Password should be at least 10 characters.', pg.locator('.err').inner_text())
    fake.min_pw = 6
    # no internet
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW); fake.fail = 'net'; pg.click('[data-act="dochpw"]'); w(pg, 800)
    check('S17 no internet gives a plain message and keeps the typed passwords', pg.locator('.err').inner_text() == 'Can’t reach the server. Check your internet and try again.' and pg.input_value('#p_new') == NEWPW and fake.users['pw@example.com']['pw'] == PW, pg.locator('.err').inner_text())
    fake.fail = None
    # login too old for "secure password change"
    fake.reauth = True; pg.click('[data-act="dochpw"]'); w(pg, 500)
    check('S17 when the server wants a fresh login, it says to log out and log in again', pg.locator('.err').inner_text() == 'For your safety, log out and log in again, then change your password.' and fake.users['pw@example.com']['pw'] == PW, pg.locator('.err').inner_text())
    fake.reauth = False
    # success, with a double click
    n0 = len(fake.calls('PUT', '/auth/v1/user'))
    lab = pg.evaluate("()=>{window.__p=act('dochpw');act('dochpw');const b=document.querySelector('[data-act=\"dochpw\"]');return b?b.textContent:'(gone)'}")
    pg.wait_for_function("document.querySelector('h1')&&document.querySelector('h1').textContent==='Password changed'", timeout=8000); w(pg, 300)
    puts = fake.calls('PUT', '/auth/v1/user')[n0:]
    check('S17 the button said "Please wait…" while working', lab == 'Please wait…', lab)
    check('S17 one request for a double click', len(puts) == 1, len(puts))
    check('S17 the request is a PUT of just the new password with the signed-in token and no other credentials', puts[0]['body'] == {'password': NEWPW} and (puts[0]['auth'] or '').startswith('Bearer at-') and puts[0]['auth'] != 'Bearer ' + KEY, (puts[0]['body'], puts[0]['auth']))
    check('S17 the fake service saw no rule broken', fake.violations == [], fake.violations)
    check('S17 the account password is now the new one', fake.users['pw@example.com']['pw'] == NEWPW and fake.pw_changes == ['pw@example.com'], fake.pw_changes)
    check('S17 the success screen says so and shows the email', pg.locator('h1').inner_text() == 'Password changed' and 'pw@example.com' in pg.locator('.box').inner_text() and pg.locator('#p_new').count() == 0, pg.locator('.box').inner_text())
    d = store(pg)
    check('S17 the new password is not kept anywhere in the browser', all(NEWPW not in v and PW not in v for v in d.values()), [k for k, v in d.items() if NEWPW in v or PW in v])
    check('S17 the person is still logged in here, with the same login', pg.evaluate("S.me") == 'pw@example.com' and sbs(pg)['uid'] == uid and not fake.calls('POST', '/auth/v1/token'))
    pg.click('[data-act="back2"]'); w(pg, 800)
    check('S17 Done goes back to Settings (the one before the screen)', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.tab") == 'Settings' and pg.locator('#main h1').inner_text() == 'Settings', (pg.evaluate("S.stage"), pg.evaluate("S.tab")))
    ctx.close()

    # the old password stops working and the new one works, from a fresh browser (like another device)
    ctx, pg, errs = newpage(b, D, fake, APP0)
    pg.click('#full [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'pw@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 500)
    check('S17 the old password no longer logs in', pg.locator('.err').inner_text() == 'Email or password is incorrect.' and pg.evaluate("S.me") is None, pg.locator('.err').inner_text())
    pg.fill('#a_pw', NEWPW); pg.click('[data-act="dologin"]'); pg.wait_for_function("S.me==='pw@example.com'", timeout=8000); w(pg, 500)
    check('S17 the new password logs in on another device', pg.evaluate("S.me") == 'pw@example.com')
    ctx.close()

    # back out without changing anything, and the browser Back button
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'back@example.com', state=dict(APP, tab='Settings'))
    w(pg, 500)
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW)
    pg.click('#full [data-act="back2"]'); w(pg, 800)
    check('S17 the Back link returns to Settings and changes nothing', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.tab") == 'Settings' and not fake.calls('PUT', '/auth/v1/user') and fake.users['back@example.com']['pw'] == PW)
    pg.click('#main [data-act="chpw"]'); w(pg)
    check('S17 opening it again starts with empty boxes', pg.input_value('#p_new') == '' and pg.input_value('#p_new2') == '')
    pg.go_back(); w(pg, 600)
    check('S17 the browser Back button leaves the screen', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.tab") == 'Settings', (pg.evaluate("S.stage"), pg.evaluate("S.tab")))
    # Enter key submits
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW); pg.press('#p_new2', 'Enter')
    pg.wait_for_function("document.querySelector('h1')&&document.querySelector('h1').textContent==='Password changed'", timeout=8000)
    check('S17 the Enter key changes the password', fake.users['back@example.com']['pw'] == NEWPW)
    ctx.close()

    # reload on the screen keeps it; a reload with no login falls back to the app
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'rel@example.com', state=dict(APP, tab='Settings'))
    w(pg, 500)
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.reload(); w(pg, 800)
    check('S17 reloading on the screen shows the empty form again (still logged in)', pg.evaluate("S.stage") == 'chpw' and pg.locator('#p_new').count() == 1 and pg.evaluate("S.me") == 'rel@example.com')
    hl = pg.evaluate("history.length")
    pg.evaluate("localStorage.removeItem('bl.sb')"); pg.reload(); w(pg, 800)
    check('S17 reloading on the screen with no login adds no extra Back-button step', pg.evaluate("history.length") == hl, (hl, pg.evaluate("history.length")))
    check('S17 reloading on the screen with no login falls back to the app, not a blank page', pg.evaluate("S.stage") == 'app' and pg.locator('#main h1').count() == 1 and pg.locator('#full').inner_text().strip() == '', (pg.evaluate("S.stage"), pg.locator('#full').inner_text()[:80]))
    ctx.close()

    # an expired token is refreshed and the change is retried once
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'exp@example.com', state=dict(APP, tab='Settings'), ttl=-100)
    w(pg, 800)
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW); pg.click('[data-act="dochpw"]')
    pg.wait_for_function("document.querySelector('h1')&&document.querySelector('h1').textContent==='Password changed'", timeout=8000)
    check('S17 an expired login is refreshed first and the change still goes through', fake.users['exp@example.com']['pw'] == NEWPW and any(c['q'].get('grant_type') == 'refresh_token' for c in fake.calls('POST', '/auth/v1/token')))
    ctx.close()
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'f401@example.com', state=dict(APP, tab='Settings'))
    w(pg, 800)
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW); fake.force401 = 1; pg.click('[data-act="dochpw"]')
    pg.wait_for_function("document.querySelector('h1')&&document.querySelector('h1').textContent==='Password changed'", timeout=8000)
    check('S17 a 401 answer gets one refresh and one retry (two PUTs)', len(fake.calls('PUT', '/auth/v1/user')) == 2 and fake.users['f401@example.com']['pw'] == NEWPW, len(fake.calls('PUT', '/auth/v1/user')))
    ctx.close()

    # the login ends while the screen is open: the person lands on the log in screen with the notice
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'end@example.com', state=dict(APP, tab='Settings'))
    w(pg, 800)
    pg.click('#main [data-act="chpw"]'); w(pg)
    pg.fill('#p_new', NEWPW); pg.fill('#p_new2', NEWPW)
    pg.evaluate("SBS.exp=1;SBS.refresh='rt-gone';sbSave()")
    pg.click('[data-act="dochpw"]'); w(pg, 1500)
    inf = pg.locator('.inf').first.inner_text() if pg.locator('.inf').count() else '(no notice)'
    check('S17 if the login has ended, the person gets the log in screen with the plain notice', pg.evaluate("S.stage") == 'login' and inf == 'Your login ended. Please log in again.' and fake.users['end@example.com']['pw'] == PW, (pg.evaluate("S.stage"), inf))
    shown = pg.locator('.err').first.inner_text() if pg.locator('.err').count() else ''
    check('S17 and no confusing network message is shown on that screen', shown == '' and 'reach the server' not in pg.locator('body').inner_text(), shown)
    ctx.close()

    # ---------- S18: the school waitlist (a form that anyone can use, signed in or not) ----------
    def to_slide3(pg):
        pg.click('[data-act="snext"]'); w(pg, 200); pg.click('[data-act="snext"]'); w(pg, 300)
    JW = lambda f: f.calls('POST', '/rpc/join_waitlist')
    # one read in the page each, so a screen that changes between two steps cannot make them wait for something that is gone
    H1 = lambda pg: pg.evaluate("(()=>{const e=document.querySelector('h1');return e?e.innerText:''})()")
    ERR = lambda pg: pg.evaluate("(()=>{const e=document.querySelector('#full .err');return e?e.innerText:''})()")
    BTN = lambda pg: pg.evaluate("(()=>{const e=document.querySelector('[data-act=dowl]');return e?e.innerText:'(gone)'})()")
    WLDONE = "!!document.querySelector('h1')&&document.querySelector('h1').textContent==='You’re on the list.'"
    SW = "({sw:document.documentElement.scrollWidth,iw:innerWidth})"
    STG = "[S.stage,S.slide]"
    EM = 'principal@lincolnhigh.edu'
    def wl_fill(pg, org, email, note=''):
        pg.fill('#w_org', org); pg.fill('#w_email', email); pg.fill('#w_note', note)
    def wl_fresh(pg):
        """From the Get started screen, or the thank-you screen, get to an empty form."""
        if pg.evaluate("S.stage") == 'waitlist' and pg.locator('#w_org').count() == 0:
            pg.click('#full button[data-act="wlback"]'); w(pg, 700)
        if pg.evaluate("S.stage") != 'waitlist':
            pg.click('.plan [data-act="waitlist"]'); w(pg)

    fake = Fake(); fake.sql = True
    ctx, pg, errs = newpage(b, D, fake, None, visit=False)
    to_slide3(pg)
    check('S18 we are on the Get started screen', pg.evaluate(STG) == ['intro', 2], pg.evaluate(STG))
    check('S18 it offers "Join the waitlist" inside the Schools and organizations row, next to COMING SOON',
          pg.evaluate("(()=>{const bs=document.querySelectorAll('.plan [data-act=waitlist]');if(bs.length!==1)return false;const row=bs[0].closest('.plan > div');return row.innerText.includes('Schools and organizations')&&row.innerText.includes('COMING SOON')&&!row.innerText.includes('FREE')})()"))
    check('S18 the link text is "Join the waitlist"', pg.locator('.plan [data-act="waitlist"]').inner_text().startswith('Join the waitlist'), pg.locator('.plan [data-act="waitlist"]').inner_text())
    check('S18 a guest looking at that screen has made no request', len(fake.log) == 0, fake.log)
    pg.click('.plan [data-act="waitlist"]'); w(pg)
    check('S18 it opens the Join the school waitlist form', pg.evaluate("S.stage") == 'waitlist' and H1(pg) == 'Join the school waitlist' and pg.locator('form#af').count() == 1, (pg.evaluate("S.stage"), H1(pg)))
    check('S18 opening the form makes no request', len(fake.log) == 0, len(fake.log))
    check('S18 the top bar is hidden while the form is open', pg.evaluate("document.body.classList.contains('full')") and not pg.locator('#hacct').is_visible())
    lab = pg.evaluate("['w_org','w_email','w_note'].map(id=>{const l=document.querySelector('label[for='+id+']');return l?l.textContent.trim():null})")
    check('S18 each box has its own label, and the note says it is optional', lab[0] == 'School or organization' and lab[1] == 'Your email' and (lab[2] or '').startswith('Anything you want us to know?') and '(optional)' in (lab[2] or ''), lab)
    check('S18 browsers can autofill the organization and the email', pg.get_attribute('#w_org', 'autocomplete') == 'organization' and pg.get_attribute('#w_email', 'autocomplete') == 'email' and pg.get_attribute('#w_email', 'type') == 'email')
    check('S18 the boxes have the same length limits as the database (120, 254, 500)', [pg.get_attribute(i, 'maxlength') for i in ('#w_org', '#w_email', '#w_note')] == ['120', '254', '500'])
    check('S18 the form says why the answers are saved', 'We save your answers so we can reach you about' in pg.locator('.box .meta').inner_text(), pg.locator('.box .meta').inner_text())
    hp = pg.evaluate("(()=>{const e=document.getElementById('w_hp'),r=e.getBoundingClientRect();return{ti:e.tabIndex,ah:e.closest('.hp').getAttribute('aria-hidden'),r:r.right,v:e.value}})()")
    check('S18 a trap box for robots is off screen, skipped by Tab, hidden from screen readers and empty', hp['ti'] == -1 and hp['r'] < 0 and hp['ah'] == 'true' and hp['v'] == '', hp)
    pg.focus('#w_note'); pg.keyboard.press('Tab')
    check('S18 Tab goes from the note straight to the Join button and never into the trap box', pg.evaluate("document.activeElement.getAttribute('data-act')") == 'dowl', pg.evaluate("document.activeElement.id||document.activeElement.tagName"))

    # mistakes are stopped here, in plain words, and what was typed stays
    pg.click('[data-act="dowl"]'); w(pg, 200)
    check('S18 an empty form is stopped with a plain message', ERR(pg) == 'Enter the name of your school or organization.', ERR(pg))
    pg.fill('#w_org', 'L'); pg.click('[data-act="dowl"]'); w(pg, 150)
    check('S18 a one-letter name is stopped too', ERR(pg) == 'Enter the name of your school or organization.', ERR(pg))
    pg.fill('#w_org', 'Lincoln High'); pg.fill('#w_email', 'principal-at-school'); pg.click('[data-act="dowl"]'); w(pg, 150)
    check('S18 an email with no @ is stopped', ERR(pg) == 'Enter a valid email address.', ERR(pg))
    pg.fill('#w_email', 'two words@school.org'); pg.click('[data-act="dowl"]'); w(pg, 150)
    check('S18 an email with a space in it is stopped', ERR(pg) == 'Enter a valid email address.', ERR(pg))
    check('S18 what was typed is still there after the mistakes', pg.input_value('#w_org') == 'Lincoln High' and pg.input_value('#w_email') == 'two words@school.org')
    check('S18 none of the mistakes made a request', len(fake.log) == 0, len(fake.log))

    # a good entry: tidied, sent once, with the publishable key only
    wl_fill(pg, '  Lincoln High  ', '  Principal@LincolnHigh.EDU ', '  We run 40 clubs  ')
    pg.evaluate("()=>{window.__p=act('dowl');act('dowl')}")
    lab = BTN(pg)
    pg.wait_for_function(WLDONE, timeout=8000); w(pg, 300)
    check('S18 the button said "Please wait…" while working', lab == 'Please wait…', lab)
    check('S18 a double click sends only one request', len(JW(fake)) == 1, len(JW(fake)))
    c = JW(fake)[0]
    check('S18 the request has the publishable key only: no Authorization header', c['auth'] is None, c['auth'])
    check('S18 it sends three named values, tidied (trimmed, email in lower case)', c['body'] == {'p_org': 'Lincoln High', 'p_email': EM, 'p_note': 'We run 40 clubs'}, c['body'])
    check('S18 the fake service saw no rule broken', fake.violations == [], fake.violations)
    check('S18 one row was added with those values', len(fake.waitlist) == 1 and (fake.waitlist[0]['org'], fake.waitlist[0]['email'], fake.waitlist[0]['note']) == ('Lincoln High', EM, 'We run 40 clubs'), fake.waitlist)
    check('S18 the thank-you screen says "You’re on the list." and shows the email', H1(pg) == 'You’re on the list.' and EM in pg.locator('.box b').inner_text(), pg.locator('.box').inner_text())
    check('S18 the form is gone from that screen', pg.locator('#w_org').count() == 0 and pg.locator('[data-act="dowl"]').count() == 0)
    d = store(pg)
    check('S18 nothing about the entry and no login is kept in the browser', 'bl.sb' not in d and all(EM not in v and 'Lincoln High' not in v for v in d.values()), [k for k, v in d.items() if EM in v or 'Lincoln High' in v])
    hl = pg.evaluate("history.length")
    pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 Done goes back to the Get started screen using the browser history (no new history entry)', pg.evaluate(STG) == ['intro', 2] and pg.evaluate("history.length") == hl, (pg.evaluate(STG), hl, pg.evaluate("history.length")))
    pg.click('.plan [data-act="waitlist"]'); w(pg)
    check('S18 opening it again gives an empty form, not the old thank-you screen', pg.locator('#w_org').count() == 1 and pg.input_value('#w_org') == '' and pg.input_value('#w_email') == '' and pg.input_value('#w_note') == '')

    # the same email twice looks the same and writes nothing new
    wl_fill(pg, 'Different Name', 'PRINCIPAL@lincolnhigh.edu')
    pg.click('[data-act="dowl"]'); pg.wait_for_function(WLDONE, timeout=8000)
    check('S18 using the same email again shows the same thank-you screen', H1(pg) == 'You’re on the list.' and len(JW(fake)) == 2, len(JW(fake)))
    check('S18 and writes nothing new, so the form cannot be used to find out who is on the list', len(fake.waitlist) == 1 and fake.waitlist[0]['org'] == 'Lincoln High', fake.waitlist)

    # a robot that fills the hidden box is thanked and ignored
    wl_fresh(pg)
    wl_fill(pg, 'Bot School', 'bot@spam.example'); pg.evaluate("document.getElementById('w_hp').value='http://spam.example'")
    n0 = len(JW(fake)); pg.click('[data-act="dowl"]'); w(pg, 600)
    check('S18 a robot that fills the hidden trap box sees the normal thank-you screen', H1(pg) == 'You’re on the list.')
    check('S18 but nothing is sent or saved for it', len(JW(fake)) == n0 and len(fake.waitlist) == 1, (len(JW(fake)) - n0, len(fake.waitlist)))

    # the Enter key sends the form
    wl_fresh(pg)
    wl_fill(pg, 'Enter School', 'enter@school.edu'); pg.press('#w_email', 'Enter'); pg.wait_for_function(WLDONE, timeout=8000)
    check('S18 pressing Enter in a box sends the form', any(isinstance(x['body'], dict) and x['body'].get('p_email') == 'enter@school.edu' for x in JW(fake)))

    # when something goes wrong: a plain message, the typed text stays, the button works again
    def fail_case(name, setup, undo, msg):
        wl_fresh(pg)
        wl_fill(pg, 'Err School', 'err@school.edu', 'my note')
        setup(); n1 = len(fake.waitlist)
        pg.click('[data-act="dowl"]'); w(pg, 900)
        undo()
        check(f'S18 {name}: the plain message is shown', ERR(pg) == msg, ERR(pg))
        check(f'S18 {name}: the typed text is kept and the button works again', pg.input_value('#w_org') == 'Err School' and pg.input_value('#w_email') == 'err@school.edu' and pg.input_value('#w_note') == 'my note' and BTN(pg) == 'Join the waitlist' and pg.locator('[data-act="dowl"]').is_enabled(), (pg.input_value('#w_org'), BTN(pg)))
        check(f'S18 {name}: nothing was saved', len(fake.waitlist) == n1 and not any(x['email'] == 'err@school.edu' for x in fake.waitlist))
    def setattr_(k, v): return lambda: setattr(fake, k, v)
    fail_case('no internet', setattr_('fail', 'net'), setattr_('fail', None), 'Can’t reach the server. Check your internet and try again.')
    fail_case('too many tries', setattr_('fail', '429'), setattr_('fail', None), 'Too many tries right now. Wait a minute and try again.')
    fail_case('the SQL has not been run yet', setattr_('sql', False), setattr_('sql', True), 'The waitlist isn’t open yet. Please try again soon.')
    fail_case('the database is busy', setattr_('wl_busy', True), setattr_('wl_busy', False), 'The waitlist is busy right now. Please try again in a few minutes.')
    pg.evaluate("document.getElementById('w_note').value='x'.repeat(501)")
    pg.click('[data-act="dowl"]'); w(pg, 700)
    check('S18 a note that is too long (pasted past the limit) gets the database message and nothing is saved', ERR(pg) == 'That note is too long. Keep it under 500 characters.' and not any(x['email'] == 'err@school.edu' for x in fake.waitlist), ERR(pg))
    pg.fill('#w_note', 'short again'); pg.click('[data-act="dowl"]'); pg.wait_for_function(WLDONE, timeout=8000)
    check('S18 after all those errors the same form can still be sent', any(x['email'] == 'err@school.edu' and x['note'] == 'short again' for x in fake.waitlist), fake.waitlist)
    check('S18 the fake service saw no rule broken in all of that', fake.violations == [], fake.violations)

    # typed text survives a redraw of the page (quotes and HTML included)
    pg.click('#full [data-act="wlback"]'); w(pg, 800); pg.click('.plan [data-act="waitlist"]'); w(pg)
    tricky = 'Tom\'s "Best" <b>School</b> & Co'
    wl_fill(pg, tricky, 'a"b@x.org', 'line <i>one</i>\nline two')
    pg.evaluate("render()"); w(pg, 200)
    check('S18 a redraw of the page keeps what was typed, even quotes and HTML, as plain text', pg.input_value('#w_org') == tricky and pg.input_value('#w_email') == 'a"b@x.org' and pg.input_value('#w_note') == 'line <i>one</i>\nline two' and pg.locator('#full b').count() == 0, (pg.input_value('#w_org'), pg.input_value('#w_note')))

    # Back, the browser Back button, a reload and the no-history fallback
    n0 = len(fake.log)
    pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 the Back link returns to the Get started screen without sending anything', pg.evaluate(STG) == ['intro', 2] and len(fake.log) == n0, (pg.evaluate(STG), len(fake.log) - n0))
    pg.click('.plan [data-act="waitlist"]'); w(pg)
    pg.go_back(); w(pg, 700)
    check('S18 the browser Back button also returns to the Get started screen', pg.evaluate(STG) == ['intro', 2], pg.evaluate(STG))
    pg.click('.plan [data-act="waitlist"]'); w(pg)
    pg.reload(); w(pg, 900)
    check('S18 reloading on the form shows the empty form again', pg.evaluate("S.stage") == 'waitlist' and pg.locator('#w_org').count() == 1 and pg.input_value('#w_org') == '')
    pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 and Back from there still leads to the Get started screen', pg.evaluate(STG) == ['intro', 2], pg.evaluate(STG))
    pg.click('.plan [data-act="waitlist"]'); w(pg)
    pg.evaluate("hDepth=0"); pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 with no earlier page in the history, Back still returns to the Get started screen', pg.evaluate(STG) == ['intro', 2], pg.evaluate(STG))
    check('S18 no page errors on any of this', errs == [], errs[:3])
    ctx.close()

    # HTML in an email is shown as text on the thank-you screen
    fake = Fake(); fake.sql = True
    ctx, pg, errs = newpage(b, D, fake, None, visit=False)
    to_slide3(pg); pg.click('.plan [data-act="waitlist"]'); w(pg)
    wl_fill(pg, 'Markup School', '<i>x</i>@example.com'); pg.click('[data-act="dowl"]'); pg.wait_for_function(WLDONE, timeout=8000)
    check('S18 an email with HTML in it is shown as text on the thank-you screen, not run', pg.locator('.box b i').count() == 0 and '<i>x</i>@example.com' in pg.locator('.box b').inner_text(), pg.locator('.box b').inner_html())
    ctx.close()

    # Settings has the same form, for guests and for signed-in people
    fake = Fake(); fake.sql = True
    ctx, pg, errs = newpage(b, D, fake, dict(APP, tab='Settings'))
    check('S18 a guest finds "School waitlist" in Settings, under More', pg.locator('#main [data-act="waitlist"]').count() == 1 and pg.locator('#main [data-act="waitlist"]').inner_text() == 'School waitlist')
    pg.click('#main [data-act="waitlist"]'); w(pg)
    check('S18 it opens the same form', pg.evaluate("S.stage") == 'waitlist' and H1(pg) == 'Join the school waitlist')
    pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 Back from there returns to Settings', pg.evaluate("[S.stage,S.tab]") == ['app', 'Settings'] and pg.locator('#main h1').inner_text() == 'Settings', pg.evaluate("[S.stage,S.tab]"))
    ctx.close()

    fake = Fake(); fake.sql = True
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'wl@example.com', state=dict(APP, tab='Settings'))
    w(pg, 700)
    pg.click('#main [data-act="waitlist"]'); w(pg)
    wl_fill(pg, 'Signed In School', 'signedin@school.edu'); pg.click('[data-act="dowl"]'); pg.wait_for_function(WLDONE, timeout=8000)
    c = JW(fake)[0]
    check('S18 a signed-in person sends it the same way: publishable key only, no login token', c['auth'] is None and fake.violations == [], (c['auth'], fake.violations))
    check('S18 their entry is saved with what they typed', fake.waitlist and fake.waitlist[0]['email'] == 'signedin@school.edu', fake.waitlist)
    pg.click('#full [data-act="wlback"]'); w(pg, 800)
    check('S18 Done returns them to Settings and they are still logged in', pg.evaluate("[S.stage,S.tab]") == ['app', 'Settings'] and pg.evaluate("S.me") == 'wl@example.com' and sbs(pg)['uid'] == uid, (pg.evaluate("[S.stage,S.tab]"), pg.evaluate("S.me")))
    ctx.close()

    # device-only mode (no Supabase address): there is nowhere to send it, so there is no waitlist
    fake = Fake(); fake.sql = True
    ctx, pg, errs = newpage(b, D, fake, None, visit=False, local=True)
    to_slide3(pg)
    check('S18 device-only mode: no waitlist link on the Get started screen, and COMING SOON is still there', pg.locator('[data-act="waitlist"]').count() == 0 and 'COMING SOON' in pg.locator('.plan').inner_text())
    pg.evaluate("act('waitlist')"); w(pg)
    check('S18 device-only mode: calling it directly does nothing', pg.evaluate("S.stage") == 'intro')
    ctx.close()
    ctx, pg, errs = newpage(b, D, fake, dict(APP, tab='Settings'), local=True)
    check('S18 device-only mode: Settings has no School waitlist button', pg.locator('[data-act="waitlist"]').count() == 0)
    ctx.close()
    ctx, pg, errs = newpage(b, D, fake, dict(APP, stage='waitlist'), local=True)
    check('S18 device-only mode: a waitlist screen left over from an online visit becomes the app, not a blank page', pg.evaluate("S.stage") == 'app' and pg.locator('#main h1').count() == 1 and pg.locator('#full').inner_text().strip() == '', (pg.evaluate("S.stage"), pg.locator('#full').inner_text()[:60]))
    ctx.close()
    ctx, pg, errs = newpage(b, D, fake, dict(APP, stage='waitlist', seen=False), local=True)
    check('S18 device-only mode: and a new visitor in that state sees the welcome screens', pg.evaluate("S.stage") == 'intro', pg.evaluate("S.stage"))
    ctx.close()

    # it fits on small screens in every state (form, mistake, thank-you), with long text
    LONGEM = 'a' * 60 + '@' + 'b' * 40 + '.example.org'
    for label, vp in (('desktop', D), ('phone', P), ('narrow', {'width': 320, 'height': 600})):
        fake = Fake(); fake.sql = True
        ctx, pg, errs = newpage(b, vp, fake, dict(APP, tab='Settings'))
        pg.click('#main [data-act="waitlist"]'); w(pg)
        g1 = pg.evaluate(SW)
        wl_fill(pg, 'x' * 100, 'nope', 'y' * 300); pg.click('[data-act="dowl"]'); w(pg, 200)
        g2 = pg.evaluate(SW)
        pg.fill('#w_email', LONGEM); pg.click('[data-act="dowl"]'); pg.wait_for_function(WLDONE, timeout=8000); w(pg, 200)
        g3 = pg.evaluate(SW)
        check(f'S18 {label}: no sideways scrolling on the form, with a mistake, or on the thank-you screen with a very long email', max(g1['sw'], g2['sw'], g3['sw']) <= g1['iw'], (g1, g2, g3))
        ctx.close()

    # ---------- S19: the Admin page (only for accounts on the database's admin list) ----------
    BOSS = 'boss@example.com'
    DAYS = [0, 0, 1, 0, 2, 0, 0, 0, 3, 0, 0, 5, 1, 2]
    def daily(ns):
        t = datetime.date.today()
        return [{'day': (t - datetime.timedelta(days=13 - i)).isoformat(), 'n': n} for i, n in enumerate(ns)]
    def admin_world(email=BOSS):
        """A pretend project with one admin, four students with quiz answers, some saved items and four waitlist entries."""
        f = Fake(); f.sql = True
        f.add_user(email, PW, {'name': 'Boss Person', 'role': 'Teacher', 'provider': False, 'org': ''}); f.make_admin(email)
        ids = []
        for i, (g, s) in enumerate([('9th grade', 'The Village School'), ('10th grade', 'The Village School'), ('10th grade', 'Another School'), ('11th grade', 'The Village School')]):
            u = f.add_user(f'stu{i}@example.com', PW, {'name': f'Stu {i}', 'role': 'Student', 'provider': False, 'org': ''})
            f.profiles[u]['quiz_answers'] = {'grade': g, 'school': s, 'learn': 'PRIVATE ANSWER %d' % i}
            ids.append(u)
        f.activity = [{'user_id': ids[k], 'opp_id': o, 'kind': 'saved'} for k, o in [(0, 'school-001'), (1, 'school-001'), (2, 'school-001'), (0, 'community-001'), (1, 'community-001'), (3, 'explore-001'), (0, 'gone-123'), (1, 'gone-123')]]
        f.activity.append({'user_id': ids[2], 'opp_id': 'explore-002', 'kind': 'doing'})
        f.ov_extra = {'accounts': 41, 'accounts_7d': 7, 'quiz_done': 23, 'saved': 118, 'doing': 64, 'daily': daily(DAYS)}
        f.add_waitlist('Lincoln High', 'principal@lincoln.edu', 'We run 40 clubs', minutes_ago=300)
        f.add_waitlist('<i>Evil</i> Academy', 'x@evil.test', '<img src=x onerror="window.__xss=1;alert(1)">', minutes_ago=120)
        f.add_waitlist('=cmd|" /C calc"!A1', 'formula@test.org', 'line one\nline\ttwo', minutes_ago=60)
        f.add_waitlist('Maple Middle', 'office@maple.org', None, minutes_ago=5)
        return f
    def wait_ok(pg, js, ms=8000):
        """True if the page gets to the state in time. A plain failed check is easier to read than a time-out stack trace."""
        try:
            pg.wait_for_function(js, timeout=ms); return True
        except Exception:
            return False
    H1 = lambda pg: pg.evaluate("(()=>{const e=document.querySelector('h1');return e?e.innerText:''})()")
    OVQ = lambda f: f.calls('POST', '/rpc/admin_overview')
    ISQ = lambda f: f.calls('POST', '/rpc/is_admin')
    ADMOK = "!!document.querySelector('#main .ad-stats')"
    ADMBTN = "(()=>{const e=document.getElementById('hadm');return{vis:!e.hidden&&e.getBoundingClientRect().width>0,on:e.classList.contains('on'),txt:e.textContent}})()"
    BODY = lambda pg: pg.locator('body').inner_text()
    def adm_page(vp, f, adm=True, state=None, **kw):
        ctx, pg, errs, uid, sess = logged_in_page(b, vp, f, BOSS, state=state if state is not None else dict(APP, tab='Admin'), adm=adm, **kw)
        return ctx, pg, errs, uid

    # a signed-in student (the SQL is installed) never sees Admin
    fake = Fake(); fake.sql = True
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'plain@example.com', state=dict(APP, tab='Settings'))
    w(pg, 800)
    ia = ISQ(fake)
    check('S19 a signed-in student: the page asks the database once whether they are an admin, with their own token', len(ia) == 1 and (ia[0]['auth'] or '').startswith('Bearer at-') and KEY not in (ia[0]['auth'] or '') and ia[0]['body'] == {}, [(c['auth'], c['body']) for c in ia])
    a = pg.evaluate(ADMBTN)
    check('S19 ...the answer is no, so there is no Admin button', a['vis'] is False and pg.evaluate("document.getElementById('hadm').hidden") is True, a)
    pg.evaluate("go('Admin')"); w(pg, 400)
    check('S19 even asking for the Admin page directly ends on the Home tab and asks for no admin data', pg.evaluate("S.tab") == 'Home' and pg.locator('#main h1').inner_text() != 'Admin' and not OVQ(fake), (pg.evaluate("S.tab"), len(OVQ(fake))))
    check('S19 the answer is remembered as "not an admin" on this device', sbs(pg).get('adm') in (False, None), sbs(pg).get('adm'))
    ctx.close()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'stale@example.com', state=dict(APP, tab='Admin'), adm=True)
    w(pg, 900)
    check('S19 a student whose device still says "Admin" (left over, or edited by hand) is put back on Home and sees no admin data', pg.evaluate("S.tab") == 'Home' and not pg.locator('#main .ad-stats').count() and not pg.locator('#hadm').is_visible() and len(OVQ(fake)) <= 1 and pg.evaluate("ADM") is None, (pg.evaluate("S.tab"), len(OVQ(fake))))
    check('S19 even if that request was made, the database said no (403) and nothing was kept', pg.evaluate("ADM") is None and sbs(pg).get('adm') is False, sbs(pg))
    ctx.close()

    # the SQL has not been run: no Admin button, no errors, no repeated asking
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'nosql@example.com', state=dict(APP, tab='Settings'))
    w(pg, 800)
    pg.evaluate("sbSync()"); w(pg, 300); pg.evaluate("sbSync()"); w(pg, 500)
    check('S19 before the SQL is run there is no Admin button and the page works as before', not pg.locator('#hadm').is_visible() and pg.locator('#main h1').inner_text() == 'Settings')
    check('S19 and the page stops asking after the first "no such function" answer', len(ISQ(fake)) == 1, len(ISQ(fake)))
    check('S19 and shows no error', errs == [] and pg.locator('.err:visible, .inf:visible').count() == 0, errs[:3])
    ctx.close()

    # the SQL is run while the site is already open in a tab: logging out and in again is enough, no reload needed
    fake = admin_world(); fake.sql = False
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, BOSS, state=dict(APP, tab='Settings'))
    w(pg, 900)
    check('S19 before the SQL is run, even the admin has no Admin button', not pg.locator('#hadm').is_visible() and len(ISQ(fake)) == 1, len(ISQ(fake)))
    fake.sql = True     # the owner runs admin.sql in another tab
    pg.click('#main [data-act="logout"]'); w(pg, 900)
    pg.click('#full [data-act="login"]'); w(pg)
    pg.fill('#a_email', BOSS); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]')
    landed = wait_ok(pg, ADMOK)
    check('S19 after the SQL is run, logging out and in again lands on the Admin page without reloading the site', landed and pg.evaluate("S.tab") == 'Admin' and pg.evaluate(ADMBTN)['vis'] is True, (landed, pg.evaluate("S.tab")))
    ctx.close()

    # logging in as the admin lands on the Admin page
    fake = admin_world(); bossid = fake.users[BOSS]['id']
    ctx, pg, errs = newpage(b, D, fake, APP0)   # a guest with no quiz answers (at the account step), so nothing is uploaded into the admin's account on login
    check('S19 a guest at the account step sees no Admin button', pg.evaluate("S.stage") == 'auth' and not pg.locator('#hadm').is_visible())
    pg.click('#full [data-act="login"]'); w(pg)
    d0 = len(DIALOGS)
    pg.fill('#a_email', BOSS); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]')
    landed = wait_ok(pg, ADMOK); w(pg, 400)
    check('S19 logging in as the admin lands on the Admin page', landed and pg.evaluate("[S.stage,S.tab]") == ['app', 'Admin'] and H1(pg) == 'Admin' and pg.locator('#main .eyebrow').inner_text() == 'ADMIN', (landed, pg.evaluate("[S.stage,S.tab]")))
    check('S19 the page names the signed-in email', BOSS in pg.locator('#main > p').first.inner_text(), pg.locator('#main > p').first.inner_text())
    a = pg.evaluate(ADMBTN)
    check('S19 the top bar shows an Admin button marked as the current page, and no Sign up button', a['vis'] and a['on'] and a['txt'] == 'Admin' and not pg.locator('#hacct').is_visible(), a)
    ia, ov = ISQ(fake), OVQ(fake)
    check('S19 it took one admin check and one overview request, both with the signed-in token and empty bodies', len(ia) == 1 and len(ov) == 1 and all((c['auth'] or '').startswith('Bearer at-') and KEY not in c['auth'] and c['body'] == {} for c in ia + ov), [(c['path'], c['auth'], c['body']) for c in ia + ov])
    check('S19 the fake service saw no rule broken', fake.violations == [], fake.violations)
    tiles = pg.evaluate("[...document.querySelectorAll('#main .ad-s')].map(e=>[e.querySelector('.ad-l').textContent,e.querySelector('.ad-n').textContent])")
    check('S19 six number tiles with the right labels and numbers', tiles == [['Accounts', '41'], ['New in 7 days', '7'], ['Finished the quiz', '23'], ['Saved items', '118'], ['“I’m doing” items', '64'], ['On the waitlist', '4']], tiles)
    rows = pg.evaluate("[...document.querySelectorAll('#main .ad-w')].map(e=>({org:e.querySelector('b').textContent,when:e.children[1].textContent,email:e.querySelector('.em').textContent,note:e.querySelector('.ad-nt')?e.querySelector('.ad-nt').textContent:null}))")
    check('S19 the waitlist is listed newest first with organization, email and note', [r['org'] for r in rows] == ['Maple Middle', '=cmd|" /C calc"!A1', '<i>Evil</i> Academy', 'Lincoln High'] and [r['email'] for r in rows] == ['office@maple.org', 'formula@test.org', 'x@evil.test', 'principal@lincoln.edu'], rows)
    check('S19 a row with no note shows no note line, and notes show what was written', rows[0]['note'] is None and ' '.join(rows[1]['note'].split()) == 'line one line two' and rows[3]['note'] == 'We run 40 clubs', rows)
    check('S19 every row has a readable date', all(re.match(r'^[A-Z][a-z]{2} \d{1,2}, \d{4}', r['when']) for r in rows), [r['when'] for r in rows])
    check('S19 the heading counts the waitlist', pg.locator('#main .pnl h2').first.inner_text() == 'Waitlist (4)', pg.locator('#main .pnl h2').first.inner_text())
    check('S19 text typed by visitors is shown as plain text: no HTML made, no script run', pg.locator('#main .ad-w img').count() == 0 and pg.locator('#main .ad-w i').count() == 0 and pg.evaluate("window.__xss") is None and len(DIALOGS) == d0, (pg.locator('#main .ad-w img').count(), DIALOGS[d0:]))
    bars = pg.evaluate("[...document.querySelectorAll('#main .ad-bars i')].map(e=>[e.style.height,e.className])")
    exp = [['3%', 'z'] if n == 0 else [f'{max(6, round(n / 5 * 100))}%', ''] for n in DAYS]
    check('S19 the 14-day chart has 14 bars, tall in proportion, and empty days are marked', bars == exp, bars)
    aria = pg.get_attribute('#main .ad-bars', 'aria-label') or ''
    check('S19 the chart has a text version for screen readers with all 14 numbers', pg.get_attribute('#main .ad-bars', 'role') == 'img' and ', '.join(str(n) for n in DAYS) in aria and aria.startswith('New accounts per day'), aria)
    n_s1, n_c1, n_e1 = [pg.evaluate("(id)=>ALL.find(x=>x.id===id).name", i) for i in ('school-001', 'community-001', 'explore-001')]
    ms = pg.evaluate("[...document.querySelectorAll('#main .ad-two .pnl')[0].querySelectorAll('.ad-r')].map(e=>[e.children[0].textContent,e.children[1].textContent])")
    check('S19 Most saved shows opportunity names with counts, most saved first, and an item the page no longer knows by its id', ms == [[n_s1, '3'], [n_c1, '2'], ['gone-123', '2'], [n_e1, '1']], ms)
    sg = pg.evaluate("[...document.querySelectorAll('#main .ad-two .pnl')[1].querySelectorAll('h2, .ad-r')].map(e=>e.tagName==='H2'?e.textContent:e.children[0].textContent+'='+e.children[1].textContent)")
    check('S19 Schools and Grades show names with counts', sg == ['Schools', 'The Village School=3', 'Another School=1', 'Grades', '10th grade=2', '11th grade=1', '9th grade=1'], sg)
    check('S19 nobody’s quiz answers or other private text appear anywhere on the page', 'PRIVATE ANSWER' not in BODY(pg) and 'PRIVATE ANSWER' not in pg.content())
    lnk = pg.evaluate("(()=>{const a=document.querySelector('#main a[href*=\"supabase.com\"]');return a?[a.href,a.target,a.rel]:null})()")
    foot = pg.locator('#main > p.meta').last.inner_text()
    check('S19 the footer says what accounts show, says quiz answers and saved items are never shown, and links to the Supabase project in a new tab',
          'Accounts show name, email and dates.' in foot and 'quiz answers or saved items are shown' in foot and 'counts only' not in foot and lnk == ['https://supabase.com/dashboard/project/urotelcllngtcctheelb', '_blank', 'noopener'], (foot, lnk))
    check('S19 the page shows when it was updated', 'Updated ' in pg.locator('#main > p.meta').last.inner_text(), pg.locator('#main > p.meta').last.inner_text())
    d = store(pg)
    check('S19 the waitlist and the numbers are not kept in the browser storage', all('principal@lincoln.edu' not in v and 'PRIVATE ANSWER' not in v and 'Maple Middle' not in v for v in d.values()), [k for k, v in d.items() if 'principal@lincoln.edu' in v])
    check('S19 what is kept about being an admin is only a yes on this device', sbs(pg).get('adm') is True, sbs(pg))

    # Open the app / Admin button switch without asking for the numbers again
    pg.click('#main [data-tab="Home"]'); w(pg, 400)
    a = pg.evaluate(ADMBTN)
    check('S19 "Open the app" opens Home and leaves the Admin page, and the Admin button stays in the top bar but is no longer the current page', pg.evaluate("S.tab") == 'Home' and a['vis'] and not a['on'], (pg.evaluate("S.tab"), a))
    check('S19 Home tells an admin so, with a way to the Admin page', pg.locator('#main .inf [data-tab="Admin"]').count() == 1 and 'You’re an admin.' in pg.locator('#main .inf').inner_text(), pg.locator('#main').inner_text()[:200])
    pg.click('#hadm'); w(pg, 500)
    check('S19 the Admin button comes back to the same numbers without asking again', pg.evaluate("S.tab") == 'Admin' and pg.locator('#main .ad-stats').count() == 1 and len(OVQ(fake)) == 1, (pg.evaluate("S.tab"), len(OVQ(fake))))

    # the copy buttons
    pg.evaluate("window.__clip=[];Object.defineProperty(navigator,'clipboard',{value:{writeText:t=>{window.__clip.push(t);return Promise.resolve()}},configurable:true})")
    pg.click('[data-act="admcopy"][data-v="emails"]'); w(pg, 300)
    clip = pg.evaluate("window.__clip")
    check('S19 Copy emails copies every email, newest first, separated by commas', clip == ['office@maple.org, formula@test.org, x@evil.test, principal@lincoln.edu'], clip)
    check('S19 and says how many were copied', pg.locator('#admnote').inner_text() == 'Copied 4 emails.', pg.locator('#admnote').inner_text())
    pg.click('[data-act="admcopy"][data-v="sheet"]'); w(pg, 300)
    sheet = pg.evaluate("window.__clip")[1]
    lines = sheet.split('\n'); cells = [l.split('\t') for l in lines]
    check('S19 Copy as spreadsheet gives a header line and one line per entry, four tab-separated columns each', lines[0] == 'School or organization\tEmail\tNote\tJoined' and len(lines) == 5 and all(len(c) == 4 for c in cells), lines)
    check('S19 a note that had a new line and a tab in it stays on one line', cells[2][2] == 'line one line two' and cells[2][1] == 'formula@test.org', cells[2])
    check('S19 a cell that starts with = (or + - @) gets a quote in front so a spreadsheet will not run it as a formula', cells[2][0] == '\'=cmd|" /C calc"!A1' and all(not re.match(r'^[=+\-@]', c) for r in cells[1:] for c in r), cells[2])
    check('S19 an empty note is an empty cell, and the date column is year-month-day', cells[1][2] == '' and all(re.match(r'^\d{4}-\d{2}-\d{2}$', r[3]) for r in cells[1:]), [r[3] for r in cells[1:]])
    check('S19 and says how many rows were copied', pg.locator('#admnote').inner_text() == 'Copied 4 rows.', pg.locator('#admnote').inner_text())
    pg.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('blocked'))},configurable:true});document.execCommand=()=>false")
    pg.click('[data-act="admcopy"][data-v="emails"]'); w(pg, 400)
    check('S19 if the browser refuses to copy, the page says so plainly', pg.locator('#admnote').inner_text() == 'Couldn’t copy. Select the text and copy it yourself.', pg.locator('#admnote').inner_text())
    pg.evaluate("document.execCommand=()=>true")
    pg.click('[data-act="admcopy"][data-v="emails"]'); w(pg, 400)
    check('S19 if only the old copy method works, it is used', pg.locator('#admnote').inner_text() == 'Copied 4 emails.', pg.locator('#admnote').inner_text())

    # Refresh: one request even for a double click, shows new entries
    n0 = len(OVQ(fake))
    fake.add_waitlist('Brand New School', 'new@school.edu', 'hi', minutes_ago=0)
    pg.evaluate("()=>{act('admload');act('admload')}")
    lab, dis = pg.evaluate("(()=>{const b=document.querySelector('#main [data-act=admload]');return [b.textContent,b.disabled]})()")
    pg.wait_for_function("document.querySelector('#main [data-act=admload]')&&document.querySelector('#main [data-act=admload]').textContent==='Refresh'", timeout=8000); w(pg, 300)
    check('S19 Refresh shows "Refreshing…" while it works and is switched off', lab == 'Refreshing…' and dis, (lab, dis))
    check('S19 a double click on Refresh asks only once', len(OVQ(fake)) == n0 + 1, len(OVQ(fake)) - n0)
    t2 = pg.evaluate("[...document.querySelectorAll('#main .ad-s')].map(e=>e.querySelector('.ad-n').textContent)")
    check('S19 Refresh shows the new entry at the top and the new total', pg.locator('#main .ad-w b').first.inner_text() == 'Brand New School' and t2[-1] == '5' and pg.locator('#main .pnl h2').first.inner_text() == 'Waitlist (5)', (pg.locator('#main .ad-w b').first.inner_text(), t2))

    # the person is removed from the admin list while the page is open
    fake.admins.discard(bossid)
    pg.click('#main [data-act="admload"]'); w(pg, 900)
    check('S19 if they were removed as admin, Refresh takes them off the Admin page and the button goes (this person never took the quiz, so they are held at the quiz step)', pg.evaluate("S.tab") == 'Home' and not pg.locator('#hadm').is_visible() and pg.evaluate("S.stage") == 'prompt', (pg.evaluate("S.tab"), pg.locator('#hadm').is_visible(), pg.evaluate("S.stage")))
    check('S19 and the admin data is gone from memory and from the page', pg.evaluate("ADM") is None and 'principal@lincoln.edu' not in pg.content() and sbs(pg).get('adm') is False, sbs(pg))
    pg.evaluate("go('Admin')"); w(pg, 300)
    check('S19 asking for the Admin page again still ends on Home', pg.evaluate("S.tab") == 'Home')
    check('S19 no page errors in all of that', errs == [], errs[:3])
    ctx.close()

    # reload on Admin: a returning admin (remembered on this device) stays there; a cold start does not guess
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 400)
    check('S19 a returning admin who was on the Admin page is shown it again, with the numbers', pg.evaluate("S.tab") == 'Admin' and pg.locator('#main h1').inner_text() == 'Admin' and len(pg.locator('#main .ad-w').all()) == 4)
    pg.reload(); pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    check('S19 a reload on the Admin page shows it again', pg.evaluate("S.tab") == 'Admin' and pg.evaluate("document.getElementById('hadm').classList.contains('on')"), pg.evaluate("S.tab"))
    ctx.close()
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=None)
    w(pg, 900)
    a = pg.evaluate(ADMBTN)
    check('S19 on a device that has not met this admin yet, the page starts on Home, then the Admin button appears after the check', pg.evaluate("S.tab") == 'Home' and a['vis'] and not a['on'] and sbs(pg).get('adm') is True, (pg.evaluate("S.tab"), a))
    check('S19 and the numbers are only fetched when the Admin button is used', len(OVQ(fake)) == 0, len(OVQ(fake)))
    pg.click('#hadm'); pg.wait_for_function(ADMOK, timeout=8000)
    check('S19 using the button loads the numbers once', pg.evaluate("S.tab") == 'Admin' and len(OVQ(fake)) == 1, len(OVQ(fake)))
    ctx.close()

    # logging out wipes everything; the next person on the same page is not an admin
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    tab(pg, 'Settings'); pg.click('#main [data-act="logout"]'); w(pg, 900)
    check('S19 logging out wipes the admin data from memory, the page and this device', pg.evaluate("ADM") is None and 'principal@lincoln.edu' not in pg.content() and all('principal@lincoln.edu' not in v for v in store(pg).values()) and pg.evaluate("Object.keys(sessionStorage).every(k=>!sessionStorage.getItem(k).includes('lincoln.edu'))"))
    check('S19 and the Admin button is gone, and the person is back at the account step', not pg.locator('#hadm').is_visible() and pg.evaluate("S.stage") == 'auth' and pg.evaluate("S.tab") != 'Admin', (pg.evaluate("[S.stage,S.tab]"),))
    pg.evaluate("go('Admin')"); w(pg, 300)
    check('S19 a guest asking for the Admin page ends on Home', pg.evaluate("S.tab") == 'Home')
    n0 = len(OVQ(fake))
    pg.click('#full [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'stu0@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); pg.wait_for_function("S.stage==='app'&&S.me==='stu0@example.com'", timeout=8000); w(pg, 700)
    check('S19 a student who logs in next on the same page lands on Home with no Admin button and no admin data', pg.evaluate("S.tab") == 'Home' and not pg.locator('#hadm').is_visible() and pg.evaluate("ADM") is None and len(OVQ(fake)) == n0, (pg.evaluate("S.tab"), len(OVQ(fake)) - n0))
    pg.evaluate("go('Admin')"); w(pg, 300)
    check('S19 and cannot open the Admin page either', pg.evaluate("S.tab") == 'Home' and 'principal@lincoln.edu' not in pg.content())
    ctx.close()

    # the login ends while on the Admin page
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    pg.evaluate("SBS.exp=1;SBS.refresh='rt-gone';sbSave()")
    pg.click('#main [data-act="admload"]'); w(pg, 1500)
    inf = pg.locator('.inf').first.inner_text() if pg.locator('.inf').count() else '(no notice)'
    check('S19 if the login ends while on the Admin page, the person gets the log in screen with the plain notice', pg.evaluate("S.stage") == 'login' and inf == 'Your login ended. Please log in again.', (pg.evaluate("S.stage"), inf))
    check('S19 and the admin data is gone from the page and memory', pg.evaluate("ADM") is None and 'principal@lincoln.edu' not in pg.content() and not pg.locator('#hadm').is_visible(), pg.evaluate("S.tab"))
    ctx.close()

    # the browser Back button
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    tab(pg, 'Settings'); w(pg, 300)
    pg.go_back(); w(pg, 700)
    check('S19 the browser Back button goes from Settings to Admin without asking for the numbers again', pg.evaluate("S.tab") == 'Admin' and pg.locator('#main .ad-stats').count() == 1 and len(OVQ(fake)) == 1, (pg.evaluate("S.tab"), len(OVQ(fake))))
    ctx.close()

    # problems loading the numbers
    fake = admin_world(); fake.fail = 'net'
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    w(pg, 1800)
    check('S19 with no internet the Admin page says so plainly, offers Try again and shows no numbers', 'Can’t reach the server. Check your internet and try again.' in pg.locator('#main').inner_text() and pg.locator('#main [data-act="admload"]').inner_text() == 'Try again' and pg.locator('#main .ad-stats').count() == 0, pg.locator('#main').inner_text()[:200])
    check('S19 the Admin button is still there (the person is still the admin)', pg.evaluate(ADMBTN)['vis'] is True)
    fake.fail = None; pg.click('#main [data-act="admload"]'); pg.wait_for_function(ADMOK, timeout=8000)
    check('S19 Try again then shows the numbers', pg.locator('#main .ad-w').count() == 4)
    ctx.close()
    fake = admin_world(); fake.fail = '500'
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    w(pg, 1800)
    check('S19 a server error shows a plain message, not the server’s text', 'Couldn’t load the numbers. Please try again.' in pg.locator('#main').inner_text() and pg.locator('#main .ad-stats').count() == 0, pg.locator('#main').inner_text()[:200])
    w(pg, 2500)
    check('S19 and the page asked only once (no request storm)', len(OVQ(fake)) == 1, len(OVQ(fake)))
    fake.fail = None; pg.click('#main [data-act="admload"]'); pg.wait_for_function(ADMOK, timeout=8000)
    check('S19 Try again after that works', len(OVQ(fake)) == 2 and pg.locator('#main .ad-w').count() == 4, len(OVQ(fake)))
    ctx.close()
    fake = admin_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000)
    fake.sql = False
    pg.click('#main [data-act="admload"]'); w(pg, 900)
    check('S19 if the Admin SQL disappears from the project, the page returns to Home without errors', pg.evaluate("S.tab") == 'Home' and not pg.locator('#hadm').is_visible() and pg.evaluate("ADM") is None, (pg.evaluate("S.tab"),))
    ctx.close()

    # empty and very full lists
    fake = Fake(); fake.sql = True; fake.add_user(BOSS, PW); fake.make_admin(BOSS); fake.ov_extra = {'daily': daily([0] * 14)}
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    check('S19 with nothing yet: "Nobody has joined yet.", no copy buttons, and "Nothing yet." in the other lists', 'Nobody has joined yet.' in pg.locator('#main').inner_text() and pg.locator('[data-act="admcopy"]').count() == 0 and pg.locator('#main .empty').count() == 4, pg.locator('#main .empty').count())
    check('S19 with no new accounts all 14 bars are the small empty mark', pg.locator('#main .ad-bars i').count() == 14 and pg.locator('#main .ad-bars i.z').count() == 14)
    check('S19 the tiles show zeros', [t[1] for t in pg.evaluate("[...document.querySelectorAll('#main .ad-s')].map(e=>[e.querySelector('.ad-l').textContent,e.querySelector('.ad-n').textContent])")][2:] == ['0', '0', '0', '0'])
    ctx.close()
    fake = Fake(); fake.sql = True; fake.add_user(BOSS, PW); fake.make_admin(BOSS)
    fake.add_waitlist('One School', 'one@school.edu', None, minutes_ago=2); fake.add_waitlist('Two School', 'two@school.edu', None, minutes_ago=1)
    fake.ov_extra = {'waitlist': 1234}
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    check('S19 when there are more entries than are listed, the page says so and where the rest are', pg.locator('#admnote').inner_text() == 'Showing the newest 2 of 1,234. The rest are in Supabase, Table Editor, waitlist.' and pg.locator('#main .pnl h2').first.inner_text() == 'Waitlist (1,234)', pg.locator('#admnote').inner_text())
    ctx.close()
    fake = Fake(); fake.sql = True; fake.add_user(BOSS, PW); fake.make_admin(BOSS); fake.add_waitlist('Solo School', 'solo@school.edu', None)
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    pg.evaluate("window.__clip=[];Object.defineProperty(navigator,'clipboard',{value:{writeText:t=>{window.__clip.push(t);return Promise.resolve()}},configurable:true})")
    pg.click('[data-act="admcopy"][data-v="emails"]'); w(pg, 300)
    check('S19 with exactly one entry the message says "1 email", not "1 emails"', pg.locator('#admnote').inner_text() == 'Copied 1 email.' and pg.evaluate("window.__clip") == ['solo@school.edu'], pg.locator('#admnote').inner_text())
    ctx.close()

    # the top bar and the page fit at every width, with very long text in the waitlist
    for label, vp in (('desktop', D), ('phone', P), ('narrow', {'width': 320, 'height': 700}), ('tablet', {'width': 800, 'height': 900})):
        for scheme in ('light', 'dark'):
            fake = admin_world()
            LONGE = 'a-really-long-address-' + 'x' * 50 + '@a-very-long-district-name.example.k12.tx.us'
            fake.add_waitlist('Supercalifragilistic' * 4, LONGE, 'n' * 250, minutes_ago=1)
            fake.add_user(LONGE, PW, {'name': 'Verylongname' * 12, 'role': 'Teacher', 'provider': True, 'org': 'Org'})   # the same person has an account, so both lists show their tag
            ctx, pg, errs, uid = adm_page(vp, fake, adm=True, state=dict(APP, tab='Admin', theme='auto' if scheme == 'dark' else 'light'), scheme=scheme)
            pg.wait_for_function(ADMOK, timeout=8000); w(pg, 400)
            g = pg.evaluate(HDR)
            hb = {k['c']: k for k in g['kids']}
            adm_, gear = hb.get('hadm'), hb.get('gb')
            if scheme == 'light':
                check(f'S19 {label}: the Admin button sits right before the Settings button on the same line', adm_ and gear and 0 <= gear['l'] - adm_['r'] <= 20 and abs((adm_['t'] + adm_['b']) / 2 - (gear['t'] + gear['b']) / 2) < 3, (adm_, gear))
            check(f'S19 {label} {scheme}: nothing in the top bar overlaps and the Admin page does not scroll sideways, even with very long names and emails', g['ov'] == [] and g['sw'] <= g['iw'], (g['ov'], g['sw'], g['iw']))
            ctx.close()

    # ---------- S20: the Accounts list on the Admin page (who signed up, and who is on the waitlist) ----------
    HRS = 3600
    def acct_world(extra=0):
        """One admin and four people with different details (one is also on the waitlist). `extra` more accounts fill a long list."""
        f = Fake(); f.sql = True
        t = time.time()
        f.add_user(BOSS, PW, {'name': 'Boss Person', 'role': 'Teacher', 'provider': False, 'org': ''}); f.make_admin(BOSS)
        f.users[BOSS]['created'] = t - 30 * 86400; f.users[BOSS]['last'] = t - 60
        def person(email, name, role, prov, created, last, quiz=None, org=''):
            u = f.add_user(email, PW, {'name': name, 'role': role, 'provider': prov, 'org': org})
            f.users[email]['created'] = created; f.users[email]['last'] = last
            if quiz: f.profiles[u]['quiz_answers'] = quiz
            return u
        person('nina@example.com', 'Nina Newest', 'Student', False, t - 2 * HRS, t - 1 * HRS, {'grade': '9th grade', 'school': 'The Village School', 'learn': 'PRIVATE ANSWER 1'})
        person('wanda@example.com', 'Wanda Waitlist', 'Teacher', True, t - 26 * HRS, t - 3 * HRS, None, 'Lincoln High')
        person('<u>xss</u>@example.com', '<img src=x onerror="window.__xss2=1;alert(2)">Eve', 'Student', False, t - 3 * 86400, None)   # odd text in both the name and the email
        nn = person('noname@example.com', 'x', 'Student', False, t - 5 * 86400, t - 4 * 86400)
        f.profiles[nn]['name'] = ''; f.users['noname@example.com']['meta']['name'] = ''
        for i in range(extra):
            person(f'bulk{i:03d}@example.com', f'Bulk {i:03d}', 'Student', False, t - (10 + i) * 86400 - 3600, t - 9 * 86400)
        f.add_waitlist('Lincoln High', 'wanda@example.com', 'We run 40 clubs', minutes_ago=90)
        f.add_waitlist('Other School', 'nobody@else.org', None, minutes_ago=10)
        f.ov_extra = {'daily': daily(DAYS)}
        return f
    ACCS = "[...document.querySelectorAll('#main .ad-a')].map(e=>({name:e.querySelector('b').textContent,tag:e.querySelector('.ad-t')?e.querySelector('.ad-t').textContent:null,email:e.querySelector('.em').textContent,meta:e.querySelector('.meta').textContent}))"
    WLR = "[...document.querySelectorAll('#main .ad-w')].map(e=>({org:e.querySelector('b').textContent,email:e.querySelector('.em').firstChild.textContent,tag:e.querySelector('.em .ad-t')?e.querySelector('.em .ad-t').textContent:null}))"
    H2S = "[...document.querySelectorAll('#main .pnl h2')].map(h=>h.textContent)"
    APNL = "(()=>{const p=[...document.querySelectorAll('#main .pnl')].find(x=>x.querySelector('h2').textContent.startsWith('Accounts'));return p?{text:p.innerText,note:p.querySelector('p.meta')?p.querySelector('p.meta').textContent:null,btn:p.querySelector('[data-act=admmore]')?p.querySelector('[data-act=admmore]').textContent:null}:null})()"
    DT = r'\w{3} \d{1,2}, \d{4}, \d{1,2}:\d{2}(?: [AP]M)?'

    fake = acct_world()
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 400)
    d0 = len(DIALOGS)
    check('S20 the Admin page lists the Waitlist, then Accounts, then the sign-up chart and the other lists', pg.evaluate(H2S) == ['Waitlist (2)', 'Accounts (5)', 'New accounts, last 14 days', 'Most saved', 'Schools', 'Grades'], pg.evaluate(H2S))
    rows = pg.evaluate(ACCS)
    check('S20 every account is listed, newest first, with its name and email',
          [(r['name'], r['email']) for r in rows] == [('Nina Newest', 'nina@example.com'), ('Wanda Waitlist', 'wanda@example.com'), ('<img src=x onerror="window.__xss2=1;alert(2)">Eve', '<u>xss</u>@example.com'), ('No name', 'noname@example.com'), ('Boss Person', BOSS)], rows)
    pat = lambda role, last, quiz: re.compile('^' + role + ' · Joined ' + DT + ' · Last log in ' + last + ' · ' + quiz + '$')
    metas = [r['meta'].replace(' ', ' ').replace(' ', ' ') for r in rows]
    exp = [pat('Student', DT, 'Quiz done'), pat('Teacher · Provider', DT, 'No quiz yet'), pat('Student', 'never', 'No quiz yet'), pat('Student', DT, 'No quiz yet'), pat('Teacher', DT, 'No quiz yet')]
    check('S20 each account shows its role, when it joined, when it last logged in (or "never") and whether the quiz is done', all(e.match(m) for e, m in zip(exp, metas)), metas)
    check('S20 only the person who is on the waitlist has a tag, and it names the school they typed', [r['tag'] for r in rows] == [None, 'On the waitlist: Lincoln High', None, None, None], [r['tag'] for r in rows])
    wl = pg.evaluate(WLR)
    check('S20 in the waitlist, the entry whose email has an account says "Has an account" and the other one does not', [(r['org'], r['email'], r['tag']) for r in wl] == [('Other School', 'nobody@else.org', None), ('Lincoln High', 'wanda@example.com', 'Has an account')], wl)
    check('S20 an odd name and an odd email are shown as plain text: no HTML made, no script run', pg.locator('#main .ad-a img').count() == 0 and pg.locator('#main .ad-a u').count() == 0 and pg.evaluate("window.__xss2") is None and len(DIALOGS) == d0, (pg.locator('#main .ad-a img').count(), pg.locator('#main .ad-a u').count(), DIALOGS[d0:]))
    check('S20 nobody’s quiz answers appear anywhere on the page', 'PRIVATE ANSWER' not in BODY(pg) and 'PRIVATE ANSWER' not in pg.content())
    ds = store(pg)
    check('S20 the accounts list is not kept in the browser storage', all('nina@example.com' not in v and 'Wanda' not in v and 'noname@example.com' not in v for v in ds.values()), [k for k, v in ds.items() if 'nina@example.com' in v])
    check('S20 the whole page came from the one overview request', len(OVQ(fake)) == 1, len(OVQ(fake)))
    check('S20 the Accounts tile and the list agree, and no "showing the newest" note is needed', pg.evaluate("document.querySelector('#main .ad-n').textContent") == '5' and pg.evaluate(APNL)['note'] is None, pg.evaluate(APNL))
    foot = pg.locator('#main > p.meta').last.inner_text()
    check('S20 the footer says accounts show name, email and dates (not "counts only") and that quiz answers and saved items are never shown', 'Accounts show name, email and dates. Nobody’s quiz answers or saved items are shown.' in foot and 'counts only' not in foot, foot)
    check('S20 no page errors', errs == [], errs[:3])
    ctx.close()

    # a long list: 10 first, then 20 more at a time, kept on Refresh, forgotten on log out
    fake = acct_world(extra=55)
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 400)
    cnt = lambda: pg.locator('#main .ad-a').count()
    btn = lambda: pg.evaluate(APNL)['btn']
    check('S20 a long list starts with 10 accounts and a button that says how many are left', cnt() == 10 and btn() == 'Show 20 more · 50 left' and pg.evaluate(H2S)[1] == 'Accounts (60)', (cnt(), btn()))
    pg.click('#main [data-act="admmore"]'); w(pg, 300)
    check('S20 the button adds 20 more', cnt() == 30 and btn() == 'Show 20 more · 30 left', (cnt(), btn()))
    pg.click('#main [data-act="admmore"]'); w(pg, 300)
    check('S20 near the end it says "Show the last 10"', cnt() == 50 and btn() == 'Show the last 10', (cnt(), btn()))
    pg.click('#main [data-act="admmore"]'); w(pg, 300)
    check('S20 when everything is shown the button is gone, and no new request was made', cnt() == 60 and btn() is None and len(OVQ(fake)) == 1, (cnt(), btn(), len(OVQ(fake))))
    pg.click('#main [data-act="admload"]'); w(pg, 900)
    check('S20 Refresh keeps the list as long as it was', cnt() == 60 and len(OVQ(fake)) == 2, (cnt(), len(OVQ(fake))))
    tab(pg, 'Settings'); pg.click('#main [data-act="logout"]'); w(pg, 900)
    check('S20 logging out forgets how much of the list was open and the list itself', pg.evaluate("ADMLIM") == 10 and 'bulk000@example.com' not in pg.content(), pg.evaluate("ADMLIM"))
    check('S20 no page errors', errs == [], errs[:3])
    ctx.close()

    # more accounts than the list holds
    fake = acct_world(); fake.ov_extra = {'accounts': 1234, 'daily': daily(DAYS)}
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    check('S20 when there are more accounts than are listed, the page says so and where to find everyone', pg.evaluate(H2S)[1] == 'Accounts (1,234)' and pg.evaluate(APNL)['note'] == 'Showing the newest 5 of 1,234. Everyone is in Supabase, Authentication, Users.', pg.evaluate(APNL))
    ctx.close()

    # admin.sql from before the accounts list: the page says what to do and everything else still works
    fake = acct_world(); fake.ov_old = True
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    shown = wait_ok(pg, ADMOK); w(pg, 400)
    check('S20 with the older admin.sql the Admin page still loads', shown, errs[:2])
    ap = pg.evaluate(APNL)
    check('S20 with the older admin.sql the Accounts panel says names and emails are not turned on yet, and shows no rows',
          bool(ap) and 'Names and emails aren’t turned on yet. Run the newest admin.sql in Supabase, then tap Refresh.' in ap['text'] and pg.locator('#main .ad-a').count() == 0 and (pg.evaluate(H2S) + ['', ''])[1] == 'Accounts (5)', ap)
    check('S20 and the waitlist and the other numbers still work, with no "Has an account" tags', pg.locator('#main .ad-w').count() == 2 and pg.locator('#main .ad-t').count() == 0 and pg.locator('#main .ad-bars i').count() == 14, pg.locator('#main .ad-w').count())
    fake.ov_old = False
    pg.click('#main [data-act="admload"]'); w(pg, 900)
    check('S20 once the newest admin.sql is run, Refresh shows the list and the tags', pg.locator('#main .ad-a').count() == 5 and pg.locator('#main .ad-t').count() == 2, (pg.locator('#main .ad-a').count(), pg.locator('#main .ad-t').count()))
    check('S20 no page errors with either version', errs == [], errs[:3])
    ctx.close()

    # an empty list
    fake = acct_world(); fake.ov_extra = {'accounts_list': [], 'daily': daily(DAYS)}
    ctx, pg, errs, uid = adm_page(D, fake, adm=True)
    pg.wait_for_function(ADMOK, timeout=8000); w(pg, 300)
    check('S20 an empty list says "No accounts yet."', 'No accounts yet.' in pg.evaluate(APNL)['text'] and pg.locator('#main .ad-a').count() == 0)
    ctx.close()

    # a student never gets the list: the database refuses, and nothing is shown
    fake = acct_world()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'nina@example.com', state=dict(APP, tab='Admin'), adm=True)
    w(pg, 1200)
    check('S20 a student never sees the accounts list, even if their device says Admin', pg.evaluate("S.tab") == 'Home' and 'wanda@example.com' not in pg.content() and 'boss@example.com' not in pg.content() and pg.evaluate("ADM") is None, pg.evaluate("S.tab"))
    ctx.close()

    # ---------- S21: the big "Take the quiz" banner. The quiz is required, so only people allowed in without it see it (an admin) ----------
    QB = "(()=>{const q=document.querySelector('#main .qb');if(!q)return null;const r=q.getBoundingClientRect(),b=q.querySelector('button'),br=b.getBoundingClientRect();return{first:document.getElementById('main').firstElementChild===q,top:r.top,bottom:r.bottom,w:r.width,bw:br.width,bt:br.top,bb:br.bottom,title:q.querySelector('b').textContent,sub:q.querySelector('span').textContent,btn:b.textContent,act:b.dataset.act,iw:innerWidth,ih:innerHeight,sw:document.documentElement.scrollWidth}})()"
    QN = "document.querySelectorAll('#main [data-act=quiz]').length"
    fake = admin_world()
    for label, vp, scheme in [('desktop-light', D, 'light'), ('desktop-dark', D, 'dark'), ('phone-light', P, 'light'), ('phone-dark', P, 'dark'), ('narrow-light', {'width': 320, 'height': 700}, 'light')]:
        ctx, pg, errs, uid, sess = logged_in_page(b, vp, fake, BOSS, state=dict(APP0, tab='School', theme='auto' if scheme == 'dark' else 'light'), adm=True, scheme=scheme)
        w(pg, 800)
        q = pg.evaluate(QB)
        check(f'S21 {label}: an admin who has not taken the quiz is let in and gets a banner as the very first thing on the School page', bool(q) and q['first'], q)
        if q:
            check(f'S21 {label}: it says what the quiz is for and has one clear button', q['title'] == 'Take the quiz to find your matches' and q['sub'] == 'Answer a few questions and we’ll put your best matches first. Takes about 2 minutes.' and q['btn'] == 'Take the quiz' and q['act'] == 'quiz', q)
            check(f'S21 {label}: the button is on the first screen without scrolling, above the bottom bar, and big enough to tap', 0 <= q['bt'] and q['bb'] <= q['ih'] - (80 if vp['width'] < 500 else 0) and q['bb'] - q['bt'] >= 44, q)
            check(f'S21 {label}: it is the only Take the quiz button on the page, and the page does not scroll sideways', pg.evaluate(QN) == 1 and q['sw'] <= q['iw'], (pg.evaluate(QN), q['sw'], q['iw']))
            if vp['width'] < 560:
                check(f'S21 {label}: on a small screen the button runs the full width of the banner', q['bw'] >= q['w'] - 40, q)
            else:
                check(f'S21 {label}: on a big screen the button sits at the right and does not stretch', q['bw'] < q['w'] / 3, q)
        pg.screenshot(path=f'{SP}/shots/quiz-banner-{label}.png')
        if label in ('desktop-light', 'phone-light'):
            pg.click('#main .qb [data-act="quiz"]'); w(pg, 400)
            check(f'S21 {label}: the banner button starts the quiz', pg.evaluate("[S.stage,S.step]") == ['quiz', 0], pg.evaluate("[S.stage,S.step]"))
        errs_ = list(errs)
        check(f'S21 {label}: no page errors', errs_ == [], errs_[:3])
        ctx.close()

    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, BOSS, state=dict(APP0, tab='School'), adm=True)
    w(pg, 800)
    sub = lambda: pg.evaluate("(()=>{const e=document.querySelector('#main > p.mut');return e?e.textContent:null})()")
    check('S21 without the quiz the page says it is not sorted for the person yet, and the toolbar has no second quiz button', sub() == 'Not sorted for you yet.' and pg.locator('#main .cnt [data-act="quiz"]').count() == 0, sub())
    on = {}
    for t_ in ('Home', 'Community', 'Explore', 'My Activities', 'Settings'):
        tab(pg, t_); on[t_] = (pg.locator('#main .qb').count(), pg.evaluate(QN))
    check('S21 the banner is on Home, Community and Explore, and not on My Activities or Settings (which has its own button)', on == {'Home': (1, 1), 'Community': (1, 1), 'Explore': (1, 1), 'My Activities': (0, 0), 'Settings': (0, 1)}, on)
    tab(pg, 'School')
    pg.evaluate("S.done=true;render()")
    check('S21 once the quiz is done the banner is gone, the page says best matches first, and Retake quiz is back in the toolbar', pg.locator('#main .qb').count() == 0 and sub() == 'Best matches first.' and pg.locator('#main .cnt [data-act="quiz"]').inner_text() == 'Retake quiz' and pg.evaluate(QN) == 1, (sub(),))
    pg.evaluate("S.done=false;render()")
    check('S21 and it comes back if the answers are cleared', pg.locator('#main .qb').count() == 1)
    ctx.close()
    ctx, pg, errs = newpage(b, D, fake, APP)
    check('S21 someone who already took the quiz never sees the banner', pg.locator('#main .qb').count() == 0 and sub() == 'Best matches first.' and pg.locator('#main .cnt [data-act="quiz"]').inner_text() == 'Retake quiz')
    ctx.close()
    # an ordinary signed-in account that has not taken the quiz never gets as far as the banner: it is held at the quiz step
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, P, fake, 'newbie@example.com', state=dict(APP0, tab='School'))
    w(pg, 900)
    check('S21 an ordinary account with no quiz is held at the quiz step, with one big Take the quiz button', pg.evaluate("S.stage") == 'prompt' and pg.locator('#full [data-act="quiz"]').count() == 1 and pg.locator('#main .qb').count() == 0, pg.evaluate("S.stage"))
    bt = pg.evaluate("(()=>{const b=document.querySelector('#full [data-act=quiz]').getBoundingClientRect();return{t:b.top,b:b.bottom,w:b.width,ih:innerHeight,iw:innerWidth}})()")
    check('S21 and that button is big, full width on a phone, and on the first screen without scrolling', bt['b'] <= bt['ih'] and bt['b'] - bt['t'] >= 44 and bt['w'] >= bt['iw'] * 0.6, bt)
    pg.click('#full [data-act="quiz"]'); w(pg, 400)
    check('S21 ...and the quiz opens for them', pg.evaluate("[S.stage,S.step]") == ['quiz', 0], pg.evaluate("[S.stage,S.step]"))
    ctx.close()

    # ---------- S16: how it looks ----------
    fake = Fake(); fake.add_user('look@example.com', PW, {'name': 'Look Lee', 'role': 'Student', 'provider': False, 'org': ''})
    for label, vp, scheme, dsf in [('desktop-light', D, 'light', 1), ('desktop-dark', D, 'dark', 1), ('phone-light', P, 'light', 2), ('phone-dark', P, 'dark', 2)]:
        st = dict(APP0, theme='auto' if 'dark' in label else 'light')
        ctx, pg, errs = newpage(b, vp, fake, st, scheme=scheme, dsf=dsf)
        pg.screenshot(path=f'{SP}/shots/sb-account-step-{label}.png')
        pg.click('#full [data-act="signup"]'); w(pg)
        pg.fill('#a_name', 'Look Lee'); pg.fill('#a_email', 'look@example.com'); pg.fill('#a_pw', PW)
        pg.click('[data-act="dosignup"]'); w(pg, 600)
        pg.screenshot(path=f'{SP}/shots/sb-signup-error-{label}.png')
        pg.fill('#a_email', 'x@example.com'); pg.fill('#a_pw', PW)
        pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.me&&S.stage==='prompt'", timeout=8000); w(pg, 800)
        pg.screenshot(path=f'{SP}/shots/sb-quiz-step-{label}.png')
        do_quiz(pg, 1000)
        pg.screenshot(path=f'{SP}/shots/sb-home-{label}.png')
        tab(pg, 'Settings'); pg.screenshot(path=f'{SP}/shots/sb-settings-{label}.png', full_page=True)
        ctx.close()
        fake.users.pop('x@example.com', None)
    b.close()
finally:
    srv.terminate()

bad = [r for r in results if not r[1]]
errs_flat = [e for lst_ in all_errs for e in lst_]
print('\n==== %d checks, %d failed, %d page errors' % (len(results), len(bad), len(errs_flat)))
for r in bad: print('FAILED:', r[0], '|', str(r[2])[:300])
for e in errs_flat[:10]: print('ERR:', e[:200])
