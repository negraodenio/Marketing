-- ========================================================
-- SCRIPT DE CONFIGURAÇÃO SUPABASE (COPIE E COLE NO SQL EDITOR)
-- ========================================================

-- 1. Tabela de Campanhas (Onde salvamos o que a IA gera)
CREATE TABLE IF NOT EXISTS campaigns (
  id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  user_id uuid REFERENCES auth.users(id),
  product text,
  goal text,
  result_text text,
  created_at timestamp with time zone DEFAULT now()
);

-- 2. Tabela de Tokens do Facebook/Meta (OAuth por usuário)
CREATE TABLE IF NOT EXISTS user_meta_tokens (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    access_token text NOT NULL,
    ad_account_id text,
    page_id text,
    expires_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now()
);

-- 3. Tabela de Tokens do TikTok (OAuth por usuário)
CREATE TABLE IF NOT EXISTS user_tiktok_tokens (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    access_token text NOT NULL,
    advertiser_id text,
    refresh_token text,
    expires_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now()
);

-- 4. Tabela de Análises de Performance (IA lendo Ads)
CREATE TABLE IF NOT EXISTS campaign_analyses (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    campaign_id bigint REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id uuid REFERENCES auth.users(id),
    platform text DEFAULT 'meta',
    metrics_json jsonb,
    analysis_json jsonb,
    created_at timestamp with time zone DEFAULT now()
);

-- 5. DESTRAVAR ACESSO (RLS ATIVADO PARA PRODUÇÃO)
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only see their own campaigns" ON campaigns FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can only insert their own campaigns" ON campaigns FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can only update their own campaigns" ON campaigns FOR UPDATE USING (auth.uid() = user_id);

ALTER TABLE user_meta_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only see their own meta tokens" ON user_meta_tokens FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can only upsert their own meta tokens" ON user_meta_tokens FOR ALL USING (auth.uid() = user_id);

ALTER TABLE user_tiktok_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only see their own tiktok tokens" ON user_tiktok_tokens FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can only upsert their own tiktok tokens" ON user_tiktok_tokens FOR ALL USING (auth.uid() = user_id);

ALTER TABLE campaign_analyses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only see their own analyses" ON campaign_analyses FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can only insert their own analyses" ON campaign_analyses FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 6. Função para controle de custos (Opcional - para futuro)
CREATE OR REPLACE FUNCTION increment_image_usage(p_user_id UUID, p_cost_usd FLOAT)
RETURNS VOID AS $$
BEGIN
    NULL;
END;
$$ LANGUAGE plpgsql;
