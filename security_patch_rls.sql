-- ═══════════════════════════════════════════════════════════════════
-- MKTPilot SECURITY PATCH — Row Level Security (RLS) Hardening
-- ═══════════════════════════════════════════════════════════════════
-- Instrução: Copie e cole este script no seu SQL Editor do Supabase.

-- 1. Tabelas Base (setup_supabase.sql)
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own campaigns" ON campaigns;
CREATE POLICY "Users can only see their own campaigns" ON campaigns FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own campaigns" ON campaigns;
CREATE POLICY "Users can only insert their own campaigns" ON campaigns FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only update their own campaigns" ON campaigns;
CREATE POLICY "Users can only update their own campaigns" ON campaigns FOR UPDATE USING (auth.uid() = user_id);

ALTER TABLE user_meta_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own meta tokens" ON user_meta_tokens;
CREATE POLICY "Users can only see their own meta tokens" ON user_meta_tokens FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only upsert their own meta tokens" ON user_meta_tokens;
CREATE POLICY "Users can only upsert their own meta tokens" ON user_meta_tokens FOR ALL USING (auth.uid() = user_id);

ALTER TABLE user_tiktok_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own tiktok tokens" ON user_tiktok_tokens;
CREATE POLICY "Users can only see their own tiktok tokens" ON user_tiktok_tokens FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only upsert their own tiktok tokens" ON user_tiktok_tokens;
CREATE POLICY "Users can only upsert their own tiktok tokens" ON user_tiktok_tokens FOR ALL USING (auth.uid() = user_id);

-- 2. Tabelas Premium (supabase_schema_premium.sql)
ALTER TABLE campaign_scores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own scores" ON campaign_scores;
CREATE POLICY "Users can only see their own scores" ON campaign_scores FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own scores" ON campaign_scores;
CREATE POLICY "Users can only insert their own scores" ON campaign_scores FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE funil_analyses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own funil analyses" ON funil_analyses;
CREATE POLICY "Users can only see their own funil analyses" ON funil_analyses FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own funil analyses" ON funil_analyses;
CREATE POLICY "Users can only insert their own funil analyses" ON funil_analyses FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE content_calendars ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own calendars" ON content_calendars;
CREATE POLICY "Users can only see their own calendars" ON content_calendars FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own calendars" ON content_calendars;
CREATE POLICY "Users can only insert their own calendars" ON content_calendars FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE ab_tests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own AB tests" ON ab_tests;
CREATE POLICY "Users can only see their own AB tests" ON ab_tests FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own AB tests" ON ab_tests;
CREATE POLICY "Users can only insert their own AB tests" ON ab_tests FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE viral_campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own viral campaigns" ON viral_campaigns;
CREATE POLICY "Users can only see their own viral campaigns" ON viral_campaigns FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own viral campaigns" ON viral_campaigns;
CREATE POLICY "Users can only insert their own viral campaigns" ON viral_campaigns FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 3. Tabelas Adicionais Detectadas
ALTER TABLE lead_hunter_results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own leads" ON lead_hunter_results;
CREATE POLICY "Users can only see their own leads" ON lead_hunter_results FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own leads" ON lead_hunter_results;
CREATE POLICY "Users can only insert their own leads" ON lead_hunter_results FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own configs" ON user_configs;
CREATE POLICY "Users can only see their own configs" ON user_configs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own configs" ON user_configs;
CREATE POLICY "Users can only insert their own configs" ON user_configs FOR ALL USING (auth.uid() = user_id);

ALTER TABLE competitor_monitors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own monitors" ON competitor_monitors;
CREATE POLICY "Users can only see their own monitors" ON competitor_monitors FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own monitors" ON competitor_monitors;
CREATE POLICY "Users can only insert their own monitors" ON competitor_monitors FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE autopilot_configs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can only see their own autopilot configs" ON autopilot_configs;
CREATE POLICY "Users can only see their own autopilot configs" ON autopilot_configs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can only insert their own autopilot configs" ON autopilot_configs;
CREATE POLICY "Users can only insert their own autopilot configs" ON autopilot_configs FOR ALL USING (auth.uid() = user_id);

-- 4. Tabelas de Template (Acesso Público para Leitura)
ALTER TABLE viral_hooks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public reading for viral hooks" ON viral_hooks;
CREATE POLICY "Public reading for viral hooks" ON viral_hooks FOR SELECT USING (true);

ALTER TABLE marketplace_templates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public reading for marketplace" ON marketplace_templates;
CREATE POLICY "Public reading for marketplace" ON marketplace_templates FOR SELECT USING (true);

ALTER TABLE weekly_challenges ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public reading for challenges" ON weekly_challenges;
CREATE POLICY "Public reading for challenges" ON weekly_challenges FOR SELECT USING (true);

-- ═══════════════════════════════════════════════════════════════════
-- ✅ PATCH DE SEGURANÇA APLICADO
-- ═══════════════════════════════════════════════════════════════════
