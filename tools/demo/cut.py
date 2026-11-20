# Cuts the 30 second demo (arg "30") or the full demo (arg "full") from the master video.
# The SEG30 table sets how long each step lasts, to line up with the voiceover in docs/explainer-video-prompt.md.
# Usage: python3 tools/demo/cut.py FRAMES_DIR master.mp4 30 assets/bulletin-demo-30s.mp4
import json, subprocess, sys
d, master, which, out = sys.argv[1:5]
S = json.load(open(f'{d}/stamps.json')); t0 = S['stamps'][0]
M = {m['name']: m['t'] - t0 for m in S['marks']}
# (from mark, to mark, target seconds, mode)
SEG30 = [
 ('quiz1','quiz2',1.35,'speed'), ('quiz2','quiz3',3.20,'speed'), ('quiz3','quiz4',1.65,'speed'), ('quiz4','loading',1.60,'speed'),
 ('loading','results',1.00,'speed'), ('results','community',0.90,'speed'),
 ('community','explore_tab',1.50,'speed'), ('explore_tab','school_again',1.45,'speed'),
 ('school_again','scroll_down',1.00,'speed'), ('scroll_down','scroll_up',2.20,'speed'), ('scroll_up','card_explore_click',1.20,'speed'),
 ('card_explore_click','card_open',1.30,'speed'), ('card_open','save_click',4.95,'hold'),
 ('save_click','myact_click',1.90,'speed'), ('myact_click','myact',1.40,'speed'), ('myact','end',3.40,'speed'),
]
SEG_FULL = [
 ('welcome','quiz1',3.20,'speed'), ('quiz1','quiz2',3.00,'speed'), ('quiz2','quiz3',7.40,'speed'), ('quiz3','quiz4',4.20,'speed'), ('quiz4','loading',3.40,'speed'),
 ('loading','results',None,'speed'), ('results','community',None,'speed'),
 ('community','explore_tab',None,'speed'), ('explore_tab','school_again',None,'speed'),
 ('school_again','scroll_down',None,'speed'), ('scroll_down','scroll_up',None,'speed'), ('scroll_up','card_explore_click',None,'speed'),
 ('card_explore_click','card_open',None,'speed'), ('card_open','save_click',None,'speed'),
 ('save_click','myact_click',None,'speed'), ('myact_click','myact',None,'speed'), ('myact','end',None,'speed'),
]
SEGS = SEG30 if which == '30' else SEG_FULL
parts = []; labels = []; total = 0
for i, (a, b, T, mode) in enumerate(SEGS):
    s, e = M[a], M[b]; N = e - s
    if T is None: T = N
    if mode == 'hold' and T >= N:
        chain = f"trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,fps=25,tpad=stop_mode=clone:stop_duration={T-N:.3f}"
        f = 1.0
    else:
        f = N / T
        chain = f"trim=start={s:.3f}:end={e:.3f},setpts=(PTS-STARTPTS)/{f:.5f},fps=25"
    parts.append(f"[0:v]{chain}[v{i}]"); labels.append(f"[v{i}]"); total += T
    print(f"{a:>20s} -> {b:<20s} natural {N:5.2f}s  target {T:5.2f}s  speed x{f:4.2f}")
fc = ';'.join(parts) + ';' + ''.join(labels) + f"concat=n={len(SEGS)}:v=1:a=0,format=yuv420p[out]"
print('planned length', round(total, 2), 's')
cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', master, '-filter_complex', fc, '-map', '[out]',
       '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '25',
       '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
       '-movflags', '+faststart', '-an', out]
subprocess.run(cmd, check=True)
print('written', out)
