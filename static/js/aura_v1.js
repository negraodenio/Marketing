console.log("🚀 MKTPilot: Script iniciado com sucesso.");
function initApp() {

    // ==========================================
    // ESTADO DA APLICAÇÃO E AUTH
    // ==========================================
    let authToken = localStorage.getItem('sb_token');
    let userEmail = localStorage.getItem('sb_user');
    let currentPlatform = "Multicanal"; // Default
    let currentNiche = "";
    let maxStepReached = 1;

    const authScreen = document.getElementById('authScreen');
    const appScreen = document.getElementById('appScreen');

    async function checkAuth() {
        console.log("DEBUG: Verificando Auth...", authToken ? "Logado" : "Deslogado");
        if (authToken) {
            try {
                const res = await fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${authToken}` } });
                if (res.ok) {
                    authScreen.classList.add('hidden');
                    appScreen.classList.remove('hidden');
                    const userDisp = document.getElementById('userEmailDisplay');
                    if (userDisp) userDisp.innerText = userEmail;
                    console.log("DEBUG: Dashboard exibido.");
                    resetWizard();
                    checkExistingJobs();
                    return;
                }
            } catch (e) {}
            localStorage.removeItem('sb_token');
            localStorage.removeItem('sb_user');
            authToken = null;
            userEmail = null;
        }
        authScreen.classList.remove('hidden');
        appScreen.classList.add('hidden');
        console.log("DEBUG: Tela de Login exibida.");
    }
    checkAuth();

    // Logout
    document.getElementById('btnLogout')?.addEventListener('click', () => {
        localStorage.removeItem('sb_token');
        localStorage.removeItem('sb_user');
        authToken = null;
        checkAuth();
    });

    // Conectar Meta Ads (sem expor JWT em query string)
    const btnConnectMeta = document.getElementById('btnConnectMeta');
    if (btnConnectMeta) {
        btnConnectMeta.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/oauth/meta/url', {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                if (!res.ok || !data.auth_url) throw new Error(data.erro || 'Falha ao iniciar OAuth Meta');
                window.open(data.auth_url, '_blank');
            } catch (e) {
                alert('Falha ao conectar Meta Ads. Faça login novamente e tente de novo.');
            }
        });
    }

    // Conectar TikTok Ads (sem expor JWT em query string)
    const btnConnectTikTok = document.getElementById('btnConnectTikTok');
    if (btnConnectTikTok) {
        btnConnectTikTok.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/oauth/tiktok/url', {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                if (!res.ok || !data.auth_url) throw new Error(data.erro || 'Falha ao iniciar OAuth TikTok');
                window.open(data.auth_url, '_blank');
            } catch (e) {
                alert('Falha ao conectar TikTok Ads. Faça login novamente e tente de novo.');
            }
        });
    }

    // Connection cache shared across all components
    window._connCache = { meta: null, tiktok: null };
    async function checkConnections() {
        if (!authToken) return;
        try {
            const metaRes = await fetch('/api/meta/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const metaData = await metaRes.json();
            window._connCache.meta = metaData;
        } catch(e) { window._connCache.meta = { connected: false, error: true }; }
        try {
            const ttRes = await fetch('/api/tiktok/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const ttData = await ttRes.json();
            window._connCache.tiktok = ttData;
        } catch(e) { window._connCache.tiktok = { connected: false, error: true }; }
        // Update Config tab UI
        const metaStatusText = document.getElementById('metaStatusText');
        if (metaStatusText) {
            if (window._connCache.meta && window._connCache.meta.connected) {
                const name = window._connCache.meta.account_name || window._connCache.meta.ad_account_id || '';
                metaStatusText.innerHTML = '✅ Conectado' + (name ? ' como <strong>' + escapeHTML(name) + '</strong>' : '');
            } else if (window._connCache.meta && window._connCache.meta.unconfigured) {
                metaStatusText.innerHTML = '⚙️ Não configurado no servidor';
            } else {
                metaStatusText.innerHTML = '⚪ Desconectado';
            }
        }
        const tiktokStatusText = document.getElementById('tiktokStatusText');
        if (tiktokStatusText) {
            if (window._connCache.tiktok && window._connCache.tiktok.connected) {
                const name = window._connCache.tiktok.account_name || window._connCache.tiktok.advertiser_id || '';
                tiktokStatusText.innerHTML = '✅ Conectado' + (name ? ' como <strong>' + escapeHTML(name) + '</strong>' : '');
            } else if (window._connCache.tiktok && window._connCache.tiktok.unconfigured) {
                tiktokStatusText.innerHTML = '⚙️ Não configurado no servidor';
            } else {
                tiktokStatusText.innerHTML = '⚪ Desconectado';
            }
        }
    }
    if (authToken) checkConnections();


// ==========================================
// LOGIN E REGISTRO (GLOBAL PARA EVITAR TRAVAMENTOS)
// ==========================================
(document.defaultView || window).handleAuth = async function(endpoint) {
    console.log(`DEBUG: Iniciando ${endpoint}...`);
    const emailEl = document.getElementById('emailInput');
    const passEl = document.getElementById('passInput');
    const authError = document.getElementById('authError');
    
    if (!emailEl || !passEl) {
        console.error("DEBUG: Campos de login não encontrados no DOM!");
        return;
    }

    const email = emailEl.value.trim();
    const pass = passEl.value.trim();
    
    if (!email || !pass) {
        if (!authError) return;
        authError.innerText = "Preencha e-mail e senha.";
        authError.classList.remove('hidden');
        return;
    }

    try {
        const appWindow = document.defaultView || window;
        const fetchFn = appWindow.fetch || window.fetch;
        const res = await fetchFn(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: pass })
        });
        const data = await res.json();
        
        if (res.ok) {
            authToken = data.token;
            userEmail = data.user;
            const storage = (document.defaultView || window).localStorage || localStorage;
            storage.setItem('sb_token', authToken);
            storage.setItem('sb_user', userEmail);
            if (authError) authError.classList.add('hidden');
            checkAuth();
            checkConnections();
        } else {
            if (!authError) return;
            authError.innerText = data.erro || "Erro de autenticação";
            authError.classList.remove('hidden');
        }
    } catch (e) {
        console.error("DEBUG: Erro CRÍTICO no fetch", e);
        authError.innerText = "Erro de conexão. Verifique sua internet.";
        authError.classList.remove('hidden');
    }
}

// Vinculação de eventos robusta
document.addEventListener('click', (e) => {
    if (!e.target || !e.target.closest) return;
    const loginBtn = e.target.closest('#btnLogin');
    const registerBtn = e.target.closest('#btnRegister');
    if (loginBtn) window.handleAuth('/api/auth/login');
    if (registerBtn) window.handleAuth('/api/auth/register');
});

    const passInput = document.getElementById('passInput');
    if (passInput) {
        passInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') window.handleAuth('/api/auth/login');
        });
    }

    // ==========================================
    // SISTEMA DE ABAS CONSOLIDADO
    // ==========================================
    window.switchTab = function(tabId) {
        console.log("DEBUG: Alternando para aba", tabId);
        document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
        
        const baseId = tabId.replace('tab-', '');
        document.querySelectorAll(`[data-tab="${baseId}"]`).forEach(el => el.classList.add('active'));
        
        const target = document.getElementById(tabId.startsWith('tab-') ? tabId : `tab-${tabId}`);
        if (target) { 
            target.classList.remove('hidden'); 
            target.classList.add('fade-in'); 
        }

        const titleMap = { 'wizard': 'Dashboard', 'history': 'Campanhas', 'evabrain': 'Eva Oracle', 'leads': 'Lead Hunter', 'config': 'Branding' };
        const titleEl = document.getElementById('currentTabTitle');
        if (titleEl) titleEl.innerText = titleMap[baseId] || baseId;

        if (baseId === 'wizard') resetWizard();
        if (baseId === 'history') carregarHistorico();
        if (baseId === 'config') carregarBrandKit();
        if (baseId === 'automations') carregarAutomacoes();
    };

    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => { 
            e.preventDefault();
            const tab = link.dataset.tab; 
            if (tab) switchTab(`tab-${tab}`); 
        });
    });


    // ==========================================
    // BRAND KIT (DNA da Empresa)
    // ==========================================
    async function carregarBrandKit() {
        const tomEl = document.getElementById('configTomDeVoz');
        const pubEl = document.getElementById('configPublicoAlvo');
        const persEl = document.getElementById('configPersonality');
        const visEl = document.getElementById('configVisualStyle');
        const fontEl = document.getElementById('configFonts');
        const forbidEl = document.getElementById('configForbiddenWords');
        const c1 = document.getElementById('configColor1');
        const c2 = document.getElementById('configColor2');
        const c3 = document.getElementById('configColor3');
        const c4 = document.getElementById('configColor4');
        // Try loading from Supabase first
        let settings = {};
        if (authToken) {
            try {
                const res = await fetch('/api/brand/config', {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                if (data.settings) settings = data.settings;
            } catch(e) {}
        }
        // Merge with localStorage fallback
        const merge = (key, el) => {
            if (!el) return;
            el.value = settings[key] || localStorage.getItem('brandkit_' + key) || '';
        };
        merge('tom_de_voz', tomEl);
        merge('publico', pubEl);
        merge('personality', persEl);
        merge('visual_style', visEl);
        merge('fonts', fontEl);
        merge('forbidden_words', forbidEl);
        if (c1 && settings.colors) {
            if (settings.colors[0]) c1.value = settings.colors[0];
            if (settings.colors[1]) c2.value = settings.colors[1];
            if (settings.colors[2]) c3.value = settings.colors[2];
            if (settings.colors[3]) c4.value = settings.colors[3];
        }
    }

    const btnSaveConfig = document.getElementById('btnSaveConfig');
    if (btnSaveConfig) {
        btnSaveConfig.addEventListener('click', async () => {
            const tom = document.getElementById('configTomDeVoz').value.trim();
            const publico = document.getElementById('configPublicoAlvo').value.trim();
            const personality = document.getElementById('configPersonality')?.value.trim() || '';
            const visual_style = document.getElementById('configVisualStyle')?.value.trim() || '';
            const fonts = document.getElementById('configFonts')?.value.trim() || '';
            const forbidden_words = document.getElementById('configForbiddenWords')?.value.trim() || '';
            const c1 = document.getElementById('configColor1')?.value || '#8b5cf6';
            const c2 = document.getElementById('configColor2')?.value || '#10b981';
            const c3 = document.getElementById('configColor3')?.value || '#f59e0b';
            const c4 = document.getElementById('configColor4')?.value || '#ffffff';
            const settings = {
                tom_de_voz: tom,
                publico: publico,
                personality: personality,
                visual_style: visual_style,
                fonts: fonts,
                forbidden_words: forbidden_words,
                colors: [c1, c2, c3, c4]
            };
            // Save to localStorage as fallback
            localStorage.setItem('brandkit_tom', tom);
            localStorage.setItem('brandkit_publico', publico);
            localStorage.setItem('brandkit_personality', personality);
            localStorage.setItem('brandkit_visual_style', visual_style);
            localStorage.setItem('brandkit_fonts', fonts);
            localStorage.setItem('brandkit_forbidden_words', forbidden_words);
            // Save to Supabase
            if (authToken) {
                try {
                    await fetch('/api/brand/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                        body: JSON.stringify({ settings })
                    });
                } catch(e) { console.warn('Brand save to server failed, localStorage used as fallback'); }
            }
            const msg = document.getElementById('configSaveMsg');
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 2000);
        });
    }

    const btnResetBrand = document.getElementById('btnResetBrand');
    if (btnResetBrand) {
        btnResetBrand.addEventListener('click', async () => {
            if (!confirm('Limpar todas as configurações da marca?')) return;
            ['tom_de_voz','publico','personality','visual_style','fonts','forbidden_words'].forEach(k => localStorage.removeItem('brandkit_' + k));
            ['configTomDeVoz','configPublicoAlvo','configPersonality','configVisualStyle','configFonts','configForbiddenWords'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            if (authToken) {
                try { await fetch('/api/brand/config', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` }, body: JSON.stringify({ settings: {} }) }); } catch(e) {}
            }
            const msg = document.getElementById('configSaveMsg');
            msg.textContent = '🗑️ Brand Kit limpo!';
            msg.classList.remove('hidden');
            setTimeout(() => { msg.classList.add('hidden'); msg.textContent = '✅ Identidade da Marca Atualizada!'; }, 2000);
        });
    }

    // ==========================================
    // AUTOMAÇÕES & WORKFLOWS
    // ==========================================
    function carregarAutomacoes() {
        if (!document.getElementById('autoWebhookUrl')) return;
        document.getElementById('autoWebhookUrl').value = localStorage.getItem('auto_webhook_url') || '';
        document.getElementById('autoWebhookEnabled').checked = localStorage.getItem('auto_webhook_enabled') === 'true';
        
        document.getElementById('autoAirtableKey').value = localStorage.getItem('auto_airtable_key') || '';
        document.getElementById('autoAirtableBase').value = localStorage.getItem('auto_airtable_base') || '';
        document.getElementById('autoAirtableEnabled').checked = localStorage.getItem('auto_airtable_enabled') === 'true';
        
        document.getElementById('autoDriveEnabled').checked = localStorage.getItem('auto_drive_enabled') === 'true';
    }

    const btnSaveAutomations = document.getElementById('btnSaveAutomations');
    if (btnSaveAutomations) {
        btnSaveAutomations.addEventListener('click', () => {
            localStorage.setItem('auto_webhook_url', document.getElementById('autoWebhookUrl').value.trim());
            localStorage.setItem('auto_webhook_enabled', document.getElementById('autoWebhookEnabled').checked);
            
            localStorage.setItem('auto_airtable_key', document.getElementById('autoAirtableKey').value.trim());
            localStorage.setItem('auto_airtable_base', document.getElementById('autoAirtableBase').value.trim());
            localStorage.setItem('auto_airtable_enabled', document.getElementById('autoAirtableEnabled').checked);
            
            localStorage.setItem('auto_drive_enabled', document.getElementById('autoDriveEnabled').checked);
            
            const msg = document.getElementById('autoSaveMsg');
            msg.style.display = 'block';
            setTimeout(() => msg.style.display = 'none', 2000);
        });
    }

    async function dispararAutomacao(campaignData) {
        const webhookEnabled = localStorage.getItem('auto_webhook_enabled') === 'true';
        const webhookUrl = localStorage.getItem('auto_webhook_url');

        if (webhookEnabled && webhookUrl) {
            console.log("🚀 Disparando Webhook de Automação...");
            try {
                fetch(webhookUrl, {
                    method: 'POST',
                    mode: 'no-cors',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        event: 'campaign_generated',
                        timestamp: new Date().toISOString(),
                        user: localStorage.getItem('sb_user'),
                        data: campaignData
                    })
                }).catch(e => console.warn("Webhook disparado (sem resposta CORS)"));
            } catch (e) {
                console.error("❌ Falha ao disparar webhook:", e);
            }
        }
    }

    // ==========================================
    // SEO & AI SEARCH AUDIT LOGIC
    // ==========================================
    window.runSeoAudit = async function(campaignData) {
        const seoPanel = document.getElementById('seoReviewPanel');
        if (!seoPanel) return;

        let mainText = "";
        if (campaignData.facebook_ad) {
            mainText = campaignData.facebook_ad.primary_text_a || campaignData.facebook_ad.primary_text || "";
        } else if (campaignData.instagram_posts && campaignData.instagram_posts.length > 0) {
            mainText = campaignData.instagram_posts[0].caption;
        }

        if (!mainText) return;

        seoPanel.classList.remove('hidden');
        document.getElementById('seoIssuesList').innerHTML = '<p class="loading-mini">Analisando visibilidade AI...</p>';

        try {
            const audit = await MKTPilot.SEO.analyze(mainText, window.currentKeywords || []);
            renderSeoAudit(audit);
        } catch (e) {
            console.error("SEO Audit failed", e);
        }
    }

    function renderSeoAudit(audit) {
        if (!audit || audit.error) return;

        const scoreBar = document.getElementById('seoScoreBar');
        const scoreVal = document.getElementById('seoScoreVal');
        const aiBar = document.getElementById('aiVisibilityBar');
        const aiVal = document.getElementById('aiVisibilityVal');

        if (scoreBar) {
            scoreBar.style.width = `${audit.score}%`;
            scoreVal.innerText = `${audit.score}%`;
        }
        if (aiBar) {
            aiBar.style.width = `${audit.ai_visibility_score}%`;
            aiVal.innerText = `${audit.ai_visibility_score}%`;
        }

        const issuesList = document.getElementById('seoIssuesList');
        issuesList.innerHTML = audit.issues.map(issue => `
            <div class="seo-issue ${issue.type}">
                <strong>${issue.type === 'critical' ? '🔴' : '⚠️'} ${issue.message}</strong>
                <p style="font-size: 0.75rem; margin-top: 5px; opacity: 0.8;">💡 Fix: ${issue.fix}</p>
            </div>
        `).join('');

        window.lastAuditIssues = audit.issues;
        window.lastAuditText = audit.copy;
    }

    window.toggleSeoPanel = function() {
        document.getElementById('seoReviewPanel').classList.toggle('hidden');
    }

    const btnFixSeo = document.getElementById('btnFixSeo');
    if (btnFixSeo) {
        btnFixSeo.addEventListener('click', async () => {
            btnFixSeo.innerText = "⏳ Otimizando Content...";
            btnFixSeo.disabled = true;

            const currentText = document.querySelector('.field-primary-text')?.value || "";
            
            try {
                const data = await MKTPilot.SEO.fix(currentText, window.lastAuditIssues);
                if (data.fixed_copy) {
                    const textarea = document.querySelector('.field-primary-text');
                    if (textarea) {
                        textarea.value = data.fixed_copy;
                        updateAdScore(data.fixed_copy);
                    }
                    alert("✅ SEO Otimizado com Sucesso para AI Search!");
                    toggleSeoPanel();
                }
            } catch (e) {
                alert("Erro ao aplicar correções.");
            }
            btnFixSeo.innerText = "🚀 Corrigir tudo em 1 clique";
            btnFixSeo.disabled = false;
        });
    }

    // Manual SEO Audit Tab
    const btnRunAudit = document.getElementById('btnRunAudit');
    if (btnRunAudit) {
        btnRunAudit.addEventListener('click', async () => {
            const text = document.getElementById('seoAuditInput').value;
            if (!text) return;

            btnRunAudit.innerText = "⏳ Analisando...";
            const audit = await MKTPilot.SEO.analyze(text, []);
            alert(`Audit concluído! Score: ${audit.score}%`);
            btnRunAudit.innerText = "🚀 Iniciar Auditoria AI Search";
        });
    }

    window.updateWizardProgress = function(step) {
        if (step > maxStepReached) maxStepReached = step;
        for (let i = 1; i <= 4; i++) {
            const el = document.getElementById(`pstep-${i}`);
            if (!el) continue;
            el.classList.toggle('active', i === step);
            el.classList.toggle('completed', i < step);
        }
    }

    window.goToStep = function(step) {
        if (step > 4) return;
        for (let i = 1; i <= 4; i++) {
            document.getElementById(`wiz-step-${i}`)?.classList.add('hidden');
        }
        document.getElementById(`wiz-step-${step}`)?.classList.remove('hidden');
        document.getElementById('loadingCopilot')?.classList.add('hidden');
        document.getElementById('resultadoCopilot')?.classList.add('hidden');
        updateWizardProgress(step);
    }

    function resetWizard() {
        currentPlatform = "Multicanal";
        currentNiche = "";
        maxStepReached = 1;
        for (let i = 1; i <= 4; i++) {
            document.getElementById(`wiz-step-${i}`)?.classList.add('hidden');
        }
        document.getElementById('wiz-step-1')?.classList.remove('hidden');
        document.getElementById('loadingCopilot')?.classList.add('hidden');
        document.getElementById('resultadoCopilot')?.classList.add('hidden');
        const resultado = document.getElementById('resultadoCopilot');
        if (resultado) resultado.innerHTML = '';
        updateWizardProgress(1);
    }

    function resetWizard() {
        currentPlatform = "Multicanal";
        currentNiche = "";
        maxStepReached = 1;
        for (let i = 1; i <= 5; i++) {
            document.getElementById(`wiz-step-${i}`)?.classList.add('hidden');
        }
        document.getElementById('wiz-step-1')?.classList.remove('hidden');
        document.getElementById('loadingCopilot')?.classList.add('hidden');
        document.getElementById('resultadoCopilot')?.classList.add('hidden');
        const resultado = document.getElementById('resultadoCopilot');
        if (resultado) resultado.innerHTML = '';
        const produto = document.getElementById('wizProduto');
        if (produto) produto.value = "";
        const gerarBtn = document.getElementById('btnGerarMagica');
        if (gerarBtn) gerarBtn.disabled = false;
        updateWizardProgress(1);
    }

    window.selectPlatform = function(platform) {
        currentPlatform = platform;
        goToStep(2);
    }

    window.selectNiche = function(niche) {
        currentNiche = niche;
        goToStep(3);
    }

    window.generateMarketIntelligence = async function() {
        const produto = document.getElementById('wizProduto')?.value || '';
        if (!produto) { alert('Descreva o seu produto primeiro!'); return; }
        goToStep(4); // Na estrutura Pro, Step 4 é Objetivo/Geração
    }

    function renderMarketIntelligence(data) {
        const marketArea = document.getElementById('marketDataArea');
        if (!data || data.error) {
            marketArea.innerHTML = '<p>Erro na análise de mercado.</p>';
            return;
        }
        let html = `
            <div class="market-card">
                <h4>🎯 Palavras-Chave</h4>
                <div class="keyword-tags">
                    ${data.keywords.map(k => `<span class="keyword-tag" title="Vol: ${k.volume} | Dif: ${k.difficulty}">${escapeHTML(k.term)}</span>`).join('')}
                </div>
            </div>
            <div class="market-card">
                <h4>📡 Concorrentes</h4>
                <ul style="font-size: 0.8rem; padding-left: 15px;">
                    ${data.competitors.map(c => `<li>${escapeHTML(c.name)} (Força: ${c.strength})</li>`).join('')}
                </ul>
            </div>
            <div class="market-card">
                <h4>🔥 Tendências</h4>
                <p style="font-size: 0.8rem;">${escapeHTML(data.market_trends[0] || 'Nenhuma detectada')}</p>
            </div>
        `;
        marketArea.innerHTML = html;
        const kwArea = document.getElementById('selectedKeywords');
        kwArea.innerHTML = data.keywords.slice(0, 5).map(k => `<span class="keyword-tag">${escapeHTML(k.term)}</span>`).join('');
        window.currentKeywords = data.keywords.slice(0, 5).map(k => k.term);
    }

    let activeJobs = {};

    function updateJobsUI() {
        const activeArea = document.getElementById('activeJobsArea');
        const activeList = document.getElementById('activeJobsList');
        const badge = document.getElementById('jobBadge');
        
        if (!activeArea || !activeList || !badge) return;

        const runningJobs = Object.values(activeJobs).filter(j => j.status === 'processing' || j.status === 'pending');
        
        if (runningJobs.length > 0) {
            activeArea.classList.remove('hidden');
            badge.classList.remove('hidden');
            badge.innerText = `${runningJobs.length} Tarefa Ativa`;
            
            activeList.innerHTML = runningJobs.map(job => `
                <div class="pro-card fade-in" style="margin-bottom:12px; border-left: 4px solid var(--accent-primary);">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="font-size:0.7rem; font-weight:700; color:var(--accent-primary);">AI ORCHESTRATION</span>
                        <span style="font-size:0.75rem;">${job.progress || 0}%</span>
                    </div>
                    <div style="font-size: 0.85rem; font-weight: 500;">${escapeHTML(job.current_step || 'Processando...')}</div>
                </div>
            `).join('');
        } else {
            activeArea.classList.add('hidden');
            badge.classList.add('hidden');
        }
    }

    async function checkExistingJobs() {
        if (!authToken) return;
        try {
            const res = await fetch('/api/copilot/jobs/active', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (res.status === 401) {
                console.warn("checkExistingJobs: 401 recebido — nao derrubando sessao, auth ainda pode ser valido");
                return;
            }
            const data = await res.json();
            if (data.jobs && data.jobs.length > 0) {
                data.jobs.forEach(job => {
                    if (!activeJobs[job.id]) {
                        pollJobStatus(job.id, true); 
                    }
                });
            }
        } catch (e) { console.error("Erro ao checar jobs ativos:", e); }
    }

    let _sseEventSource = null;
    let _sseActive = false;

    // Clean up SSE on page unload
    window.addEventListener('beforeunload', function _sseCleanup() {
        if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; _sseActive = false; }
    });

    function connectSSE(jobId, silent = false) {
        if (!window.EventSource) return; // browser doesn't support SSE
        if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; }
        
        try {
            const es = new EventSource(`/api/copilot/stream/${jobId}`, {
                withCredentials: true
            });
            
            es.addEventListener('connected', () => {
                _sseActive = true;
                console.log(`SSE connected for job ${jobId}`);
            });
            
            es.addEventListener('progress', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    const currentJob = activeJobs[jobId] || {};
                    currentJob.status = data.status || 'processing';
                    currentJob.progress = data.progress || 0;
                    currentJob.current_step = data.current_step || 'Processando...';
                    activeJobs[jobId] = currentJob;
                    updateJobsUI();
                    
                    const loadingCopilot = document.getElementById('loadingCopilot');
                    if (!silent && loadingCopilot && !loadingCopilot.classList.contains('hidden')) {
                        loadingCopilot.innerHTML = renderOrchestrationTimeline(data.progress || 0, data.current_step || 'Iniciando...');
                    }
                } catch (err) {
                    console.warn('SSE progress parse error', err);
                }
            });
            
            es.addEventListener('completed', (e) => {
                _sseActive = false;
                if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; }
                try {
                    const data = JSON.parse(e.data);
                    delete activeJobs[jobId];
                    updateJobsUI();
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    
                    const loadingCopilot = document.getElementById('loadingCopilot');
                    const resultadoCopilot = document.getElementById('resultadoCopilot');
                    const btnGerarMagica = document.getElementById('btnGerarMagica');
                    
                    if (!silent && loadingCopilot && resultadoCopilot) {
                        loadingCopilot.classList.add('hidden');
                        resultadoCopilot.classList.remove('hidden');
                        const result = data.result || {};
                        if (result.data) {
                            resultadoCopilot.innerHTML = renderJsonCards(result.data, result.campaign_id);
                            if (typeof dispararAutomacao === 'function') dispararAutomacao(result.data);
                            const initialText = result.data.facebook_ad?.primary_text_a || result.data.facebook_ad?.primary_text || "";
                            if (initialText) setTimeout(() => updateAdScore(initialText), 500);
                            setTimeout(() => { if (typeof runSeoAudit === 'function') runSeoAudit(result.data); }, 1000);
                        }
                        if (btnGerarMagica) btnGerarMagica.disabled = false;
                    } else {
                        console.log(`SSE: Job ${jobId} completed in background`);
                        if (document.getElementById('tab-history')?.classList.contains('active')) carregarHistorico();
                    }
                } catch (err) {
                    console.warn('SSE completed parse error', err);
                }
            });
            
            es.addEventListener('failed', (e) => {
                _sseActive = false;
                if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; }
                try {
                    const data = JSON.parse(e.data);
                    delete activeJobs[jobId];
                    updateJobsUI();
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    
                    const loadingCopilot = document.getElementById('loadingCopilot');
                    const btnGerarMagica = document.getElementById('btnGerarMagica');
                    
                    if (!silent) {
                        alert("Falha na Geracao: " + (data.error || "Erro desconhecido."));
                        if (loadingCopilot) loadingCopilot.classList.add('hidden');
                        document.getElementById('wiz-step-5')?.classList.remove('hidden');
                        if (btnGerarMagica) btnGerarMagica.disabled = false;
                    }
                } catch (err) {
                    console.warn('SSE failed parse error', err);
                }
            });
            
            es.onerror = () => {
                _sseActive = false;
                if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; }
                console.warn(`SSE disconnected for job ${jobId}, falling back to polling`);
            };
            
            _sseEventSource = es;
        } catch (err) {
            console.warn('SSE init error, using polling only', err);
            _sseActive = false;
        }
    }

    async function pollJobStatus(jobId, silent = false) {
        const loadingCopilot = document.getElementById('loadingCopilot');
        const resultadoCopilot = document.getElementById('resultadoCopilot');
        const btnGerarMagica = document.getElementById('btnGerarMagica');
        let failCount = 0;
        
        // Start SSE alongside polling
        connectSSE(jobId, silent);
        
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/copilot/status/${jobId}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (res.status === 401) {
                    console.warn("pollJobStatus: 401 para job " + jobId + " — parando polling, mantendo sessao");
                    clearInterval(pollInterval);
                    if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; _sseActive = false; }
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    delete activeJobs[jobId];
                    updateJobsUI();
                    return;
                }
                if (!res.ok) throw new Error("Servidor indisponível");
                
                const job = await res.json();
                failCount = 0; 

                // Atualiza estado global
                activeJobs[jobId] = job;
                updateJobsUI();
                
                if (job.status === 'processing' || job.status === 'pending') {
                    if (!silent && loadingCopilot && !loadingCopilot.classList.contains('hidden')) {
                        loadingCopilot.innerHTML = renderOrchestrationTimeline(job.progress || 0, job.current_step || 'Iniciando...');
                    }
                } else if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; _sseActive = false; }
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    delete activeJobs[jobId];
                    updateJobsUI();

                    if (!silent) {
                        loadingCopilot.classList.add('hidden');
                        resultadoCopilot.classList.remove('hidden');
                        const result = job.result;
                        if (result && result.data) {
                            resultadoCopilot.innerHTML = renderJsonCards(result.data, result.campaign_id);
                            if (typeof dispararAutomacao === 'function') dispararAutomacao(result.data);
                            
                            // Trigger Ad Oracle for the default variation (A)
                            const initialText = result.data.facebook_ad?.primary_text_a || result.data.facebook_ad?.primary_text || "";
                            if (initialText) setTimeout(() => updateAdScore(initialText), 500);
                            
                            setTimeout(() => { if (typeof runSeoAudit === 'function') runSeoAudit(result.data); }, 1000);
                        }
                        if (btnGerarMagica) btnGerarMagica.disabled = false;
                    } else {
                        // Se era silent (resume), notifica o usuário discretamente ou atualiza o histórico se estiver aberto
                        console.log(`✅ Job ${jobId} finalizado em background.`);
                        if (document.getElementById('tab-history').classList.contains('active')) carregarHistorico();
                    }
                } else if (job.status === 'failed') {
                    clearInterval(pollInterval);
                    if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; _sseActive = false; }
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    delete activeJobs[jobId];
                    updateJobsUI();
                    if (!silent) {
                        alert("⚠️ Falha na Geração: " + (job.error || "Erro desconhecido."));
                        loadingCopilot.classList.add('hidden');
                        document.getElementById('wiz-step-5')?.classList.remove('hidden');
                        if (btnGerarMagica) btnGerarMagica.disabled = false;
                    }
                }
            } catch (e) {
                failCount++;
                if (failCount > 5) {
                    clearInterval(pollInterval);
                    if (_sseEventSource) { _sseEventSource.close(); _sseEventSource = null; _sseActive = false; }
                    if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
                    delete activeJobs[jobId];
                    updateJobsUI();
                    if (!silent) {
                        alert("⚠️ Conexão perdida com o servidor.");
                        loadingCopilot.classList.add('hidden');
                        if (btnGerarMagica) btnGerarMagica.disabled = false;
                    }
                }
            }
        }, 2500);
    }

    const btnGerarMagica = document.getElementById('btnGerarMagica');
    const resultadoCopilot = document.getElementById('resultadoCopilot');
    const loadingCopilot = document.getElementById('loadingCopilot');

    if (btnGerarMagica && resultadoCopilot && loadingCopilot) {
        btnGerarMagica.addEventListener('click', async () => {
            const produto = document.getElementById('wizProduto')?.value || '';
            const selectedRadio = document.querySelector('input[name="objetivo"]:checked');
            const objetivo = selectedRadio ? selectedRadio.value : 'Aumentar seguidores';
            if (!produto) { alert('Preencha o produto!'); return; }
            const concorrenteUrl = document.getElementById('wizConcorrente')?.value || '';
            const tomDeVoz = localStorage.getItem('brandkit_tom') || 'Profissional';
            const publicoAlvo = localStorage.getItem('brandkit_publico') || 'Geral';
            const keywords = window.currentKeywords || [];

            document.getElementById('wiz-step-5')?.classList.add('hidden');
            loadingCopilot.classList.remove('hidden');
            loadingCopilot.innerHTML = `
                <div class="glass-panel fade-in" style="padding:40px; text-align:center; max-width:500px; margin:0 auto;">
                    <div class="spinner" style="width:50px; height:50px; margin-bottom:20px;"></div>
                    <h3 style="color:var(--accent);">Iniciando Aura IA...</h3>
                    <p style="font-size:0.85rem; opacity:0.7;">Preparando ambiente de processamento...</p>
                </div>
            `;
            resultadoCopilot.innerHTML = '';
            btnGerarMagica.disabled = true;
            try {
                const res = await fetch('/api/copilot/gerar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ 
                        plataforma: currentPlatform, nicho: currentNiche, produto, objetivo, keywords, concorrenteUrl, tomDeVoz, publicoAlvo
                    })
                });
                const data = await res.json();
                if (res.status === 401) {
                    console.warn("gerar campanha: 401 — verifique token ou reinicie o login");
                    alert("Sessão expirada. Faça login novamente.");
                    localStorage.removeItem('sb_token');
                    localStorage.removeItem('sb_user');
                    authToken = null;
                    checkAuth();
                    return;
                }
                if (data.job_id) {
                    pollJobStatus(data.job_id);
                } else {
                    throw new Error(data.erro || "Falha ao iniciar tarefa.");
                }
            } catch (e) { 
                alert("Erro: " + e.message);
                loadingCopilot.classList.add('hidden');
                document.getElementById('wiz-step-5')?.classList.remove('hidden');
                btnGerarMagica.disabled = false;
            }
        });
    }

    async function carregarHistorico() {
        const historyList = document.getElementById('historyList');
        historyList.innerHTML = '<p style="text-align:center;padding:40px;opacity:0.5;">Carregando campanhas...</p>';
        try {
            const res = await fetch('/api/campanhas/historico', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const data = await res.json();
            if (!data.campanhas || data.campanhas.length === 0) {
                historyList.innerHTML = '<p style="text-align:center;padding:60px;opacity:0.4;">Nenhuma campanha gerada ainda.</p>';
                return;
            }
            historyList.innerHTML = '';
            data.campanhas.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).forEach(c => {
                const dataHora = c.created_at ? new Date(c.created_at).toLocaleString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                const safeProduct = escapeHTML((c.product || 'Sem nome').slice(0, 60));
                const safeGoal = escapeHTML((c.goal || '-').slice(0, 30));
                let engineBadge = '';
                try {
                    const resultJson = typeof c.result_text === 'string' ? JSON.parse(c.result_text) : c.result_text;
                    const meta = resultJson && resultJson._engine_meta;
                    if (meta && meta.engine === 'pipeline_v2') {
                        engineBadge = '<span style="background:#10b981;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;">V2</span>';
                    } else if (meta) {
                        engineBadge = '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;">Legado</span>';
                    }
                } catch(e) {}
                historyList.innerHTML += `
                    <div class="history-row" style="display:flex;align-items:center;gap:16px;padding:16px 20px;border:1px solid var(--border-dim);border-radius:12px;margin-bottom:8px;transition:0.15s;cursor:pointer;background:var(--bg-card);"
                         onmouseover="this.style.borderColor='var(--accent-primary)'" onmouseout="this.style.borderColor='var(--border-dim)'"
                         onclick="window.viewCampaign('${c.id}')">
                        <div style="min-width:110px;font-size:0.75rem;opacity:0.5;">${dataHora}</div>
                        <div style="flex:1;min-width:0;">
                            <div style="font-weight:600;font-size:0.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${safeProduct}</div>
                            <div style="font-size:0.75rem;opacity:0.5;">${safeGoal}</div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            ${engineBadge}
                            <button class="btn-ninja btn-secondary" style="padding:6px 12px;font-size:0.7rem;" onclick="event.stopPropagation();window.viewCampaign('${c.id}')">📄 Ver</button>
                            <button class="btn-ninja btn-secondary" style="padding:6px 12px;font-size:0.7rem;" onclick="event.stopPropagation();window.generateAgencyProposal('${c.id}')">📋 Proposta</button>
                        </div>
                    </div>`;
            });
        } catch(e) {
            historyList.innerHTML = '<p style="text-align:center;padding:40px;color:#ef4444;">Erro ao carregar campanhas.</p>';
        }
    }

    window.viewCampaign = function(campaignId) {
        const modal = document.getElementById('campaignModal');
        const modalContent = document.getElementById('campaignModalContent');
        if (!modal || !modalContent) return;
        modalContent.innerHTML = '<p style="text-align:center;padding:40px;">Carregando...</p>';
        modal.classList.remove('hidden');
        fetch(`/api/campanhas/historico`, { headers: { 'Authorization': `Bearer ${authToken}` } })
            .then(r => r.json())
            .then(data => {
                const camp = (data.campanhas || []).find(c => c.id === campaignId);
                if (!camp) { modalContent.innerHTML = '<p>Campanha não encontrada.</p>'; return; }
                const resultData = typeof camp.result_text === 'string' ? JSON.parse(camp.result_text) : camp.result_text;
                modalContent.innerHTML = renderJsonCards(resultData || {}, campaignId);
            })
            .catch(() => { modalContent.innerHTML = '<p>Erro ao carregar.</p>'; });
    };

    document.getElementById('btnLoadHistory')?.addEventListener('click', carregarHistorico);

    // ==========================================
    // EVA BRAIN (MiniMax Contexto Massivo)
    // ==========================================
    const btnOtimizar = document.getElementById('btnOtimizar');
    const resultadoEva = document.getElementById('resultadoEva');
    const loadingEva = document.getElementById('loadingEva');
    const btnAnaliseAuto = document.getElementById('btnAnaliseAuto');
    const btnAnaliseManual = document.getElementById('btnAnaliseManual');
    const manualInputArea = document.getElementById('manualInputArea');
    let evaMode = 'manual';

    if (btnAnaliseAuto) {
        btnAnaliseAuto.addEventListener('click', () => {
            evaMode = 'auto';
            btnAnaliseAuto.classList.add('active');
            btnAnaliseManual.classList.remove('active');
            manualInputArea.classList.add('hidden');
        });
    }
    if (btnAnaliseManual) {
        btnAnaliseManual.addEventListener('click', () => {
            evaMode = 'manual';
            btnAnaliseManual.classList.add('active');
            btnAnaliseAuto.classList.remove('active');
            manualInputArea.classList.remove('hidden');
        });
    }

    if (btnOtimizar && resultadoEva && loadingEva) {
        btnOtimizar.addEventListener('click', async () => {
            const relatorio = document.getElementById('relatorioInput')?.value || '';
            if (evaMode === 'manual' && !relatorio) { alert('Cole os dados de campanha no campo de texto!'); return; }
            loadingEva.classList.remove('hidden');
            resultadoEva.classList.add('hidden');
            btnOtimizar.disabled = true;
            try {
                const payload = evaMode === 'auto' ? { auto: true } : { relatorio: relatorio };
                const response = await fetch('/api/campanhas/otimizar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                loadingEva.classList.add('hidden');
                resultadoEva.classList.remove('hidden');
                resultadoEva.innerHTML = data.resultado ? converterMarkdown(data.resultado) : (data.erro || "Erro ao analisar.");
            } catch (e) {
                loadingEva.classList.add('hidden');
                resultadoEva.classList.remove('hidden');
                resultadoEva.innerText = "Erro de conexão.";
            }
            btnOtimizar.disabled = false;
        });
    }

    // ==========================================
    // SECURITY HELPERS & RENDERING
    // ==========================================
    function escapeHTML(str) {
        if (!str) return "";
        return String(str).replace(/[&<>"']/g, function(m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
        });
    }

    function converterMarkdown(text) {
        if (typeof text !== 'string') return "";
        let safe = escapeHTML(text);
        let lines = safe.split('\n');
        let html = '', inList = false;
        for (let line of lines) {
            let match;
            if (match = line.match(/^### (.*)/)) { html += '<h3>' + match[1] + '</h3>'; inList = false; }
            else if (match = line.match(/^## (.*)/)) { html += '<h2>' + match[1] + '</h2>'; inList = false; }
            else if (match = line.match(/^# (.*)/)) { html += '<h1>' + match[1] + '</h1>'; inList = false; }
            else if (match = line.match(/^- (.*)/)) {
                if (!inList) { html += '<ul>'; inList = 'ul'; }
                html += '<li>' + match[1] + '</li>';
            }
            else if (match = line.match(/^\d+\.\s(.*)/)) {
                if (!inList) { html += '<ul>'; inList = 'ul'; }
                html += '<li>' + match[1] + '</li>';
            }
            else {
                if (inList) { html += '</ul>'; inList = false; }
                html += line + '\n';
            }
        }
        if (inList) html += '</ul>';
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    function parseSafeJson(text) {
        try {
            if (typeof text === 'object') return text;
            return JSON.parse(text);
        } catch(e) { return text; }
    }

    function renderEngineBadge(campaignData) {
        const meta = campaignData && campaignData._engine_meta;
        if (!meta) return '';
        const isV2 = meta.engine === 'pipeline_v2';
        const bg = isV2 ? '#10b981' : '#ef4444';
        const label = isV2
            ? `V2 · ${meta.stages_completed || 0} stages · $${(meta.total_estimated_cost_usd || 0).toFixed(4)}`
            : `LEGADO · ${meta.fallback_reason ? escapeHTML(String(meta.fallback_reason).slice(0, 40)) : 'fallback'}`;
        const modelsLine = (meta.models_used && meta.models_used.length)
            ? `<div style="font-size:0.7rem; margin-top:6px; opacity:0.75;">${meta.models_used.map(m => escapeHTML(m)).join(' · ')}</div>`
            : '';
        return `<div style="margin-bottom:16px;">
            <span style="background:${bg};color:white;padding:6px 12px;border-radius:6px;font-size:0.75rem;font-weight:600;">${escapeHTML(label)}</span>
            ${modelsLine}
        </div>`;
    }

    let _orchMessages = [];
    let _orchMsgIdx = 0;
    let _orchRotator = null;

    function renderOrchestrationTimeline(progress, currentStep) {
        const currentPct = progress || 0;

        const agents = [
            {
                pct: 15, name: 'Market Intelligence AI', icon: '📡', shortName: 'Scanner',
                task: 'Pattern analysis, emotional trends, competitive saturation mapping',
                thoughts: [
                    'Detectando saturação de ângulos emocionais no nicho...',
                    'ICP responde melhor a tensão psicológica aspiracional',
                    'Padrão de fatigue identificado: 3 ângulos dominantes no mercado',
                    'Audiência responde a linguagem de identidade, não de funcionalidade',
                    'Cross-referencing emotional gaps: objeção principal isolada',
                ],
                collab: '→ Enviando padrões emocionais para Behavior Analyst'
            },
            {
                pct: 25, name: 'Behavior Analyst', icon: '🧬', shortName: 'Psychologist',
                task: 'Psychological depth mapping, hidden fears, buying drivers',
                thoughts: [
                    'Medo dominante detectado: perda de identidade sem o produto',
                    'Midnight self-talk revela desejo de transformação silenciosa',
                    'Cultural references ancoradas em nostalgia emocional',
                    'Gatilho de compra não-dito: validação social aspiracional',
                    'Fator de confiança extraído: transparência radical sobre o processo',
                ],
                collab: '← Recebendo padrões de Market Intelligence · → Enviando drivers para Creative Director'
            },
            {
                pct: 35, name: 'Creative Director AI', icon: '💎', shortName: 'Strategist',
                task: 'Big Idea, positioning, creative differentiation, narrative architecture',
                thoughts: [
                    'Big Idea refinada: tensão emocional como motor narrativo central',
                    'Ângulo criativo validado: diferenciação contra saturação do mercado',
                    'Mecanismo único integrado à promessa mensurável',
                    'Posicionamento emocional: distância máxima de concorrentes',
                    'Arquitetura narrativa coerente entre todos os touchpoints',
                ],
                collab: '← Recebendo drivers psicológicos de Behavior Analyst · → Aprovando direção criativa para Copy Engine'
            },
            {
                pct: 45, name: 'Hook & Copy Engine', icon: '⚡', shortName: 'Copywriter',
                task: 'Scroll-stopping hooks, emotional headlines, conversion CTAs',
                thoughts: [
                    'Hook aprovado com score de pattern interrupt: 92/100',
                    'Headline emocional otimizada: tensão + curiosidade + identidade',
                    'CTA refinado: ação natural sem desespero — momentum psicológico',
                    'Framework diversity validado: callout, contradiction, story tease, pattern interrupt',
                    'Reescrevendo hooks para reduzir resistência psicológica de compra',
                ],
                collab: '← Recebendo Big Idea de Creative Director · → Entregando hooks validados para Campaign Architect'
            },
            {
                pct: 55, name: 'Campaign Architect', icon: '🏗️', shortName: 'Architect',
                task: 'Campaign structure, A/B/C variations, narrative coherence validation',
                thoughts: [
                    'Coerência narrativa validada entre Meta Ads, Instagram e TikTok',
                    'Variações A/B/C balanceadas para amplitude psicológica máxima',
                    'Mecanismo único integrado em todas as camadas da campanha',
                    'Estratégia criativa sincronizada com payload da campanha',
                    'Consistência de tom: posicionamento + narrativa alinhados',
                ],
                collab: '← Recebendo hooks de Copy Engine · → Preparando assets para Visual AI Studio'
            },
            {
                pct: 75, name: 'Visual AI Studio', icon: '🎨', shortName: 'Visual Designer',
                task: 'Image rendering, visual identity, feed aesthetic',
                thoughts: [
                    'Identidade visual composta: paleta emocional alinhada ao driver psicológico',
                    'Instagram feed estética validada para coerência de marca',
                    'Sinergia imagem-texto verificada: hooks visuais sincronizados com copy',
                    'Consistência visual entre todos os assets da campanha',
                ],
                collab: '← Recebendo brief de Campaign Architect · → Enviando visuais para Video Director'
            },
            {
                pct: 92, name: 'Video AI Director', icon: '🎬', shortName: 'Director',
                task: 'Storyboard, neural narration, cinematic rendering',
                thoughts: [
                    'Storyboard aprovado: 4 cenas com continuidade comercial',
                    'Narração neural sincronizada com pacing emocional do roteiro',
                    'Sound design casado com arco emocional: tensão → liberação',
                    'Pacing de cena otimizado: curiosidade → desejo → confiança',
                    'Renderizando comercial cinematográfico vertical',
                ],
                collab: '← Recebendo visuais de AI Studio · → Finalizando campanha com Orchestrator'
            },
            {
                pct: 100, name: 'Orchestrator', icon: '🧠', shortName: 'Orchestrator',
                task: 'Final assembly, quality control, delivery',
                thoughts: [
                    'Assemblando campanha multi-agente para entrega final',
                    'Coerência estratégica validada entre todos os outputs',
                    'Assets sincronizados e otimizados para deployment',
                    'Campanha completa — pronta para veiculação',
                ],
                collab: '✓ 8 agentes completos — campanha pronta para deploy'
            },
        ];

        const activeAgent = agents.find(a => currentPct < a.pct) || agents[agents.length - 1];
        const activeThoughts = activeAgent ? activeAgent.thoughts : ['Inicializando sistema de orquestração...'];
        const feedMessages = activeThoughts.slice(0);
        if (activeAgent && activeAgent.collab) feedMessages.push(activeAgent.collab);

        if (activeAgent && activeAgent !== agents[agents.length - 1] && currentPct < 100) {
            if (JSON.stringify(_orchMessages) !== JSON.stringify(feedMessages)) {
                _orchMessages = feedMessages;
                _orchMsgIdx = 0;
                if (_orchRotator) clearInterval(_orchRotator);
                _orchRotator = setInterval(() => {
                    _orchMsgIdx = (_orchMsgIdx + 1) % _orchMessages.length;
                    const el = document.getElementById('orch-thought');
                    if (el) el.textContent = _orchMessages[_orchMsgIdx];
                }, 3000);
            }
        } else if (currentPct >= 100) {
            if (_orchRotator) { clearInterval(_orchRotator); _orchRotator = null; }
            setTimeout(() => {
                const el = document.getElementById('orch-thought');
                if (el) el.textContent = '✓ 8 agentes sincronizados — campanha concluída';
            }, 500);
        } else {
            if (!_orchMessages.length) _orchMessages = feedMessages;
        }

        // Intelligence scores — derived from real progress
        const scores = [
            ['Narrative Coherence', Math.min(99, Math.round(currentPct * 0.78 + 15)), '#8b5cf6'],
            ['Emotional Precision', Math.min(99, Math.round(currentPct * 0.82 + 10)), '#ec4899'],
            ['Conversion Tension', Math.min(99, Math.round(currentPct * 0.72 + 12)), '#10b981'],
            ['Creative Differentiation', Math.min(99, Math.round(currentPct * 0.85 + 8)), '#f59e0b'],
            ['Psychological Depth', Math.min(99, Math.round(currentPct * 0.8 + 13)), '#6366f1'],
        ];

        let html = `<div class="fade-in" style="max-width:640px;margin:-20px auto 0;">`;

        // Neural Command Header
        const doneCount = agents.filter(a => currentPct >= a.pct).length;
        html += `<div style="text-align:center;margin-bottom:18px;">
            <div style="display:inline-block;padding:14px 24px;border-radius:14px;">
                <div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.15em;opacity:0.3;margin-bottom:2px;">AI Marketing Operations</div>
                <div style="font-size:1.2rem;font-weight:700;background:linear-gradient(135deg,var(--accent-primary),#8b5cf6,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-family:'Outfit',sans-serif;">${doneCount} of 8 Agents Synchronized</div>
                <div style="font-size:0.7rem;opacity:0.3;margin-top:4px;">${agents.filter(a => currentPct >= a.pct).map(a => a.shortName).join(' · ')}</div>
            </div>
        </div>`;

        // Intelligence grid
        html += `<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:16px;">
            ${scores.map(([label, val, color]) => `
                <div style="background:rgba(255,255,255,0.015);border:1px solid var(--border-dim);border-radius:6px;padding:10px 4px;text-align:center;">
                    <div style="font-size:1rem;font-weight:800;color:${color};">${val}<span style="font-size:0.5rem;">%</span></div>
                    <div style="font-size:0.45rem;opacity:0.3;text-transform:uppercase;letter-spacing:0.04em;margin-top:3px;">${label}</div>
                </div>
            `).join('')}
        </div>`;

        // Progress arc
        html += `<div style="width:100%;margin:0 auto 14px;background:rgba(255,255,255,0.02);height:3px;border-radius:2px;overflow:hidden;">
            <div style="width:${currentPct}%;height:100%;background:linear-gradient(90deg,var(--accent-primary),#8b5cf6,#ec4899,#10b981);border-radius:2px;transition:width 0.8s ease;"></div>
        </div>`;

        // Agent timeline
        agents.forEach((a) => {
            const isDone = currentPct >= a.pct;
            const isActive = !isDone && (currentPct >= a.pct - 12);
            const bg = isDone ? 'rgba(16,185,129,0.04)' : (isActive ? 'rgba(99,102,241,0.06)' : 'rgba(255,255,255,0.01)');
            const border = isDone ? 'rgba(16,185,129,0.12)' : (isActive ? 'rgba(99,102,241,0.18)' : 'var(--border-dim)');
            const opacity = isDone || isActive ? 1 : 0.2;

            html += `<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;margin-bottom:3px;background:${bg};border:1px solid ${border};border-radius:8px;opacity:${opacity};transition:all 0.4s ease;${isActive ? 'box-shadow:0 0 16px rgba(99,102,241,0.04);' : ''}">
                <span style="font-size:0.8rem;min-width:20px;text-align:center;">${a.icon}</span>
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="font-weight:600;font-size:0.72rem;${isActive ? 'color:var(--accent-primary);' : ''}">${a.name}</span>
                        <span style="font-size:0.5rem;opacity:0.2;text-transform:uppercase;">${a.shortName}</span>
                    </div>
                    <div style="font-size:0.6rem;opacity:0.3;margin-top:1px;">${a.task}</div>
                </div>
                ${isDone ? '<span style="font-size:0.45rem;background:#10b981;color:#fff;padding:1px 5px;border-radius:3px;font-weight:700;">DONE</span>' : (isActive ? '<span style="width:12px;height:12px;border:2px solid var(--accent-primary);border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;"></span>' : '')}
            </div>`;
        });

        // Live thought — cinematic, rotating AI insight
        html += `<div style="margin-top:14px;padding:12px 16px;background:linear-gradient(135deg,rgba(99,102,241,0.04),rgba(139,92,246,0.02));border:1px solid rgba(99,102,241,0.1);border-radius:10px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="width:5px;height:5px;background:#10b981;border-radius:50%;animation:pulse 1.5s ease infinite;"></span>
                <span style="font-size:0.5rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.25;">Neural Activity · ${activeAgent ? activeAgent.name : 'System'}</span>
            </div>
            <div id="orch-thought" style="font-size:0.75rem;opacity:0.55;font-weight:500;font-style:italic;min-height:18px;transition:opacity 0.3s;">
                ${_orchMessages[_orchMsgIdx] || 'Initializing neural agents...'}
            </div>
            ${activeAgent && activeAgent.collab ? `<div style="margin-top:6px;font-size:0.6rem;opacity:0.25;border-top:1px solid rgba(255,255,255,0.03);padding-top:6px;">${activeAgent.collab}</div>` : ''}
        </div>`;

        html += `</div>`;
        return html;
    }

    function renderStrategicPlan(campaignData) {
        const s = (campaignData && campaignData.strategy_insights) || {};
        if (!s.market_analysis && !s.creative_strategy) return ''; // sem dados V2, pula

        const m = s.market_analysis || {};
        const cs = s.creative_strategy || {};
        const icp = s.icp_mapping || {};
        const refBig = s.refined_big_idea || cs.big_idea || '';
        const psych = s.psychological_angle || '';
        const emotional = s.emotional_driver || '';
        const stratInsight = s.strategic_insight || '';

        const awarenessLabels = { 'unaware': 'Inconsciente', 'problem-aware': 'Ciente do Problema', 'solution-aware': 'Ciente da Solução', 'product-aware': 'Ciente do Produto', 'most-aware': 'Totalmente Ciente' };

        return `
        <div class="json-card" style="border-color:var(--accent-primary);border-left:3px solid var(--accent-primary);">
            <h3 style="display:flex;align-items:center;gap:10px;">
                <span style="background:var(--accent-primary);color:#fff;padding:2px 10px;border-radius:4px;font-size:0.65rem;font-weight:800;">AI STRATEGIST</span>
                Strategic Campaign Plan
            </h3>

            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:16px;margin-top:20px;">

                <!-- BIG IDEA -->
                ${refBig ? `
                <div style="grid-column:1/-1;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:20px;">
                    <div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.5;margin-bottom:8px;">Big Idea</div>
                    <div style="font-size:1.1rem;font-weight:700;line-height:1.4;color:#fff;">${escapeHTML(refBig)}</div>
                </div>` : ''}

                <!-- POSITIONING -->
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:6px;">Market Sophistication</div>
                    <div style="font-weight:700;font-size:1.4rem;color:var(--accent-primary);">${m.sofistication_stage || '?'}/5</div>
                    <div style="font-size:0.75rem;opacity:0.6;margin-top:4px;">${escapeHTML((m.sofistication_rationale || '').slice(0, 120))}</div>
                </div>

                <!-- AUDIENCE AWARENESS -->
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:6px;">Awareness Level</div>
                    <div style="font-weight:700;font-size:0.95rem;color:#10b981;">${escapeHTML(awarenessLabels[m.awareness_stage] || m.awareness_stage || '-')}</div>
                    <div style="font-size:0.75rem;opacity:0.6;margin-top:4px;">${escapeHTML((m.awareness_rationale || '').slice(0, 100))}</div>
                </div>

                <!-- CREATIVE STRATEGY -->
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:6px;">Creative Angle</div>
                    <div style="font-weight:600;font-size:0.85rem;line-height:1.3;">${escapeHTML((cs.chosen_angle || '').slice(0, 140))}</div>
                    ${cs.unique_mechanism_name ? `<div style="margin-top:8px;font-size:0.65rem;opacity:0.4;">Mechanism: ${escapeHTML(cs.unique_mechanism_name)}</div>` : ''}
                </div>

                <!-- PROMISE -->
                ${cs.measurable_promise ? `
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:6px;">Measurable Promise</div>
                    <div style="font-weight:600;font-size:0.85rem;color:#f59e0b;">${escapeHTML(cs.measurable_promise)}</div>
                </div>` : ''}

                <!-- PSYCHOLOGY -->
                ${psych || emotional ? `
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:6px;">Psychology</div>
                    ${emotional ? `<div style="font-size:0.8rem;margin-bottom:4px;"><span style="opacity:0.5;">Driver:</span> ${escapeHTML(emotional)}</div>` : ''}
                    ${psych ? `<div style="font-size:0.8rem;"><span style="opacity:0.5;">Angle:</span> ${escapeHTML(psych)}</div>` : ''}
                </div>` : ''}

                <!-- ICP Snapshots -->
                ${icp.icp_obvious ? `
                <div style="grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                    <div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.15);border-radius:10px;padding:16px;">
                        <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.5;margin-bottom:4px;color:#10b981;">Primary ICP</div>
                        <div style="font-weight:600;font-size:0.85rem;">${escapeHTML((icp.icp_obvious.archetype || '').slice(0, 100))}</div>
                        <div style="font-size:0.7rem;opacity:0.5;margin-top:6px;font-style:italic;">"${escapeHTML((icp.icp_obvious.midnight_self_talk || '').slice(0, 120))}"</div>
                    </div>
                    ${icp.icp_non_obvious ? `
                    <div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.15);border-radius:10px;padding:16px;">
                        <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.5;margin-bottom:4px;color:#f59e0b;">Non-Obvious ICP</div>
                        <div style="font-weight:600;font-size:0.85rem;">${escapeHTML((icp.icp_non_obvious.archetype || '').slice(0, 100))}</div>
                        <div style="font-size:0.7rem;opacity:0.5;margin-top:6px;font-style:italic;">"${escapeHTML((icp.icp_non_obvious.midnight_self_talk || '').slice(0, 120))}"</div>
                    </div>` : ''}
                </div>` : ''}

                <!-- AUDIENCE VOCABULARY -->
                ${m.audience_vocabulary && m.audience_vocabulary.length ? `
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:8px;">Audience Language</div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px;">${m.audience_vocabulary.map(w => `<span style="background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:4px;font-size:0.7rem;">${escapeHTML(w)}</span>`).join('')}</div>
                </div>` : ''}

                <!-- OBJECTIONS -->
                ${m.objections && m.objections.length ? `
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:8px;">Objections</div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px;">${m.objections.map(o => `<span style="background:rgba(239,68,68,0.1);color:#ef4444;padding:2px 8px;border-radius:4px;font-size:0.7rem;">${escapeHTML(o)}</span>`).join('')}</div>
                </div>` : ''}

                <!-- FRESH ANGLES -->
                ${m.fresh_angles && m.fresh_angles.length ? `
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-dim);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.4;margin-bottom:8px;">Fresh Angles</div>
                    ${m.fresh_angles.map(a => `<div style="font-size:0.8rem;color:#10b981;margin-bottom:4px;">→ ${escapeHTML(a)}</div>`).join('')}
                </div>` : ''}

                <!-- STRATEGIC INSIGHT -->
                ${stratInsight ? `
                <div style="grid-column:1/-1;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.2);border-radius:10px;padding:16px;">
                    <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;opacity:0.5;margin-bottom:6px;color:#8b5cf6;">Why This Campaign Works</div>
                    <div style="font-size:0.85rem;line-height:1.5;">${escapeHTML(stratInsight)}</div>
                </div>` : ''}
            </div>
        </div>`;
    }

    function renderJsonCards(campaignData, campaignId = null) {
        if (!campaignData || typeof campaignData !== 'object') return converterMarkdown(String(campaignData));

        let html = `<div class="json-campaign-results" data-campaign-id="${campaignId || ''}">`;

        html += renderEngineBadge(campaignData);

        if (campaignId) {
            html += `<div style="text-align:right; margin-bottom:32px; display:flex; gap:16px; justify-content:flex-end;">
                        <button class="btn-ninja btn-secondary" onclick="generateAgencyProposal('${campaignId}')">📄 Gerar Proposta</button>
                        <button class="btn-ninja btn-secondary" onclick="saveCampaignEdits('${campaignId}', this)">💾 Salvar Edição</button>
                    </div>`;
        }

        // STRATEGIC CAMPAIGN PLAN
        html += renderStrategicPlan(campaignData);

        html += `
        <div class="variation-tabs">
            <button class="tab-btn active" onclick="switchVariation('a', this)">🚀 Variacao A (Ganho)</button>
            <button class="tab-btn" onclick="switchVariation('b', this)">⚠️ Variacao B (Medo)</button>
            <button class="tab-btn" onclick="switchVariation('c', this)">🔍 Variacao C (Curiosidade)</button>
        </div>`;

        if (campaignData.facebook_ad) {
            const ad = campaignData.facebook_ad;
            html += `
            <div class="json-card">
                <h3><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg> Meta Ads (A/B Test)</h3>
                <div class="oracle-score-container">
                    <div class="score-circular-area">
                        <div class="circular-progress" id="main-score-circle" style="--progress: 0;">
                            <span class="score-value" id="main-score-val">--</span>
                        </div>
                        <span class="score-label" id="main-score-status">Analisando...</span>
                        <div class="metrics-list" style="margin-top:24px; width:100%;">
                            ${renderMetricRow('Clareza', 'score-clareza')}
                            ${renderMetricRow('Urgência', 'score-urgencia')}
                            ${renderMetricRow('Emoção', 'score-emocao')}
                            ${renderMetricRow('CTR Estimado', 'score-ctr')}
                            ${renderMetricRow('Especificidade', 'score-espec')}
                        </div>
                    </div>
                    <div class="editor-area">
                        <div class="field-group">
                            <label class="field-label">Headline do Anúncio</label>
                            <input type="text" class="draft-edit field-headline ab-content" data-a="${escapeHTML(ad.headline_a || ad.headline || '')}" data-b="${escapeHTML(ad.headline_b || '')}" data-c="${escapeHTML(ad.headline_c || '')}" value="${escapeHTML(ad.headline_a || ad.headline || '')}">
                        </div>
                        <div class="field-group">
                            <label class="field-label">Texto Principal (Copywriting)</label>
                            <textarea class="draft-edit field-primary-text ab-content" data-a="${escapeHTML(ad.primary_text_a || ad.primary_text || '')}" data-b="${escapeHTML(ad.primary_text_b || '')}" data-c="${escapeHTML(ad.primary_text_c || '')}" rows="8" oninput="debounceScore(this)">${escapeHTML(ad.primary_text_a || ad.primary_text || '')}</textarea>
                        </div>
                        <div style="background:rgba(99,102,241,0.05); border:1px solid rgba(99,102,241,0.1); padding:16px; border-radius:12px; margin-bottom:24px;">
                            <p style="font-size:0.85rem; color:var(--text-secondary); line-height:1.5;">
                                <strong style="color:var(--accent-primary);">💡 Sugestão Oracle:</strong> <span id="score-dica">Comece a digitar para receber sugestões de otimização em tempo real...</span>
                            </p>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
                            <label style="display:flex; align-items:center; gap:12px; cursor:pointer;">
                                <input type="checkbox" onchange="toggleAutopilot('${campaignId}', this)" style="width:18px; height:18px; accent-color:var(--accent-primary);">
                                <span style="font-size:0.9rem; font-weight:700;">🤖 Modo Autopilot (IA Otimizadora)</span>
                            </label>
                            <div id="autopilot-status-${campaignId}" style="font-size:0.8rem; color:#10b981; visibility:hidden; font-weight:800;">✨ IA AGINDO...</div>
                        </div>
                        <button class="btn-ninja btn-publish-meta" style="width:100%;" onclick="publishToMeta(this)">🚀 Publicar Campanha no Meta</button>
                    </div>
                </div>
            </div>`;
        }

        if (campaignData.instagram_posts) {
            html += `<h2 style="margin: 40px 0 24px; display:flex; align-items:center; gap:12px;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg> Instagram Creative Feed</h2><div class="pro-grid">`;
            campaignData.instagram_posts.forEach((post, i) => {
                html += `
                <div class="json-card" data-index="${i}">
                    <h4 style="margin-bottom:20px; font-size:1.1rem;">Post Criativo ${i+1}</h4>
                    <img src="${post.image_url || ''}" class="post-image" onerror="this.src='https://placehold.co/1024x1024/12141c/ffffff?text=Gerando+Arte...'">
                    <div class="field-group">
                        <label class="field-label">Legenda Estratégica</label>
                        <textarea class="draft-edit field-caption" rows="6">${escapeHTML(post.caption || '')}</textarea>
                    </div>
                    <div class="field-group">
                        <label class="field-label">Hashtags de Alcance</label>
                        <textarea class="draft-edit field-hashtags" rows="2">${escapeHTML(post.hashtags || '')}</textarea>
                    </div>
                </div>`;
            });
            html += `</div>`;
        }

        if (campaignData.email) {
            const em = campaignData.email;
            html += `
            <div class="json-card">
                <h3><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg> E-mail de Conversão</h3>
                <div class="field-group">
                    <label class="field-label">Assunto Magnético</label>
                    <input type="text" class="draft-edit field-subject ab-content" data-a="${escapeHTML(em.subject_a || em.subject || '')}" data-b="${escapeHTML(em.subject_b || '')}" value="${escapeHTML(em.subject_a || em.subject || '')}">
                </div>
                <div class="field-group">
                    <label class="field-label">Corpo do E-mail</label>
                    <textarea class="draft-edit field-body ab-content" data-a="${escapeHTML(em.body_a || em.body || '')}" data-b="${escapeHTML(em.body_b || '')}" rows="8">${escapeHTML(em.body_a || em.body || '')}</textarea>
                </div>
            </div>`;
        }

        if (campaignData.video_script) {
            const vs = campaignData.video_script;
            html += `
            <div class="json-card">
                <h3><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> Produção de Vídeo IA (Roteiro & Midia)</h3>`;
            
            if (vs.video_url) {
                html += `
                <div class="video-player-container">
                    <video controls loop playsinline class="generated-video"><source src="${vs.video_url}" type="video/mp4"></video>
                    <a href="${vs.video_url}" download class="btn-download-video">⬇️ Download Video</a>
                </div>`;
            } else if (vs.image_url) {
                html += `<img src="${vs.image_url}" class="post-image" alt="Thumbnail">`;
            }

            if (vs.audio_url) {
                html += `
                <div style="margin-bottom:32px; padding:24px; background:rgba(99,102,241,0.05); border-radius:12px; border:1px solid rgba(99,102,241,0.1);">
                    <p style="font-size:0.8rem; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> Narração IA Gerada
                    </p>
                    <audio controls style="width: 100%; height: 32px;"><source src="${vs.audio_url}" type="audio/mpeg"></audio>
                </div>`;
            }

            html += `
                <div class="field-group">
                    <label class="field-label" style="color:#ef4444;">🔥 Hook (O Gancho)</label>
                    <textarea class="draft-edit field-hook" rows="2">${escapeHTML(vs.hook || '')}</textarea>
                </div>
                <div class="field-group">
                    <label class="field-label" style="color:#3b82f6;">📝 Conteúdo / Storytelling</label>
                    <textarea class="draft-edit field-video-body" rows="4">${escapeHTML(vs.body || '')}</textarea>
                </div>
                <div class="field-group">
                    <label class="field-label" style="color:#10b981;">🎯 CTA (Chamada de Ação)</label>
                    <textarea class="draft-edit field-video-cta" rows="2">${escapeHTML(vs.cta || '')}</textarea>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:32px;">
                    <button class="btn-ninja btn-publish-tiktok" onclick="publishToTikTok(this, '${vs.video_url}')">🎵 Publicar no TikTok</button>
                    <button class="btn-ninja btn-publish-meta" onclick="publishToMeta(this)">🚀 Publicar no Meta</button>
                </div>
            </div>`;
        }
        html += '</div>';
        return html;
    }

    function renderMetricRow(label, id, colorClass = '') {
        return `<div class="metric-row">
            <div class="metric-info"><span>${label}</span><span id="${id}-val">0</span></div>
            <div class="metric-bar-bg"><div class="metric-bar-fill ${colorClass}" id="${id}-bar" style="width: 0%;"></div></div>
        </div>`;
    }

    window.switchVariation = function(version, btn) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.ab-content').forEach(el => {
            const content = el.dataset[version] || el.dataset['a'];
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                el.value = content;
                if (el.classList.contains('field-primary-text')) debounceScore(el);
            }
        });
    }

    let scoreTimeout;
    window.debounceScore = function(textarea) {
        clearTimeout(scoreTimeout);
        scoreTimeout = setTimeout(() => updateAdScore(textarea.value), 800);
    }

    async function updateAdScore(text) {
        if (!text || text.length < 10) return;
        try {
            const res = await fetch('/api/modules/score', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                body: JSON.stringify({ copy: text })
            });
            const data = await res.json();
            if (data.score !== undefined) {
                const circle = document.getElementById('main-score-circle');
                const val = document.getElementById('main-score-val');
                const status = document.getElementById('main-score-status');
                if (circle) {
                    circle.style.setProperty('--progress', data.score);
                    val.innerText = data.score;
                    status.innerText = data.grade || "Bom";
                    status.style.color = data.score > 70 ? '#10b981' : '#f59e0b';
                }
                updateMetric('score-clareza', data.clareza);
                updateMetric('score-urgencia', data.urgencia);
                updateMetric('score-emocao', data.emocional);
                updateMetric('score-ctr', data.ctr_estimado);
                updateMetric('score-espec', data.especificidade);
                const tip = document.getElementById('score-dica');
                if (tip) tip.innerText = data.tip || "...";
            }
        } catch (e) { console.error("Score Error:", e); }
    }

    function updateMetric(id, val) {
        const bar = document.getElementById(`${id}-bar`);
        const text = document.getElementById(`${id}-val`);
        if (bar && val !== undefined) { bar.style.width = `${val}%`; text.innerText = val; }
    }

    window.saveCampaignEdits = async function(campaignId, btn) {
        const container = btn.closest('.json-campaign-results');
        const campaignData = { instagram_posts: [], facebook_ad: {}, email: {}, video_script: {} };
        container.querySelectorAll('.instagram-card').forEach(card => {
            campaignData.instagram_posts.push({
                image_url: card.querySelector('img')?.src || '',
                caption: card.querySelector('.field-caption').value,
                hashtags: card.querySelector('.field-hashtags').value
            });
        });
        const metaCard = container.querySelector('.facebook-card');
        if (metaCard) {
            campaignData.facebook_ad = {
                headline: metaCard.querySelector('.field-headline').value,
                primary_text: metaCard.querySelector('.field-primary-text').value,
                cta: metaCard.querySelector('.ad-cta').innerText
            };
        }
        const emailCard = container.querySelector('.email-card');
        if (emailCard) {
            campaignData.email = {
                subject: emailCard.querySelector('.field-subject').value,
                body: emailCard.querySelector('.field-body').value
            };
        }
        const videoCard = container.querySelector('.video-card');
        if (videoCard) {
            campaignData.video_script = {
                video_url: videoCard.querySelector('source')?.src || '',
                audio_url: videoCard.querySelector('audio source')?.src || '',
                image_url: videoCard.querySelector('.post-image')?.src || '',
                hook: videoCard.querySelector('.field-hook').value,
                body: videoCard.querySelector('.field-video-body').value,
                cta: videoCard.querySelector('.field-video-cta').value
            };
        }
        btn.disabled = true; btn.innerText = "⏳ Salvando...";
        try {
            const res = await fetch('/api/campaigns/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                body: JSON.stringify({ id: campaignId, result_text: campaignData })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) { alert("Erro ao salvar alterações."); }
        btn.disabled = false; btn.innerText = "💾 Salvar Alterações";
    }

    window._ensureConnected = async function(provider) {
        if (!window._connCache || !window._connCache[provider]) await checkConnections();
        const status = window._connCache && window._connCache[provider];
        if (!status || !status.connected) {
            const names = { meta: 'Meta Ads', tiktok: 'TikTok Ads' };
            const tabs = { meta: 'tab-config', tiktok: 'tab-config' };
            if (status && status.unconfigured) {
                alert(names[provider] + ' não configurado no servidor.\nInforme o administrador para configurar as credenciais.');
            } else {
                const ok = confirm('⚠️ ' + names[provider] + ' não está conectado.\n\nClique em OK para abrir a página de conexão.');
                if (ok) {
                    document.querySelectorAll('.tab-pane').forEach(t => t.classList.add('hidden'));
                    document.getElementById(tabs[provider]).classList.remove('hidden');
                }
            }
            return false;
        }
        return true;
    }

    window.publishToMeta = async function(btn) {
        if (!await window._ensureConnected('meta')) return;
        if (!confirm("Enviar para rascunho do Gerenciador de Anúncios Meta?")) return;
        const container = btn.closest('.json-campaign-results');
        const metaCard = container ? container.querySelector('.field-headline') : null;
        const headline = metaCard ? metaCard.value : 'Campanha Copilot IA';
        try {
            const res = await fetch('/api/campaigns/publish_to_meta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                body: JSON.stringify({ action: 'publish', campaign_name: headline })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) { alert("Erro ao publicar anúncio."); }
    }

    window.publishToTikTok = async function(btn, videoUrl) {
        if (!await window._ensureConnected('tiktok')) return;
        if (!confirm("Enviar este vídeo para o TikTok Ads Manager?")) return;
        const container = btn.closest('.json-campaign-results');
        const videoCard = container ? container.querySelector('.field-hook') : null;
        const headline = videoCard ? videoCard.value : 'Campanha Copilot IA';
        try {
            const res = await fetch('/api/campaigns/publish_to_tiktok', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                body: JSON.stringify({ video_url: videoUrl, headline: headline })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) { alert("Erro ao publicar no TikTok."); }
    }

    const btnBuscarLeads = document.getElementById('btnBuscarLeads');
    if (btnBuscarLeads) {
        btnBuscarLeads.addEventListener('click', async () => {
            const nicho = document.getElementById('leadNicho').value.trim();
            const cidade = document.getElementById('leadCidade').value.trim();
            if (!nicho || !cidade) { alert("Preencha o nicho e a cidade."); return; }
            const loadingLeads = document.getElementById('loadingLeads');
            const leadsListArea = document.getElementById('leadsListArea');
            const leadsTableBody = document.getElementById('leadsTableBody');
            loadingLeads.classList.remove('hidden'); leadsListArea.classList.add('hidden');
            btnBuscarLeads.disabled = true;
            try {
                const res = await fetch('/api/leads/buscar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ nicho, cidade })
                });
                const data = await res.json();
                leadsTableBody.innerHTML = '';
                if (data.leads && data.leads.length > 0) {
                    data.leads.forEach(lead => {
                        const score = lead.health_score || 0;
                        const scoreColor = score > 80 ? '#10b981' : (score > 60 ? '#f59e0b' : '#ef4444');
                        
                        leadsTableBody.innerHTML += `
                            <tr style="border-bottom: 1px solid var(--border-dim); transition: 0.2s;">
                                <td style="padding: 16px;">
                                    <div style="font-weight:600; color:var(--text-primary);">${escapeHTML(lead.nome)}</div>
                                    <div style="font-size:0.75rem; color:var(--text-secondary);">${escapeHTML(lead.telefone || 'N/A')}</div>
                                </td>
                                <td style="padding: 16px;">
                                    <div style="display:flex; align-items:center; gap:8px;">
                                        <div style="width:36px; height:36px; border-radius:50%; border:2px solid ${scoreColor}; display:flex; align-items:center; justify-content:center; font-size:0.7rem; font-weight:700; color:${scoreColor};">
                                            ${score}%
                                        </div>
                                        <span style="font-size:0.75rem; color:var(--text-secondary);">${score > 80 ? 'Alta Prod.' : 'Oportunidade'}</span>
                                    </div>
                                </td>
                                <td style="padding: 16px;">
                                    <div style="background:rgba(239, 68, 68, 0.05); color:#ef4444; padding:4px 10px; border-radius:6px; font-size:0.75rem; border:1px solid rgba(239, 68, 68, 0.1); display:inline-block;">
                                        ⚠️ ${escapeHTML(lead.dor || 'Vulnerabilidade Detectada')}
                                    </div>
                                    <div style="font-size:0.7rem; color:var(--text-muted); margin-top:4px;">${escapeHTML(lead.oportunidade || '')}</div>
                                </td>
                                <td style="padding: 16px; text-align: right;">
                                    <button class="btn-ninja" style="padding: 8px 16px; font-size: 0.75rem; background: var(--bg-surface); border: 1px solid var(--border-dim);" 
                                            onclick="abrirPitchNinja('${lead.nome.replace(/'/g, "")}', '${(lead.pitch_script || '').replace(/'/g, "").replace(/\n/g, " ")}', '${lead.telefone}')">
                                        ✨ Ninja Pitch
                                    </button>
                                </td>
                            </tr>
                        `;
                    });
                    leadsListArea.classList.remove('hidden');
                } else {
                    leadsTableBody.innerHTML = `<tr><td colspan="4" style="padding:32px;text-align:center;color:var(--text-muted);font-size:0.85rem;">
                        Nenhum lead encontrado. Para melhores resultados, configure <code style="background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;">SERPAPI_KEY</code> no .env.
                    </td></tr>`;
                    leadsListArea.classList.remove('hidden');
                }
            } catch (e) { alert("Erro ao buscar leads."); } finally { loadingLeads.classList.add('hidden'); btnBuscarLeads.disabled = false; }
        });
    }

    window.abrirPitchNinja = function(nome, pitch, telefone) {
        const zapClean = (telefone || '').replace(/\D/g, '');
        const finalPitch = pitch || `Olá ${nome}, vi que sua empresa pode escalar com IA...`;
        if (confirm(`PITCH NINJA PARA ${nome.toUpperCase()}:\n\n"${finalPitch}"\n\nEnviar via WhatsApp agora?`)) {
            window.open(`https://wa.me/55${zapClean}?text=${encodeURIComponent(finalPitch)}`, '_blank');
        }
    };

    window.prospectarLead = async function(nome, site) {
        const modalMsg = prompt(`Gerando abordagem para ${nome}. Qual produto você quer oferecer?`, "Marketing Digital");
        if (!modalMsg) return;
        try {
            const res = await fetch('/api/leads/pitch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                body: JSON.stringify({ nome, site, meu_produto: modalMsg })
            });
            const data = await res.json();
            if (data.pitch) window.open(`https://wa.me/?text=${encodeURIComponent(data.pitch)}`, '_blank');
        } catch (e) { alert("Erro ao gerar pitch."); }
    };

    const btnGerarCalendario = document.getElementById('btnGerarCalendario');
    if (btnGerarCalendario) {
        btnGerarCalendario.addEventListener('click', async () => {
            const calendarArea = document.getElementById('calendarArea');
            const calendarContent = document.getElementById('calendarContent');
            btnGerarCalendario.disabled = true; btnGerarCalendario.innerText = "📅 Gerando...";
            try {
                const res = await fetch('/api/calendar/generate', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                if (data.calendario) {
                    calendarContent.innerHTML = '';
                    data.calendario.forEach(item => {
                        calendarContent.innerHTML += `<div class="glass-panel" style="padding:15px; border-left:4px solid var(--accent);">
                            <div style="font-weight:700; color:var(--accent);">DIA ${item.dia}</div>
                            <div>${escapeHTML(item.titulo)}</div>
                            <div style="font-size:0.7rem; opacity:0.6;">${escapeHTML(item.tipo)}</div>
                        </div>`;
                    });
                    calendarArea.classList.remove('hidden');
                }
            } catch (e) { alert("Erro ao gerar calendário."); } finally { btnGerarCalendario.disabled = false; btnGerarCalendario.innerText = "⚡ Gerar Plano de 30 Dias"; }
        });
    }

    window.copyToClipboard = (text) => { navigator.clipboard.writeText(text); alert("Copiado!"); }

    const btnClonarFunil = document.getElementById('btnClonarFunil');
    if (btnClonarFunil) {
        btnClonarFunil.addEventListener('click', async () => {
            const url = document.getElementById('funnelUrl').value;
            const resArea = document.getElementById('funnelResult');
            btnClonarFunil.disabled = true; btnClonarFunil.innerText = "🌪️ Analisando...";
            try {
                const res = await fetch('/api/funnel/clone', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                resArea.innerHTML = converterMarkdown(data.analise);
                resArea.classList.remove('hidden');
            } catch (e) { alert("Erro ao clonar funil."); } finally { btnClonarFunil.disabled = false; btnClonarFunil.innerText = "🌪️ Analisar e Clonar"; }
        });
    }

    const btnViralCheck = document.getElementById('btnViralCheck');
    if (btnViralCheck) {
        btnViralCheck.addEventListener('click', async () => {
            const content = document.getElementById('viralContent');
            btnViralCheck.innerText = "⚡ Mapeando...";
            try {
                const res = await fetch('/api/viral/trends', { method: 'POST', headers: { 'Authorization': `Bearer ${authToken}` } });
                const data = await res.json();
                content.innerHTML = '<h3 style="margin-top:20px;">🔥 Tendências Detectadas (24h)</h3>';
                data.trends.forEach(t => {
                    content.innerHTML += `<div class="glass-panel" style="margin-top:10px; border-left:4px solid #f59e0b;">
                        <strong>${escapeHTML(t.tema)}</strong><p style="font-size:0.85rem; opacity:0.8;">${escapeHTML(t.oportunidade)}</p>
                    </div>`;
                });
                content.classList.remove('hidden');
            } catch (e) {} finally { btnViralCheck.innerText = "🔥 Detectar Tendências"; }
        });
    }

    window.loadMarketplace = async function() {
        const grid = document.getElementById('marketGrid');
        grid.innerHTML = '<div class="spinner"></div>';
        try {
            const res = await fetch('/api/marketplace/list');
            const data = await res.json();
            grid.innerHTML = '';
            data.templates.forEach(t => {
                grid.innerHTML += `<div class="glass-panel fade-in" style="padding:20px; display:flex; flex-direction:column; gap:10px;">
                    <div style="font-size:0.7rem; color:var(--accent); text-transform:uppercase; font-weight:700;">${escapeHTML(t.niche)}</div>
                    <h4 style="margin:0;">${escapeHTML(t.title)}</h4>
                    <div style="font-size:1.2rem; font-weight:700; margin:10px 0;">€ ${t.price}</div>
                    <button class="btn-primary" style="margin-top:auto;" onclick="buyTemplate('${t.id}')">🛒 Clonar Agora</button>
                </div>`;
            });
        } catch (e) { grid.innerHTML = "Erro ao carregar mercado."; }
    }

    window.buyTemplate = (id) => {
        alert("Simulação de Checkout Stripe...");
        setTimeout(() => alert("Template Clonado com Sucesso!"), 1500);
    }

    const btnWatchCompetitor = document.getElementById('btnWatchCompetitor');
    if (btnWatchCompetitor) {
        btnWatchCompetitor.addEventListener('click', async () => {
            const url = document.getElementById('compUrl').value;
            const log = document.getElementById('radarLog');
            btnWatchCompetitor.innerText = "📡 Sincronizando...";
            try {
                const res = await fetch('/api/competitors/watch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                alert(data.status);
                log.innerHTML = `<div class="glass-panel" style="border-left:4px solid #3b82f6;"><strong>📡 Radar Ativo: ${escapeHTML(url)}</strong></div>`;
            } catch (e) { alert("Erro ao ativar radar."); } finally { btnWatchCompetitor.innerText = "📡 Ativar Radar"; }
        });
    }

    window.toggleAutopilot = function(id, checkbox) {
        const status = document.getElementById(`autopilot-status-${id}`);
        if (checkbox.checked) {
            status.style.visibility = 'visible';
            alert("🤖 Modo Autopilot Ativado!");
        } else { status.style.visibility = 'hidden'; }
    }

    window.generateAgencyProposal = async function(campaignId) {
        try {
            const res = await fetch(`/api/campaigns/proposal/${campaignId}`, { headers: { 'Authorization': `Bearer ${authToken}` } });
            const data = await res.json();
            if (data.html) {
                const win = window.open("", "_blank");
                win.document.write(data.html); win.document.close();
            } else { alert(data.erro || "Erro ao gerar proposta."); }
        } catch (e) { alert("Erro de conexão."); }
    }
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log("%c🚀 Aura UI v1.0 Loaded", "color: #6366f1; font-weight: bold; font-size: 14px;");
        initApp();
    });
} else {
    console.log("%c🚀 Aura UI v1.0 Loaded", "color: #6366f1; font-weight: bold; font-size: 14px;");
    initApp();
}
