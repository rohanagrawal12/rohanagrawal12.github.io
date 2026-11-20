# Demo recording tools

These scripts record the screen demo (`assets/bulletin-demo.mp4` and `assets/bulletin-demo-30s.mp4`) straight from the live `index.html`, so the video always matches the current look of the site. Run them again after any visual change.

Needs: Node with Playwright and its Chromium, Python 3, and ffmpeg.

1. Record (about 80 seconds, writes JPEG frames and `stamps.json` with the time of each step):
   `node tools/demo/record.js /tmp/frames`
2. Build the natural-speed master (1920x1080, 25 fps):
   `python3 tools/demo/compose.py /tmp/frames /tmp/master.mp4`
3. Cut the two versions:
   `python3 tools/demo/cut.py /tmp/frames /tmp/master.mp4 30 assets/bulletin-demo-30s.mp4`
   `python3 tools/demo/cut.py /tmp/frames /tmp/master.mp4 full assets/bulletin-demo.mp4`

Notes
- The page is 1280x720 at a real 1.5x scale, so frames are 1920x1080 and the layout is the normal desktop one. Zooming a 1920 page instead changes the layout, so do not.
- Native dropdowns are not clicked for real (they look wrong in recordings); the value is set after a pretend click.
- The quiz answers are in `ANS` at the top of `record.js`. The 30 second timing table is `SEG30` in `cut.py` and follows the voiceover (quiz about 8 s, then clubs, volunteer spots, programs, a card, save, My Activities).
- The cursor is drawn by the page itself (an arrow that follows the same path as the real mouse).
