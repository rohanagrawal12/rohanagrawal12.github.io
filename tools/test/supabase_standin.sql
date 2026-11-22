-- A very small stand-in for the parts of Supabase that Bulletin's SQL files rely on.
-- tools/test/test_sql.py loads this into a throwaway Postgres, then runs supabase/*.sql as the "postgres" role.
-- It is NOT Supabase: it copies only the roles, the auth.users table, auth.uid() and the default permissions
-- (new tables and functions in "public" are open to the API roles until the SQL revokes them, as in a real project).
create role anon nologin noinherit;
create role authenticated nologin noinherit;
create role service_role nologin noinherit bypassrls;
create role postgres createrole createdb login bypassrls in role anon, authenticated, service_role;

create schema auth authorization postgres;
create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  created_at timestamptz not null default now(),
  raw_user_meta_data jsonb not null default '{}'::jsonb
);
alter table auth.users owner to postgres;
create function auth.uid() returns uuid language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim.sub', true), ''),
                  (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'))::uuid
$$;
alter function auth.uid() owner to postgres;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;

grant all on schema public to postgres, anon, authenticated, service_role;
alter default privileges for role postgres in schema public grant all on tables to postgres, anon, authenticated, service_role;
alter default privileges for role postgres in schema public grant all on functions to postgres, anon, authenticated, service_role;
alter default privileges for role postgres in schema public grant all on sequences to postgres, anon, authenticated, service_role;
