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
# waits until every picture on the page has loaded (the welcome pages show real screenshots of the app)
def pics_ready(pg):
    pg.wait_for_function("[...document.images].every(i=>i.complete)",timeout=8000)
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
# where the bar with the dots and the Back and next buttons is, and how tall the page is
BAR="(()=>{const b=document.querySelector('.w-bar').getBoundingClientRect(),n=document.querySelector('.bb .wbtn').getBoundingClientRect();return {bottom:b.bottom,top:b.top,ih:innerHeight,btnTop:n.top,btnBottom:n.bottom,h:document.documentElement.scrollHeight}})()"
# every element on the welcome page that sticks out past the sides of the screen
OUT="(()=>{const iw=document.documentElement.clientWidth,o=[];document.querySelectorAll('.sl2 *').forEach(e=>{const r=e.getBoundingClientRect();if(r.width>0&&(r.right>iw+0.5||r.left<-0.5))o.push((e.className||e.tagName)+':'+Math.round(r.left)+'-'+Math.round(r.right))});return o.slice(0,6)})()"
try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    for label,vp in [('phone',{'width':390,'height':844}),('desktop',{'width':1440,'height':900})]:
      for scheme in ['light','dark']:
        L=f'{label}-{scheme}'
        ctx,pg,errs=new(b,vp,scheme)
        pics_ready(pg)
        # ---- screen 1: Home
        t=txt(pg)
        check(f'{L} 1 logo is shown in the header',pg.locator('.sl2 .top .wm2 svg, .sl2 .top .wm2 img').count()>=1)
        check(f'{L} 1 no numbered "01 / 03" captions any more (these are full pages, not cards)','/ 03' not in t and 'WELCOME' not in t,t[:200])
        check(f'{L} 1 a small label above the headline says where it starts','STARTING AT THE VILLAGE SCHOOL' in t)
        check(f'{L} 1 exactly one h1, and it is the tagline',pg.locator('h1').count()==1 and pg.locator('h1').inner_text().strip().lower().startswith('find your thing'),pg.locator('h1').all_inner_texts())
        check(f'{L} 1 red dot after the tagline',pg.locator('h1 .rd').count()==1)
        check(f'{L} 1 promo message (first paragraph) says what it does','two-minute quiz' in t and 'ranks every club' in t)
        # real pictures of the app, not drawings
        pics=pg.evaluate("[...document.querySelectorAll('.w-pair img')].map(i=>({ok:i.complete&&i.naturalWidth>=700,alt:i.alt.length>20,src:i.getAttribute('src')}))")
        check(f'{L} 1 two real pictures of the app (Home and School) are shown and loaded',len(pics)==2 and all(x['ok'] and x['alt'] for x in pics) and pics[0]['src']=='assets/screen-home.webp' and pics[1]['src']=='assets/screen-school.webp',pics)
        # on a computer the pictures sit beside the words, on a phone under them
        g=pg.evaluate("(()=>{const a=document.querySelector('.w-hero > div').getBoundingClientRect(),c=document.querySelector('.w-pair').getBoundingClientRect();return {textRight:a.right,textBottom:a.bottom,picLeft:c.left,picTop:c.top}})()")
        check(f'{L} 1 the pictures are {"beside" if label=="desktop" else "under"} the words',(g['picLeft']>=g['textRight']-1) if label=='desktop' else (g['picTop']>=g['textBottom']-1),g)
        check(f'{L} 1 three reasons in cards (one place, matched, free)',pg.locator('.w-white .w-card').count()==3)
        check(f'{L} 1 the video sits in its own black band',pg.locator('.w-ink .vid.play').count()==1)
        check(f'{L} 1 footer with the logo and where it was made',pg.locator('.w-foot .wm2 svg').count()==1 and 'Made by a student in Houston' in pg.locator('.w-foot').inner_text())
        check(f'{L} 1 video box shows Play the video',pg.locator('.vid.play').count()==1 and 'Play the video' in t)
        check(f'{L} 1 Take the quiz button (call to action)',pg.locator('.cta2 [data-act="start"]').count()==1 and pg.locator('.cta2 [data-act="start"]').inner_text().strip()=='Take the quiz',pg.locator('.cta2').inner_text())
        cb=pg.evaluate("(()=>{const r=document.querySelector('.cta2 .wbtn').getBoundingClientRect();return {top:r.top,bottom:r.bottom,bar:document.querySelector('.w-bar').getBoundingClientRect().top}})()")
        check(f'{L} 1 the Take the quiz button is on the first screen, above the bar',cb['top']>=0 and cb['bottom']<=cb['bar'],cb)
        check(f'{L} 1 no way into the app without the quiz: no Open the app or skip anywhere','Open the app' not in t and 'skip' not in t.lower(),t[:300])
        check(f'{L} 1 three points: one place, matched to you, free for students','One place for everything' in t and 'Matched to you' in t and 'Free for students' in t)
        check(f'{L} 1 next button says About us',pg.locator('[data-act="snext"]').inner_text().strip().startswith('About us'),pg.locator('[data-act="snext"]').inner_text())
        check(f'{L} 1 no Back button on the first screen',pg.locator('[data-act="sback"]').count()==0)
        check(f'{L} 1 Log in button for a new visitor','Log in' in pg.locator('.pill').inner_text())
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 1 no sideways scroll',ov<=0,ov)
        # the bar with the dots and the next button stays on screen while the page scrolls
        r=pg.evaluate(BAR)
        check(f'{L} 1 the bar with the next button is stuck to the bottom of the screen',abs(r['bottom']-r['ih'])<=1 and r['btnTop']>=0 and r['btnBottom']<=r['ih'],r)
        check(f'{L} 1 the page is taller than the screen (it scrolls)',r['h']>r['ih']+300,r)
        pg.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)"); w(pg,200)
        r=pg.evaluate(BAR); check(f'{L} 1 and it is still at the bottom of the screen after scrolling all the way down',abs(r['bottom']-r['ih'])<=1 and r['btnBottom']<=r['ih'],r)
        pg.evaluate("window.scrollTo(0,0)"); w(pg,100)
        # play the video on screen 1
        pg.locator('.vid.play').click(); w(pg,300)
        src=pg.evaluate("(document.querySelector('.vid iframe')||{}).src||''")
        check(f'{L} 1 clicking the video starts the Synthesia player in place','share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f' in src and 'autoplay=1' in src,src)
        # ---- screen 2: About us
        pg.click('[data-act="snext"]'); w(pg); pics_ready(pg); t=txt(pg); v=view(pg)
        check(f'{L} 2 on slide index 1 with the dark colour',v['slide']==1 and pg.locator('.sl2.k').count()==1,v)
        check(f'{L} 2 the page starts at the top after Next',pg.evaluate("scrollY")==0)
        check(f'{L} 2 label ABOUT US, no numbered caption','ABOUT US' in t and '/ 03' not in t)
        check(f'{L} 2 exactly one h1: Built by a student, for students.',pg.locator('h1').count()==1 and 'Built by a student, for students.' in pg.locator('h1').inner_text())
        check(f'{L} 2 startup story mentions the school and the Google Form start','The Village School in Houston' in t and 'Google Form' in t and 'grew into a website' in t)
        check(f'{L} 2 mission and who it is for','OUR MISSION' in t and 'WHO IT IS FOR' in t and 'nobody misses out' in t)
        # the mission statement is the owner's sentence from docs/brand.md, in very large bold type on a white band, with a red full stop
        m=pg.evaluate("(()=>{const p=document.querySelector('.mis p'),b=document.querySelector('.blk .w-lead');if(!p||!b)return null;const c=getComputedStyle(p),r=p.getBoundingClientRect(),q=b.parentElement.getBoundingClientRect(),z=document.querySelector('.mis').getBoundingClientRect();return {text:p.textContent,red:p.querySelectorAll('.rd').length,size:parseFloat(c.fontSize),weight:parseInt(c.fontWeight),other:parseFloat(getComputedStyle(b).fontSize),left:Math.abs(z.left-q.left),right:r.right,vw:innerWidth,white:!!document.querySelector('.w-white .mis')}})()")
        check(f'{L} 2 the mission is the full sentence from the brand sheet, ending in one red full stop',m and m['text']==MISSION+'.' and m['red']==1,m)
        check(f'{L} 2 the mission is in very large bold type, bigger than the text under Who it is for',m and m['size']>=26 and m['weight']>=700 and m['size']>m['other'],m)
        check(f'{L} 2 the mission is on a white band, lines up with the Who it is for block and stays on screen',m and m['white'] and m['left']<=1 and m['right']<=m['vw'],m)
        tot=pg.evaluate("DATA.school.length+DATA.community.length+DATA.explore.length")
        check(f'{L} 2 how it got built: four steps with the real details',pg.locator('.w-time li').count()==4 and 'A Google Form quiz' in t and 'Feedback from 8 classmates' in t and 'A redesign' in t and f'It ranks {tot} opportunities' in t,(tot,pg.locator('.w-time').inner_text()))
        check(f'{L} 2 three problems and what changed (quiz too long, first name taken, design too busy)',pg.locator('.w-fix > div').count()==3 and 'The quiz was too long.' in t and 'It became Bulletin.' in t and 'The first design felt too busy.' in t)
        check(f'{L} 2 who it is for: four kinds of people, and organizations say coming soon (they cannot post yet)',pg.locator('.w-who > div').count()==4 and 'Coming soon' in pg.locator('.w-who').inner_text() and 'Parents and guardians' in t and 'Teachers and counselors' in t)
        mk=pg.evaluate("getComputedStyle(document.querySelector('.w-mark')).display")
        check(f'{L} 2 the big logo mark is shown on a computer and hidden on a phone',mk==('block' if label=='desktop' else 'none'),mk)
        check(f'{L} 2 no old art or caption left over',pg.locator('.mid').count()==0 and pg.locator('.mid .art').count()==0)
        check(f'{L} 2 buttons Back and Get started',pg.locator('[data-act="sback"]').count()==1 and 'Get started' in pg.locator('[data-act="snext"]').inner_text())
        r=pg.evaluate(BAR); check(f'{L} 2 the bar is stuck to the bottom of the screen',abs(r['bottom']-r['ih'])<=1 and r['h']>r['ih']+300,r)
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 2 no sideways scroll',ov<=0,ov)
        # ---- screen 3: Get started
        pg.click('[data-act="snext"]'); w(pg); pics_ready(pg); t=txt(pg); v=view(pg)
        check(f'{L} 3 on slide index 2 with the charcoal colour',v['slide']==2 and pg.locator('.sl2.r').count()==1,v)
        check(f'{L} 3 label GET STARTED, no numbered caption','GET STARTED' in t and '/ 03' not in t)
        check(f'{L} 3 exactly one h1: Free for students. Always.',pg.locator('h1').count()==1 and 'Free for students. Always.' in pg.locator('h1').inner_text())
        n=pg.evaluate("[DATA.school.length,DATA.community.length,DATA.explore.length]")
        tiles=pg.evaluate("[...document.querySelectorAll('.w-nums > div')].map(d=>[d.querySelector('b').textContent,d.querySelector('span').textContent])")
        check(f'{L} 3 the three big numbers match the data (98/31/28)',n==[98,31,28] and tiles==[['98','school clubs and teams'],['31','Houston opportunities'],['28','online programs']],(n,tiles))
        check(f'{L} 3 three steps',pg.locator('.steps li').count()==3)
        sp=pg.evaluate("[...document.querySelectorAll('.steps .w-shot img')].map(i=>({ok:i.complete&&i.naturalWidth>=700,alt:i.alt.length>20,src:i.getAttribute('src')}))")
        check(f'{L} 3 each step has a real picture of the app (account form, quiz, School list)',len(sp)==3 and all(x['ok'] and x['alt'] for x in sp) and [x['src'] for x in sp]==['assets/screen-signup.webp','assets/screen-quiz.webp','assets/screen-school.webp'],sp)
        check(f'{L} 3 plan card: Students FREE, Schools COMING SOON',pg.locator('.plan').inner_text().count('FREE')==1 and 'COMING SOON' in pg.locator('.plan').inner_text() and 'Students' in t and 'Schools and organizations' in t)
        check(f'{L} 3 students never pay is said above the plan card','Students never pay.' in t)
        bb=pg.locator('.bb [data-act="start"]')
        check(f'{L} 3 the Take the quiz button is the big button at the bottom',bb.count()==1 and bb.inner_text().strip().startswith('Take the quiz') and pg.locator('.cta2').count()==0,pg.locator('.bb').inner_text())
        r=pg.evaluate("(()=>{const r=document.querySelector('.bb .wbtn').getBoundingClientRect();return [r.top,r.bottom,innerHeight]})()")
        check(f'{L} 3 the button is on the first screen without scrolling',r[0]>=0 and r[1]<=r[2]+1,r)
        check(f'{L} 3 no skip note, no Open the app, and nothing is "matched to you" before the quiz','skip' not in t.lower() and 'Open the app' not in t and 'matched to you' not in t,t[-400:])
        check(f'{L} 3 says it takes about 2 minutes and ranks them after the quiz','Takes about 2 minutes.' in t and 'Take the quiz and Bulletin ranks them for you.' in t,t[-500:])
        check(f'{L} 3 first step is making a free account','Make a free account.' in pg.locator('.steps').inner_text(),pg.locator('.steps').inner_text())
        # the red sign-up block at the end (what a new visitor sees)
        rb=pg.evaluate("(()=>{const e=document.querySelector('.w-red');if(!e)return null;const h=e.querySelector('h2'),s=e.querySelector('[data-act=signup]'),l=e.querySelector('[data-act=login]'),c=getComputedStyle(e),hc=getComputedStyle(h);return {bg:c.backgroundColor,fg:hc.color,size:parseFloat(hc.fontSize),h:h.textContent,s:s&&s.textContent,l:l&&l.textContent,w:e.getBoundingClientRect().width,iw:document.documentElement.clientWidth}})()")
        check(f'{L} 3 the red sign-up block: brand red, white big headline, Create a free account and a log in link',rb and rb['bg']=='rgb(214, 69, 47)' and rb['fg']=='rgb(255, 255, 255)' and rb['size']>=32 and rb['h']=='Ready to find your thing?' and rb['s']=='Create a free account' and rb['l']=='I already have an account' and abs(rb['w']-rb['iw'])<=1,rb)
        check(f'{L} 3 the page also ends with the footer',pg.locator('.w-foot').count()==1)
        ov=pg.evaluate("document.documentElement.scrollWidth-innerWidth"); check(f'{L} 3 no sideways scroll',ov<=0,ov)
        check(f'{L} 3 nothing sticks out past the sides of the screen',pg.evaluate(OUT)==[],pg.evaluate(OUT))
        # the red block's buttons: Create a free account opens the form, and Back comes back to this page
        pg.locator('.w-red [data-act="signup"]').click(); w(pg); v=view(pg)
        check(f'{L} 3 Create a free account opens the sign-up form',v['stage']=='signup',v)
        pg.go_back(); w(pg); v=view(pg)
        check(f'{L} 3 browser Back from the form returns to screen 3',v['stage']=='intro' and v['slide']==2,v)
        pg.locator('.w-red [data-act="login"]').click(); w(pg); v=view(pg)
        check(f'{L} 3 I already have an account opens the log in form',v['stage']=='login',v)
        pg.go_back(); w(pg); v=view(pg)
        check(f'{L} 3 browser Back from log in returns to screen 3',v['stage']=='intro' and v['slide']==2,v)
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
    # small phones, a tablet: nothing sticks out sideways, the logo and the top button do not overlap, and the first screen has the headline and the main button
    for sw,sh in [(320,640),(375,667),(768,1024)]:
        ctx,pg,errs=new(b,{'width':sw,'height':sh},'light')
        for k in range(3):
            pics_ready(pg); w(pg,150)
            S=f'{sw}px slide {k+1}'
            check(f'{S}: no sideways scroll and nothing sticks out',pg.evaluate("document.documentElement.scrollWidth-innerWidth")<=0 and pg.evaluate(OUT)==[],(pg.evaluate("document.documentElement.scrollWidth-innerWidth"),pg.evaluate(OUT)))
            tp=pg.evaluate("(()=>{const l=document.querySelector('.top .wm2').getBoundingClientRect(),p=document.querySelector('.top .pill').getBoundingClientRect();return {logoRight:l.right,pillLeft:p.left,pillRight:p.right,iw:innerWidth,txt:document.querySelector('.top .pill').innerText}})()")
            check(f'{S}: the logo and the Log in button sit side by side inside the screen',tp['logoRight']<=tp['pillLeft']-4 and tp['pillRight']<=tp['iw'],tp)
            r=pg.evaluate(BAR); check(f'{S}: the bar with Back and next is on screen and its buttons are fully visible',abs(r['bottom']-r['ih'])<=1 and r['btnTop']>=0,r)
            if k==0:
                cb=pg.evaluate("(()=>{const r=document.querySelector('.cta2 .wbtn').getBoundingClientRect();return {bottom:r.bottom,bar:document.querySelector('.w-bar').getBoundingClientRect().top,h1:document.querySelector('h1').getBoundingClientRect().top}})()")
                check(f'{S}: the headline and the Take the quiz button are on the first screen above the bar',cb['h1']>=0 and cb['bottom']<=cb['bar'],cb)
            if k==2:
                nm=pg.evaluate("[...document.querySelectorAll('.w-nums > div')].map(d=>{const r=d.getBoundingClientRect();return [Math.round(r.left),Math.round(r.right)]})")
                check(f'{S}: the three big numbers sit in a row inside the screen',len(nm)==3 and nm[0][1]<=nm[1][0] and nm[1][1]<=nm[2][0] and nm[2][1]<=sw,nm)
            if k<2: pg.click('[data-act="snext"]'); w(pg,250)
        check(f'{sw}px no page errors',not errs,errs)
        ctx.close()
    # returning visitor who finished the quiz: screen 3 button says Go to my Home and goes there
    ctx,pg,errs=new(b,{'width':390,'height':844},'light',APP,False)
    check('returning: top button says Go to my Home, not Log in','Go to my Home' in pg.locator('.pill').inner_text() and 'Log in' not in pg.locator('.pill').inner_text(),pg.locator('.pill').inner_text())
    check('returning: first screen button says Go to my Home',pg.locator('.cta2 [data-act="home"]').count()==1 and 'Go to my Home' in pg.locator('.cta2').inner_text(),pg.locator('.cta2').inner_text())
    pg.click('[data-act="snext"]'); w(pg); pg.click('[data-act="snext"]'); w(pg)
    check('returning: screen 3 button says Go to my Home',pg.locator('.bb [data-act="home"]').inner_text().strip().startswith('Go to my Home'),pg.locator('.bb').inner_text())
    check('returning: the red block at the end says Welcome back and offers Go to my Home (no account form)',pg.locator('.w-red h2').inner_text()=='Welcome back.' and pg.locator('.w-red [data-act="home"]').count()==1 and pg.locator('.w-red [data-act="signup"]').count()==0 and pg.locator('.w-red [data-act="login"]').count()==0,pg.locator('.w-red').inner_text())
    pg.locator('.w-red [data-act="home"]').click(); w(pg); v=view(pg)
    check('returning: the red block button opens the Home page',v['stage']=='app' and v['tab']=='Home',v)
    check('returning: no page errors',not errs,errs); ctx.close()
    # returning visitor who never finished the quiz: no way in, the quiz is the only way forward
    ctx,pg,errs=new(b,{'width':390,'height':844},'light',dict(APP,done=False,ans={}),False)
    check('returning without quiz: top button is Log in','Log in' in pg.locator('.pill').inner_text(),pg.locator('.pill').inner_text())
    pg.click('[data-act="snext"]'); w(pg); pg.click('[data-act="snext"]'); w(pg)
    check('returning without quiz: screen 3 button is Take the quiz',pg.locator('.bb [data-act="start"]').count()==1 and pg.locator('.bb [data-act="home"]').count()==0,pg.locator('.bb').inner_text())
    check('returning without quiz: the red block at the end offers an account, not a way into the app',pg.locator('.w-red [data-act="signup"]').count()==1 and pg.locator('.w-red [data-act="home"]').count()==0,pg.locator('.w-red').inner_text())
    check('returning without quiz: no page errors',not errs,errs); ctx.close()
    # the three versions of the red block: a new visitor, someone logged in who still owes the quiz, someone who can get in
    ctx,pg,errs=new(b,{'width':390,'height':844},'light')
    j=pg.evaluate("slJoin()")
    check('red block for a new visitor: Create a free account and a log in link, nothing about Home','Ready to find your thing?' in j and 'data-act="signup"' in j and 'data-act="login"' in j and 'data-act="home"' not in j and 'data-act="start"' not in j,j)
    j=pg.evaluate("(()=>{users['t@example.com']={name:'Tess',email:'t@example.com',role:'Student'};S.me='t@example.com';S.done=false;return slJoin()})()")
    check('red block for someone logged in who still owes the quiz: One last step and Take the quiz (no account buttons)','One last step.' in j and 'data-act="start"' in j and 'data-act="signup"' not in j and 'data-act="login"' not in j,j)
    j=pg.evaluate("(()=>{S.done=true;return slJoin()})()")
    check('red block for someone who can get in: Welcome back and Go to my Home','Welcome back.' in j and 'data-act="home"' in j and 'data-act="signup"' not in j,j)
    check('red block: no page errors',not errs,errs); ctx.close()
    # Settings > Welcome screens replays the new screens
    ctx,pg,errs=new(b,{'width':1440,'height':900},'light',APP,True)
    pg.evaluate("act('welcome')") if pg.evaluate("typeof act==='function'") else None
    w(pg)
    check('Settings > Welcome screens replays the first welcome page',view(pg)['stage']=='intro' and view(pg)['slide']==0 and pg.locator('.sl2.y').count()==1,view(pg))
    check('replay: no page errors',not errs,errs)
    ctx.close()
    b.close()
finally:
    srv.terminate()
print(f"\n==== {len(results)} checks, {results.count(False)} failed")
