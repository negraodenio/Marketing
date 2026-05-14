-- ═══════════════════════════════════════════════════════════════════
-- MKTPilot Pro — MASTER DATABASE SETUP
-- ═══════════════════════════════════════════════════════════════════
-- INSTRUÇÕES: 
-- 1. Acesse seu projeto no Supabase (app.supabase.com)
-- 2. Vá em "SQL Editor" no menu lateral esquerdo
-- 3. Clique em "+ New query"
-- 4. Cole TODO o código abaixo e clique em "Run"
-- ═══════════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- 1. CORE: CAMPANHAS E TOKENS
create table if not exists campaigns (
  id bigint primary key generated always as identity,
  user_id uuid references auth.users(id) on delete cascade,
  product text,
  goal text,
  result_text text,
  created_at timestamptz default now()
);

create table if not exists user_meta_tokens (
    id bigint primary key generated always as identity,
    user_id uuid references auth.users(id) on delete cascade unique,
    access_token text not null,
    ad_account_id text,
    page_id text,
    expires_at timestamptz,
    updated_at timestamptz default now()
);

create table if not exists user_tiktok_tokens (
    id bigint primary key generated always as identity,
    user_id uuid references auth.users(id) on delete cascade unique,
    access_token text not null,
    advertiser_id text,
    refresh_token text,
    expires_at timestamptz,
    updated_at timestamptz default now()
);

-- 2. JOBS EM SEGUNDO PLANO (Aura IA)
create table if not exists background_jobs (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  status       text not null default 'pending', -- pending, processing, completed, failed
  payload      jsonb,
  result       jsonb,
  error        text,
  progress     int default 0,
  current_step text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- 3. INTELIGÊNCIA E ANÁLISES
create table if not exists campaign_scores (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users(id) on delete cascade,
  copy_text       text not null,
  score           smallint not null check (score between 0 and 100),
  clareza         smallint,
  urgencia        smallint,
  emocional       smallint,
  ctr_estimado    smallint,
  especificidade  smallint,
  grade           text,
  tip             text,
  created_at      timestamptz default now()
);

create table if not exists campaign_analyses (
    id bigint primary key generated always as identity,
    campaign_id bigint references campaigns(id) on delete cascade,
    user_id uuid references auth.users(id) on delete cascade,
    platform text default 'meta',
    metrics_json jsonb,
    analysis_json jsonb,
    created_at timestamptz default now()
);

-- 4. CONTEÚDO E PLANEJAMENTO
create table if not exists content_calendars (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  nicho       text,
  objetivo    text,
  canais      text[],
  mes         text,
  dias        jsonb not null,
  created_at  timestamptz default now()
);

-- 5. AUTOMAÇÃO E MARKETPLACE
create table if not exists marketplace_templates (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  title       text not null,
  description text,
  category    text,
  payload     jsonb,
  status      text default 'pending', -- pending, approved
  created_at  timestamptz default now()
);

create table if not exists autopilot_configs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  is_active   boolean default true,
  settings    jsonb,
  created_at  timestamptz default now()
);

create table if not exists autopilot_logs (
  id          uuid primary key default gen_random_uuid(),
  config_id   uuid references autopilot_configs(id) on delete cascade,
  action      text,
  ai_reasoning text,
  created_at  timestamptz default now()
);

create table if not exists competitor_monitors (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  url         text not null,
  last_hash   text,
  status      text default 'watching',
  created_at  timestamptz default now()
);

-- 6. RLS (SEGURANÇA)
alter table campaigns enable row level security;
alter table user_meta_tokens enable row level security;
alter table user_tiktok_tokens enable row level security;
alter table background_jobs enable row level security;
alter table campaign_scores enable row level security;
alter table campaign_analyses enable row level security;
alter table content_calendars enable row level security;
alter table marketplace_templates enable row level security;
alter table autopilot_configs enable row level security;
alter table autopilot_logs enable row level security;
alter table competitor_monitors enable row level security;

-- Políticas Simplificadas
create policy "own_campaigns" on campaigns for all using (auth.uid() = user_id);
create policy "own_meta" on user_meta_tokens for all using (auth.uid() = user_id);
create policy "own_tiktok" on user_tiktok_tokens for all using (auth.uid() = user_id);
create policy "own_jobs" on background_jobs for all using (auth.uid() = user_id);
create policy "own_scores" on campaign_scores for all using (auth.uid() = user_id);
create policy "own_analyses" on campaign_analyses for all using (auth.uid() = user_id);
create policy "own_calendars" on content_calendars for all using (auth.uid() = user_id);
create policy "own_marketplace" on marketplace_templates for all using (auth.uid() = user_id);
create policy "own_configs" on autopilot_configs for all using (auth.uid() = user_id);
create policy "own_logs" on autopilot_logs for all using (exists (select 1 from autopilot_configs where id = autopilot_logs.config_id and user_id = auth.uid()));
create policy "own_monitors" on competitor_monitors for all using (auth.uid() = user_id);

-- Trigger para updated_at
create or replace function update_modified_column()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language 'plpgsql';

-- ═══════════════════════════════════════════════════════════════════
-- FIM DO SCRIPT
-- ═══════════════════════════════════════════════════════════════════
