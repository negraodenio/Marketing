-- ═══════════════════════════════════════════════════════════════════
-- MKTPilot — Schema Supabase para os 6 Módulos Premium
-- ═══════════════════════════════════════════════════════════════════

create extension if not exists "pgcrypto";

-- 1. SCORES DE CAMPANHA
create table if not exists campaign_scores (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users(id) on delete cascade,
  copy_text       text        not null,
  score           smallint    not null check (score between 0 and 100),
  clareza         smallint,
  urgencia        smallint,
  emocional       smallint,
  ctr_estimado    smallint,
  especificidade  smallint,
  grade           text,
  tip             text,
  created_at      timestamptz default now()
);
create index if not exists idx_scores_user on campaign_scores(user_id, created_at desc);
alter table campaign_scores disable row level security; -- Desativado para MVP conforme padrão anterior

-- 2. ANÁLISES DE FUNIL
create table if not exists funil_analyses (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid references auth.users(id) on delete cascade,
  concorrente_url  text,
  meu_produto      text,
  resultado        jsonb,       -- { concorrente:{...}, superior:{...} }
  created_at       timestamptz default now()
);
alter table funil_analyses disable row level security;

-- 3. CALENDÁRIOS DE CONTEÚDO
create table if not exists content_calendars (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  nicho       text,
  objetivo    text,
  canais      text[],
  mes         text,            -- 'YYYY-MM'
  dias        jsonb not null,  -- array de dias gerados
  created_at  timestamptz default now()
);
alter table content_calendars disable row level security;

-- 4. HOOKS VIRAIS
create table if not exists viral_hooks (
  id           uuid primary key default gen_random_uuid(),
  nicho        text,
  angulo       text,    -- medo | ganho | curiosidade | prova_social
  texto        text    not null,
  plataforma   text,
  score        smallint,
  ctr_estimado numeric(4,1),
  calor        smallint check (calor between 1 and 5),
  semana       date,           -- segunda-feira da semana
  created_at   timestamptz default now()
);
create index if not exists idx_hooks_semana on viral_hooks(semana desc, nicho, angulo);

-- 5. A/B TESTS
create table if not exists ab_tests (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete cascade,
  copy_original text,
  produto       text,
  objetivo      text,
  variantes     jsonb not null,  -- [{ label, angulo, copy, ctr_estimado, notas }]
  meta_export   jsonb,           -- payload exportado para Meta Ads
  status        text default 'draft',  -- draft | exported | live | completed
  created_at    timestamptz default now()
);
alter table ab_tests disable row level security;

-- 6. CAMPANHAS VIRAIS
create table if not exists viral_campaigns (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users(id) on delete cascade,
  tendencia       jsonb,
  produto         text,
  nicho           text,
  headline        text,
  copy_principal  text,
  cta             text,
  roteiro_30s     text,
  hashtags        text[],
  melhor_horario  text,
  created_at      timestamptz default now()
);
alter table viral_campaigns disable row level security;
