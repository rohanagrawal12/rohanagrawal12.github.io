# Opportunity Finder (working name)

Student opportunity finder for The Village School (Houston). One page, no build step.

## Run it
Open `index.html` in a browser. That's it.

## Put it on GitHub Pages
1. Create a repo and upload these files.
2. Settings > Pages > Deploy from branch > `main` / root.

## How it works
- First visit: 3-page quiz (about 2 minutes). On submit, results show instantly.
- Everything is saved in the browser (`localStorage`, key `ofinder.v1`): quiz answers, which page you were on, filters, search, "Already in" and "Explored" lists. A refresh restores it all.
- Tabs: School, Community, Explore, My Activities. Settings (gear) can retake the quiz or clear saved data.

## Match level (1-10)
Computed per student, per tab, in `score()` inside `index.html`:
1. Free-text answers become keywords (with a small synonym list, e.g. "doctor" also matches medicine and healthcare).
2. Keywords are compared to each opportunity's tags (heaviest), name, category, "good fit" traits and description. Rare matches count more.
3. Bonuses: matches the "what do you want to do most" picks and the "main reason" picks.
4. "Don't want to do" answers subtract points.
5. Filters multiply the score down (grade mismatch, too many hours, wrong format, no ride, paid only, not free at that time, closed).
6. Scores are scaled so the best match in each tab is 10.

## Data
`data/opportunities.json` has the full list. `index.html` has a copy embedded in `const DATA`. To change data, edit the JSON and regenerate that line (or replace the embedded object). `index.src.html` is the same app with a `__DATA__` placeholder.
Fields are explained in the JSON's `about` section. 68 extra School clubs with too little info are listed at the bottom of the JSON.

## Not built yet
Accounts and a real database (data is per device right now), first-time tutorial, help page, club leader submissions, admin approval, "Suggest a club", real club-by-club live data.
Community and Explore details need checking against official sites (see each row's notes).

## Prompt to give Cursor
"Convert this single-file app in index.html into a Vite + React project. Keep the matching logic in its own module, load data/opportunities.json, keep localStorage persistence, and keep the UI the same."
