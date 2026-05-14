-- ═══════════════════════════════════════════════════════════════════
-- MKTPilot — Tabela de Jobs em Segundo Plano
-- ═══════════════════════════════════════════════════════════════════

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

-- Habilitar RLS
alter table background_jobs enable row level security;

-- Políticas de Segurança
create policy "Users can only see their own jobs" on background_jobs
  for select using (auth.uid() = user_id);

create policy "Users can only insert their own jobs" on background_jobs
  for insert with check (auth.uid() = user_id);
  
create policy "Users can only update their own jobs" on background_jobs
  for update using (auth.uid() = user_id);

-- Trigger para updated_at
create or replace function update_modified_column()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language 'plpgsql';

create trigger update_jobs_modtime before update on background_jobs for each row execute procedure update_modified_column();
