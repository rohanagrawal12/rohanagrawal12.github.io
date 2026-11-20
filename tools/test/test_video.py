import subprocess, time, json, os
from playwright.sync_api import sync_playwright
REPO=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); PORT=8773; SHOTS=os.environ.get('BL_SHOTS','/tmp/bulletin-test-shots')+'/shots'; os.makedirs(SHOTS,exist_ok=True)
EXP='https://share.synthesia.io/embeds/videos/7f128605-78cd-5867-8b47-7f6732abaf0f?autoplay=1'
srv=subprocess.Popen(['python3','-I','-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=REPO,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
res=[]
def check(n,ok,d=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(d)),flush=True)
try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    for label,vp,dsf in [('phone',{'width':390,'height':844},2),('desktop',{'width':1440,'height':900},1),('tablet',{'width':820,'height':1180},1)]:
        mob=vp['width']<500
        ctx=b.new_context(viewport=vp,device_scale_factor=dsf,is_mobile=mob,has_touch=mob,color_scheme='light')
        ctx.add_init_script("try{if(!sessionStorage.getItem('__s')){sessionStorage.setItem('__s','1');localStorage.clear()}}catch(e){}")
        ctx.route('https://share.synthesia.io/**',lambda route,req:route.fulfill(status=200,content_type='text/html',body='<body style="margin:0;background:#111113;color:#fff;font:16px sans-serif;display:grid;place-items:center;height:100vh">player stub</body>'))
        pg=ctx.new_page(); errs=[]
        pg.on('pageerror',lambda e,errs=errs:errs.append(str(e)))
        pg.on('console',lambda m,errs=errs:errs.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text and 'ERR_' not in m.text else None)
        pg.goto(f'http://127.0.0.1:{PORT}/index.html'); pg.wait_for_timeout(600)
        pg.wait_for_function("document.querySelector('.vid.play img')&&document.querySelector('.vid.play img').complete",timeout=5000)
        tag=pg.locator('.vid.play .tag').inner_text().strip()
        check(f'{label} live page shows the thumbnail with "Play the video"',tag=='Play the video',tag)
        pg.screenshot(path=f'{SHOTS}/{label}-live-before-click.png')
        h0=pg.evaluate('history.length')
        pg.locator('button.vid.play').click(); pg.wait_for_timeout(700)
        got=pg.locator('.vid iframe').first.get_attribute('src') if pg.locator('.vid iframe').count() else None
        check(f'{label} click swaps in the Synthesia player at the right address',got==EXP,got)
        m=pg.evaluate("(()=>{const f=document.querySelector('.vid iframe').getBoundingClientRect(),t=document.querySelector('.vid').getBoundingClientRect();return {w:f.width,h:f.height,l:f.left,r:f.right,vw:innerWidth,sw:document.documentElement.scrollWidth,tw:t.width,th:t.height}})()")
        check(f'{label} player is 16:9 and fits the screen',abs(m['w']/m['h']-16/9)<0.02 and m['l']>=0 and m['r']<=m['vw'] and m['sw']<=m['vw'],m)
        check(f'{label} click did not add a Back-button entry',pg.evaluate('history.length')==h0,(h0,pg.evaluate('history.length')))
        pg.screenshot(path=f'{SHOTS}/{label}-live-after-click.png')
        pg.locator('[data-act="quiz"]').click(); pg.wait_for_timeout(300)
        check(f'{label} Take the quiz still works after the video',pg.evaluate('S.stage')=='quiz',pg.evaluate('S.stage'))
        pg.go_back(); pg.wait_for_timeout(400)
        st=pg.evaluate('({stage:S.stage,slide:S.slide})')
        check(f'{label} Back returns to the welcome screen with the thumbnail again',st['stage']=='intro' and st['slide']==0 and pg.locator('button.vid.play img').count()==1,st)
        check(f'{label} no page errors',not errs,errs[:3])
        ctx.close()
    b.close()
finally:
    srv.terminate()
print('\n==== %d checks, %d failed'%(len(res),res.count(False)))
