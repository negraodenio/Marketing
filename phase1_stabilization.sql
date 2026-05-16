-- Phase 1 stabilization migration (safe + idempotent)
-- Run in Supabase SQL Editor before enabling strict cost controls.

create table if not exists ai_usage_daily (
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_date date not null default current_date,
  ia_calls integer not null default 0,
  image_gens integer not null default 0,
  video_gens integer not null default 0,
  estimated_cost_usd numeric(12,4) not null default 0,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  primary key (user_id, usage_date)
);

alter table ai_usage_daily enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'ai_usage_daily'
      and policyname = 'own_ai_usage_daily'
  ) then
    create policy "own_ai_usage_daily"
      on ai_usage_daily
      for all
      using (auth.uid() = user_id)
      with check (auth.uid() = user_id);
  end if;
end $$;
