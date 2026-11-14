-- Bulletin database. In Supabase: SQL Editor > New query > paste this > Run.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  role text not null default 'Student',
  is_provider boolean not null default false,
  org text,
  quiz_answers jsonb,
  created_at timestamptz not null default now()
);
create table if not exists public.activity (
  user_id uuid not null references auth.users(id) on delete cascade,
  opp_id text not null,
  kind text not null check (kind in ('saved','doing')),
  created_at timestamptz not null default now(),
  primary key (user_id, opp_id, kind)
);
create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  owner uuid not null references auth.users(id) on delete cascade,
  scope text not null check (scope in ('School','Community','Explore')),
  name text not null, type text, description text not null,
  meets text, location text, tags text[], link text,
  status text not null default 'Pending review',
  created_at timestamptz not null default now()
);
create table if not exists public.friendships (
  user_id uuid not null references auth.users(id) on delete cascade,
  friend_id uuid not null references auth.users(id) on delete cascade,
  primary key (user_id, friend_id)
);
create table if not exists public.messages (
  id bigint generated always as identity primary key,
  from_user uuid not null references auth.users(id) on delete cascade,
  to_user uuid references auth.users(id) on delete cascade,
  to_email text, subject text not null, body text not null, opp_id text,
  read boolean not null default false,
  created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
alter table public.activity enable row level security;
alter table public.posts enable row level security;
alter table public.friendships enable row level security;
alter table public.messages enable row level security;
create policy "profiles: own row" on public.profiles for all using (auth.uid() = id) with check (auth.uid() = id);
create policy "activity: own rows" on public.activity for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "posts: read approved or own" on public.posts for select using (status = 'Approved' or owner = auth.uid());
create policy "posts: insert own" on public.posts for insert with check (owner = auth.uid());
create policy "posts: update own" on public.posts for update using (owner = auth.uid());
create policy "posts: delete own" on public.posts for delete using (owner = auth.uid());
create policy "friends: own rows" on public.friendships for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "messages: read mine" on public.messages for select using (auth.uid() in (from_user, to_user));
create policy "messages: send as me" on public.messages for insert with check (from_user = auth.uid());
create policy "messages: mark mine read" on public.messages for update using (to_user = auth.uid());
