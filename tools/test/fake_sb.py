"""A pretend Supabase for testing Bulletin's sign-up, login and saving without touching the real project.
It answers the same URLs the page calls, with the same JSON shapes the real service uses, and it checks
the rules that matter: the publishable key only in "apikey", never as a Bearer token; Row Level Security style
own-rows-only access; token expiry and refresh-token rotation."""
import collections, json, re, time, uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs

KEY = 'sb_publishable_sQhpqrrzvwO1oyKf5loSCg_ezg0B8Uo'
HOST = 'urotelcllngtcctheelb.supabase.co'
SBRE = re.compile(r'https://' + re.escape(HOST) + r'/.*')
CORS = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*',
        'access-control-allow-methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS', 'access-control-expose-headers': '*'}


class Fake:
    def __init__(self):
        self.reset()

    def reset(self):
        self.users = {}       # email -> {id, pw, meta}
        self.by_id = {}       # id -> email
        self.profiles = {}    # id -> row
        self.activity = []    # {user_id, opp_id, kind}
        self.access = {}      # access token -> (uid, exp)
        self.refresh = {}     # valid refresh token -> uid
        self.log = []         # {m, path, q, auth, body}
        self.violations = []
        self.confirm = False  # "Confirm email" switched on
        self.rpc = False      # delete_my_account installed
        self.reauth = False   # "Secure password change" on and the login is older than a day
        self.pw_changes = []  # emails whose password was changed through PUT /auth/v1/user
        self.fail = None      # None | 'net' | '500' | '429'
        self.min_pw = 6
        self.ttl = 3600
        self.force401 = 0     # answer this many REST requests with 401 "JWT expired", once each
        self.sql = False      # supabase/admin.sql has been run: join_waitlist(), is_admin() and admin_overview() exist
        self.admins = set()   # ids of the accounts on the admins list
        self.waitlist = []    # {id, org, email, note, created_at}, oldest first
        self.wl_busy = False  # the database's flood guard is on
        self.ov_extra = {}    # replaces parts of the admin_overview() answer
        self.n = 0

    # ---- helpers the tests use to set things up ----
    def add_user(self, email, pw='secret1', meta=None):
        uid = str(uuid.uuid4())
        self.users[email] = {'id': uid, 'pw': pw, 'meta': meta or {'name': email.split('@')[0], 'role': 'Student', 'provider': False, 'org': ''}, 'created': time.time()}
        self.by_id[uid] = email
        m = self.users[email]['meta']
        self.profiles[uid] = {'id': uid, 'name': m.get('name') or email.split('@')[0], 'role': m.get('role', 'Student'),
                              'is_provider': bool(m.get('provider')), 'org': m.get('org') or None, 'quiz_answers': None}
        return uid

    def session(self, uid, ttl=None):
        self.n += 1
        at, rt = f'at-{self.n}', f'rt-{self.n}'
        exp = int(time.time()) + (self.ttl if ttl is None else ttl)
        self.access[at] = (uid, exp)
        self.refresh[rt] = uid
        em = self.by_id[uid]
        return {'access_token': at, 'token_type': 'bearer', 'expires_in': max(0, exp - int(time.time())), 'expires_at': exp,
                'refresh_token': rt, 'user': {'id': uid, 'email': em, 'user_metadata': self.users[em]['meta']}}

    def sb_seed(self, sess):
        return {'uid': sess['user']['id'], 'email': sess['user']['email'], 'access': sess['access_token'], 'refresh': sess['refresh_token'],
                'exp': sess['expires_at'], 'known': {'saved': [], 'doing': []}, 'dirty': False}

    def rows(self, uid, kind=None):
        return sorted(r['opp_id'] for r in self.activity if r['user_id'] == uid and (kind is None or r['kind'] == kind))

    def calls(self, method=None, contains=None):
        return [c for c in self.log if (method is None or c['m'] == method) and (contains is None or contains in c['path'] + ('?' + c['qs'] if c['qs'] else ''))]

    def make_admin(self, email):
        """supabase/admin.sql has been run and this account is on the admins list."""
        self.sql = True
        self.admins.add(self.users[email]['id'])

    def add_waitlist(self, org, email, note=None, minutes_ago=0):
        self.waitlist.append({'id': len(self.waitlist) + 1, 'org': org, 'email': email, 'note': note,
                              'created_at': (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()})

    def overview(self):
        """What admin_overview() answers, worked out from the pretend data (the real one is SQL, tested in test_sql.py)."""
        now = time.time()
        day = lambda t: datetime.fromtimestamp(t, timezone.utc).date()
        today = day(now)
        daily = []
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            daily.append({'day': d.isoformat(), 'n': sum(1 for u in self.users.values() if day(u.get('created', now)) == d)})
        saved = {}
        for a in self.activity:
            if a['kind'] == 'saved':
                saved[a['opp_id']] = saved.get(a['opp_id'], 0) + 1
        by = lambda key: sorted(({'name': k, 'n': n} for k, n in collections.Counter(
            (p['quiz_answers'] or {}).get(key) for p in self.profiles.values() if (p['quiz_answers'] or {}).get(key)).items()), key=lambda x: (-x['n'], x['name']))
        o = {'accounts': len(self.users), 'accounts_7d': sum(1 for u in self.users.values() if now - u.get('created', now) < 7 * 86400),
             'quiz_done': sum(1 for p in self.profiles.values() if p['quiz_answers']), 'providers': sum(1 for p in self.profiles.values() if p['is_provider']),
             'saved': sum(saved.values()), 'doing': sum(1 for a in self.activity if a['kind'] == 'doing'), 'waitlist': len(self.waitlist),
             'daily': daily, 'top_saved': [{'opp_id': k, 'n': n} for k, n in sorted(saved.items(), key=lambda x: (-x[1], x[0]))[:8]],
             'schools': by('school')[:6], 'grades': by('grade')[:9], 'waitlist_rows': list(reversed(self.waitlist))[:500]}
        o.update(self.ov_extra)
        return o

    # ---- the route handler ----
    def handler(self, route, request):
        u = urlsplit(request.url)
        path, qs = u.path, u.query
        q = {k: v[0] for k, v in parse_qs(qs, keep_blank_values=True).items()}
        h = request.headers
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS, body='')
        if self.fail == 'net':
            return route.abort('failed')
        body = None
        if request.post_data:
            try:
                body = json.loads(request.post_data)
            except Exception:
                body = request.post_data
        auth = h.get('authorization')
        self.log.append({'m': request.method, 'path': path, 'qs': qs, 'q': q, 'auth': auth, 'body': body, 'prefer': h.get('prefer')})
        if h.get('apikey') != KEY:
            self.violations.append(f'{request.method} {path}: apikey header missing or wrong')
        if auth and KEY in auth:
            self.violations.append(f'{request.method} {path}: publishable key sent as a Bearer token')

        def out(status=200, data=None):
            if data is None:
                return route.fulfill(status=status, headers=CORS, body='')
            return route.fulfill(status=status, headers={**CORS, 'content-type': 'application/json'}, body=json.dumps(data))

        if self.fail == '500':
            return out(500, {'message': 'boom'})
        if self.fail == '429':
            return out(429, {'code': 429, 'error_code': 'over_request_rate_limit', 'msg': 'Request rate limit reached'})

        # ---------------- auth ----------------
        if path == '/auth/v1/signup':
            if auth:
                self.violations.append('signup must not carry an Authorization header')
            email = (body.get('email') or '').lower()
            pw = body.get('password') or ''
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                return out(400, {'code': 400, 'error_code': 'validation_failed', 'msg': 'Unable to validate email address: invalid format'})
            if len(pw) < self.min_pw:
                return out(422, {'code': 422, 'error_code': 'weak_password', 'msg': f'Password should be at least {self.min_pw} characters.', 'weak_password': {'reasons': ['length']}})
            if email in self.users:
                return out(422, {'code': 422, 'error_code': 'user_already_exists', 'msg': 'User already registered'})
            uid = str(uuid.uuid4())
            self.users[email] = {'id': uid, 'pw': pw, 'meta': body.get('data') or {}}
            self.by_id[uid] = email
            if self.confirm:
                return out(200, {'id': uid, 'email': email, 'user_metadata': self.users[email]['meta']})
            return out(200, self.session(uid))
        if path == '/auth/v1/token':
            if auth:
                self.violations.append('token must not carry an Authorization header')
            if q.get('grant_type') == 'password':
                email = (body.get('email') or '').lower()
                u2 = self.users.get(email)
                if not u2 or u2['pw'] != body.get('password'):
                    return out(400, {'code': 400, 'error_code': 'invalid_credentials', 'msg': 'Invalid login credentials'})
                return out(200, self.session(u2['id']))
            if q.get('grant_type') == 'refresh_token':
                rt = body.get('refresh_token')
                uid = self.refresh.pop(rt, None)
                if not uid:
                    return out(400, {'code': 400, 'error_code': 'refresh_token_not_found', 'msg': 'Invalid Refresh Token: Refresh Token Not Found'})
                return out(200, self.session(uid))
            return out(400, {'code': 400, 'error_code': 'validation_failed', 'msg': 'unsupported grant type'})
        if path == '/auth/v1/user' and request.method == 'PUT':
            # the call supabase-js makes for updateUser({password}); a bearer token is required
            expired = {'code': 401, 'error_code': 'bad_jwt', 'msg': 'invalid JWT: unable to parse or verify signature, token has invalid claims: token is expired'}
            if self.force401 > 0:
                self.force401 -= 1
                return out(401, expired)
            if not auth:
                return out(401, {'code': 401, 'error_code': 'no_authorization', 'msg': 'This endpoint requires a Bearer token'})
            info = self.access.get(auth.replace('Bearer ', ''))
            if not info or info[1] < time.time():
                return out(401, expired)
            uid = info[0]
            em = self.by_id[uid]
            pw = body.get('password') if isinstance(body, dict) else None
            if self.reauth:
                return out(400, {'code': 400, 'error_code': 'reauthentication_needed', 'msg': 'Password update requires reauthentication'})
            if not isinstance(pw, str) or len(pw) < self.min_pw:
                return out(422, {'code': 422, 'error_code': 'weak_password', 'msg': f'Password should be at least {self.min_pw} characters.', 'weak_password': {'reasons': ['length']}})
            if pw == self.users[em]['pw']:
                return out(422, {'code': 422, 'error_code': 'same_password', 'msg': 'New password should be different from the old password.'})
            self.users[em]['pw'] = pw
            self.pw_changes.append(em)
            return out(200, {'id': uid, 'email': em, 'user_metadata': self.users[em]['meta'], 'updated_at': '2026-11-20T12:00:00Z'})
        if path == '/auth/v1/logout':
            tok = (auth or '').replace('Bearer ', '')
            info = self.access.pop(tok, None)
            if info:
                for rt in [r for r, u3 in self.refresh.items() if u3 == info[0]]:
                    self.refresh.pop(rt)
            return out(204)

        # ---------------- data (REST) ----------------
        if not path.startswith('/rest/v1/'):
            return out(404, {'message': 'not found'})

        def missing(sig):
            return out(404, {'code': 'PGRST202', 'details': f'Searched for the function public.{sig} in the schema cache, but no matches were found.',
                             'hint': None, 'message': f'Could not find the function public.{sig} in the schema cache'})

        # visitors can join the waitlist with the publishable key alone, signed in or not
        if path == '/rest/v1/rpc/join_waitlist' and request.method == 'POST':
            if auth:
                self.violations.append('join_waitlist must be sent with the publishable key only, no Authorization header')
            if not self.sql:
                return missing('join_waitlist(p_email, p_note, p_org)')
            b = body if isinstance(body, dict) else {}
            org, email, note = (b.get('p_org') or '').strip(), (b.get('p_email') or '').strip().lower(), (b.get('p_note') or '').strip() or None
            bad = lambda msg: out(400, {'code': 'P0001', 'details': None, 'hint': None, 'message': msg})
            if not 2 <= len(org) <= 120:
                return bad('Enter the name of your school or organization.')
            if len(email) > 254 or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                return bad('Enter a valid email address.')
            if note and len(note) > 500:
                return bad('That note is too long. Keep it under 500 characters.')
            if any(w['email'] == email for w in self.waitlist):
                return out(204)
            if self.wl_busy:
                return bad('The waitlist is busy right now. Please try again in a few minutes.')
            self.add_waitlist(org, email, note)
            return out(204)
        tok = (auth or '').replace('Bearer ', '') if auth else ''
        info = self.access.get(tok)
        if self.force401 > 0:
            self.force401 -= 1
            return out(401, {'code': 'PGRST303', 'details': None, 'hint': None, 'message': 'JWT expired'})
        if not info:
            return out(401, {'code': 'PGRST301', 'details': None, 'hint': None, 'message': 'JWT invalid'})
        uid, exp = info
        if exp < time.time():
            return out(401, {'code': 'PGRST303', 'details': None, 'hint': None, 'message': 'JWT expired'})
        what = path[len('/rest/v1/'):]
        m = request.method

        def rls(code='42501', table=''):
            return out(403, {'code': code, 'details': None, 'hint': None, 'message': f'new row violates row-level security policy for table "{table}"'})

        if what == 'profiles':
            if m == 'GET':
                want = (q.get('id') or '').replace('eq.', '')
                rows = [self.profiles[uid]] if (want == uid and uid in self.profiles) else []
                return out(200, rows)
            if m == 'POST':
                if not isinstance(body, dict) or body.get('id') != uid:
                    return rls(table='profiles')
                if not body.get('name'):
                    return out(400, {'code': '23502', 'message': 'null value in column "name" of relation "profiles" violates not-null constraint'})
                row = self.profiles.setdefault(uid, {'id': uid, 'role': 'Student', 'is_provider': False, 'org': None, 'quiz_answers': None})
                row.update(body)
                return out(201)
            if m == 'DELETE':
                if (q.get('id') or '').replace('eq.', '') == uid:
                    self.profiles.pop(uid, None)
                return out(204)
        if what == 'activity':
            if m == 'GET':
                return out(200, [{'opp_id': r['opp_id'], 'kind': r['kind']} for r in self.activity if r['user_id'] == uid])
            if m == 'POST':
                if not isinstance(body, list):
                    return out(400, {'code': 'PGRST102', 'message': 'expected an array'})
                for r in body:
                    if r.get('user_id') != uid:
                        return rls(table='activity')
                    if r.get('kind') not in ('saved', 'doing'):
                        return out(400, {'code': '23514', 'message': 'check constraint violated'})
                for r in body:
                    if not any(a['user_id'] == uid and a['opp_id'] == r['opp_id'] and a['kind'] == r['kind'] for a in self.activity):
                        self.activity.append({'user_id': uid, 'opp_id': r['opp_id'], 'kind': r['kind']})
                return out(201)
            if m == 'DELETE':
                kind = (q.get('kind') or '').replace('eq.', '') or None
                ids = None
                if q.get('opp_id', '').startswith('in.('):
                    ids = q['opp_id'][4:-1].split(',')
                who = (q.get('user_id') or '').replace('eq.', '')
                if who and who != uid:
                    return out(204)
                self.activity = [a for a in self.activity if not (a['user_id'] == uid and (kind is None or a['kind'] == kind) and (ids is None or a['opp_id'] in ids))]
                return out(204)
        if what == 'rpc/is_admin' and m == 'POST':
            if not self.sql:
                return missing('is_admin without parameters')
            return out(200, uid in self.admins)
        if what == 'rpc/admin_overview' and m == 'POST':
            if not self.sql:
                return missing('admin_overview without parameters')
            if uid not in self.admins:
                return out(403, {'code': '42501', 'details': None, 'hint': None, 'message': 'Admins only.'})
            return out(200, self.overview())
        if what == 'rpc/delete_my_account' and m == 'POST':
            if not self.rpc:
                return out(404, {'code': 'PGRST202', 'details': 'Searched for the function public.delete_my_account without parameters, but no matches were found in the schema cache.',
                                 'hint': None, 'message': 'Could not find the function public.delete_my_account without parameters in the schema cache'})
            em = self.by_id.pop(uid, None)
            self.users.pop(em, None)
            self.admins.discard(uid)
            self.profiles.pop(uid, None)
            self.activity = [a for a in self.activity if a['user_id'] != uid]
            for t in [t for t, (u4, _) in self.access.items() if u4 == uid]:
                self.access.pop(t)
            for r in [r for r, u4 in self.refresh.items() if u4 == uid]:
                self.refresh.pop(r)
            return out(204)
        return out(404, {'code': 'PGRST205', 'message': 'not found: ' + what})
