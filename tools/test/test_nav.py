import json, os, subprocess, time, sys
from playwright.sync_api import sync_playwright

REPO=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP=os.environ.get('BL_SHOTS','/tmp/bulletin-test-shots'); os.makedirs(SP+'/shots',exist_ok=True)
PORT=8771
URL=f'http://127.0.0.1:{PORT}/index.html'
import re
HTML_LIVE=open(REPO+'/index.html',encoding='utf-8').read()
HTML=re.sub(r'const VIDEO="[^"]*";','const VIDEO="";',HTML_LIVE,count=1)
LIVE_VIDEO=re.search(r'const VIDEO="([^"]*)";',HTML_LIVE).group(1)
print('live VIDEO =',LIVE_VIDEO)
srv=subprocess.Popen(['python3','-I','-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=REPO,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1.0)

results=[]; all_errs=[]
def check(name,ok,detail=''):
    results.append((name,bool(ok),detail)); print(('PASS ' if ok else 'FAIL ')+name+((' | '+str(detail)) if (detail!='' and not ok) else ''),flush=True)

ANS={'grade':'10th grade','school':'The Village School','learn':'biology and chemistry','want':['Join a club'],'why':['Trying new things'],'time':'3-5 hours'}
APP={'stage':'app','tab':'School','seen':True,'done':True,'theme':'light','ans':ANS}
FILL="""(()=>{for(const q of PAGES[S.step].q){if(q.opt)continue;const o=q.o||[];S.ans[q.id]=q.k==='zip'?'77095':q.k==='text'?'I like robotics, biology and helping people':(q.k==='select'||q.k==='radio')?o[0]:q.k==='skills'?(S.ans.skills||{}):[o[0]]}})()"""

def seed(state,session):
    if state is not None: state=dict(state); state.setdefault('toured',True)   # keep the first-login tour out of the way (test_tour.py covers it)
    js="try{if(!sessionStorage.getItem('__seed')){sessionStorage.setItem('__seed','1');"
    if state is not None: js+="localStorage.setItem('bl.state',%s);"%json.dumps(json.dumps(state))
    if session: js+="sessionStorage.setItem('bl.visit','1');"
    return js+"}}catch(e){}"

def newpage(b,vp,state=None,session=True,dsf=1):
    mob=vp['width']<500
    ctx=b.new_context(viewport=vp,device_scale_factor=dsf,is_mobile=mob,has_touch=mob,color_scheme='light')
    ctx.add_init_script(seed(state,session))
    pg=ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append('pageerror: '+str(e)))
    pg.on('console',lambda m:errs.append('console: '+m.text) if m.type=='error' and 'Failed to load resource' not in m.text and 'ERR_' not in m.text else None)
    all_errs.append(errs)
    pg.goto(URL); pg.wait_for_timeout(500)
    return ctx,pg,errs
w=lambda pg,ms=250:pg.wait_for_timeout(ms)
view=lambda pg:pg.evaluate("({stage:S.stage,slide:S.slide,step:S.step,tab:S.tab,q:S.q})")
cards=lambda pg:pg.locator('#main .it2').count()
def tab(pg,name):
    pg.locator(f'button[data-tab="{name}"]:visible').first.click(); w(pg)
hl=lambda pg:pg.evaluate('history.length')

try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    for label,vp in [('phone',{'width':390,'height':844}),('desktop',{'width':1440,'height':900})]:
        L=label
        # A: returning visitor opens the site in a new tab -> welcome screens first
        ctx,pg,errs=newpage(b,vp,APP,session=False)
        v=view(pg); check(f'{L} A1 returning visitor on a fresh visit sees welcome screen 1',v['stage']=='intro' and v['slide']==0,v)
        check(f'{L} A2 top button says Go to my Home (the quiz is done)','Go to my Home' in pg.locator('.pill').inner_text())
        pg.locator('.pill').click(); w(pg); v=view(pg)
        check(f'{L} A3 Go to my Home opens the Home page',v['stage']=='app' and v['tab']=='Home',v)
        tab(pg,'School')
        check(f'{L} A4 School list starts with 8 items',cards(pg)==8,cards(pg))
        pg.go_back(); w(pg); v=view(pg); check(f'{L} A4b Back from School returns to Home',v['tab']=='Home',v)
        pg.go_back(); w(pg); v=view(pg); check(f'{L} A5 Back again returns to the welcome screen',v['stage']=='intro',v)
        pg.go_back(); w(pg,400); check(f'{L} A6 Back again leaves the site (first page of the visit)',pg.url=='about:blank',pg.url)
        ctx.close()

        # B: brand new visitor, welcome screens and in-app Back button
        ctx,pg,errs=newpage(b,vp,None,session=False)
        v=view(pg); check(f'{L} B1 new visitor sees welcome 1 with Log in pill',v['stage']=='intro' and v['slide']==0 and 'Log in' in pg.locator('.pill').inner_text(),v)
        pg.click('[data-act="snext"]'); w(pg); pg.click('[data-act="snext"]'); w(pg)
        check(f'{L} B2 three colours: screen 3 is the charcoal one',pg.locator('.sl2.r').count()==1 and view(pg)['slide']==2)
        n=hl(pg); pg.go_back(); w(pg); v=view(pg)
        check(f'{L} B3 browser Back goes to screen 2 (dark)',v['slide']==1 and pg.locator('.sl2.k').count()==1,v)
        pg.go_forward(); w(pg); check(f'{L} B4 Forward goes to screen 3',view(pg)['slide']==2)
        pg.click('[data-act="sback"]'); w(pg,700); v=view(pg)
        check(f'{L} B5 in-app Back button goes to screen 2 without adding history',v['slide']==1 and hl(pg)==n,(v,hl(pg),n))
        pg.click('[data-act="snext"]'); w(pg); pg.click('.bb [data-act="start"]'); w(pg)
        check(f'{L} B6 Take the quiz on the last screen goes to the account step for a new visitor',view(pg)['stage']=='auth',view(pg))
        pg.go_back(); w(pg); check(f'{L} B7 Back from account screen returns to screen 3',view(pg)['stage']=='intro' and view(pg)['slide']==2)
        ctx.close()

        # C: tabs and Back/Forward
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        check(f'{L} C1 session flag skips the welcome screens',view(pg)['stage']=='app')
        tab(pg,'Community'); tab(pg,'Explore'); tab(pg,'My Activities')
        seq=[]
        for _ in range(3):
            pg.go_back(); w(pg); seq.append(view(pg)['tab'])
        check(f'{L} C2 Back walks Explore, Community, School',seq==['Explore','Community','School'],seq)
        pg.go_forward(); w(pg); check(f'{L} C3 Forward returns to Community',view(pg)['tab']=='Community',view(pg))
        ctx.close()

        # D: Show more adds 20 + Back restores list length and scroll
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        counts=[cards(pg)]; labels=[]
        while pg.locator('[data-act="more"]').count():
            labels.append(pg.locator('[data-act="more"]').inner_text()); pg.locator('[data-act="more"]').click(); w(pg,120); counts.append(cards(pg))
        steps=[b2-a2 for a2,b2 in zip(counts,counts[1:])]
        check(f'{L} D1 each Show more adds 20 (last adds the remainder)',all(s==20 for s in steps[:-1]) and 0<steps[-1]<=20 and counts[0]==8,(counts,labels))
        check(f'{L} D2 labels read well',labels[0].startswith('Show 20 more') and labels[-1].startswith('Show the last'),labels)
        pg.locator('[data-act="more"]').count()==0 or None
        # scroll test on a fresh load with 28 showing
        ctx2,pg2,e2=newpage(b,vp,APP,session=True)
        pg2.locator('[data-act="more"]').click(); w(pg2); pg2.evaluate('scrollTo(0,1500)'); w(pg2,150); y=pg2.evaluate('scrollY')
        tab(pg2,'Community'); pg2.go_back(); w(pg2,350)
        check(f'{L} D3 Back restores 28 items and scroll position',cards(pg2)==28 and abs(pg2.evaluate('scrollY')-y)<6,(cards(pg2),pg2.evaluate('scrollY'),y))
        ctx.close(); ctx2.close()

        # E: search then Back
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        pg.fill('#q','robot'); w(pg,400); check(f'{L} E1 typing opens Search',view(pg)['tab']=='Search',view(pg))
        pg.go_back(); w(pg,350); v=view(pg)
        check(f'{L} E2 Back leaves Search and clears the box',v['tab']=='School' and pg.input_value('#q')=='',(v,pg.input_value('#q')))
        ctx.close()

        # F: quiz, loading screen, Back
        ctx,pg,errs=newpage(b,vp,{'stage':'quiz','step':0,'seen':True,'done':False,'theme':'light','ans':{}},session=True)
        for i in range(3):
            pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg)
        check(f'{L} F1 quiz reaches page 4',view(pg)['step']==3,view(pg))
        n=hl(pg); pg.click('[data-act="back"]'); w(pg,700); v=view(pg)
        check(f'{L} F2 quiz Back button goes to page 3 without adding history',v['step']==2 and hl(pg)==n,(v,hl(pg),n))
        pg.click('[data-act="next"]'); w(pg); pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg,200)
        check(f'{L} F3 last page shows the loading screen',view(pg)['stage']=='loading',view(pg))
        pg.go_back(); w(pg,300); v=view(pg)
        check(f'{L} F4 Back during loading returns to the quiz',v['stage']=='quiz' and v['step']==2,v)
        w(pg,4500); check(f'{L} F5 loading does not pull you into the app afterwards',view(pg)['stage']=='quiz',view(pg))
        ctx.close()
        ctx,pg,errs=newpage(b,vp,{'stage':'quiz','step':0,'seen':True,'done':False,'theme':'light','ans':{}},session=True)
        for i in range(4):
            pg.evaluate(FILL); pg.click('[data-act="next"]'); w(pg,200)
        pg.wait_for_function("S.stage==='app'",timeout=15000); w(pg,300)
        check(f'{L} F6 finishing the quiz lands in the app',view(pg)['stage']=='app',view(pg))
        pg.go_back(); w(pg,300); v=view(pg)
        check(f'{L} F7 Back from results goes to quiz page 4, not the loading screen',v['stage']=='quiz' and v['step']==3,v)
        ctx.close()

        # G: reload keeps your place
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        tab(pg,'Community'); pg.reload(); w(pg,500); v=view(pg)
        check(f'{L} G1 reload in the same tab keeps Community',v['stage']=='app' and v['tab']=='Community',v)
        pg.go_back(); w(pg,300); check(f'{L} G2 Back after reload still works',view(pg)['tab']=='School',view(pg))
        ctx.close()

        # H: Settings > Welcome screens
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        tab(pg,'Settings'); pg.click('[data-act="welcome"]'); w(pg)
        check(f'{L} H1 Settings has Welcome screens',view(pg)['stage']=='intro' and view(pg)['slide']==0,view(pg))
        pg.locator('.pill').click(); w(pg); check(f'{L} H2 Go to my Home returns to the app',view(pg)['stage']=='app' and view(pg)['tab']=='Home',view(pg))
        pg.go_back(); w(pg); check(f'{L} H3 Back returns to the welcome screen',view(pg)['stage']=='intro',view(pg))
        ctx.close()

        # I: clear saved data -> welcome screen again
        ctx,pg,errs=newpage(b,vp,APP,session=True)
        tab(pg,'Settings'); pg.click('[data-act="clear"]'); w(pg,700); v=view(pg)
        check(f'{L} I1 Clear my saved data restarts at the welcome screen',v['stage']=='intro' and v['slide']==0,v)
        ctx.close()

    # T: thumbnail in the video box on the first welcome screen
    for label,vp in [('phone',{'width':390,'height':844}),('desktop',{'width':1440,'height':900})]:
        L=label
        ctx,pg,errs=newpage(b,vp,None,session=False)
        pg.wait_for_function("document.querySelector('.vid.thumb img')&&document.querySelector('.vid.thumb img').complete",timeout=5000)
        info=pg.evaluate("(()=>{const i=document.querySelector('.vid.thumb img'),b=document.querySelector('.vid.thumb').getBoundingClientRect(),t=document.querySelector('.vid .tag');return {nw:i.naturalWidth,nh:i.naturalHeight,w:b.width,h:b.height,l:b.left,r:b.right,vw:innerWidth,sw:document.documentElement.scrollWidth,tag:t.innerText}})()")
        check(f'{L} T1 thumbnail loads at 1920x1080',info['nw']==1920 and info['nh']==1080,info)
        check(f'{L} T2 box is 16:9',abs(info['w']/info['h']-16/9)<0.02,info)
        check(f'{L} T3 box fits the screen, no sideways scroll',info['l']>=0 and info['r']<=info['vw'] and info['sw']<=info['vw'],info)
        check(f'{L} T4 label says Play the video (live config)',info['tag'].strip()=='Play the video',info)
        check(f'{L} T5 Take the quiz button still there',pg.locator('.cta2 [data-act="start"]').count()==1)
        pg.screenshot(path=f'{SP}/shots/{L}-welcome1-new-thumb.png')
        ctx.close()

    # V: video link types (desktop). The thumbnail shows first; clicking it loads the player.
    TH='assets/video-thumbnail.png'
    SYN='6e255031-2fb9-46df-8795-c081b67e9e56'
    VARS=[('YouTube watch link','https://www.youtube.com/watch?v=dQw4w9WgXcQ','iframe','https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0&playsinline=1'),
          ('youtu.be link','https://youtu.be/dQw4w9WgXcQ?si=abc','iframe','https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0&playsinline=1'),
          ('YouTube Shorts link','https://www.youtube.com/shorts/dQw4w9WgXcQ','iframe','https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0&playsinline=1'),
          ('Vimeo link','https://vimeo.com/123456789','iframe','https://player.vimeo.com/video/123456789?autoplay=1'),
          ('Synthesia embed link','https://share.synthesia.io/embeds/videos/'+SYN,'iframe','https://share.synthesia.io/embeds/videos/'+SYN+'?autoplay=1'),
          ('Synthesia share link','https://share.synthesia.io/'+SYN,'iframe','https://share.synthesia.io/embeds/videos/'+SYN+'?autoplay=1'),
          ('Synthesia share link (the real one)','https://share.synthesia.io/7f128605-78cd-5867-8b47-7f6732abaf0f','iframe','https://share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f?autoplay=1'),
          ('Synthesia share link, trailing slash and query','https://share.synthesia.io/7f128605-78cd-5867-8b47-7f6732abaf0f/?x=1','iframe','https://share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f?autoplay=1'),
          ('Synthesia embed link from oEmbed (has ?source)','https://share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f?source=oembed','iframe','https://share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f?autoplay=1'),
          ('Other Synthesia page (not a video id)','https://share.synthesia.io/abc','link','https://share.synthesia.io/abc'),
          ('Any other web page','https://example.com/watch','link','https://example.com/watch'),
          ('file in assets','assets/explainer.mp4','video','assets/explainer.mp4'),
          ('mp4 web link','https://example.com/clip.mp4?x=1','video','https://example.com/clip.mp4?x=1'),
          ('empty (thumbnail with Coming soon)','','thumb','Coming soon')]
    def variant(url,vp={'width':1440,'height':900},extra=None):
        html=HTML.replace('const VIDEO="";','const VIDEO="%s";'%url)
        ctx=b.new_context(viewport=vp); errs=[]; all_errs.append(errs)
        ctx.route('**/variant.html',(lambda h:(lambda route,request:route.fulfill(status=200,content_type='text/html',body=h)))(html))
        if extra: extra(ctx)
        pg=ctx.new_page(); pg.on('pageerror',lambda e,errs=errs:errs.append('pageerror: '+str(e)))
        pg.goto(f'http://127.0.0.1:{PORT}/variant.html'); w(pg,400)
        return ctx,pg
    for name,url,kind,exp in VARS:
        ctx,pg=variant(url)
        if kind in ('iframe','video'):
            pre=(pg.locator('button.vid.thumb.play img').count()==1 and 'Play the video' in pg.locator('button.vid.play').inner_text()
                 and pg.locator('.vid iframe, .vid video').count()==0 and pg.locator('button.vid.play').get_attribute('aria-label').startswith('Play the'))
            pg.locator('button.vid.play').click(); w(pg,300)
            if kind=='iframe':
                n=pg.locator('.vid iframe').count(); got=pg.locator('.vid iframe').first.get_attribute('src') if n else None
                ok=pre and got==exp and pg.locator('button.vid.play').count()==0 and all(k in (pg.locator('.vid iframe').first.get_attribute('allow') or '') for k in ('autoplay','fullscreen','encrypted-media'))
            else:
                n=pg.locator('.vid video').count()
                got=tuple(pg.locator('.vid video').first.get_attribute(k) for k in ('src','poster','autoplay')) if n else None
                ok=pre and bool(got) and got[0]==exp and got[1]==TH and got[2] is not None and pg.locator('button.vid.play').count()==0
        elif kind=='link':
            got=pg.locator('a.vid').first.get_attribute('href') if pg.locator('a.vid').count() else None
            ok=got==exp and 'Watch the video' in pg.locator('a.vid').inner_text() and pg.locator('a.vid.thumb img').count()==1 and pg.locator('button.vid.play').count()==0
        else:
            got=pg.locator('.vid.thumb').inner_text(); ok=exp in got and pg.locator('.vid.thumb img').count()==1 and pg.locator('button.vid.play').count()==0 and pg.locator('.vid.thumb[data-act]').count()==0
        check(f'V video: {name}',ok,got); ctx.close()

    # P: real playback (small WebM served from the test folder), keyboard, and the rest of the page still works
    webm=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'test.webm'),'rb').read()
    serve=lambda ctx: ctx.route('https://example.com/clip.webm',lambda route,request:route.fulfill(status=200,content_type='video/webm',body=webm))
    ctx,pg=variant('https://example.com/clip.webm',extra=serve)
    pg.locator('button.vid.play').click(); w(pg,1600)
    st=pg.evaluate("(()=>{const v=document.querySelector('.vid video');return v?{paused:v.paused,t:v.currentTime,err:v.error&&v.error.code,rs:v.readyState}:null})()")
    check('P1 clicking the thumbnail starts the video playing',bool(st) and (not st['paused']) and st['t']>0.2,st)
    r=pg.evaluate("(()=>{const b=document.querySelector('.vid').getBoundingClientRect();return {w:b.width,h:b.height}})()")
    check('P2 player box keeps the 16:9 size of the thumbnail',abs(r['w']/r['h']-16/9)<0.02,r)
    pg.locator('.cta2 [data-act="start"]').click(); w(pg); check('P3 Take the quiz still works after playing (account step first)',view(pg)['stage']=='auth',view(pg))
    ctx.close()
    ctx,pg=variant('https://example.com/clip.webm',extra=serve)
    pg.focus('button.vid.play'); pg.keyboard.press('Enter'); w(pg,1600)
    st=pg.evaluate("(()=>{const v=document.querySelector('.vid video');return v?{paused:v.paused,t:v.currentTime}:null})()")
    check('P4 keyboard (Tab to the thumbnail, Enter) plays the video',bool(st) and (not st['paused']) and st['t']>0.2,st)
    ctx.close()
    # looks: thumbnail with Play chip, phone and computer
    for label,vp,dsf in [('phone',{'width':390,'height':844},2),('desktop',{'width':1440,'height':900},1)]:
        html=HTML.replace('const VIDEO="";','const VIDEO="https://youtu.be/dQw4w9WgXcQ";')
        ctx=b.new_context(viewport=vp,device_scale_factor=dsf,is_mobile=vp['width']<500,has_touch=vp['width']<500)
        ctx.route('**/variant.html',(lambda h:(lambda route,request:route.fulfill(status=200,content_type='text/html',body=h)))(html))
        pg=ctx.new_page(); errs=[]; all_errs.append(errs); pg.on('pageerror',lambda e,errs=errs:errs.append('pageerror: '+str(e)))
        pg.goto(f'http://127.0.0.1:{PORT}/variant.html'); w(pg,500)
        pg.wait_for_function("document.querySelector('.vid.play img')&&document.querySelector('.vid.play img').complete",timeout=5000)
        info=pg.evaluate("(()=>{const x=document.querySelector('.vid.play'),b=x.getBoundingClientRect(),i=x.querySelector('img'),t=x.querySelector('.tag').getBoundingClientRect();return {w:b.width,h:b.height,l:b.left,r:b.right,vw:innerWidth,sw:document.documentElement.scrollWidth,nw:i.naturalWidth,ih:i.getBoundingClientRect().height,tagInside:t.left>=b.left&&t.right<=b.right&&t.bottom<=b.bottom}})()")
        check(f'{label} P5 play thumbnail is 16:9, fits the screen and the label sits inside',abs(info['w']/info['h']-16/9)<0.02 and info['l']>=0 and info['r']<=info['vw'] and info['sw']<=info['vw'] and info['tagInside'] and info['nw']==1920 and abs(info['ih']-info['h'])<2,info)
        pg.screenshot(path=f'{SP}/shots/{label}-play-thumb.png')
        if label=='desktop':
            pg.hover('button.vid.play'); w(pg,250); pg.screenshot(path=f'{SP}/shots/{label}-play-thumb-hover.png')
            pg.locator('button.vid.play').click(); w(pg,500); pg.screenshot(path=f'{SP}/shots/{label}-play-after-click.png')
        ctx.close()

    # S: screenshots for a look
    for label,vp,dsf in [('phone',{'width':390,'height':844},2),('desktop',{'width':1440,'height':900},1)]:
        ctx,pg,errs=newpage(b,vp,APP,session=False,dsf=dsf); pg.screenshot(path=f'{SP}/shots/{label}-welcome1-returning.png'); 
        pg.click('[data-act="snext"]'); w(pg); pg.screenshot(path=f'{SP}/shots/{label}-welcome2.png')
        pg.click('[data-act="snext"]'); w(pg); pg.screenshot(path=f'{SP}/shots/{label}-welcome3-returning.png')
        pg.click('.bb [data-act="home"]'); w(pg); pg.screenshot(path=f'{SP}/shots/{label}-home.png'); tab(pg,'School'); pg.evaluate("document.querySelector('.more2').scrollIntoView({block:'center'})"); w(pg,200)
        pg.screenshot(path=f'{SP}/shots/{label}-list-show-more.png'); ctx.close()
    b.close()
finally:
    srv.terminate()

bad=[r for r in results if not r[1]]
errs_flat=[e for lst in all_errs for e in lst]
print('\n==== %d checks, %d failed, %d page errors'%(len(results),len(bad),len(errs_flat)))
for r in bad: print('FAILED:',r[0],'|',r[2])
for e in errs_flat[:10]: print('ERR:',e[:200])
