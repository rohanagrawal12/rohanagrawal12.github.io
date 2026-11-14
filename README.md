# Bulletin: Find your thing.

Bulletin helps students find clubs, volunteering and programs that fit them. Answer a short quiz in your own words and every opportunity is ranked with a 1-10 match level. It starts with The Village School (Houston), plus Houston community programs and national or online programs.

Live: https://rohanagrawal12.github.io

One page, no build step. Open `index.html` in a browser to try it.

## What is here
- `index.html`: the whole app (this is what GitHub Pages serves)
- `data/`: the opportunity list (`opportunities.json` and a spreadsheet copy)
- `assets/`: logos, app icons, previews and a demo screen recording
- `docs/`: brand sheet, Synthesia video prompt, pitch answers, landing page copy
- `supabase/schema.sql`: database tables for accounts, saves, posts, friends and messages
- `CLAUDE.md`: project notes so an AI assistant can pick up where the last session stopped

## Everything is saved in the browser for now
Quiz answers, saved items, accounts and messages are stored in `localStorage` (keys `bl.state`, `bl.users`, `bl.msgs`, `bl.custom`). Real accounts through Supabase are the next step.

## Add the explainer video to the homepage
Upload the video to YouTube as Unlisted. In `index.html`, find `const VIDEO=""` and paste the link, for example `const VIDEO="https://youtu.be/XXXXXXXXXXX"`. Or put an MP4 in `assets/` and use `const VIDEO="assets/explainer.mp4"`.

## Supabase
1. In the Supabase project, open SQL Editor, click New query, paste the SQL code from `supabase/schema.sql` (the code, not the file name) and click Run. Five tables appear under Table Editor.
2. Copy the Project URL and the publishable (anon) key. Never share or commit the secret or service_role key.
3. Browser library: `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`.

## Custom domain
In GitHub: Settings > Pages > Custom domain. At the domain registrar, add four A records (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and a `www` CNAME to the github.io address. Turn on Enforce HTTPS once it is available.

## License
GPL-3.0. See `LICENSE`.
