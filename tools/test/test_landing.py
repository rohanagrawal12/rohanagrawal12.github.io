import json, os, subprocess, time, re
from playwright.sync_api import sync_playwright
REPO=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); PORT=8776
URL=f'http://127.0.0.1:{PORT}/index.html'
srv=subprocess.Popen(['python3','-I','-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=REPO,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
results=[]
# the mission statement as written in docs/brand.md (the page adds a red full stop after it)
MISSION='Helping students find clubs, volunteering and programs that fit them, so nobody misses out on something they would love just because they never heard about it'
def check(name,ok,detail=''):
    results.append(bool(ok)); print(('PASS ' if ok else 'FAIL ')+name+((' | '+str(detail)) if (detail!='' and not ok) else ''),flush=True)
view=lambda pg:pg.evaluate("({stage:S.stage,slide:S.slide,step:S.step,tab:S.tab})")
txt=lambda pg:pg.evaluate("document.body.innerText")
w=lambda pg,ms=250:pg.wait_for_timeout(ms)
def seed(state,session=True):
    js="try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    if state is not None: js+="localStorage.setItem('bl.state',%s);"%json.dumps(json.dumps(state))
    if session: js+="sessionStorage.setItem('bl.visit','1');"
    return js+"}}catch(e){}"
APP={'stage':'app','tab':'School','seen':True,'done':True,'theme':'light','ans':{'grade':'10th grade','school':'The Village School','learn':'biology and chemistry','want':['Join a club'],'why':['Trying new things'],'time':'3-5 hours'}}
def new(b,vp,scheme='light',state=None,session=False):
    mob=vp['width']<500
    ctx=b.new_context(viewport=vp,device_scale_factor=1,is_mobile=mob,has_touch=mob,color_scheme=scheme)
    ctx.route(re.compile(r'https://share\.synthesia\.io/.*'),lambda r:r.fulfill(status=200,content_type='text/html',body='<html><body>player stub</body></html>'))
    if state is not None or session: ctx.add_init_script(seed(state,session))
    pg=ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.on('console',lambda m:errs.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text and 'ERR_' not in m.text else None)
    pg.goto(URL); w(pg,500)
    return ctx,pg,errs
try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    for label,vp in [('phone',{'width':390,'height':844}),('desktop',{'width':1440,'height':900})]:
      for scheme in ['light','dark']:
        L=f'{label}-{scheme}'
        ctx,pg,errs=new(b,vp,scheme)
        # ---- screen 1: Home
        t=txt(pg)
        check(f'{L} 1 logo is shown in the header',pg.locator('.sl2 .top .wm2 svg, .sl2 .top .wm2 img').count()>=1)
        check(f'{L} 1 caption WELCOME 01 / 03','WELCOME 01 / 03' in t)
        check(f'{L} 1 headline is the tagline',pg.locator('h1').inner_text().strip().lower().startswith('find your thing'),pg.locator('h1').inner_text())
        check(f'{L} 1 red dot after the tagline',pg.locator('h1 .rd').count()==1)
        check(f'{L} 1 promo message (first paragraph) says what it does','two-minute quiz' in t and 'ranks every club' in t)
        check(f'{L} 1 video box shows Play the video',pg.locator('.vid.play').count()==1 and 'Play the video' in t)
        check(f'{L} 1 Take the quiz button (call to action)',pg.locator('.cta2 [data-act="start"]').count()==1 and pg.locator('.cta2 [data-act="start"]').inner_text().strip()=='Take the quiz',pg.locator('.cta2').inner_text())
        check(f'{L} 1 no way into the app without the quiz: no Open the app or skip anywhere','Open the app' not in t and 'skip' not in t.lower(),t[:300])
        check(f'{L} 1 three points line','One place for everything' in t and 'Matched to you' in t and 'Free for students' in t)
        check(f'{L} 1 next button says About us',pg.locator('[data-act="snext"]').inner_text().strip().startswith('About us'),pg.locator('[data-act="snext"]').inner_text())
        check(f'{L} 1 no Back button on the first screen',pg.locator('[data-act="sback"]').count()==0)
        check(f'{L} 1 Log in button for a new visitor','Log in' in pg.locator('.pill').inner_text())
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 1 no sideways scroll',ov<=0,ov)
        # play the video on screen 1
        pg.locator('.vid.play').click(); w(pg,300)
        src=pg.evaluate("(document.querySelector('.vid iframe')||{}).src||''")
        check(f'{L} 1 clicking the video starts the Synthesia player in place','share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f' in src and 'autoplay=1' in src,src)
        # ---- screen 2: About us
        pg.click('[data-act="snext"]'); w(pg); t=txt(pg); v=view(pg)
        check(f'{L} 2 on slide index 1 with the dark colour',v['slide']==1 and pg.locator('.sl2.k').count()==1,v)
        check(f'{L} 2 caption ABOUT US 02 / 03','ABOUT US 02 / 03' in t)
        check(f'{L} 2 headline Built by a student, for students.','Built by a student, for students.' in pg.locator('h1').inner_text())
        check(f'{L} 2 startup story mentions the school and the Google Form start','The Village School in Houston' in t and 'Google Form' in t and 'grew into a website' in t)
        check(f'{L} 2 mission and who it is for','OUR MISSION' in t and 'WHO IT IS FOR' in t and 'nobody misses out' in t)
        # the mission statement is the owner's sentence from docs/brand.md, in large bold type, with a red full stop
        m=pg.evaluate("(()=>{const p=document.querySelector('.mis p'),b=document.querySelector('.blk div:not(.cap)');if(!p||!b)return null;const c=getComputedStyle(p),r=p.getBoundingClientRect(),q=b.parentElement.getBoundingClientRect(),z=document.querySelector('.mis').getBoundingClientRect();return {text:p.textContent,red:p.querySelectorAll('.rd').length,size:parseFloat(c.fontSize),weight:parseInt(c.fontWeight),other:parseFloat(getComputedStyle(b).fontSize),left:Math.abs(z.left-q.left),right:r.right,vw:innerWidth}})()")
        check(f'{L} 2 the mission is the full sentence from the brand sheet, ending in one red full stop',m and m['text']==MISSION+'.' and m['red']==1,m)
        check(f'{L} 2 the mission is in large bold type, bigger than the text under Who it is for',m and m['size']>=22 and m['weight']>=700 and m['size']>m['other'],m)
        check(f'{L} 2 the mission lines up with the Who it is for block and stays on screen',m and m['left']<=1 and m['right']<=m['vw'],m)
        check(f'{L} 2 no leftover art or empty small text',pg.locator('.mid .art').count()==0 and pg.locator('.mid small').count()==0)
        check(f'{L} 2 buttons Back and Get started',pg.locator('[data-act="sback"]').count()==1 and 'Get started' in pg.locator('[data-act="snext"]').inner_text())
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 2 no sideways scroll',ov<=0,ov)
        # ---- screen 3: Get started
        pg.click('[data-act="snext"]'); w(pg); t=txt(pg); v=view(pg)
        check(f'{L} 3 on slide index 2 with the charcoal colour',v['slide']==2 and pg.locator('.sl2.r').count()==1,v)
        check(f'{L} 3 caption GET STARTED 03 / 03','GET STARTED 03 / 03' in t)
        check(f'{L} 3 headline Free for students. Always.','Free for students. Always.' in pg.locator('h1').inner_text())
        n=pg.evaluate("[DATA.school.length,DATA.community.length,DATA.explore.length]")
        check(f'{L} 3 numbers on the page match the data (98/31/28)',n==[98,31,28] and f'{n[0]} school clubs and teams, {n[1]} Houston opportunities and {n[2]} online programs' in t,(n,t[:300]))
        check(f'{L} 3 three steps',pg.locator('.steps li').count()==3)
        check(f'{L} 3 plan card: Students FREE, Schools COMING SOON',pg.locator('.plan').inner_text().count('FREE')==1 and 'COMING SOON' in pg.locator('.plan').inner_text() and 'Students' in t and 'Schools and organizations' in t)
        bb=pg.locator('.bb [data-act="start"]')
        check(f'{L} 3 the Take the quiz button is the big button at the bottom',bb.count()==1 and bb.inner_text().strip().startswith('Take the quiz') and pg.locator('.cta2').count()==0,pg.locator('.bb').inner_text())
        r=pg.evaluate("(()=>{const r=document.querySelector('.bb .wbtn').getBoundingClientRect();return [r.top,r.bottom,innerHeight]})()")
        check(f'{L} 3 the button is on the first screen without scrolling',r[0]>=0 and r[1]<=r[2]+1,r)
        check(f'{L} 3 no skip note, no Open the app, and nothing is "matched to you" before the quiz','skip' not in t.lower() and 'Open the app' not in t and 'matched to you' not in t,t[-400:])
        check(f'{L} 3 says it takes about 2 minutes and ranks them after the quiz','Takes about 2 minutes.' in t and 'Take the quiz and Bulletin ranks them for you.' in t,t[-500:])
        check(f'{L} 3 first step is making a free account','Make a free account.' in pg.locator('.steps').inner_text(),pg.locator('.steps').inner_text())
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 3 no sideways scroll',ov<=0,ov)
        # Take the quiz from screen 3
        pg.click('.bb [data-act="start"]'); w(pg); v=view(pg)
        check(f'{L} 3 Take the quiz starts with the account step for a new visitor',v['stage']=='auth',v)
        pg.go_back(); w(pg); v=view(pg)
        check(f'{L} 3 browser Back from the account step returns to screen 3',v['stage']=='intro' and v['slide']==2,v)
        # Back chain: 3 -> 2 -> 1 and the video box is the thumbnail again
        pg.click('[data-act="sback"]'); w(pg); check(f'{L} back to screen 2',view(pg)['slide']==1)
        pg.click('[data-act="sback"]'); w(pg)
        check(f'{L} back to screen 1 shows the thumbnail again (not the old player)',view(pg)['slide']==0 and pg.locator('.vid.play').count()==1 and pg.locator('.vid iframe').count()==0)
        check(f'{L} no page errors',not errs,errs)
        ctx.close()
    # returning visitor who finished the quiz: screen 3 button says Go to my Home and goes there
    ctx,pg,errs=new(b,{'width':390,'height':844},'light',APP,False)
    check('returning: top button says Go to my Home, not Log in','Go to my Home' in pg.locator('.pill').inner_text() and 'Log in' not in pg.locator('.pill').inner_text(),pg.locator('.pill').inner_text())
    check('returning: first screen button says Go to my Home',pg.locator('.cta2 [data-act="home"]').count()==1 and 'Go to my Home' in pg.locator('.cta2').inner_text(),pg.locator('.cta2').inner_text())
    pg.click('[data-act="snext"]'); w(pg); pg.click('[data-act="snext"]'); w(pg)
    check('returning: screen 3 button says Go to my Home',pg.locator('.bb [data-act="home"]').inner_text().strip().startswith('Go to my Home'),pg.locator('.bb').inner_text())
    pg.click('.bb [data-act="home"]'); w(pg); v=view(pg)
    check('returning: Go to my Home opens the Home page',v['stage']=='app' and v['tab']=='Home',v)
    check('returning: no page errors',not errs,errs); ctx.close()
    # returning visitor who never finished the quiz: no way in, the quiz is the only way forward
    ctx,pg,errs=new(b,{'width':390,'height':844},'light',dict(APP,done=False,ans={}),False)
    check('returning without quiz: top button is Log in','Log in' in pg.locator('.pill').inner_text(),pg.locator('.pill').inner_text())
    pg.click('[data-act="snext"]'); w(pg); pg.click('[data-act="snext"]'); w(pg)
    check('returning without quiz: screen 3 button is Take the quiz',pg.locator('.bb [data-act="start"]').count()==1 and pg.locator('.bb [data-act="home"]').count()==0,pg.locator('.bb').inner_text())
    check('returning without quiz: no page errors',not errs,errs); ctx.close()
    # Settings > Welcome screens replays the new screens
    ctx,pg,errs=new(b,{'width':1440,'height':900},'light',APP,True)
    pg.evaluate("act('welcome')") if pg.evaluate("typeof act==='function'") else None
    w(pg)
    ctx.close()
    b.close()
finally:
    srv.terminate()
print(f"\n==== {len(results)} checks, {results.count(False)} failed")
