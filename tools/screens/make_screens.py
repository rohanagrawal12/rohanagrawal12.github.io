"""
Makes the pictures of the app that the welcome screens show (assets/screen-*.webp).

It starts the page on a small local web server, pretends to be Supabase (the same pretend one the tests use,
tools/test/fake_sb.py), logs in a made-up student called Alex with made-up quiz answers, and takes pictures at
phone size (390 x 844, twice as sharp): Home, the School list, the quiz and the Create account form.
The pictures are saved as WebP files in assets/. Run it again after any visual change to the app, so the
welcome screens never show an old look:

    python3 tools/screens/make_screens.py

Needs Playwright with Chromium, the Inter font installed and Pillow (all there in the workspace).
"""
import io, json, os, subprocess, sys, time
from subprocess import DEVNULL
from playwright.sync_api import sync_playwright
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'tools', 'test'))
from fake_sb import Fake, SBRE

PORT = 8795
URL = f'http://127.0.0.1:{PORT}/index.html'
OUT = os.environ.get('SCREENS_OUT', os.path.join(REPO, 'assets'))
PW = 'secret1'
# made-up quiz answers for the made-up student (about robots, biology and helping people)
ANS = {'grade': '10th grade', 'school': 'The Village School', 'zip': '77095',
       'learn': 'I like biology and robotics because I love figuring out how things work.',
       'learn2': 'Coding, forensics and how businesses start.',
       'free': 'Drawing, soccer and building things with my little brother.',
       'make': 'I like building things and helping people, especially when we build it together.',
       'self': 'I am curious, I like working on a team and I want to try something new this year.',
       'want': ['Join a club', 'Volunteer'], 'why': ['Trying new things', 'Meeting people'], 'time': '3-5 hours'}
# a few items already saved or being done, so Home shows some numbers (ids come from the data in index.html)
SAVED = {'school-001': True, 'school-002': True, 'community-001': True}
DOING = {'explore-001': True}

srv = subprocess.Popen(['python3', '-I', '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=REPO, stdout=DEVNULL, stderr=DEVNULL)
time.sleep(1.0)


def seeded_context(b, state, sb=None, users=None, fake=None):
    """A phone-size browser with the saved page state put in place before the page starts."""
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='light')
    js = "try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    js += "localStorage.setItem('bl.state',%s);" % json.dumps(json.dumps(state))
    if sb is not None: js += "localStorage.setItem('bl.sb',%s);" % json.dumps(json.dumps(sb))
    if users is not None: js += "localStorage.setItem('bl.users',%s);" % json.dumps(json.dumps(users))
    js += "sessionStorage.setItem('bl.visit','1');}}catch(e){}"
    ctx.add_init_script(js)
    # the fonts come from this computer (Inter is installed); never wait for Google Fonts
    ctx.route('**/fonts.googleapis.com/**', lambda r: r.fulfill(status=200, content_type='text/css', body=''))
    if fake is not None: ctx.route(SBRE, fake.handler)
    return ctx


def save(png_bytes, name):
    """Turns the PNG picture into a WebP file in assets/ and says how big it is."""
    img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    path = os.path.join(OUT, name)
    img.save(path, 'WEBP', quality=90, method=6)
    print(f'{name}: {img.size[0]}x{img.size[1]}, {os.path.getsize(path) // 1024} KB')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        # a made-up logged-in student for Home and the School list
        fake = Fake()
        email = 'alex@example.com'
        uid = fake.add_user(email, PW, {'name': 'Alex Rivera', 'role': 'Student', 'provider': False, 'org': ''})
        fake.profiles[uid]['quiz_answers'] = ANS
        seed = fake.sb_seed(fake.session(uid, None))
        users = {email: {'name': 'Alex Rivera', 'email': email, 'role': 'Student', 'provider': False, 'org': '', 'friends': [], 'sb': 1, 'toured': True}}
        state = {'stage': 'app', 'tab': 'Home', 'seen': True, 'done': True, 'toured': True, 'theme': 'light', 'ans': ANS, 'me': email, 'saved': SAVED, 'mine': DOING}
        for tab, name in (('Home', 'screen-home.webp'), ('School', 'screen-school.webp')):
            ctx = seeded_context(b, dict(state, tab=tab), sb=seed, users=users, fake=fake)
            pg = ctx.new_page(); pg.goto(URL); pg.wait_for_timeout(1500)
            pg.evaluate("window.scrollTo(0,0)")
            save(pg.screenshot(full_page=False), name)
            ctx.close()
        # the quiz page where students write in their own words (page 2 of 4), with two answers typed in
        ctx = seeded_context(b, {'stage': 'quiz', 'step': 1, 'seen': True, 'done': False, 'toured': True, 'theme': 'light', 'ans': {}})
        pg = ctx.new_page(); pg.goto(URL); pg.wait_for_timeout(800)
        boxes = pg.locator('#full textarea')
        boxes.nth(0).fill('I like biology and robotics because I love figuring out how things work.')
        boxes.nth(1).fill('Coding, forensics and how businesses start.')
        pg.wait_for_timeout(200)
        save(pg.screenshot(full_page=False), 'screen-quiz.webp')
        ctx.close()
        # the Create account form (nothing typed in)
        ctx = seeded_context(b, {'stage': 'signup', 'seen': True, 'done': False, 'toured': True, 'theme': 'light', 'ans': {}})
        pg = ctx.new_page(); pg.goto(URL); pg.wait_for_timeout(800)
        save(pg.screenshot(full_page=False), 'screen-signup.webp')
        ctx.close()
        b.close()
finally:
    srv.terminate()
