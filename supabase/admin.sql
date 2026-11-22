-- Bulletin: the school waitlist and the Admin page.
-- In Supabase: SQL Editor > New query > paste this > Run. It is safe to run more than once.
--
-- BEFORE YOU RUN IT: in section 3 (the last part), change your-email@example.com to the email of the
-- account that should be the admin. That account has to exist already, so sign up on the site first if you
-- have not. (The copy of this file on GitHub keeps a fake email on purpose, so no real address is public.)

-- 1. The waitlist -----------------------------------------------------------------------------
-- Visitors add themselves with join_waitlist(). Nobody can read or change this table through the
-- website. You read it on the Admin page, or in Table Editor > waitlist.
create table if not exists public.waitlist (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  org text not null check (char_length(org) between 2 and 120),
  email text not null check (char_length(email) <= 254 and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
  note text check (note is null or char_length(note) <= 500)
);
-- one row per email address, whatever the capital letters
create unique index if not exists waitlist_email_key on public.waitlist (lower(email));
alter table public.waitlist enable row level security;
revoke all on public.waitlist from anon, authenticated;

-- The only way in. It tidies the text and checks it. An email that is already on the list gets the normal
-- answer and nothing is written (so nobody can use this to find out who is on the list). New entries stop
-- at 30 a minute or 10,000 in total, so a script cannot fill the database. It returns nothing.
create or replace function public.join_waitlist(p_org text, p_email text, p_note text default null)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_org text := btrim(coalesce(p_org, ''));
  v_email text := lower(btrim(coalesce(p_email, '')));
  v_note text := nullif(btrim(coalesce(p_note, '')), '');
begin
  if char_length(v_org) < 2 or char_length(v_org) > 120 then
    raise exception 'Enter the name of your school or organization.';
  end if;
  if char_length(v_email) > 254 or v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    raise exception 'Enter a valid email address.';
  end if;
  if char_length(coalesce(v_note, '')) > 500 then
    raise exception 'That note is too long. Keep it under 500 characters.';
  end if;
  if exists (select 1 from public.waitlist where lower(email) = v_email) then
    return;
  end if;
  if (select count(*) from public.waitlist where created_at > now() - interval '1 minute') >= 30
     or (select count(*) from public.waitlist) >= 10000 then
    raise exception 'The waitlist is busy right now. Please try again in a few minutes.';
  end if;
  insert into public.waitlist (org, email, note) values (v_org, v_email, v_note)
  on conflict (lower(email)) do nothing;
end;
$$;
revoke all on function public.join_waitlist(text, text, text) from public, anon, authenticated;
grant execute on function public.join_waitlist(text, text, text) to anon, authenticated;

-- 2. Admins ------------------------------------------------------------------------------------
-- Who may open the Admin page. The website can never add to or read this list: only this SQL editor can.
create table if not exists public.admins (
  user_id uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now()
);
alter table public.admins enable row level security;
revoke all on public.admins from anon, authenticated;

-- true if the signed-in person is on the list. The site asks this to decide whether to show the Admin button.
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- Everything the Admin page shows, in one go. It checks for itself that the caller is an admin, and it
-- hands back counts, never anyone's quiz answers, saved items or email (except the waitlist emails).
-- Days are counted in Houston time.
create or replace function public.admin_overview()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_admin() then
    raise exception 'Admins only.' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'accounts',    (select count(*) from auth.users),
    'accounts_7d', (select count(*) from auth.users where created_at > now() - interval '7 days'),
    'quiz_done',   (select count(*) from public.profiles where quiz_answers is not null and quiz_answers <> '{}'::jsonb),
    'providers',   (select count(*) from public.profiles where is_provider),
    'saved',       (select count(*) from public.activity where kind = 'saved'),
    'doing',       (select count(*) from public.activity where kind = 'doing'),
    'waitlist',    (select count(*) from public.waitlist),
    'daily', (
      select coalesce(jsonb_agg(jsonb_build_object('day', to_char(d.day, 'YYYY-MM-DD'), 'n', coalesce(c.n, 0)) order by d.day), '[]'::jsonb)
      from generate_series((now() at time zone 'America/Chicago')::date - 13, (now() at time zone 'America/Chicago')::date, interval '1 day') as g(ts)
      cross join lateral (select g.ts::date as day) d
      left join (select (created_at at time zone 'America/Chicago')::date as day, count(*) as n from auth.users group by 1) c on c.day = d.day
    ),
    'top_saved', (
      select coalesce(jsonb_agg(jsonb_build_object('opp_id', t.opp_id, 'n', t.n) order by t.n desc, t.opp_id), '[]'::jsonb)
      from (select opp_id, count(*) as n from public.activity where kind = 'saved' group by opp_id order by count(*) desc, opp_id limit 8) t
    ),
    'schools', (
      select coalesce(jsonb_agg(jsonb_build_object('name', t.name, 'n', t.n) order by t.n desc, t.name), '[]'::jsonb)
      from (select quiz_answers ->> 'school' as name, count(*) as n from public.profiles
            where quiz_answers ->> 'school' is not null group by 1 order by count(*) desc, 1 limit 6) t
    ),
    'grades', (
      select coalesce(jsonb_agg(jsonb_build_object('name', t.name, 'n', t.n) order by t.n desc, t.name), '[]'::jsonb)
      from (select quiz_answers ->> 'grade' as name, count(*) as n from public.profiles
            where quiz_answers ->> 'grade' is not null group by 1 order by count(*) desc, 1 limit 9) t
    ),
    'waitlist_rows', (
      select coalesce(jsonb_agg(jsonb_build_object('id', w.id, 'org', w.org, 'email', w.email, 'note', w.note, 'created_at', w.created_at) order by w.created_at desc, w.id desc), '[]'::jsonb)
      from (select id, org, email, note, created_at from public.waitlist order by created_at desc, id desc limit 500) w
    )
  );
end;
$$;
revoke all on function public.admin_overview() from public, anon;
grant execute on function public.admin_overview() to authenticated;

-- Tells the Supabase API that the new functions exist (it normally notices by itself; this makes sure).
notify pgrst, 'reload schema';

-- 3. Make yourself the admin ------------------------------------------------------------------------
-- Change your-email@example.com below, then Run. If the result at the bottom is empty, that email has no
-- account yet: sign up on the site with it, then run this section again.
insert into public.admins (user_id)
select id from auth.users where lower(email) = lower('your-email@example.com')
on conflict do nothing;

-- The last result you see here should list the admin(s). Your email should be in it.
select u.email, a.added_at
from public.admins a
join auth.users u on u.id = a.user_id
order by a.added_at;
