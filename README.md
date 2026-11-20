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

## Where things are saved
- Guests: quiz answers and saved items stay in the browser (`localStorage`, key `bl.state`).
- Accounts: sign-up and login use Supabase. The quiz answers and the saved and "I'm doing" items are saved to the account and follow the person to any device. The login is kept in the browser under `bl.sb`.
- Friends, messages and posts from providers are still saved in the browser only (`bl.users`, `bl.msgs`, `bl.custom`). Moving them to Supabase is the next step.
- If `SB_URL` or `SB_KEY` in `index.html` is emptied, the whole site goes back to saving everything in the browser.

## The explainer video on the homepage
It is set by `const VIDEO=` near the top of the script in `index.html`. It accepts a YouTube, Vimeo or Synthesia link, or an MP4 (a link or a file in `assets/`). Leave it empty to show "Coming soon".

## Supabase
1. In the Supabase project, open SQL Editor, click New query, paste the SQL code from `supabase/schema.sql` (the code, not the file name) and click Run. Five tables appear under Table Editor.
2. The site address and the publishable (anon) key are in `index.html` as `SB_URL` and `SB_KEY`. They are public by design. Never share or commit the secret or service_role key.
3. The site talks to Supabase with plain `fetch` calls, no library. In Supabase under Authentication, keep Email on and "Confirm email" off until custom email sending is set up (the built-in email service only sends 2 emails an hour to team members).

## Custom domain
In GitHub: Settings > Pages > Custom domain. At the domain registrar, add four A records (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and a `www` CNAME to the github.io address. Turn on Enforce HTTPS once it is available.

## License
GPL-3.0. See `LICENSE`.
