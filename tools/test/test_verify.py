"""
Tests for the email-code step at sign-up.

When the Supabase project has "Confirm email" switched on, sign-up does not log anyone in. It emails a code, and the account
only works once that code is typed on the page. (While "Confirm email" is off, as on the live project today, none of this shows
and sign-up works as before: V8 checks that.)

What this covers:
  V1  sign-up shows the Check your email screen and creates nothing until the right code is typed
  V2  the screen survives a reload and the browser Back button
  V3  wrong, old, too short and badly typed codes; spaces and dashes are ignored
  V4  Send a new code (the old one stops working) and the flood limit
  V5  an email that already has a confirmed account is told so, and no code is sent
  V6  logging in with an email that was never confirmed leads to the same screen
  V7  Use a different email, and an organizer (no quiz) after the code
  V8  Confirm email off: nothing changes
  V9  other code lengths, the older /verify type name, and network and server errors
  V10 looks: phone, small phone and computer, light and dark

It runs the real page in headless Chromium against the pretend Supabase in fake_sb.py. Run it from the repo folder:
    python3 tools/test/test_verify.py
"""
import json, os, re, subprocess, sys, time
from subprocess import DEVNULL
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fake_sb import Fake, SBRE, KEY

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.environ.get('BL_SHOTS', '/tmp/bulletin-test-shots'); os.makedirs(SP + '/shots', exist_ok=True)
PORT = 8779
URL = f'http://127.0.0.1:{PORT}/index.html'
srv = subprocess.Popen(['python3', '-I', '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=REPO, stdout=DEVNULL, stderr=DEVNULL)
time.sleep(1.0)

results = []; all_errs = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' | ' + str(detail)[:300]) if (detail != '' and not ok) else ''), flush=True)

ANS = {'grade': '10th grade', 'school': 'The Village School', 'zip': '77095', 'learn': 'biology and chemistry', 'want': ['Join a club'], 'why': ['Trying new things'], 'time': '3-5 hours'}
APP0 = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': False, 'theme': 'light', 'ans': {}}
FILL = """(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='zip'?'77095':q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""
PW = 'secret1'
D = {'width': 1440, 'height': 900}
P = {'width': 390, 'height': 844}
SP5 = {'width': 320, 'height': 640}
ROLE_TXT = {'Student': 'I’m a student', 'Parent': 'parent or guardian', 'Teacher': 'I’m a teacher', 'Organizer': 'run a club'}
WRONG = 'That code didn’t work. Check it, or ask for a new one below.'


def newpage(b, vp, fake, state=None, visit=True, scheme='light'):
    mob = vp['width'] < 500
    ctx = b.new_context(viewport=vp, is_mobile=mob, has_touch=mob, color_scheme=scheme)
    js = "try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    if state is not None: js += "localStorage.setItem('bl.state',%s);" % json.dumps(json.dumps(state))
    if visit: js += "sessionStorage.setItem('bl.visit','1');"
    ctx.add_init_script(js + "}}catch(e){}")
    ctx.route(SBRE, fake.handler)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_' not in m.text else None)
    pg.on('dialog', lambda d: d.accept())
    all_errs.append(errs)
    pg.goto(URL); pg.wait_for_timeout(500)
    return ctx, pg, errs

w = lambda pg, ms=250: pg.wait_for_timeout(ms)
def txt(pg, sel='#full'): return pg.locator(sel).inner_text()
def stage(pg): return pg.evaluate("S.stage")
def err(pg):
    # the red message above the button; '' when the screen has none (for example once the person has moved on to the quiz step)
    loc = pg.locator('#full .err')
    return loc.first.inner_text().strip() if loc.count() else ''
def store(pg, k): return json.loads(pg.evaluate(f"localStorage.getItem('{k}')") or 'null')
def fill_signup(pg, name, email, role='Student', org=None, pw=PW):
    pg.fill('#a_name', name); pg.fill('#a_email', email); pg.fill('#a_pw', pw)
    pg.locator('.role', has_text=ROLE_TXT[role]).click()
    if org is not None: pg.fill('#a_org', org)
def do_quiz(pg):
    pg.click('#full [data-act="quiz"]'); w(pg, 200)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 500)
def to_verify(b, vp, fake, email='new@example.com', name='Nia New', role='Student', org=None, scheme='light'):
    """A guest at the account step creates an account; with Confirm email on, the page lands on the code screen."""
    ctx, pg, errs = newpage(b, vp, fake, APP0, scheme=scheme)
    pg.click('#full [data-act="signup"]'); w(pg)
    fill_signup(pg, name, email, role, org)
    pg.click('[data-act="dosignup"]'); w(pg, 900)
    return ctx, pg, errs
def type_code(pg, code, press=False):
    pg.fill('#v_code', code)
    if press: pg.press('#v_code', 'Enter')
    else: pg.click('[data-act="doverify"]')
    w(pg, 900)
def on(fake): fake.confirm = True; return fake
def section(fn):
    try:
        fn()
    except Exception as e:
        check(f'{fn.__name__} CRASHED', False, repr(e)[:400])


def run(b):
    # ---------- V1: nothing is created until the right code is typed ----------
    def v1_flow():
        for label, vp in (('phone', P), ('desktop', D)):
            fake = on(Fake())
            ctx, pg, errs = to_verify(b, vp, fake, 'nia@example.com')
            check(f'V1 {label}: sign-up with Confirm email on goes to the Check your email screen', stage(pg) == 'verify' and 'Check your email' in txt(pg), [stage(pg), txt(pg)[:100]])
            check(f'V1 {label}: it names the address the code went to', pg.locator('#full b', has_text='nia@example.com').count() == 1)
            check(f'V1 {label}: the project emailed exactly one code', [(k, e) for k, e, c in fake.emails] == [('signup', 'nia@example.com')], fake.emails)
            check(f'V1 {label}: the sign-up request carried the details, no login and no Authorization header', fake.calls('POST', '/auth/v1/signup')[0]['auth'] is None and fake.calls('POST', '/auth/v1/signup')[0]['body']['data']['name'] == 'Nia New')
            inp = pg.locator('#v_code')
            check(f'V1 {label}: the code box is for numbers and lets the phone offer the emailed code', inp.get_attribute('inputmode') == 'numeric' and inp.get_attribute('autocomplete') == 'one-time-code')
            check(f'V1 {label}: nobody is logged in and nothing was created on the device', pg.evaluate("[S.me,SBS]") == [None, None] and store(pg, 'bl.sb') is None and 'nia@example.com' not in (store(pg, 'bl.users') or {}), [pg.evaluate("[S.me,SBS]"), store(pg, 'bl.users')])
            check(f'V1 {label}: the app cannot be reached from here', pg.evaluate("S.stage") == 'verify' and pg.locator('#main').inner_text().strip() == '' and pg.locator('.hd').is_hidden())
            check(f'V1 {label}: there is a Back link and no skip', pg.locator('#full [data-act="back2"]').count() == 1 and 'skip' not in txt(pg).lower())
            check(f'V1 {label}: the pretend project has the account but it is not confirmed yet', fake.users['nia@example.com']['confirmed'] is False)
            code = fake.codes['nia@example.com']
            type_code(pg, code)
            calls = fake.calls('POST', '/auth/v1/verify')
            check(f'V1 {label}: the right code logs in, and is sent with the address and no Authorization header', len(calls) == 1 and calls[0]['body'] == {'type': 'email', 'email': 'nia@example.com', 'token': code} and calls[0]['auth'] is None, calls and calls[0])
            check(f'V1 {label}: the account is confirmed now', fake.users['nia@example.com']['confirmed'] is True)
            check(f'V1 {label}: a brand new account goes to the quiz step, not into the app', pg.evaluate("[S.stage,S.done,S.vmail]") == ['prompt', False, ''], pg.evaluate("[S.stage,S.done,S.vmail]"))
            check(f'V1 {label}: now there is a login and a device copy of the account', store(pg, 'bl.sb') and store(pg, 'bl.sb')['email'] == 'nia@example.com' and store(pg, 'bl.users')['nia@example.com']['name'] == 'Nia New', store(pg, 'bl.users'))
            check(f'V1 {label}: no password was kept on the device', 'pw' not in store(pg, 'bl.users')['nia@example.com'])
            do_quiz(pg)
            check(f'V1 {label}: after the quiz the person is on Home', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True])
            check(f'V1 {label}: no page errors and no broken fake rules', errs == [] and fake.violations == [], [errs[:2], fake.violations])
            ctx.close()
    section(v1_flow)

    # ---------- V2: reload and Back ----------
    def v2_reload():
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'rae@example.com')
        pg.reload(); w(pg, 800)
        check('V2 a reload keeps the person on the code screen, with the same address', stage(pg) == 'verify' and pg.locator('#full b', has_text='rae@example.com').count() == 1, [stage(pg), txt(pg)[:80]])
        type_code(pg, fake.codes['rae@example.com'])
        check('V2 the code still works after the reload', stage(pg) == 'prompt' and fake.users['rae@example.com']['confirmed'], stage(pg))
        ctx.close()
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'sol@example.com')
        pg.go_back(); w(pg, 500)
        check('V2 the browser Back button goes to the sign-up form, with the details still in it', stage(pg) == 'signup' and pg.input_value('#a_email') == 'sol@example.com' and pg.input_value('#a_name') == 'Nia New', [stage(pg), pg.evaluate("FORM")])
        pg.go_forward(); w(pg, 500)
        check('V2 Forward comes back to the code screen', stage(pg) == 'verify' and 'sol@example.com' in txt(pg))
        pg.click('#full [data-act="back2"]'); w(pg, 600)
        check('V2 the on-screen Back link does the same as the browser Back button', stage(pg) == 'signup', stage(pg))
        # signing up again with the same address (the first code never arrived) sends a new code and keeps working
        pg.fill('#a_pw', PW); pg.click('[data-act="dosignup"]'); w(pg, 900)
        check('V2 signing up again with an address that was never confirmed leads back to the code screen with a new code', stage(pg) == 'verify' and [k for k, e, c in fake.emails] == ['signup', 'signup'] and fake.emails[0][2] != fake.emails[1][2], fake.emails)
        type_code(pg, fake.emails[0][2])
        check('V2 the first code no longer works', stage(pg) == 'verify' and err(pg) == WRONG, [stage(pg), err(pg)])
        type_code(pg, fake.emails[1][2])
        check('V2 the newest code does', stage(pg) == 'prompt')
        ctx.close()
    section(v2_reload)

    # ---------- V3: wrong, short and badly typed codes ----------
    def v3_codes():
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'tia@example.com')
        code = fake.codes['tia@example.com']
        wrong = '000000' if code != '000000' else '111111'
        type_code(pg, wrong)
        check('V3 a wrong code says so in plain words and stays on the screen', stage(pg) == 'verify' and err(pg) == WRONG, [stage(pg), err(pg)])
        check('V3 what was typed is still in the box, and the button works again', pg.input_value('#v_code') == wrong and pg.locator('[data-act="doverify"]').is_enabled())
        check('V3 a wrong code logged nobody in', pg.evaluate("[S.me,SBS]") == [None, None] and fake.users['tia@example.com']['confirmed'] is False)
        type_code(pg, '123')
        check('V3 a code that is too short is caught on the page, without asking the server', err(pg).startswith('Type the code from the email') and len(fake.calls('POST', '/auth/v1/verify')) == 1, [err(pg), len(fake.calls('POST', '/auth/v1/verify'))])
        type_code(pg, 'abcdef')
        check('V3 letters do not count as a code', err(pg).startswith('Type the code from the email'), err(pg))
        type_code(pg, '')
        check('V3 an empty box is caught too', err(pg).startswith('Type the code from the email'))
        fake.code_old.add('tia@example.com')
        type_code(pg, code)
        check('V3 a code that has run out says the same plain thing', stage(pg) == 'verify' and err(pg) == WRONG, err(pg))
        fake.code_old.discard('tia@example.com')
        type_code(pg, code[:3] + ' ' + code[3:])
        check('V3 a space in the middle (as in some email apps) is ignored', stage(pg) == 'prompt', [stage(pg), err(pg)])
        ctx.close()
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'uma@example.com')
        code = fake.codes['uma@example.com']
        type_code(pg, ' ' + code[:3] + '-' + code[3:] + ' ')
        check('V3 a dash and spaces around the code are ignored', stage(pg) == 'prompt', [stage(pg), err(pg)])
        ctx.close()
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'vic@example.com')
        type_code(pg, fake.codes['vic@example.com'], press=True)
        check('V3 pressing Enter in the code box confirms it', stage(pg) == 'prompt', stage(pg))
        ctx.close()
    section(v3_codes)

    # ---------- V4: send a new code ----------
    def v4_resend():
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'wyn@example.com')
        first = fake.codes['wyn@example.com']
        pg.click('#full [data-act="resend"]'); w(pg, 700)
        check('V4 Send a new code emails a new code', [k for k, e, c in fake.emails] == ['signup', 'resend'] and fake.emails[1][2] != first, fake.emails)
        check('V4 the page says a new code was sent and the old one stops working', 'We sent a new code to wyn@example.com' in pg.locator('#full .inf').inner_text() and 'old one no longer works' in pg.locator('#full .inf').inner_text(), pg.locator('#full .inf').count())
        rs = fake.calls('POST', '/auth/v1/resend')
        check('V4 the request names the address and has no Authorization header', len(rs) == 1 and rs[0]['body'] == {'type': 'signup', 'email': 'wyn@example.com'} and rs[0]['auth'] is None, rs)
        type_code(pg, first)
        check('V4 the old code is refused', stage(pg) == 'verify' and err(pg) == WRONG, [stage(pg), err(pg)])
        fake.resend_wait = True
        pg.click('#full [data-act="resend"]'); w(pg, 700)
        check('V4 asking again too soon gets the plain “wait a minute” message and no new email', err(pg) == 'Too many tries right now. Wait a minute and try again.' and len(fake.emails) == 2, [err(pg), len(fake.emails)])
        fake.resend_wait = False
        type_code(pg, fake.codes['wyn@example.com'])
        check('V4 the new code works', stage(pg) == 'prompt', [stage(pg), err(pg)])
        ctx.close()
    section(v4_resend)

    # ---------- V5: an email that already has an account ----------
    def v5_existing():
        fake = on(Fake())
        fake.add_user('old@example.com', PW, {'name': 'Old Timer', 'role': 'Student', 'provider': False, 'org': ''})
        ctx, pg, errs = newpage(b, P, fake, APP0)
        pg.click('#full [data-act="signup"]'); w(pg)
        fill_signup(pg, 'Someone Else', 'old@example.com'); pg.click('[data-act="dosignup"]'); w(pg, 900)
        check('V5 an email that already has a confirmed account is told so, on the form', stage(pg) == 'signup' and err(pg) == 'That email already has an account. Try logging in.', [stage(pg), err(pg)])
        check('V5 no code was sent and nothing was logged in', fake.emails == [] and pg.evaluate("[S.me,SBS]") == [None, None])
        check('V5 what was typed is still in the form', pg.input_value('#a_name') == 'Someone Else' and pg.input_value('#a_email') == 'old@example.com')
        check('V5 the existing account was not changed', fake.users['old@example.com']['meta']['name'] == 'Old Timer' and fake.users['old@example.com']['pw'] == PW)
        ctx.close()
    section(v5_existing)

    # ---------- V6: log in before confirming ----------
    def v6_login():
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'xan@example.com')
        ctx.close()   # the person closed the tab without typing the code
        ctx2, pg2, errs2 = newpage(b, P, fake, APP0)
        pg2.click('#full [data-act="login"]'); w(pg2)
        pg2.fill('#a_email', 'xan@example.com'); pg2.fill('#a_pw', 'wrongpass'); pg2.click('[data-act="dologin"]'); w(pg2, 700)
        check('V6 a wrong password on an unconfirmed account is just a wrong password', stage(pg2) == 'login' and err(pg2) == 'Email or password is incorrect.', [stage(pg2), err(pg2)])
        pg2.fill('#a_pw', PW); pg2.click('[data-act="dologin"]'); w(pg2, 900)
        check('V6 the right password on an unconfirmed account leads to the code screen with a plain note', stage(pg2) == 'verify' and 'xan@example.com' in txt(pg2) and 'isn’t confirmed yet' in pg2.locator('#full .inf').inner_text(), [stage(pg2), txt(pg2)[:200]])
        check('V6 nobody is logged in yet', pg2.evaluate("[S.me,SBS]") == [None, None])
        pg2.click('#full [data-act="resend"]'); w(pg2, 700)
        check('V6 a new code can be asked for from there', len(fake.emails) == 2 and fake.emails[1][0] == 'resend')
        type_code(pg2, fake.codes['xan@example.com'])
        check('V6 the code confirms the account and logs in (no quiz answers yet, so the quiz step)', stage(pg2) == 'prompt' and fake.users['xan@example.com']['confirmed'] is True, [stage(pg2), err(pg2)])
        check('V6 the details given at sign-up came through', store(pg2, 'bl.users')['xan@example.com']['name'] == 'Nia New')
        ctx2.close()
        # a confirmed account with quiz answers logs in as usual and never sees the code screen
        fake = on(Fake())
        uid = fake.add_user('yan@example.com', PW, {'name': 'Yan', 'role': 'Student', 'provider': False, 'org': ''}); fake.profiles[uid]['quiz_answers'] = ANS
        ctx3, pg3, errs3 = newpage(b, P, fake, APP0)
        pg3.click('#full [data-act="login"]'); w(pg3)
        pg3.fill('#a_email', 'yan@example.com'); pg3.fill('#a_pw', PW); pg3.click('[data-act="dologin"]'); w(pg3, 1000)
        check('V6 a confirmed account logs in as usual and goes to Home', pg3.evaluate("[S.stage,S.tab]") == ['app', 'Home'] and fake.calls('POST', '/auth/v1/verify') == [], pg3.evaluate("[S.stage,S.tab]"))
        ctx3.close()
    section(v6_login)

    # ---------- V7: a different email, and an organizer ----------
    def v7_change():
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, P, fake, 'typo@exmaple.com')
        pg.click('#full [data-act="vchange"]'); w(pg, 500)
        check('V7 Use a different email goes back to the sign-up form with the old address ready to fix', stage(pg) == 'signup' and pg.input_value('#a_email') == 'typo@exmaple.com' and pg.input_value('#a_name') == 'Nia New' and pg.evaluate("S.vmail") == '', [stage(pg), pg.input_value('#a_email')])
        pg.fill('#a_email', 'right@example.com'); pg.fill('#a_pw', PW); pg.click('[data-act="dosignup"]'); w(pg, 900)
        check('V7 the corrected address gets its own code', stage(pg) == 'verify' and 'right@example.com' in txt(pg) and fake.emails[-1][1] == 'right@example.com', fake.emails)
        type_code(pg, fake.codes['right@example.com'])
        check('V7 and works', stage(pg) == 'prompt' and store(pg, 'bl.sb')['email'] == 'right@example.com')
        check('V7 the mistyped address stays unconfirmed in the project (it cannot log in)', fake.users['typo@exmaple.com']['confirmed'] is False)
        ctx.close()
        fake = on(Fake())
        ctx, pg, errs = to_verify(b, D, fake, 'org@example.com', name='Olive Organizer', role='Organizer', org='Houston Robotics Club')
        check('V7 an organizer also gets the code screen first', stage(pg) == 'verify', stage(pg))
        type_code(pg, fake.codes['org@example.com'])
        check('V7 after the code an organizer goes straight to Home with no quiz', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', False] and 'Post an opportunity' in pg.locator('#main').inner_text(), pg.evaluate("[S.stage,S.tab,S.done]"))
        check('V7 the organization name and account type came through', store(pg, 'bl.users')['org@example.com']['provider'] is True and store(pg, 'bl.users')['org@example.com']['org'] == 'Houston Robotics Club')
        ctx.close()
    section(v7_change)

    # ---------- V8: Confirm email off (how the live project is today) ----------
    def v8_off():
        fake = Fake()   # fake.confirm is False
        ctx, pg, errs = newpage(b, P, fake, APP0)
        pg.click('#full [data-act="signup"]'); w(pg)
        fill_signup(pg, 'Ona Off', 'ona@example.com'); pg.click('[data-act="dosignup"]'); w(pg, 900)
        check('V8 with Confirm email off, sign-up goes straight to the quiz step (no code screen)', stage(pg) == 'prompt' and fake.emails == [] and fake.calls('POST', '/auth/v1/verify') == [], [stage(pg), fake.emails])
        check('V8 and the person is logged in', store(pg, 'bl.sb') and store(pg, 'bl.sb')['email'] == 'ona@example.com')
        ctx.close()
    section(v8_off)

    # ---------- V9: other code lengths, the older verify type, errors ----------
    def v9_other():
        fake = on(Fake()); fake.code_len = 8
        ctx, pg, errs = to_verify(b, P, fake, 'abe@example.com')
        code = fake.codes['abe@example.com']
        check('V9 the pretend project is set to 8-digit codes', len(code) == 8, code)
        type_code(pg, code[:6])
        check('V9 six digits of an eight-digit code are refused by the server and the person is told', stage(pg) == 'verify' and err(pg) == WRONG, err(pg))
        type_code(pg, code)
        check('V9 an eight-digit code works', stage(pg) == 'prompt', [stage(pg), err(pg)])
        ctx.close()
        fake = on(Fake()); fake.verify_types = ('signup',)
        ctx, pg, errs = to_verify(b, P, fake, 'bea@example.com')
        type_code(pg, fake.codes['bea@example.com'])
        vs = fake.calls('POST', '/auth/v1/verify')
        check('V9 a project that only knows the older type name “signup” is retried once with it and works', stage(pg) == 'prompt' and [c['body']['type'] for c in vs] == ['email', 'signup'], [stage(pg), [c['body'] for c in vs]])
        ctx.close()
        fake = on(Fake()); fake.verify_types = ('email',)
        ctx, pg, errs = to_verify(b, P, fake, 'cal@example.com')
        type_code(pg, '000000')
        check('V9 a wrong code is asked about only once (a refused code is not retried under another type)', len(fake.calls('POST', '/auth/v1/verify')) == 1, len(fake.calls('POST', '/auth/v1/verify')))
        for mode, want in (('net', 'Can’t reach the server. Check your internet and try again.'), ('500', 'Something went wrong. Please try again.'), ('429', 'Too many tries right now. Wait a minute and try again.')):
            fake.fail = mode
            type_code(pg, fake.codes['cal@example.com'])
            check(f'V9 server trouble ({mode}) gives a plain message and keeps the screen', stage(pg) == 'verify' and err(pg) == want and pg.locator('[data-act="doverify"]').is_enabled(), [stage(pg), err(pg)])
        fake.fail = None
        type_code(pg, fake.codes['cal@example.com'])
        check('V9 and when it is back the same code still works', stage(pg) == 'prompt', [stage(pg), err(pg)])
        ctx.close()
    section(v9_other)

    # ---------- V10: looks ----------
    def v10_looks():
        for label, vp in (('phone', P), ('narrow', SP5), ('desktop', D)):
            for scheme in ('light', 'dark'):
                fake = on(Fake())
                ctx, pg, errs = to_verify(b, vp, fake, 'a-very-long-email-address-for-testing-the-layout@example-school-district.org', scheme=scheme)
                if scheme == 'dark': pg.evaluate("S.theme='dark';render()"); w(pg, 200)
                pg.screenshot(path=f'{SP}/shots/verify-{label}-{scheme}.png')
                pg.fill('#v_code', '000000'); pg.click('[data-act="doverify"]'); w(pg, 700)
                pg.screenshot(path=f'{SP}/shots/verify-{label}-{scheme}-error.png')
                check(f'V10 {label} {scheme}: no sideways scrolling, even with a very long email address', pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), pg.evaluate("[document.documentElement.scrollWidth,innerWidth]"))
                bad = pg.evaluate("[...document.querySelectorAll('#full *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+1||r.left<-1)}).map(e=>e.className||e.tagName).slice(0,5)")
                check(f'V10 {label} {scheme}: nothing sticks out past the edge of the screen', bad == [], bad)
                check(f'V10 {label} {scheme}: the code box and the Confirm email button are on screen', pg.evaluate("(()=>{const a=document.getElementById('v_code').getBoundingClientRect(),b=document.querySelector('[data-act=doverify]').getBoundingClientRect();return a.top>=0&&b.bottom<=innerHeight+1&&a.width>100})()"))
                check(f'V10 {label} {scheme}: no page errors', errs == [], errs[:2])
                ctx.close()
    section(v10_looks)


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
