import json, os, re, subprocess, sys, time
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

ANS = {'grade': '10th grade', 'school': 'The Village School', 'learn': 'biology and chemistry', 'want': ['Join a club'], 'why': ['Trying new things'], 'time': '3-5 hours'}
APP = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': True, 'theme': 'light', 'ans': ANS}
APP0 = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': False, 'theme': 'light', 'ans': {}}
FILL = """(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""
PW = 'secret1'
DIALOGS = []; ACCEPT = [True]

def newpage(b, vp, fake, state=None, sb=None, users=None, visit=True, scheme='light', dsf=1, url=URL, local=False):
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
def logged_in_page(b, vp, fake, email, state=None, ttl=None, saved=None, known=None, **kw):
    if email not in fake.users:
        fake.add_user(email, PW, {'name': email.split('@')[0].title(), 'role': 'Student', 'provider': False, 'org': ''})
    uid = fake.users[email]['id']
    sess = fake.session(uid, ttl)
    seed = fake.sb_seed(sess)
    if known: seed['known'] = known
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

    # ---------- S2: sign up (with a quiz and a saved item made as a guest) ----------
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, dict(APP, saved={'school-001': True}))
    tab(pg, 'Settings'); pg.click('#main [data-act="signup"]'); w(pg)
    check('S2 sign-up form is shown', pg.locator('#a_name').count() == 1 and pg.locator('form#af').count() == 1)
    check('S2 autocomplete hints are set', pg.get_attribute('#a_name', 'autocomplete') == 'name' and pg.get_attribute('#a_email', 'autocomplete') == 'email' and pg.get_attribute('#a_pw', 'autocomplete') == 'new-password')
    check('S2 notice on the form says what is stored online', 'stored in your account' in pg.locator('.box').inner_text())
    pg.fill('#a_name', 'Ada Lovelace'); pg.fill('#a_email', 'Ada@Example.com'); pg.fill('#a_pw', PW)
    pg.select_option('#a_role', 'Teacher'); pg.check('input[name="a_prov"][value="yes"]'); pg.fill('#a_org', 'Robotics Club')
    # double click must send one sign-up only, and the button shows it is working
    pg.evaluate("()=>{window.__p=act('dosignup');act('dosignup')}")
    lab = pg.locator('[data-act="dosignup"]').inner_text() if pg.locator('[data-act="dosignup"]').count() else '(gone)'
    pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 600)
    check('S2 button said "Please wait…" while working', lab == 'Please wait…', lab)
    check('S2 only one sign-up request for a double click', len(fake.calls('POST', '/auth/v1/signup')) == 1, len(fake.calls('POST', '/auth/v1/signup')))
    su = fake.calls('POST', '/auth/v1/signup')[0]
    check('S2 sign-up body carries email, password and the profile details', su['body'] == {'email': 'ada@example.com', 'password': PW, 'data': {'name': 'Ada Lovelace', 'role': 'Teacher', 'provider': True, 'org': 'Robotics Club'}}, su['body'])
    check('S2 sign-up request has no Authorization header', su['auth'] is None, su['auth'])
    uid = fake.users['ada@example.com']['id']
    rest = [c for c in fake.log if c['path'].startswith('/rest/')]
    check('S2 every data request carries the signed-in token and never the publishable key', rest and all(c['auth'] and c['auth'].startswith('Bearer at-') for c in rest), [c['auth'] for c in rest])
    check('S2 the fake service saw no rule broken', fake.violations == [], fake.violations)
    prof = fake.profiles.get(uid) or {}
    check('S2 profile row created with name, role, provider and organization', (prof.get('name'), prof.get('role'), prof.get('is_provider'), prof.get('org')) == ('Ada Lovelace', 'Teacher', True, 'Robotics Club'), prof)
    check('S2 quiz answers made as a guest went up with the new account', prof.get('quiz_answers') == ANS, prof.get('quiz_answers'))
    check('S2 the guest saved item went up with the new account', fake.rows(uid, 'saved') == ['school-001'], fake.rows(uid))
    d = store(pg)
    check('S2 password is not stored anywhere in the browser', all(PW not in v for v in d.values()), [k for k, v in d.items() if PW in v])
    s = sbs(pg)
    check('S2 login saved on this device with ids and tokens', s and s['uid'] == uid and s['email'] == 'ada@example.com' and s['access'].startswith('at-') and s['refresh'].startswith('rt-'), s)
    check('S2 sync info up to date (known saved matches, answers clean)', s and s['known']['saved'] == ['school-001'] and s['dirty'] is False, s)
    u = lst(pg, 'bl.users').get('ada@example.com', {})
    check('S2 device copy of the account has no password hash and no quiz answers', 'pw' not in u and 'ans' not in u and u.get('sb') == 1, u)
    check('S2 after sign-up the app is shown (already seen the welcome)', pg.evaluate("S.stage") == 'app' and pg.evaluate("S.me") == 'ada@example.com')
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
    tab(pg, 'Settings'); check('S6 Settings now offers log in again', pg.locator('#main [data-act="login"]').count() == 1)
    ctx.close()

    # ---------- S4: finishing the quiz while signed in sends the answers ----------
    fake = Fake()
    ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'quiz@example.com')
    pg.evaluate("act('quiz')"); w(pg)
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
    tab(pg, 'Settings'); pg.click('#main [data-act="login"]'); w(pg)
    check('S7 login form has current-password hint and no name box', pg.get_attribute('#a_pw', 'autocomplete') == 'current-password' and pg.locator('#a_name').count() == 0)
    pg.fill('#a_email', 'Grace@Example.com'); pg.fill('#a_pw', 'wrongpass')
    pg.click('[data-act="dologin"]'); w(pg, 500)
    check('S7 wrong password shows a plain message in place', pg.locator('.err').inner_text() == 'Email or password is incorrect.', pg.locator('.err').inner_text())
    check('S7 typed email and password are still in the boxes after the error', pg.input_value('#a_email') == 'Grace@Example.com' and pg.input_value('#a_pw') == 'wrongpass')
    check('S7 button is usable again after the error', pg.locator('[data-act="dologin"]').is_enabled() and pg.locator('[data-act="dologin"]').inner_text() == 'Log in')
    pg.fill('#a_pw', PW); pg.press('#a_pw', 'Enter')
    pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 500)
    check('S7 Enter key logs in', pg.evaluate("S.me") == 'grace@example.com')
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
    tab(pg, 'Settings'); pg.click('#main [data-act="signup"]'); w(pg)
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
    tab(pg, 'Settings'); pg.click('#main [data-act="signup"]'); w(pg)
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
    n = len(fake.log); fake.force401 = 2
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
    tab(pg, 'Settings'); pg.click('#main [data-act="login"]'); w(pg)
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
    ctx.unroute(SBRE); ctx.route(SBRE, orig)
    pg.evaluate("dispatchEvent(new Event('online'))"); w(pg, 1500)
    check('S11b back online it loads the account data', pg.evaluate("sbNeedPull") is False)
    ctx.close()

    # ---------- S12: delete account ----------
    for rpc in (False, True):
        fake = Fake(); fake.rpc = rpc
        ctx, pg, errs, uid, sess = logged_in_page(b, D, fake, 'del@example.com', state=APP)
        fake.activity += [{'user_id': uid, 'opp_id': 'school-001', 'kind': 'saved'}]
        pg.reload(); w(pg, 1000)
        tab(pg, 'Settings'); DIALOGS.clear(); ACCEPT[0] = False
        pg.click('[data-act="del"]'); w(pg, 500)
        nreq = len(fake.calls(None, '/rpc/'))
        check(f'S12 rpc={rpc} cancelling the question deletes nothing', pg.evaluate("S.me") == 'del@example.com' and nreq == 0 and 'del@example.com' in fake.users and 'delete your account' in DIALOGS[0].lower(), (DIALOGS, nreq))
        ACCEPT[0] = True
        pg.click('[data-act="del"]'); pg.wait_for_function("S.me===null", timeout=8000); w(pg, 600)
        rp = fake.calls('POST', '/rpc/delete_my_account')
        check(f'S12 rpc={rpc} the delete function is called with the token', len(rp) == 1 and (rp[0]['auth'] or '').startswith('Bearer at-'), rp)
        check(f'S12 rpc={rpc} afterwards logged out, data cleared here, on the Settings screen', pg.evaluate("S.me") is None and pg.evaluate("localStorage.getItem('bl.sb')") is None and pg.evaluate("S.tab") == 'Settings')
        txt = pg.locator('#main .inf').inner_text() if pg.locator('#main .inf').count() else ''
        if rpc:
            check('S12 rpc=True the account is gone online and says so', 'del@example.com' not in fake.users and txt == 'Your account was deleted.', (list(fake.users), txt))
        else:
            check('S12 rpc=False data rows deleted online, login kept, and it says so honestly', uid not in fake.profiles and fake.rows(uid) == [] and 'del@example.com' in fake.users and 'Removing the login itself is not switched on yet' in txt, (fake.profiles.keys(), fake.rows(uid), txt))
        check(f'S12 rpc={rpc} the notice goes away when leaving Settings', (lambda: (tab(pg, 'School'), pg.locator('.inf').count() == 0)[1])())
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
    ctx, pg, errs = newpage(b, D, fake, APP0, local=True)
    tab(pg, 'Settings'); st = pg.locator('#main').inner_text()
    check('S14 local mode says everything is saved on this device only', 'Everything is saved on this device only.' in st and 'Create an account to keep' not in st, st[:300])
    pg.click('#main [data-act="signup"]'); w(pg)
    check('S14 local sign-up page keeps the prototype note', 'Prototype: accounts, friends and messages are saved on this device' in pg.locator('.box').inner_text())
    pg.fill('#a_name', 'Local Lee'); pg.fill('#a_email', 'lee@example.com'); pg.fill('#a_pw', PW); pg.press('#a_pw', 'Enter')
    pg.wait_for_function("S.me==='lee@example.com'", timeout=5000); w(pg, 400)
    u = lst(pg, 'bl.users')['lee@example.com']
    check('S14 Enter key creates a device-only account with a password hash', len(u['pw']) == 64 and 'sb' not in u and PW not in json.dumps(store(pg)))
    check('S14 local mode makes no requests', len(fake.log) == 0, fake.log)
    tab(pg, 'Settings'); pg.click('[data-act="logout"]'); w(pg, 500)
    tab(pg, 'Settings'); pg.click('#main [data-act="login"]'); w(pg)
    pg.fill('#a_email', 'lee@example.com'); pg.fill('#a_pw', 'nope'); pg.click('[data-act="dologin"]'); w(pg, 400)
    check('S14 local wrong password shows the message in place and keeps the typed email', pg.locator('.err').inner_text() == 'Email or password is incorrect.' and pg.input_value('#a_email') == 'lee@example.com')
    pg.fill('#a_pw', PW); pg.click('[data-act="dologin"]'); w(pg, 500)
    check('S14 local log in works', pg.evaluate("S.me") == 'lee@example.com' and pg.evaluate("S.stage") == 'app')
    pg.evaluate("act('quiz')"); w(pg)
    check('S14 local quiz note is the old one', 'not sent to a server' in pg.locator('.note').inner_text())
    tab(pg, 'Settings') if pg.evaluate("S.stage") == 'app' else None
    ACCEPT[0] = True; DIALOGS.clear()
    pg.evaluate("S.stage='app';S.tab='Settings';render()"); w(pg)
    pg.click('[data-act="del"]'); w(pg, 500)
    check('S14 local delete still asks about this device and removes the account', DIALOGS and 'on this device' in DIALOGS[0] and 'lee@example.com' not in lst(pg, 'bl.users'), (DIALOGS, lst(pg, 'bl.users')))
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
    pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 600)
    check('S15 after signing up the button is gone from the top bar', not pg.locator('#hacct').is_visible() and pg.evaluate("S.me") == 'hedy@example.com')
    tab(pg, 'Settings'); pg.click('[data-act="logout"]'); w(pg, 800)
    check('S15 after logging out the button is back', pg.locator('#hacct').is_visible())
    ctx.close()

    # a guest who just did the quiz can sign up from the top bar and keeps the answers
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP0)
    pg.evaluate("act('quiz')"); w(pg)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 500)
    check('S15 a guest who finished the quiz sees the Sign up button', pg.locator('#hacct').is_visible() and len(fake.log) == 0, len(fake.log))
    pg.click('#hacct'); w(pg)
    pg.fill('#a_name', 'Quiz Guest'); pg.fill('#a_email', 'qg@example.com'); pg.fill('#a_pw', PW)
    pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.stage==='app'&&S.me", timeout=8000); w(pg, 1500)
    q = (fake.profiles.get(fake.users['qg@example.com']['id']) or {}).get('quiz_answers') or {}
    check('S15 the quiz answers made as a guest go into the new account', q.get('learn') == 'I like robotics, biology and helping people', q)
    ctx.close()

    # with no Supabase address the button still works (device-only accounts)
    fake = Fake()
    ctx, pg, errs = newpage(b, D, fake, APP0, local=True)
    check('S15 local mode: guests see the button too', pg.locator('#hacct').is_visible())
    pg.click('#hacct'); w(pg)
    check('S15 local mode: it opens the same form with the prototype note', pg.evaluate("S.stage") == 'signup' and 'Prototype: accounts' in pg.locator('.box').inner_text())
    ctx.close()

    # ---------- S16: how it looks ----------
    fake = Fake(); fake.add_user('look@example.com', PW, {'name': 'Look Lee', 'role': 'Student', 'provider': False, 'org': ''})
    for label, vp, scheme, dsf in [('desktop-light', D, 'light', 1), ('desktop-dark', D, 'dark', 1), ('phone-light', P, 'light', 2), ('phone-dark', P, 'dark', 2)]:
        st = dict(APP0, theme='auto' if 'dark' in label else 'light')
        ctx, pg, errs = newpage(b, vp, fake, st, scheme=scheme, dsf=dsf)
        tab(pg, 'Settings'); pg.click('#main [data-act="signup"]'); w(pg)
        pg.fill('#a_name', 'Look Lee'); pg.fill('#a_email', 'look@example.com'); pg.fill('#a_pw', PW)
        pg.click('[data-act="dosignup"]'); w(pg, 600)
        pg.screenshot(path=f'{SP}/shots/sb-signup-error-{label}.png')
        pg.fill('#a_email', 'x@example.com'); pg.fill('#a_pw', PW)
        pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.stage==='app'", timeout=8000); w(pg, 800)
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
