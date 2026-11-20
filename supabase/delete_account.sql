-- Bulletin: lets a signed-in person delete their own account (the "Delete my account" button in Settings).
-- In Supabase: SQL Editor > New query > paste this > Run. It is safe to run more than once.
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Not signed in';
  end if;
  -- This removes the login itself. The profile, saved items, posts, friends and messages
  -- are removed with it, because those tables point at auth.users with "on delete cascade".
  delete from auth.users where id = auth.uid();
end;
$$;

-- Only signed-in people may call it, and it can only ever delete the caller's own account.
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
