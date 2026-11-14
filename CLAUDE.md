# Bulletin: notes for Claude

Bulletin ("Find your thing.") is a student opportunity finder. A student writes a few sentences about themselves in a short quiz, and the app ranks clubs, volunteering and programs with a 1-10 match level. It starts with The Village School in Houston, TX (98 school clubs), plus 31 Houston community opportunities and 28 national or online "Explore" programs.

## How to work with the owner
- The owner is new to coding and often works from a phone. Give short, plain-English steps with the exact button names, one thing at a time. Say plainly when something could not be checked.
- They dislike anything that looks "AI-made" or busy. Keep the design clean and simple: black, white and gray with one red accent, lots of empty space, square-ish corners, no gradients, glows or emoji.
- They want changes live quickly. Pushing to `main` updates the website, so keep commits small and say what changed.
- Never put secret keys in this repo. The Supabase publishable (anon) key is public by design and is fine. The Supabase secret or service_role key is never OK.

## Files
- `index.html` is the whole app (HTML, CSS, JS and the opportunity data in one file, no build step). GitHub Pages serves it. Edit this file directly.
- `index.src.html` is an older template of the same page, from before the logo and data were embedded. It is not the source of truth. Do not try to rebuild `index.html` from it.
- `data/opportunities.json` has the opportunity data (keys: about, school, community, explore, extra_opportunities_not_enough_info). The same data is embedded in `index.html` as `DATA`. If you change the JSON, update the embedded copy too.
- `assets/` has the logos, icons, previews and a demo screen recording. `docs/` has the brand sheet, the Synthesia video prompt, pitch answers and landing copy. `supabase/schema.sql` creates the database tables. `manifest.webmanifest` makes it installable on a phone.

## How the app works
- One state object `S` is saved in the browser under `localStorage` key `bl.state`. Accounts are in `bl.users`, messages in `bl.msgs`, provider posts in `bl.custom`. Settings > clear removes them.
- `S.stage` goes intro (3 welcome slides, the first has the video box) > auth > prompt > quiz (4 pages, defined in `PAGES`) > loading > app. Tabs: School, Community, Explore, My Activities, plus Search and Settings.
- Pages are string templates. `render()` rebuilds the page. All clicks go through `act(name, data)` using `data-act` attributes, and `go(tab)` switches tabs.
- Matching is `score()`. It stems the student's answers and expands them with a small synonym list, compares them to each opportunity's tags (heaviest), name, category, "good fit" traits and description with rarity weights, adds bonuses for the "want" and "why" picks and skill ratings, subtracts for "avoid" text, applies filters (grade, hours, format, ride, paid, free time, closed), then scales each tab to 1-10.
- Themes: auto, light, dark, forest, yellow, marker (`THEMES`). Brand name is `BRAND`.
- `const VIDEO=""` near the top fills the homepage video box. A YouTube link embeds. A file path such as `assets/explainer.mp4` plays directly.

## Testing
Playwright with headless Chromium works. Seed the state before the page loads, for example an init script that runs:
`localStorage.setItem('bl.state', JSON.stringify({stage:'app',tab:'School',seen:true,done:true,theme:'light',ans:{grade:'10th grade',school:'The Village School',learn:'biology and chemistry',want:['Join a club'],why:['Trying new things'],time:'3-5 hours'}}))`
Check phone (390x844) and desktop (1440x900), in light and dark.

## Brand
Colours: Ink #111113, Gray #6B6B72, Fog #E1E1E4, Paper #F3F3F4, Pin Red #D6452F (optional Forest theme #1F4D36). Font: Inter (Bold for logo and headings, Regular for the rest). Logo: four rounded tiles (one red = "your match") next to the lowercase wordmark "bulletin" with a red dot on the i. Tagline: Find your thing. Details in `docs/brand.md`.

## Where things stand (2026-11-13)
Done: the site, logo, brand board, and the Supabase tables (`supabase/schema.sql` was run in the Supabase project "Bulletin", with row-level security on).

Not done yet:
1. **Company-name URL.** The site is at https://rohanagrawal12.github.io and the owner wants the company name in the address. Options: (a) a new free GitHub organization named after the company with a repo called `<org>.github.io`; (b) a Student Developer Pack domain (Namecheap .me or Name.com) used as a GitHub Pages custom domain (four A records 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153 plus a `www` CNAME to the github.io address). Add a `CNAME` file only after the DNS records exist, or the site breaks.
2. **Supabase wiring.** The app still keeps everything in the browser. Next: add `@supabase/supabase-js@2` from a CDN, then real sign-up and login, and save quiz answers, saved and "doing" items, provider posts, friends and messages. This needs the project URL and publishable key from the owner (not in the repo yet). Keep the browser-only mode as a fallback when those are empty. In Supabase Auth: Email on, "Confirm email" off while testing, and Site URL and Redirect URLs set to the final site address.
3. **Explainer video.** The owner is making it in Synthesia from `docs/explainer-video-prompt.md`, using `assets/bulletin-demo.mp4` for the demo scene. When it is done, set `const VIDEO`.
