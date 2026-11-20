# Tests for the Bulletin page

These check the page in a real headless browser (Chromium through Playwright). They need Python 3 and the `playwright` package with its Chromium. Nothing here talks to the real Supabase project.

Run one from the repo folder, for example:

    python3 tools/test/test_sb.py

Each script starts its own small web server on a spare port, prints PASS or FAIL for every check, and ends with a line like `112 checks, 0 failed`. Screenshots go to `/tmp/bulletin-test-shots/shots` (set `BL_SHOTS` to use another folder).

| Script | What it covers |
|---|---|
| `test_sb.py` | Sign-up, login, logout, saving, quiz answers, expired logins, offline, delete account, and the device-only fallback. Uses `fake_sb.py`. |
| `test_nav.py` | The welcome screens, the browser Back button, search, show more, and the video box. |
| `test_landing.py` | Layout and wording of the three welcome screens on phone, tablet and desktop. |
| `test_video.py` | The explainer video thumbnail and player. |

## The pretend Supabase (`fake_sb.py`)
It answers the same web addresses the page calls (`/auth/v1/...` and `/rest/v1/...`) with the same JSON shapes the real service uses. It also checks the rules that matter and records any broken one in `fake.violations`:
- the publishable key is only ever sent in the `apikey` header, never as a Bearer token;
- the sign-up and login requests carry no `Authorization` header;
- data requests only see the signed-in person's own rows (like row-level security);
- access tokens expire and refresh tokens can only be used once.

It can also pretend that email confirmation is on, that the internet is down or the server is busy (`fake.fail`), that the `delete_my_account()` database function is installed (`fake.rpc`), or that a token has expired (`fake.force401`).

## What these cannot tell you
The shell that runs them cannot reach the real Supabase project, so a real sign-up, the real answers of the service and real phones or Safari are checked by hand on the live site. The pretend service was written from Supabase's documented behavior and from read-only checks of the real project (error shapes, that email confirmation is off, that the five tables exist and that browsers are allowed to call it).
