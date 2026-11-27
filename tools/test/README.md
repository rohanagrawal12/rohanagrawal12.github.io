# Tests for the Bulletin page

These check the page in a real headless browser (Chromium through Playwright). They need Python 3 and the `playwright` package with its Chromium. Nothing here talks to the real Supabase project.

Run one from the repo folder, for example:

    python3 tools/test/test_sb.py

Each script starts its own small web server on a spare port, prints PASS or FAIL for every check, and ends with a line like `187 checks, 0 failed`. Screenshots go to `/tmp/bulletin-test-shots/shots` (set `BL_SHOTS` to use another folder).

| Script | What it covers |
|---|---|
| `test_sb.py` | Sign-up (a new account starts empty and goes to the required quiz), login (lands on Home), logout, the Sign up button in the top bar, change password, saving, quiz answers, expired logins, offline, delete account, the school waitlist form, the Admin page (S19), its Accounts list (S20), the Take the quiz banner that only admins without a quiz can see (S21), and the device-only fallback. Uses `fake_sb.py`. |
| `test_home.py` | The required quiz (account step, quiz step and quiz page 1 have no skip and always a way back), the four account types and the wording each gets, organizers skipping the quiz, where a person lives (school clubs only for The Village School, Community only for Houston ZIP codes), the ZIP code card for older accounts, what Home shows, and the logo and name going Home. Uses `fake_sb.py`. |
| `test_nav.py` | The welcome screens, the browser Back button, search, show more, and the video box. |
| `test_landing.py` | Layout and wording of the three welcome screens on phone, tablet and desktop. |
| `test_video.py` | The explainer video thumbnail and player. |
| `test_sql.py` | The SQL files in `supabase/` on a real throwaway Postgres: the tables are closed to the website, `join_waitlist()` checks and de-duplicates, `is_admin()` and `admin_overview()` only work for people on the admin list, `admin_overview()` lists the newest 500 accounts (name, email, dates, waitlist school) without ever returning quiz answers or password hashes, and deleting an account removes its admin row. Needs a Postgres install (it says SKIPPED without one) and uses `supabase_standin.sql` to pretend to be Supabase’s roles and `auth` schema. |

## The pretend Supabase (`fake_sb.py`)
It answers the same web addresses the page calls (`/auth/v1/...` and `/rest/v1/...`) with the same JSON shapes the real service uses. It also checks the rules that matter and records any broken one in `fake.violations`:
- the publishable key is only ever sent in the `apikey` header, never as a Bearer token;
- the sign-up and login requests carry no `Authorization` header;
- data requests only see the signed-in person's own rows (like row-level security);
- access tokens expire and refresh tokens can only be used once.

It can also pretend that email confirmation is on, that the internet is down or the server is busy (`fake.fail`), that the `delete_my_account()` database function is installed (`fake.rpc`), that a token has expired (`fake.force401` for the next few requests, or `fake.expire_now()` for every request that still carries a token handed out so far, which does not depend on the order requests arrive in), or that Supabase's "Secure password change" is on (`fake.reauth`). It also answers `PUT /auth/v1/user`, the call that changes a password, and lists the accounts whose password changed in `fake.pw_changes`.

For the waitlist and the Admin page it can pretend that `supabase/admin.sql` has been run (`fake.sql`, or `fake.make_admin(email)` which also puts that account on the admin list), keep the waitlist (`fake.add_waitlist(...)`, `fake.waitlist`), turn on the database’s flood guard (`fake.wl_busy`), change parts of the numbers (`fake.ov_extra`) and pretend the project still has the older `admin.sql` with no accounts list (`fake.ov_old`). Each account can have `created` and `last` (last log in) times. It answers `join_waitlist()`, `is_admin()` and `admin_overview()` the way the real functions do, including the 404 / PGRST202 answer when the SQL has not been run and the 403 / 42501 answer for someone who is not an admin. It records a rule broken if `join_waitlist()` is sent with a login token. The real SQL is checked separately by `test_sql.py`.

## What these cannot tell you
The shell that runs them cannot reach the real Supabase project, so a real sign-up, the real answers of the service and real phones or Safari are checked by hand on the live site. The pretend service was written from Supabase's documented behavior and from read-only checks of the real project (error shapes, that email confirmation is off, that the five tables exist and that browsers are allowed to call it). The waitlist and Admin SQL (`supabase/admin.sql`) has not been run on the real project yet, so the real answers of `join_waitlist()`, `is_admin()` and `admin_overview()` have only been checked on a stand-in Postgres.
