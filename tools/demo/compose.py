# Builds the natural-speed master video from a frames folder.
# Usage: python3 tools/demo/compose.py FRAMES_DIR master.mp4
import json, os, subprocess, sys
d = sys.argv[1]                      # frames dir
out = sys.argv[2]                    # master mp4
S = json.load(open(f'{d}/stamps.json'))
st = S['stamps']; n = len(st)
end_t = S['marks'][-1]['t']
lines = []
for i in range(n):
    dur = (st[i+1] - st[i]) if i + 1 < n else max(0.05, end_t - st[i])
    lines.append(f"file '{os.path.abspath(d)}/f{i:05d}.jpg'\nduration {dur:.5f}")
lines.append(f"file '{os.path.abspath(d)}/f{n-1:05d}.jpg'")
open(f'{d}/list.txt', 'w').write('\n'.join(lines) + '\n')
vf = "fps=25,scale=in_range=pc:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int,format=yuv420p"
cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/list.txt',
       '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-pix_fmt', 'yuv420p',
       '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
       '-movflags', '+faststart', out]
subprocess.run(cmd, check=True)
print('master written', out, round(os.path.getsize(out)/1e6, 1), 'MB')
