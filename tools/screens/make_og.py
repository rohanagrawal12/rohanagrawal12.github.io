"""
Makes the share picture (assets/og-image.png, 1200 x 630).

This is the picture that shows up when someone shares the Bulletin link in a text, a chat app or a social post.
The page points to it from the og:image and twitter:image tags near the top of index.html.

It draws one card in the brand colours (Paper background, Ink text, one red accent): the logo, the headline
"Find your thing." with its red full stop, one plain sentence, the web address, and two real pictures of the app
(assets/screen-home.webp and assets/screen-school.webp, made by make_screens.py). Run make_screens.py first if the
app's look has changed, then run this:

    python3 tools/screens/make_og.py

Needs Playwright with Chromium, the Inter font installed and Pillow (all there in the workspace).
"""
import os, sys, tempfile
from playwright.sync_api import sync_playwright
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(REPO, 'assets')
OUT = os.environ.get('OG_OUT', os.path.join(ASSETS, 'og-image.png'))

# the address shown on the card (the real address of the site)
ADDRESS = 'yourbulletin.tech'
# the one sentence under the headline
LINE = 'Clubs, volunteering and programs, ranked by how well they fit you.'

# the card itself: 1200 x 630 pixels, plain colours, no gradients, corners only slightly rounded
HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1200px;height:630px;overflow:hidden}
body{background:#F3F3F4;font-family:Inter,sans-serif;color:#111113;position:relative}
.logo{position:absolute;left:72px;top:60px;height:50px;display:block}
h1{position:absolute;left:72px;top:172px;font-size:100px;line-height:1.02;font-weight:800;letter-spacing:-.035em}
h1 i{font-style:normal;color:#D6452F}
.sub{position:absolute;left:72px;top:404px;width:500px;font-size:29px;line-height:1.38;color:#4F4F56}
.url{position:absolute;left:72px;bottom:54px;font-size:28px;font-weight:700;letter-spacing:-.01em}
.ph{position:absolute;width:250px;background:#fff;border:2px solid #C4C4CA;border-radius:10px;overflow:hidden}
.ph img{display:block;width:100%;height:auto}
</style></head><body>
<img class="logo" src="file://__ASSETS__/bulletin-logo.svg" alt="">
<h1>Find your<br>thing<i>.</i></h1>
<p class="sub">__LINE__</p>
<div class="url">__ADDRESS__</div>
<div class="ph" style="left:624px;top:118px"><img src="file://__ASSETS__/screen-home.webp" alt=""></div>
<div class="ph" style="left:898px;top:188px"><img src="file://__ASSETS__/screen-school.webp" alt=""></div>
</body></html>
"""
# fill in the three placeholders (plain text swaps, because the style rules above contain percent signs)
HTML = HTML.replace('__ASSETS__', ASSETS).replace('__LINE__', LINE).replace('__ADDRESS__', ADDRESS)

tmp = tempfile.mkdtemp()
page_file = os.path.join(tmp, 'og.html')
with open(page_file, 'w', encoding='utf-8') as f:
    f.write(HTML)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 1200, 'height': 630}, device_scale_factor=1)
    pg.goto('file://' + page_file)
    # wait until the font and the pictures are really loaded before taking the picture
    pg.evaluate('document.fonts.ready')
    pg.wait_for_function('Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)')
    pg.screenshot(path=OUT, clip={'x': 0, 'y': 0, 'width': 1200, 'height': 630})
    b.close()

# shrink the file a little without changing a single pixel, then check the size
im = Image.open(OUT)
assert im.size == (1200, 630), im.size
im.save(OUT, optimize=True)
print('saved', OUT, im.size, os.path.getsize(OUT), 'bytes')
sys.exit(0)
