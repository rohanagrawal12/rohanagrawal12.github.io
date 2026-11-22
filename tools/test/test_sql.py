"""Tests Bulletin's SQL files (supabase/*.sql) on a throwaway Postgres.

It starts its own temporary database, loads a tiny stand-in for Supabase (tools/test/supabase_standin.sql:
the roles, auth.users, auth.uid() and the default permissions), runs the real SQL files as the "postgres"
role, then pretends to be a visitor, a signed-in student and the admin to check who can do what.

Needs the Postgres programs (initdb, pg_ctl, psql). If they are not installed it says so and stops.
It does not talk to the real Supabase project. It cannot test PostgREST (the web layer in front of the
database), so the exact HTTP answers are only checked by hand on the live site.
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = '54330'


def find_bin():
    for d in sorted(glob.glob('/usr/lib/postgresql/*/bin'), reverse=True):
        if os.path.exists(d + '/initdb') and os.path.exists(d + '/psql'):
            return d
    p = shutil.which('initdb')
    return os.path.dirname(p) if p else None


BIN = find_bin()
if not BIN:
    print('SKIPPED: Postgres (initdb, pg_ctl, psql) is not installed here, so the SQL was not tested.')
    print('\n==== 0 checks, 0 failed')
    sys.exit(0)

ROOT = os.geteuid() == 0
DATA = tempfile.mkdtemp(prefix='blpg')
if ROOT:
    shutil.chown(DATA, 'postgres')
    os.chmod(DATA, 0o700)
AS = ['runuser', '-u', 'postgres', '--'] if ROOT else []
ENV = dict(os.environ, PGHOST=DATA, PGPORT=PORT, PGOPTIONS='-c client_min_messages=warning')

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' | ' + str(detail)[:300]) if (detail != '' and not ok) else ''), flush=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def psql(sql, user='postgres', role=None, uid=None, file=None):
    """Run SQL in a fresh session. role/uid pretend to be an API caller, the way PostgREST does."""
    script = ''
    if role:
        script += f'set role {role};\n'
        claims = {'role': role}
        if uid:
            claims['sub'] = uid
        script += "select set_config('request.jwt.claims', '%s', false) \\gset\n" % json.dumps(claims)
    args = [BIN + '/psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-v', 'VERBOSITY=verbose', '-U', user, '-d', 'postgres']
    if file:
        return sh(args + ['-f', file], env=ENV)
    return sh(args + ['-f', '-'], env=ENV, input=script + sql + '\n')


def one(sql, **kw):
    r = psql(sql, **kw)
    return r.stdout.strip() if r.returncode == 0 else 'ERR: ' + r.stderr.strip()


def err(sql, **kw):
    r = psql(sql, **kw)
    return r.stderr if r.returncode != 0 else ''


def must(sql, **kw):
    r = psql(sql, **kw)
    assert r.returncode == 0, sql[:120] + ' -> ' + r.stderr
    return r.stdout.strip()


def count(table='public.waitlist', where=''):
    return int(one(f'select count(*) from {table} {where}'))


try:
    r = sh(AS + [BIN + '/initdb', '-D', DATA + '/d', '-A', 'trust', '--no-sync', '-U', 'supabase_admin'])
    assert r.returncode == 0, r.stderr
    r = sh(AS + [BIN + '/pg_ctl', '-D', DATA + '/d', '-o', f"-p {PORT} -c listen_addresses='' -c unix_socket_directories={DATA} -c fsync=off",
                 '-l', DATA + '/log', '-w', 'start'])
    assert r.returncode == 0, r.stdout + r.stderr
    r = sh([BIN + '/psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-U', 'supabase_admin', '-d', 'postgres', '-f', HERE + '/supabase_standin.sql'], env=ENV)
    check('S0 the stand-in for Supabase loads', r.returncode == 0, r.stderr)

    # ---------- the files load, and can be run again ----------
    for f in ['schema.sql', 'delete_account.sql']:
        r = psql('', file=REPO + '/supabase/' + f)
        check(f'S0 supabase/{f} runs as the postgres role', r.returncode == 0, r.stderr)
    ADMIN_SQL = open(REPO + '/supabase/admin.sql', encoding='utf-8').read()
    PLACE = 'your-email@example.com'
    emails = set(re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}', ADMIN_SQL))
    check('S0 admin.sql in the repo holds only the fake email, so no real address is public', emails == {PLACE}, emails)
    check('S0 admin.sql has exactly one line to put the real email in', ADMIN_SQL.count("lower('" + PLACE + "')") == 1)
    OWNER = 'owner@example.com'

    def run_admin(email=OWNER):
        f = DATA + '/admin_run.sql'
        open(f, 'w', encoding='utf-8').write(ADMIN_SQL.replace(PLACE, email))
        return psql('', file=f)

    r = run_admin()
    check('S0 admin.sql runs on a project that has no account for that email yet', r.returncode == 0, r.stderr)
    check('S0 and then shows nobody as admin, so the owner can tell to sign up first', r.stdout.strip() == '', repr(r.stdout))

    # ---------- some pretend people ----------
    def user(email, days_ago=0, login_hours_ago=None, meta=None):
        ll = 'null' if login_hours_ago is None else f"now() - interval '{login_hours_ago} hours'"
        md = (json.dumps(meta) if meta else '{}').replace("'", "''")
        return must(f"insert into auth.users (email, created_at, last_sign_in_at, encrypted_password, raw_user_meta_data) values ('{email}', now() - interval '{days_ago} days' - interval '1 hour', {ll}, 'HASH-SECRET-{email}', '{md}'::jsonb) returning id")

    OWN = user(OWNER, 3, 2); STU = user('student@example.com', 0, 0.5); STU2 = user('kid2@example.com', 1); OLD = user('old@example.com', 40, 240)
    r = run_admin()
    check('S0 admin.sql runs again once the account exists (it is safe to run twice)', r.returncode == 0, r.stderr)
    check('S0 and then lists that account as the admin', r.stdout.strip().startswith(OWNER + '|'), r.stdout)
    r = run_admin()
    check('S0 a third run changes nothing', r.returncode == 0 and count('public.admins') == 1, r.stderr)
    anon = dict(role='anon'); auth_stu = dict(role='authenticated', uid=STU); ADM = dict(role='authenticated', uid=OWN)

    # ---------- a brand new project: nothing there yet ----------
    J0 = json.loads(one('select public.admin_overview()', **ADM))
    zero = ['accounts_7d', 'quiz_done', 'providers', 'saved', 'doing', 'waitlist']
    check('S0 with no data yet the admin gets zeros, not errors or nulls', J0['accounts'] == 4 and all(J0[k] == 0 for k in zero if k != 'accounts_7d') and J0['accounts_7d'] == 3, J0)
    check('S0 and empty lists, with 14 empty days', J0['top_saved'] == [] and J0['schools'] == [] and J0['grades'] == [] and J0['waitlist_rows'] == [] and len(J0['daily']) == 14, J0)
    check('S0 accounts with no profile row yet are still listed, with no name', len(J0['accounts_list']) == 4 and all(a['name'] is None and a['quiz_done'] is False and a['provider'] is False and a['wl_org'] is None for a in J0['accounts_list']), J0['accounts_list'])

    for uid, name, ans, prov in [(OWN, 'Owner', {'grade': '12th grade', 'school': 'The Village School'}, False),
                                 (STU, 'Stu', {'grade': '10th grade', 'school': 'The Village School', 'learn': 'secret words'}, False),
                                 (STU2, 'Kid', {'grade': '10th grade', 'school': 'Another school (not listed yet)'}, True),
                                 (OLD, 'Old', None, False)]:
        a = 'null' if ans is None else "'" + json.dumps(ans) + "'::jsonb"
        must(f"insert into public.profiles (id, name, is_provider, quiz_answers) values ('{uid}', '{name}', {str(prov).lower()}, {a})")
    for uid, opp, kind in [(OWN, 'school-001', 'saved'), (STU, 'school-001', 'saved'), (STU2, 'school-001', 'saved'), (STU, 'school-002', 'saved'),
                           (STU2, 'school-002', 'saved'), (OLD, 'community-001', 'saved'), (STU, 'school-003', 'doing')]:
        must(f"insert into public.activity (user_id, opp_id, kind) values ('{uid}', '{opp}', '{kind}')")

    # ---------- the waitlist: visitors ----------
    join = lambda org, email, note='null', **kw: psql(f'select public.join_waitlist({org}, {email}, {note})', **kw)
    r = join("'Houston Academy'", "'Teacher@School.org'", "'We have 40 clubs.'", **anon)
    check('S1 a visitor with no account can join', r.returncode == 0, r.stderr)
    check('S1 the row is stored with the email in lower case', one("select org || '|' || email || '|' || note from public.waitlist") == 'Houston Academy|teacher@school.org|We have 40 clubs.')
    r = join("'Someone Else'", "'TEACHER@school.ORG'", **anon)
    check('S1 the same email again (other capitals, other name) is accepted without a second row', r.returncode == 0 and count() == 1, r.stderr)
    check('S1 and the first answer is not changed', one('select org from public.waitlist') == 'Houston Academy')
    r = join("'  Tidy Club  '", "'  Pad@Example.COM  '", "'   '", **anon)
    check('S1 spaces are trimmed and a blank note is stored as empty', r.returncode == 0 and one("select org || '|' || email || '|' || coalesce(note, 'NULL') from public.waitlist where org = 'Tidy Club'") == 'Tidy Club|pad@example.com|NULL', r.stderr)
    r = join("'Signed In School'", "'in@example.com'", **auth_stu)
    check('S1 a signed-in student can join too', r.returncode == 0 and count() == 3, r.stderr)
    r = psql("select public.join_waitlist(p_org => 'Named Args School', p_email => 'named@example.com')", **anon)
    check('S1 it works with the argument names the website sends, with the note left out', r.returncode == 0 and count(where="where email = 'named@example.com'") == 1, r.stderr)
    r = psql("select public.join_waitlist(p_org => 'Named Note School', p_email => 'named2@example.com', p_note => 'hello')", **anon)
    check('S1 and with the note put in', r.returncode == 0 and one("select note from public.waitlist where email = 'named2@example.com'") == 'hello', r.stderr)
    r = psql("select public.join_waitlist('École Française de Houston', 'first.last+tag@mail.school.k12.tx.us')", **anon)
    check('S1 accents, plus signs and long domains are fine', r.returncode == 0 and count(where="where email = 'first.last+tag@mail.school.k12.tx.us'") == 1, r.stderr)
    r = psql("select public.join_waitlist('Robert''); drop table public.waitlist;--', 'bobby@example.com')", **anon)
    check('S1 odd text is stored as plain text and does nothing', r.returncode == 0 and one("select org from public.waitlist where email = 'bobby@example.com'") == "Robert'); drop table public.waitlist;--")
    n0 = count()
    for label, org, email, note, want in [
        ('no name', "''", "'a@b.co'", 'null', 'Enter the name'), ('a one-letter name', "'X'", "'a@b.co'", 'null', 'Enter the name'),
        ('a name of 121 letters', "'" + 'x' * 121 + "'", "'a@b.co'", 'null', 'Enter the name'), ('a missing name', 'null', "'a@b.co'", 'null', 'Enter the name'),
        ('an email with no @', "'Okay School'", "'nope'", 'null', 'valid email'), ('an email with no dot after the @', "'Okay School'", "'a@b'", 'null', 'valid email'),
        ('an email with a space inside', "'Okay School'", "'a b@c.co'", 'null', 'valid email'), ('an empty email', "'Okay School'", "''", 'null', 'valid email'),
        ('an email with two @', "'Okay School'", "'a@b@c.co'", 'null', 'valid email'), ('a missing email', "'Okay School'", 'null', 'null', 'valid email'),
        ('an email of 255 characters', "'Okay School'", "'" + 'a' * 246 + "@bbbb.com'", 'null', 'valid email'),
        ('a note of 501 characters', "'Okay School'", "'a@b.co'", "'" + 'n' * 501 + "'", 'too long')]:
        e = err(f'select public.join_waitlist({org}, {email}, {note})', **anon)
        check(f'S1 refused with a plain message: {label}', want in e and count() == n0, e[:200])
    check('S1 a note of exactly 500 characters is fine', join("'Long Note School'", "'long@example.com'", "'" + 'n' * 500 + "'", **anon).returncode == 0)
    check('S1 a name of exactly 120 letters and an email of exactly 254 characters are fine', join("'" + 'é' * 120 + "'", "'" + 'a' * 245 + "@bbbb.com'", **anon).returncode == 0)
    check('S1 the unique index on the lower-case email is there', one("select count(*) from pg_indexes where indexname = 'waitlist_email_key' and indexdef ilike '%unique%lower(email%'") == '1')

    # ---------- the waitlist: nobody but the owner of the database can read or change it ----------
    n0 = count(); org0 = one("select org from public.waitlist where email = 'teacher@school.org'")
    for who, kw in [('a visitor', anon), ('a signed-in student', auth_stu), ('the admin', ADM)]:
        for label, sql in [('read it', 'select * from public.waitlist'), ('read one column', 'select email from public.waitlist'),
                           ('write to it', "insert into public.waitlist (org, email) values ('Evil School', 'e@e.co')"),
                           ('change it', "update public.waitlist set org = 'x'"), ('delete from it', 'delete from public.waitlist'),
                           ('empty it', 'truncate public.waitlist')]:
            e = err(sql, **kw)
            check(f'S2 {who} cannot {label} through the website', 'permission denied' in e, e[:200])
    check('S2 so nothing was lost or changed', count() == n0 and one("select org from public.waitlist where email = 'teacher@school.org'") == org0)

    # ---------- the waitlist: the flood guards ----------
    must("update public.waitlist set created_at = now() - interval '2 minutes'")
    r = join("'After A Pause'", "'pause@example.com'", **anon)
    check('S3 entries older than a minute do not count towards the limit', r.returncode == 0)
    must("insert into public.waitlist (org, email) select 'Bot ' || g, 'bot' || g || '@example.com' from generate_series(1, 29) g")
    check('S3 setup: 30 new rows inside the last minute', count(where="where created_at > now() - interval '1 minute'") == 30)
    e = err("select public.join_waitlist('Late School', 'late@example.com')", **anon)
    check('S3 a 31st new entry within a minute is refused with a plain message', 'busy right now' in e and count(where="where email = 'late@example.com'") == 0, e[:200])
    check('S3 an honest repeat of an email already on the list still works and writes nothing', join("'Again'", "'bot1@example.com'", **anon).returncode == 0 and count(where="where org = 'Again'") == 0)
    must("update public.waitlist set created_at = now() - interval '2 minutes'")
    check('S3 a little later it takes entries again', join("'Late School'", "'late@example.com'", **anon).returncode == 0)
    must("update public.waitlist set created_at = now() - interval '2 minutes'")
    must("insert into public.waitlist (org, email, created_at) select 'Old ' || g, 'old' || g || '@example.com', now() - interval '1 day' from generate_series(1, 10000 - (select count(*) from public.waitlist)) g")
    check('S3 setup: the table holds exactly 10,000 rows', count() == 10000, count())
    e = err("select public.join_waitlist('Too Many', 'toomany@example.com')", **anon)
    check('S3 at 10,000 rows no new entry is taken', 'busy right now' in e and count() == 10000, e[:200])
    check('S3 but an email that is already there still gets the normal answer', join("'Again'", "'old1@example.com'", **anon).returncode == 0)
    must("delete from public.waitlist where org like 'Old %' or org like 'Bot %'")
    check('S3 after clearing the junk in the Table Editor it takes entries again', join("'Fresh School'", "'fresh@example.com'", **anon).returncode == 0)

    # ---------- admins ----------
    check('S4 a visitor cannot ask is_admin()', 'permission denied' in err('select public.is_admin()', **anon))
    check('S4 a visitor cannot open admin_overview()', 'permission denied' in err('select public.admin_overview()', **anon))
    check('S4 a signed-in student is not an admin', one('select public.is_admin()', **auth_stu) == 'f')
    e = err('select public.admin_overview()', **auth_stu)
    check('S4 and is refused by admin_overview() with "Admins only."', 'Admins only.' in e and '42501' in e, e[:200])
    check('S4 the owner is an admin', one('select public.is_admin()', **ADM) == 't')
    check('S4 a call with no user id in it is not an admin either', one('select public.is_admin()', role='authenticated') == 'f')
    for who, kw in [('a visitor', anon), ('a signed-in student', auth_stu), ('the admin', ADM)]:
        for label, sql in [('read the admins list', 'select * from public.admins'),
                           ('make someone an admin', f"insert into public.admins (user_id) values ('{STU}')"),
                           ('remove an admin', 'delete from public.admins')]:
            e = err(sql, **kw)
            check(f'S4 {who} cannot {label} through the website', 'permission denied' in e, e[:200])
    check('S4 the admin list is unchanged', count('public.admins') == 1)

    # ---------- what the Admin page gets ----------
    raw = one('select public.admin_overview()', **ADM)
    try:
        J = json.loads(raw)
    except Exception:
        J = {}
        check('S5 admin_overview() returns JSON', False, raw[:300])
    exp_keys = {'accounts', 'accounts_7d', 'quiz_done', 'providers', 'saved', 'doing', 'waitlist', 'daily', 'top_saved', 'schools', 'grades', 'accounts_list', 'waitlist_rows'}
    check('S5 it returns exactly the expected parts and nothing else', set(J) == exp_keys, sorted(set(J) ^ exp_keys))
    check('S5 accounts: 4 in total', J.get('accounts') == 4, J.get('accounts'))
    check('S5 accounts in the last 7 days: 3 (the 40-day-old one is left out)', J.get('accounts_7d') == 3, J.get('accounts_7d'))
    check('S5 finished the quiz: 3 (the one with no answers is left out)', J.get('quiz_done') == 3, J.get('quiz_done'))
    check('S5 providers: 1', J.get('providers') == 1, J.get('providers'))
    check('S5 saved items: 6, "I am doing" items: 1', (J.get('saved'), J.get('doing')) == (6, 1), (J.get('saved'), J.get('doing')))
    check('S5 the waitlist count matches the table', J.get('waitlist') == count(), (J.get('waitlist'), count()))
    check('S5 most saved: school-001 (3), school-002 (2), community-001 (1)', J.get('top_saved', [])[:3] == [{'opp_id': 'school-001', 'n': 3}, {'opp_id': 'school-002', 'n': 2}, {'opp_id': 'community-001', 'n': 1}], J.get('top_saved'))
    check('S5 "doing" items are not counted as saved', all(t['opp_id'] != 'school-003' for t in J.get('top_saved', [])))
    check('S5 schools: The Village School 2, the other one 1', J.get('schools') == [{'name': 'The Village School', 'n': 2}, {'name': 'Another school (not listed yet)', 'n': 1}], J.get('schools'))
    check('S5 grades: 10th grade 2, 12th grade 1', J.get('grades') == [{'name': '10th grade', 'n': 2}, {'name': '12th grade', 'n': 1}], J.get('grades'))
    d = J.get('daily', [])
    today = datetime.now(timezone.utc).astimezone(ZoneInfo('America/Chicago')).date()
    check('S5 daily: 14 days, oldest first, the last one is today in Houston', len(d) == 14 and d[0]['day'] == (today - timedelta(days=13)).isoformat() and d[-1]['day'] == today.isoformat(), [x['day'] for x in d][:1] + [x['day'] for x in d][-1:])
    exp = {}
    for days_ago in (3, 0, 1, 40):
        day = (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=1)).astimezone(ZoneInfo('America/Chicago')).date().isoformat()
        exp[day] = exp.get(day, 0) + 1
    got = {x['day']: x['n'] for x in d}
    check('S5 daily: each day shows the right number of new accounts', sum(got.values()) == 3 and all(got.get(k, 0) == v for k, v in exp.items() if k >= d[0]['day']), (got, exp))
    rows = J.get('waitlist_rows', [])
    check('S5 waitlist rows: newest first, each with name, email, note, time and whether that email has an account', len(rows) == count() and rows[0]['org'] == 'Fresh School' and set(rows[0]) == {'id', 'org', 'email', 'note', 'created_at', 'has_account'}, rows[:1])
    check('S5 the note a visitor wrote is there', any(x['note'] == 'We have 40 clubs.' and x['email'] == 'teacher@school.org' for x in rows))
    check('S5 no quiz answer text and no password hash leaks into the result', 'secret words' not in raw and 'quiz_answers' not in raw and 'HASH-SECRET' not in raw and 'encrypted_password' not in raw, raw[:300])
    must("insert into public.waitlist (org, email, created_at) select 'Many ' || g, 'many' || g || '@example.com', now() - interval '1 day' - g * interval '1 second' from generate_series(1, 600) g")
    J2 = json.loads(one('select public.admin_overview()', **ADM))
    check('S5 the list holds the newest 500, while the count is the real total', len(J2['waitlist_rows']) == 500 and J2['waitlist'] == count() and J2['waitlist'] > 500, (len(J2['waitlist_rows']), J2['waitlist']))
    must("delete from public.waitlist where org like 'Many %'")

    # ---------- the accounts list: who signed up, and who is on the waitlist ----------
    r = join("'Student Org'", "'Student@Example.com'", **anon)
    check('S5b setup: one of the students also joins the waitlist', r.returncode == 0, r.stderr)
    J3 = json.loads(one('select public.admin_overview()', **ADM))
    acc = J3.get('accounts_list', [])
    order = ['student@example.com', 'kid2@example.com', OWNER, 'old@example.com']
    by_email = {a['email']: a for a in acc}
    check('S5b the accounts list has every account, newest first', [a['email'] for a in acc] == order, [a['email'] for a in acc])
    check('S5b each account has a name, email, role, provider flag, joined time, last log in, quiz flag and waitlist school, and nothing else',
          bool(acc) and all(set(a) == {'name', 'email', 'role', 'provider', 'created_at', 'last_login', 'quiz_done', 'wl_org'} for a in acc), [sorted(a) for a in acc][:1])
    check('S5b the names come from the profiles', [by_email[e]['name'] for e in order] == ['Stu', 'Kid', 'Owner', 'Old'], by_email)
    check('S5b role and provider come from the profile (only the second student is a provider)',
          {e: (a['role'], a['provider']) for e, a in by_email.items()} == {'student@example.com': ('Student', False), 'kid2@example.com': ('Student', True), OWNER: ('Student', False), 'old@example.com': ('Student', False)}, by_email)
    check('S5b quiz finished: yes for three, no for the one with no answers',
          {e: a['quiz_done'] for e, a in by_email.items()} == {'student@example.com': True, 'kid2@example.com': True, OWNER: True, 'old@example.com': False}, by_email)
    check('S5b last log in is there, and empty for the one who never logged in again', [by_email[e]['last_login'] is None for e in order] == [False, True, False, False], by_email)
    check('S5b joined and last log in are real timestamps', all(re.match(r'^\d{4}-\d\d-\d\dT', a['created_at']) for a in acc) and re.match(r'^\d{4}-\d\d-\d\dT', by_email[OWNER]['last_login']) is not None, acc[:1])
    check('S5b the student who joined the waitlist shows the school they typed, the others show none',
          {e: a['wl_org'] for e, a in by_email.items()} == {'student@example.com': 'Student Org', 'kid2@example.com': None, OWNER: None, 'old@example.com': None}, by_email)
    wl = {x['email']: x for x in J3['waitlist_rows']}
    check('S5b and that waitlist entry says it has an account, while another one does not',
          wl['student@example.com']['has_account'] is True and wl['teacher@school.org']['has_account'] is False, (wl.get('student@example.com'), wl.get('teacher@school.org')))
    raw3 = json.dumps(J3)
    check('S5b still no quiz answer text and no password hash anywhere in the result', 'secret words' not in raw3 and 'quiz_answers' not in raw3 and 'HASH-SECRET' not in raw3 and 'encrypted_password' not in raw3)
    NP = user('meta@example.com', 0, 1, {'name': '  Meta Name ', 'role': 'Student', 'provider': True, 'org': 'Chess Club'})
    J4 = json.loads(one('select public.admin_overview()', **ADM))
    a5 = {a['email']: a for a in J4['accounts_list']}.get('meta@example.com', {})
    check('S5b an account with no profile row yet takes its name, role and provider flag from what was typed at sign-up',
          (a5.get('name'), a5.get('role'), a5.get('provider'), a5.get('quiz_done')) == ('Meta Name', 'Student', True, False), a5)
    check('S5b and the account count and the list both grow by one', J4['accounts'] == 5 and len(J4['accounts_list']) == 5, (J4['accounts'], len(J4['accounts_list'])))
    must(f"delete from auth.users where id = '{NP}'")
    must("insert into auth.users (email, created_at) select 'bulk' || g || '@example.com', now() - interval '100 days' - g * interval '1 second' from generate_series(1, 600) g")
    J5 = json.loads(one('select public.admin_overview()', **ADM))
    check('S5b the list holds the newest 500, while the count is the real total (the newest accounts stay at the top)',
          len(J5['accounts_list']) == 500 and J5['accounts'] == 604 and [a['email'] for a in J5['accounts_list']][:4] == order, (len(J5['accounts_list']), J5['accounts']))
    must("delete from auth.users where email like 'bulk%@example.com'")

    # ---------- taking admin away, and deleting accounts ----------
    must(f"delete from public.admins where user_id = '{OWN}'")
    check('S6 once removed from the list the owner is refused again', one('select public.is_admin()', **ADM) == 'f' and 'Admins only.' in err('select public.admin_overview()', **ADM))
    run_admin()
    check('S6 and is an admin again after section 3 is run again', one('select public.is_admin()', **ADM) == 't')
    n_wl = count()
    r = psql('select public.delete_my_account()', **ADM)
    check('S6 deleting the admin account (Settings > Delete my account) works and removes the admin row with it', r.returncode == 0 and count('public.admins') == 0 and count('auth.users') == 3 and count('public.profiles') == 3, r.stderr)
    check('S6 the waitlist is not tied to accounts, so it is untouched', count() == n_wl)

    # ---------- the older tables are still closed ----------
    check('S7 a student still sees only their own profile', one('select count(*) from public.profiles', **auth_stu) == '1')
    check('S7 a visitor still sees no profiles and no saved items', one('select count(*) from public.profiles', **anon) == '0' and one('select count(*) from public.activity', **anon) == '0')

    # ---------- the rights on everything the file adds ----------
    q = """select p.proname || ':' || string_agg(distinct a.grantee::regrole::text, ',' order by a.grantee::regrole::text)
           from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
           where n.nspname = 'public' and p.proname in ('join_waitlist', 'is_admin', 'admin_overview') and a.privilege_type = 'EXECUTE'
           group by p.proname order by 1"""
    got = one(q)
    check('S8 who may run each function: join_waitlist visitors and signed-in people, the other two signed-in people only, never "public"',
          got.splitlines() == ['admin_overview:authenticated,postgres,service_role', 'is_admin:authenticated,postgres,service_role', 'join_waitlist:anon,authenticated,postgres,service_role'], got)
    check('S8 both new tables have row-level security turned on', one("select count(*) from pg_class where relname in ('waitlist', 'admins') and relrowsecurity") == '2')
    check('S8 all three functions run with the owner\'s rights and an empty search path', one("select count(*) from pg_proc where proname in ('join_waitlist', 'is_admin', 'admin_overview') and prosecdef and proconfig @> array['search_path=\"\"']") == '3')
    check('S8 the website roles have no rights at all on the two new tables', one("select count(*) from information_schema.role_table_grants where table_schema = 'public' and table_name in ('waitlist', 'admins') and grantee in ('anon', 'authenticated')") == '0')
finally:
    sh(AS + [BIN + '/pg_ctl', '-D', DATA + '/d', '-m', 'immediate', '-w', 'stop'])
    shutil.rmtree(DATA, ignore_errors=True)

bad = [r for r in results if not r[1]]
print('\n==== %d checks, %d failed' % (len(results), len(bad)))
for r in bad:
    print('FAILED:', r[0], '|', str(r[2])[:300])
sys.exit(1 if bad else 0)
