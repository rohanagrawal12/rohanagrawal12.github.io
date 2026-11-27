"""
Tests for the new way into the app and for the Home page.

What this covers:
  H1  the quiz is required: the account step, the quiz step and the quiz itself have no way to skip, and always a way back
  H2  the four account types (student, parent, teacher, organizer) and the wording each one gets
  H3  where the person lives: the school clubs are for The Village School, the community list is for Houston
  H4  the ZIP code nudge for accounts that answered the quiz before the ZIP question existed
  H5  what Home shows
  H6  the logo and the name take you Home, and the tabs are in the right order

It runs the real page in headless Chromium against the pretend Supabase in fake_sb.py. Run it from the repo folder:
    python3 tools/test/test_home.py
"""
import json, os, re, subprocess, sys, time
from subprocess import DEVNULL
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fake_sb import Fake, SBRE, KEY

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = os.environ.get('BL_SHOTS', '/tmp/bulletin-test-shots'); os.makedirs(SP + '/shots', exist_ok=True)
PORT = 8777
URL = f'http://127.0.0.1:{PORT}/index.html'
srv = subprocess.Popen(['python3', '-I', '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=REPO, stdout=DEVNULL, stderr=DEVNULL)
time.sleep(1.0)

results = []; all_errs = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' | ' + str(detail)[:300]) if (detail != '' and not ok) else ''), flush=True)

ANS = {'grade': '10th grade', 'school': 'The Village School', 'zip': '77095', 'learn': 'biology and chemistry', 'want': ['Join a club'], 'why': ['Trying new things'], 'time': '3-5 hours'}
APP = {'stage': 'app', 'tab': 'Home', 'seen': True, 'done': True, 'theme': 'light', 'ans': ANS}
APP0 = {'stage': 'app', 'tab': 'School', 'seen': True, 'done': False, 'theme': 'light', 'ans': {}}
FILL = """(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='zip'?'77095':q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""
PW = 'secret1'
D = {'width': 1440, 'height': 900}
P = {'width': 390, 'height': 844}
ROLE_TXT = {'Student': 'I’m a student', 'Parent': 'parent or guardian', 'Teacher': 'I’m a teacher', 'Organizer': 'run a club'}

def newpage(b, vp, fake, state=None, sb=None, users=None, visit=True, scheme='light'):
    # keep the first-login tour out of the way here (it is covered by test_tour.py): guests and accounts count as having seen it
    if state is not None:
        state = dict(state); state.setdefault('toured', True)
    if users is not None:
        users = {k: dict(v, toured=v.get('toured', True)) for k, v in users.items()}
    mob = vp['width'] < 500
    ctx = b.new_context(viewport=vp, is_mobile=mob, has_touch=mob, color_scheme=scheme)
    js = "try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    if state is not None: js += "localStorage.setItem('bl.state',%s);" % json.dumps(json.dumps(state))
    if sb is not None: js += "localStorage.setItem('bl.sb',%s);" % json.dumps(json.dumps(sb))
    if users is not None: js += "localStorage.setItem('bl.users',%s);" % json.dumps(json.dumps(users))
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
def tab(pg, name):
    pg.locator(f'button[data-tab="{name}"]:visible').first.click(); w(pg)
def logged_in_page(b, vp, fake, email, state=None, role='Student', **kw):
    if email not in fake.users:
        fake.add_user(email, PW, {'name': email.split('@')[0].title(), 'role': role, 'provider': role == 'Organizer', 'org': ''})
    uid = fake.users[email]['id']
    seed = fake.sb_seed(fake.session(uid, None))
    st = dict(state if state is not None else APP, me=email)
    u = {email: {'name': fake.profiles[uid]['name'], 'email': email, 'role': role, 'provider': role == 'Organizer', 'org': '', 'friends': [], 'sb': 1}}
    ctx, pg, errs = newpage(b, vp, fake, state=st, sb=seed, users=u, **kw)
    return ctx, pg, errs, uid
def fill_signup(pg, name, email, role='Student', org=None):
    pg.fill('#a_name', name); pg.fill('#a_email', email); pg.fill('#a_pw', PW)
    pg.locator('.role', has_text=ROLE_TXT[role]).click()
    if org is not None: pg.fill('#a_org', org)
def do_quiz(pg, ms=700):
    pg.click('#full [data-act="quiz"]'); w(pg, 200)
    for i in range(4):
        pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
    pg.wait_for_function("S.stage==='app'", timeout=9000)
    pg.evaluate("if(TOUR!==null)tourEnd()")   # a guest's first visit to Home starts the tour: close it so it does not cover the page
    w(pg, ms)
def txt(pg, sel='body'):
    return pg.locator(sel).inner_text()
def stage(pg):
    return pg.evaluate("S.stage")

def section(fn):
    try:
        fn()
    except Exception as e:
        check(f'{fn.__name__} CRASHED', False, repr(e)[:400])


def run(b):
    # ---------- H1: the quiz is required, and there is always a way back ----------
    def h1_required():
        fake = Fake()
        for label, vp in (('phone', P), ('desktop', D)):
            ctx, pg, errs = newpage(b, vp, fake, APP0)
            t = txt(pg, '#full')
            check(f'H1 {label}: with no quiz and no login the first thing is the account step', stage(pg) == 'auth' and 'STEP 1 OF 2' in t and 'First, make a free account.' in t, t[:200])
            check(f'H1 {label}: it offers Create account, Continue as a guest and Log in, and nothing that skips the quiz',
                  all(pg.locator(f'#full [data-act="{a}"]').count() == 1 for a in ('signup', 'guest', 'login')) and not re.search(r'skip|open the app|not now|go to app', txt(pg), re.I), t[:300])
            for js in ("S.stage='app';S.tab='School';render()", "go('Community')", "act('home')", "act('start')", "S.tab='Explore';S.stage='app';render()"):
                pg.evaluate(js); w(pg, 150)
                check(f'H1 {label}: trying to get in with {js[:24]!r} does not work', stage(pg) != 'app', stage(pg))
            pg.click('#full [data-act="guest"]'); w(pg)
            t = txt(pg, '#full')
            check(f'H1 {label}: "Continue as a guest" leads to the quiz step, which says nothing is matched yet', stage(pg) == 'prompt' and 'ONE LAST STEP' in t and 'Take the quiz to see your matches.' in t and 'Nothing is matched to you yet.' in t, t[:300])
            bx = pg.locator('#full [data-act="quiz"]').bounding_box()
            check(f'H1 {label}: the Take the quiz button is big and on the first screen without scrolling', bx and bx['height'] >= 44 and bx['y'] + bx['height'] <= vp['height'] and bx['width'] >= 200, bx)
            check(f'H1 {label}: that step has no skip, no Open the app and no Not now', not re.search(r'skip|open the app|not now|go to app', txt(pg), re.I), t[:300])
            pg.click('#full [data-act="back2"]'); w(pg, 500)
            check(f'H1 {label}: the Back link on that step goes back to the account step', stage(pg) == 'auth', stage(pg))
            pg.click('#full [data-act="guest"]'); w(pg)
            pg.go_back(); w(pg, 500)
            check(f'H1 {label}: the browser Back button also goes back to the account step', stage(pg) == 'auth', stage(pg))
            pg.click('#full [data-act="guest"]'); w(pg)
            pg.click('#full [data-act="quiz"]'); w(pg)
            t = txt(pg, '#full')
            check(f'H1 {label}: quiz page 1 is about “you”, has a Back button and no skip', stage(pg) == 'quiz' and 'TELL US ABOUT YOU' in t and 'What grade/year are you in?' in t and pg.locator('.qf .btn').first.inner_text().strip() == '‹ Back' and not re.search(r'skip|not now', t, re.I), t[:300])
            pg.click('[data-act="next"]'); w(pg, 200)
            check(f'H1 {label}: Next with nothing answered says what to answer', pg.locator('#full .err').inner_text() == 'Please answer: What grade/year are you in?', pg.locator('#full .err').inner_text())
            pg.select_option('select[data-id="grade"]', '10th grade'); pg.select_option('select[data-id="school"]', 'The Village School')
            for bad, why in (('', 'empty'), ('1234', 'four digits'), ('abcde', 'letters'), ('77 95', 'a space')):
                pg.fill('input[data-id="zip"]', bad); pg.click('[data-act="next"]'); w(pg, 150)
                check(f'H1 {label}: a ZIP of {why} is stopped with a plain message', pg.locator('#full .err').inner_text() == 'Enter a 5-digit ZIP code, like 77095.' and pg.evaluate("S.step") == 0, pg.locator('#full .err').inner_text())
            pg.fill('input[data-id="zip"]', '77095'); pg.click('[data-act="next"]'); w(pg, 200)
            check(f'H1 {label}: a good ZIP lets the quiz move on', pg.evaluate("S.step") == 1)
            pg.click('.qf [data-act="back"]'); w(pg, 500)
            check(f'H1 {label}: Back on page 2 returns to page 1 and keeps what was typed', pg.evaluate("S.step") == 0 and pg.input_value('input[data-id="zip"]') == '77095' and pg.input_value('select[data-id="grade"]') == '10th grade')
            # tapping Back and then Next again quickly must not trip the Back button's safety timer (it used to send the person one page back 0.4 s later)
            pg.evaluate(FILL); pg.click('[data-act="next"]'); pg.wait_for_function("S.step===1", timeout=3000)
            pg.click('.qf [data-act="back"]'); pg.wait_for_function("S.step===0", timeout=3000)
            pg.evaluate(FILL); pg.click('[data-act="next"]'); pg.wait_for_function("S.step===1", timeout=3000)
            pg.evaluate(FILL); pg.click('[data-act="next"]'); pg.wait_for_function("S.step===2", timeout=3000); w(pg, 900)
            check(f'H1 {label}: Back then Next quickly twice ends on the right page, not one page back', pg.evaluate("S.step") == 2, pg.evaluate("S.step"))
            for i in range(2):
                pg.click('.qf [data-act="back"]'); pg.wait_for_function("S.step===%d" % (1 - i), timeout=3000)
            pg.click('.qf [data-act="qback"]'); w(pg, 500)
            check(f'H1 {label}: Back on page 1 returns to the quiz step, not into the app', stage(pg) == 'prompt', stage(pg))
            pg.reload(); w(pg, 600)
            check(f'H1 {label}: reloading on the quiz step keeps it there', stage(pg) == 'prompt', stage(pg))
            do_quiz(pg)
            t = txt(pg, '#main')
            check(f'H1 {label}: finishing the quiz opens Home', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', True] and 'HOME' in t, pg.evaluate("[S.stage,S.tab,S.done]"))
            check(f'H1 {label}: a guest’s Home says so and offers a free account', 'You’re using Bulletin as a guest' in t and pg.locator('#main [data-act="signup"]').count() == 1, t[:300])
            check(f'H1 {label}: and still no Open the app or skip anywhere', not re.search(r'open the app|skip', txt(pg), re.I))
            pg.reload(); w(pg, 600)
            check(f'H1 {label}: after the quiz a reload stays in the app', pg.evaluate("[S.stage,S.done]") == ['app', True], pg.evaluate("[S.stage,S.done]"))
            check(f'H1 {label}: no page errors', errs == [], errs[:3])
            ctx.close()
    section(h1_required)

    # ---------- H2: the four account types ----------
    def h2_roles():
        cases = [
            ('Student', 'Take the quiz to see your matches.', 'Nothing is matched to you yet.', 'TELL US ABOUT YOU', 'What grade/year are you in?', 'Here’s a summary of your matches and your activity.'),
            ('Parent', 'Take the quiz about your child.', 'Nothing is matched to your child yet.', 'TELL US ABOUT YOUR CHILD', 'What grade/year is your child in?', 'Here’s what we found for your child.'),
            ('Teacher', 'Take the quiz about the student.', 'Nothing is matched to the student yet.', 'TELL US ABOUT THE STUDENT', 'What grade/year is the student in?', 'Here’s what we found for the student.'),
        ]
        for role, h1, nothing, eyebrow, q1, homeline in cases:
            fake = Fake()
            ctx, pg, errs = newpage(b, D, fake, APP0)
            pg.click('#full [data-act="signup"]'); w(pg)
            if role == 'Student':
                cards = pg.locator('.role').all_inner_texts()
                check('H2 the sign-up form shows four kinds of account, each with a plain sentence about what changes', len(cards) == 4 and all(len(c.split('\n')[-1]) > 40 for c in cards), cards)
                check('H2 the cards name the four kinds', [c.split('\n')[0] for c in cards] == ['I’m a student', 'I’m a parent or guardian', 'I’m a teacher, counselor or professor', 'I run a club, program or organization'], [c.split('\n')[0] for c in cards])
                check('H2 the Parent card says the quiz is answered about the child', 'answer the quiz about your child' in cards[1], cards[1])
                check('H2 the Teacher card says the quiz is about a student they are helping', 'quiz about a student you’re helping' in cards[2], cards[2])
                check('H2 the Organizer card says organizers do not take the quiz', 'don’t take the quiz' in cards[3], cards[3])
                check('H2 the organization box is hidden until Organizer is picked, and shows when it is', not pg.locator('#a_org').is_visible() and (pg.locator('.role', has_text='run a club').click() or True) and pg.locator('#a_org').is_visible())
            fill_signup(pg, f'Pat {role}', f'{role.lower()}@example.com', role)
            pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.me&&S.stage==='prompt'", timeout=8000); w(pg, 300)
            t = txt(pg, '#full')
            check(f'H2 {role}: after sign-up the quiz step says “{h1}” and “{nothing}”', h1 in t and nothing in t, t[:300])
            pg.click('#full [data-act="quiz"]'); w(pg, 200)
            t = txt(pg, '#full')
            check(f'H2 {role}: quiz page 1 says {eyebrow.title()} and asks “{q1}”', eyebrow in t and q1 in t, t[:300])
            if role != 'Student':
                pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 200)
                t = txt(pg, '#full')
                check(f'H2 {role}: page 2 talks about them, not about “you”', 'telling a friend about' in t and 'enjoy learning about' in t and 'What do you enjoy' not in t, t[:300])
                pg.click('.qf [data-act="back"]'); pg.wait_for_function("S.step===0", timeout=4000); w(pg, 200)
            for i in range(4):
                pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg, 150)
            pg.wait_for_function("S.stage==='app'", timeout=9000); w(pg, 600)
            t = txt(pg, '#main')
            check(f'H2 {role}: Home is the first screen and says “{homeline}”', pg.evaluate("S.tab") == 'Home' and homeline in t and f'Hi, Pat.' in t, t[:300])
            check(f'H2 {role}: the account is shown as {role} in Settings', (tab(pg, 'Settings') or True) and f'· {role}' in txt(pg, '#main'), txt(pg, '#main')[:300])
            check(f'H2 {role}: the answers were saved to the account about the person, role kept', fake.profiles[fake.users[f"{role.lower()}@example.com"]["id"]].get('role') == role)
            check(f'H2 {role}: no page errors', errs == [], errs[:3])
            ctx.close()
        # an organizer posts opportunities instead of looking for them: no quiz
        fake = Fake()
        ctx, pg, errs = newpage(b, D, fake, APP0)
        pg.click('#full [data-act="signup"]'); w(pg)
        fill_signup(pg, 'Olive Organizer', 'olive@example.com', 'Organizer')
        pg.click('[data-act="dosignup"]'); w(pg, 500)
        check('H2 Organizer: an organization name is required', pg.locator('#af .err').inner_text() == 'Enter the name of your organization.', pg.locator('#af .err').inner_text())
        pg.fill('#a_org', 'Houston Robotics Club'); pg.click('[data-act="dosignup"]'); pg.wait_for_function("S.me", timeout=8000); w(pg, 800)
        check('H2 Organizer: goes straight to Home with no quiz', pg.evaluate("[S.stage,S.tab,S.done]") == ['app', 'Home', False], pg.evaluate("[S.stage,S.tab,S.done]"))
        t = txt(pg, '#main')
        check('H2 Organizer: Home is about listings, with a Post an opportunity button and what students see', 'Houston Robotics Club · You post opportunities for students to find.' in t and 'Post an opportunity' in t and 'Your listings' in t and 'What students see' in t and 'You haven’t posted anything yet.' in t, t[:400])
        check('H2 Organizer: Home has no quiz button, no match levels and no ZIP box', pg.locator('#main [data-act="quiz"]').count() == 0 and pg.locator('#main .hm').count() == 0 and pg.locator('#z_in').count() == 0)
        prof = fake.profiles[fake.users['olive@example.com']['id']]
        check('H2 Organizer: the account is saved as an organizer with its organization', prof.get('role') == 'Organizer' and prof.get('is_provider') is True and prof.get('org') == 'Houston Robotics Club', prof)
        tab(pg, 'School')
        check('H2 Organizer: a list tab shows what students see, with no quiz banner and no Retake button', 'This is what students see.' in txt(pg, '#main') and pg.locator('#main .qb').count() == 0 and pg.locator('#main [data-act="quiz"]').count() == 0, txt(pg, '#main')[:200])
        pg.reload(); w(pg, 800)
        check('H2 Organizer: a reload stays in the app (never held at the quiz)', stage(pg) == 'app', stage(pg))
        check('H2 Organizer: no page errors', errs == [], errs[:3])
        ctx.close()
    section(h2_roles)

    # ---------- H3: where the person is ----------
    def h3_places():
        fake = Fake()
        cases = [
            ('Houston, Village School', dict(zip='77095', school='The Village School'), True, True),
            ('Houston, another school', dict(zip='77095', school='Another school (not listed yet)'), False, True),
            ('far away, Village School', dict(zip='90210', school='The Village School'), True, False),
            ('far away, another school', dict(zip='90210', school='Another school (not listed yet)'), False, False),
        ]
        for name, extra, has_school, has_comm in cases:
            ctx, pg, errs = newpage(b, D, fake, dict(APP, ans=dict(ANS, **extra)))
            t = txt(pg, '#main')
            check(f'H3 {name}: Home ' + ('shows school clubs' if has_school else 'says there is no club list for the school yet'), ('No club list for your school yet' in t) == (not has_school), t[:200])
            check(f'H3 {name}: Home ' + ('shows community opportunities' if has_comm else 'says nothing is near the ZIP and points to Explore'), ('nothing is near ZIP' in t) == (not has_comm) and (has_comm or f'nothing is near ZIP {extra["zip"]} yet. Explore has programs open to everyone.' in t), t[:300])
            sec = pg.evaluate("[...document.querySelectorAll('#main .hs')].map(s=>s.querySelectorAll('.hr').length)")
            check(f'H3 {name}: Home lists three Explore matches either way', sec[2] == 3, sec)
            check(f'H3 {name}: Home lists three matches for each place that has some', (sec[0] == 3) == has_school and (sec[1] == 3) == has_comm, sec)
            tab(pg, 'School'); n = pg.locator('#main .it2').count(); t = txt(pg, '#main')
            check(f'H3 {name}: the School tab ' + ('has clubs' if has_school else 'explains there is no list yet and offers Community and Explore'), (n > 0) == has_school and (has_school or ('No club list for your school yet' in t and pg.locator('#main .empty + .row [data-tab="Explore"]').count() == 1)), (n, t[:200]))
            tab(pg, 'Community'); n = pg.locator('#main .it2').count(); t = txt(pg, '#main')
            check(f'H3 {name}: the Community tab ' + ('has opportunities' if has_comm else 'explains nothing is near the ZIP and offers Explore'), (n > 0) == has_comm and (has_comm or (f'nothing near ZIP {extra["zip"]}' in t.replace('there is nothing near', 'nothing near') and pg.locator('#main .empty + .row [data-tab="Explore"]').count() == 1)), (n, t[:250]))
            tab(pg, 'Explore'); n = pg.locator('#main .it2').count()
            check(f'H3 {name}: the Explore tab always has programs', n > 0, n)
            if not has_school:
                pg.evaluate("go('Home')"); w(pg, 200)
                pg.fill('#q', 'robotics'); w(pg, 400)
                scopes = pg.evaluate("[...document.querySelectorAll('#main h2')].map(h=>h.textContent.split(' ')[0])")
                check(f'H3 {name}: search never shows school clubs for a different school', 'School' not in scopes, scopes)
            check(f'H3 {name}: no page errors', errs == [], errs[:3])
            ctx.close()
    section(h3_places)

    # ---------- H4: the ZIP nudge for older accounts ----------
    def h4_zip_nudge():
        old = {k: v for k, v in ANS.items() if k != 'zip'}
        # a guest on this device, quiz done before the ZIP question existed
        fake = Fake()
        ctx, pg, errs = newpage(b, P, fake, dict(APP, ans=old))
        t = txt(pg, '#main')
        check('H4 a guest with no ZIP sees an Add your ZIP code card on Home, with a box and a Save button', 'Add your ZIP code' in t and pg.locator('#main #z_in').count() == 1 and pg.locator('#main [data-act="setzip"]').count() == 1, t[:300])
        check('H4 the ZIP box is a numeric box with a 5 character limit and a label for screen readers', pg.get_attribute('#z_in', 'inputmode') == 'numeric' and pg.get_attribute('#z_in', 'maxlength') == '5' and pg.get_attribute('#z_in', 'aria-label') == 'ZIP code')
        pg.screenshot(path=f'{SP}/shots/home-zip-card-phone.png', full_page=True)
        lay = pg.evaluate("(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return[Math.round(b.left),Math.round(b.right)]};return{iw:innerWidth,sw:document.documentElement.scrollWidth,box:r('#z_in'),btn:r('[data-act=setzip]')}})()")
        check('H4 on a phone the ZIP box and its Save button sit side by side inside the screen', lay['box'][0] >= 0 and lay['btn'][1] <= lay['iw'] and lay['box'][1] <= lay['btn'][0] and lay['sw'] <= lay['iw'], lay)
        for bad in ('', 'abc', '1234'):
            pg.fill('#z_in', bad); pg.click('[data-act="setzip"]'); w(pg, 200)
            check(f'H4 a ZIP of {bad!r} is stopped with a plain message and the card stays', pg.locator('#main .err').inner_text() == 'Enter a 5-digit ZIP code, like 77095.' and pg.locator('#z_in').count() == 1, pg.locator('#main .err').inner_text())
        pg.fill('#z_in', '90210'); pg.click('[data-act="setzip"]'); w(pg, 300)
        t = txt(pg, '#main')
        check('H4 a good ZIP is saved, the card goes away, and Home now knows the person is far from Houston', pg.evaluate("S.ans.zip") == '90210' and 'Add your ZIP code' not in t and 'nothing is near ZIP 90210' in t, t[:300])
        pg.reload(); w(pg, 600)
        check('H4 after a reload the card stays gone', 'Add your ZIP code' not in txt(pg, '#main') and pg.evaluate("S.ans.zip") == '90210')
        ctx.close()
        # a signed-in account: the ZIP goes up to the account
        fake = Fake()
        uid = fake.add_user('old@example.com', PW, {'name': 'Old Timer', 'role': 'Student', 'provider': False, 'org': ''})
        fake.profiles[uid]['quiz_answers'] = old
        ctx, pg, errs, uid = logged_in_page(b, D, fake, 'old@example.com', state=dict(APP, ans=old))
        w(pg, 900)
        check('H4 a signed-in account with no ZIP gets the card too', 'Add your ZIP code' in txt(pg, '#main'))
        pg.fill('#z_in', '77095'); pg.click('[data-act="setzip"]'); w(pg, 1800)
        check('H4 the ZIP reaches the account, with the old answers kept', (fake.profiles[uid].get('quiz_answers') or {}).get('zip') == '77095' and fake.profiles[uid]['quiz_answers'].get('learn') == 'biology and chemistry', fake.profiles[uid].get('quiz_answers'))
        check('H4 and the card is gone', 'Add your ZIP code' not in txt(pg, '#main'))
        check('H4 no page errors', errs == [], errs[:3])
        ctx.close()
        # a person who has the ZIP never sees it
        ctx, pg, errs = newpage(b, D, Fake(), APP)
        check('H4 someone who already gave a ZIP never sees the card', 'Add your ZIP code' not in txt(pg, '#main'))
        ctx.close()
    section(h4_zip_nudge)

    # ---------- H5: what Home shows ----------
    def h5_home():
        fake = Fake()
        uid = fake.add_user('ada@example.com', PW, {'name': 'Ada Lovelace', 'role': 'Student', 'provider': False, 'org': ''})
        fake.profiles[uid]['quiz_answers'] = ANS
        for label, vp in (('desktop', D), ('phone', P)):
            ctx, pg, errs, uid = logged_in_page(b, vp, fake, 'ada@example.com', state=dict(APP, saved={'school-001': True, 'community-001': True}, mine={'explore-001': True}))
            w(pg, 1200)
            t = txt(pg, '#main')
            check(f'H5 {label}: Home greets the person by first name and says what it is', pg.evaluate("S.tab") == 'Home' and 'HOME' in t and 'Hi, Ada.' in t and 'Here’s a summary of your matches and your activity.' in t, t[:200])
            tiles = pg.evaluate("[...document.querySelectorAll('#main .ht')].map(e=>[e.querySelector('span').textContent,e.querySelector('b').textContent])")
            check(f'H5 {label}: four count boxes: Saved, I’m doing, Messages, Friends', tiles == [['Saved', '2'], ['I’m doing', '1'], ['Messages', '0'], ['Friends', '0']], tiles)
            titles = pg.evaluate("[...document.querySelectorAll('#main .hs .hh h3')].map(e=>e.textContent)")
            check(f'H5 {label}: three top-match sections: At your school, Near you, Online and national', titles == ['At your school', 'Near you', 'Online and national'], titles)
            rows = pg.evaluate("[...document.querySelectorAll('#main .hs')].slice(0,3).map(s=>[...s.querySelectorAll('.hr')].map(r=>({n:r.querySelector('.hn button').textContent,m:r.querySelector('.hm')?r.querySelector('.hm').textContent:null,b:!!r.querySelector('.bm')})))")
            check(f'H5 {label}: each section has three rows, each with a name, a match level out of 10 and a bookmark', all(len(s) == 3 and all(r['n'] and re.fullmatch(r'(10|[1-9])/10', r['m'] or '') and r['b'] for r in s) for s in rows), rows)
            sc = pg.evaluate("[...document.querySelectorAll('#main .hs')].slice(0,3).map(s=>[...s.querySelectorAll('.hm')].map(e=>parseInt(e.textContent)))")
            check(f'H5 {label}: inside each section the best match is first', all(s == sorted(s, reverse=True) for s in sc), sc)
            check(f'H5 {label}: something the person is already doing is not offered again', 'explore-001' not in pg.evaluate("[...document.querySelectorAll('#main .hs [data-act=viewopp]')].map(e=>e.dataset.id)"))
            ln = pg.evaluate("[...document.querySelectorAll('#main .hh .lk')].map(e=>e.dataset.tab)")
            check(f'H5 {label}: each section has a See all link to its tab', ln == ['School', 'Community', 'Explore'], ln)
            cu = pg.evaluate("[...document.querySelectorAll('#main .hcols section')].map(s=>[s.querySelector('h2').textContent,s.querySelectorAll('.hr').length])")
            check(f'H5 {label}: Coming up (up to three dated things) and Saved (the two saved ones) sit below', cu[0][0] == 'Coming up' and 1 <= cu[0][1] <= 3 and cu[1] == ['Saved', 2], cu)
            check(f'H5 {label}: the page does not scroll sideways', pg.evaluate("document.documentElement.scrollWidth<=innerWidth"))
            pg.screenshot(path=f'{SP}/shots/home-{label}.png', full_page=True)
            # tiles open that part of My Activities
            pg.locator('#main .ht').nth(0).click(); w(pg, 300)
            check(f'H5 {label}: the Saved box opens My Activities on the saved items', pg.evaluate("[S.tab,S.seg]") == ['My Activities', 'saved'], pg.evaluate("[S.tab,S.seg]"))
            tab(pg, 'Home')
            pg.locator('#main .ht').nth(1).click(); w(pg, 300)
            check(f'H5 {label}: the I’m doing box opens that list', pg.evaluate("[S.tab,S.seg]") == ['My Activities', 'doing'], pg.evaluate("[S.tab,S.seg]"))
            tab(pg, 'Home')
            # See all
            for i, tb in enumerate(('School', 'Community', 'Explore')):
                pg.locator('#main .hh .lk').nth(i).click(); w(pg, 250)
                check(f'H5 {label}: See all in section {i + 1} opens {tb}', pg.evaluate("S.tab") == tb, pg.evaluate("S.tab"))
                tab(pg, 'Home')
            # a name opens that opportunity, expanded, in its own tab
            first = pg.locator('#main .hs').nth(2).locator('.hn button').first
            oid = first.get_attribute('data-id'); first.click(); w(pg, 300)
            check(f'H5 {label}: tapping a name opens that opportunity, already expanded, on its own tab', pg.evaluate("S.tab") == 'Explore' and pg.locator('#main .it2.open').count() == 1 and pg.locator('#main .it2.open [data-act="explore"]').get_attribute('data-id') == oid, pg.evaluate("S.tab"))
            tab(pg, 'Home')
            # the bookmark on Home saves it and the box goes up
            bm = pg.locator('#main .hs').nth(2).locator('.bm').first
            sid = bm.get_attribute('data-id'); bm.click(); w(pg, 400)
            check(f'H5 {label}: the bookmark on Home saves it, the Saved count goes up and it shows under Saved', pg.evaluate("!!S.saved['%s']" % sid) and pg.locator('#main .ht').nth(0).locator('b').inner_text() == '3' and pg.locator('#main .hcols section').nth(1).locator('.hr').count() == 3, (sid, pg.locator('#main .ht').nth(0).locator('b').inner_text()))
            check(f'H5 {label}: no page errors', errs == [], errs[:3])
            ctx.close()
        # an account with a lot saved shows only three, with a link to the rest
        ctx, pg, errs, uid = logged_in_page(b, D, fake, 'ada@example.com', state=dict(APP, saved={'school-001': True, 'school-002': True, 'school-003': True, 'school-004': True, 'community-001': True}))
        w(pg, 1000)
        check('H5 five saved items: Home shows three and a link to see all of them', pg.locator('#main .hcols section').nth(1).locator('.hr').count() == 3 and pg.locator('#main [data-act="goseg"][data-v="saved"].lk').count() == 1, pg.locator('#main .hcols section').nth(1).inner_text()[:200])
        ctx.close()
        # nothing saved yet
        ctx, pg, errs = newpage(b, D, Fake(), APP)
        check('H5 nothing saved yet: Home says how to save something', 'Nothing saved yet. Tap the bookmark on anything you like.' in txt(pg, '#main'))
        ctx.close()
    section(h5_home)

    # ---------- H6: the logo and the name take you Home; the tabs ----------
    def h6_logo():
        for label, vp in (('desktop', D), ('phone', P)):
            ctx, pg, errs = newpage(b, vp, Fake(), APP)
            order = pg.evaluate("[...document.querySelectorAll('#nav button')].map(e=>e.dataset.tab)")
            check(f'H6 {label}: five tabs, Home first', order == ['Home', 'School', 'Community', 'Explore', 'My Activities'], order)
            bn = pg.evaluate("[...document.querySelectorAll('#bn button')].map(e=>e.innerText.trim())")
            check(f'H6 {label}: the bottom bar has the same five, with a shorter last name', bn == ['Home', 'School', 'Community', 'Explore', 'Activity'], bn)
            check(f'H6 {label}: the Home tab is marked as the current one', pg.evaluate("document.querySelector('#nav button.on').dataset.tab") == 'Home')
            for t_ in ('School', 'Community', 'Explore', 'My Activities', 'Settings'):
                tab(pg, t_)
                pg.click('.brand'); w(pg, 300)
                check(f'H6 {label}: the logo and name on {t_} go Home', pg.evaluate("S.tab") == 'Home' and 'HOME' in txt(pg, '#main'), pg.evaluate("S.tab"))
            bx = pg.locator('.brand').bounding_box()
            for part, fx in (('the left end (the four tiles)', 0.06), ('the right end (the word “bulletin”)', 0.94)):
                tab(pg, 'School')
                pg.mouse.click(bx['x'] + bx['width'] * fx, bx['y'] + bx['height'] / 2); w(pg, 300)
                check(f'H6 {label}: tapping {part} goes Home', pg.evaluate("S.tab") == 'Home', (pg.evaluate("S.tab"), bx))
            tab(pg, 'Explore'); pg.click('.brand'); w(pg, 300); pg.go_back(); w(pg, 500)
            check(f'H6 {label}: the browser Back button after the logo returns to the page before', pg.evaluate("S.tab") == 'Explore', pg.evaluate("S.tab"))
            pg.fill('#q', 'robot'); w(pg, 400)
            check(f'H6 {label}: searching opens the results', pg.evaluate("S.tab") == 'Search')
            pg.click('.brand'); w(pg, 300)
            check(f'H6 {label}: the logo leaves the search results for Home', pg.evaluate("S.tab") == 'Home' and 'HOME' in txt(pg, '#main'))
            pg.fill('#q', 'robot'); w(pg, 300); pg.fill('#q', ''); w(pg, 400)
            check(f'H6 {label}: clearing the search box goes to Home', pg.evaluate("S.tab") == 'Home')
            check(f'H6 {label}: no page errors', errs == [], errs[:3])
            ctx.close()
        # looks: Home, light and dark, phone and desktop (screenshots; also check nothing is wider than the screen)
        for label, vp, scheme in (('desktop-light', D, 'light'), ('desktop-dark', D, 'dark'), ('phone-light', P, 'light'), ('phone-dark', P, 'dark'), ('narrow-light', {'width': 320, 'height': 700}, 'light')):
            ctx, pg, errs = newpage(b, vp, Fake(), dict(APP, theme='auto' if scheme == 'dark' else 'light', saved={'school-001': True}), scheme=scheme)
            pg.screenshot(path=f'{SP}/shots/home-{label}.png', full_page=True)
            check(f'H6 {label}: Home does not scroll sideways', pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), pg.evaluate("[document.documentElement.scrollWidth,innerWidth]"))
            bad = pg.evaluate("[...document.querySelectorAll('#main *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+1||r.left<-1)}).map(e=>e.className||e.tagName).slice(0,5)")
            check(f'H6 {label}: nothing on Home sticks out past the edge of the screen', bad == [], bad)
            ctx.close()
    section(h6_logo)


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
