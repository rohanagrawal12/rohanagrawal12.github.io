# Opportunity Finder (working name)

Student opportunity finder for The Village School (Houston). One page, no build step.

## Run it
Open `index.html` in a browser. That's it.

## Put it on GitHub Pages
1. Create a repo and upload these files.
2. Settings > Pages > Deploy from branch > `main` / root.

## How it works
- The lists are visible right away. The quiz is optional: take it when you want results sorted for you.
- Quiz pages: about you, what you like (including what you want to learn), follow-up skill and interest questions when your answers mention a topic, then what you’re looking for. Opportunity types and reasons have no pick limit.
- Everything is saved in the browser (`localStorage`, key `ofinder.v1`): quiz answers, filters, search, "Already in" and "Explored" lists. A refresh restores it.
- Tabs: School, Community, Explore, My Activities. Settings (gear or your name) has the account, light/dark/match-device, retake, and clear.
- Accounts are stored on this device only (`ofinder.accounts.v1`). There is no server login yet.
- School clubs that were held back for missing details, including DECA and FBLA, are on the School list with a status such as “Pending approval.” Use the Status filter to show only those, or only clubs ready to join.
- Filters are a compact row: category, format, status, and sort.

## Branding
Edit the `BRAND` object at the top of the script in `index.src.html` (name, mark, school name, light colors, dark colors), then run `node build.js`. That regenerates `index.html`.

## Match level (1-10)
Computed per student, per tab, in `score()` inside `index.html`:
1. Free-text answers become keywords (with a small synonym list, e.g. "doctor" also matches medicine and healthcare).
2. Keywords are compared to each opportunity's tags (heaviest), name, category, "good fit" traits and description. Rare matches count more.
3. Bonuses: matches the "what do you want to do most" picks and the "main reason" picks.
4. "Don't want to do" answers subtract points.
5. Filters multiply the score down (grade mismatch, too many hours, wrong format, no ride, paid only, not free at that time, closed).
6. Scores are scaled so the best match in each tab is 10.

## Data
`data/opportunities.json` has the full list, including `extra_opportunities_not_enough_info`. The app shows those extras on the School tab. `index.html` has a copy embedded in `const DATA`. To change data or the page, edit `data/opportunities.json` and/or `index.src.html`, then run `node build.js`.
Fields are explained in the JSON's `about` section. 68 extra School clubs with too little info are listed at the bottom of the JSON.

## Not built yet
Online accounts and a real database (accounts and answers stay on this device), first-time tutorial, help page, club leader submissions, admin approval, "Suggest a club", real club-by-club live data.
Community and Explore details need checking against official sites (see each row's notes).

## Prompt to give Cursor
"Convert this single-file app in index.html into a Vite + React project. Keep the matching logic in its own module, load data/opportunities.json, keep localStorage persistence, and keep the UI the same."
