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

    function checkAuth() {
        console.log("DEBUG: Verificando Auth...", authToken ? "Logado" : "Deslogado");
        if (authToken) {
            authScreen.classList.add('hidden');
            appScreen.classList.remove('hidden');
            const userDisp = document.getElementById('userEmailDisplay');
            if (userDisp) userDisp.innerText = userEmail;
            console.log("DEBUG: Dashboard exibido.");
            checkExistingJobs(); // Recupera tarefas em background
        } else {
            authScreen.classList.remove('hidden');
            appScreen.classList.add('hidden');
            console.log("DEBUG: Tela de Login exibida.");
        }
    }
    checkAuth();

    // Valida token com servidor — se invalido, forca logout imediato
    async function validateSession() {
        if (!authToken) return;
        try {
            const res = await fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${authToken}` } });
            if (!res.ok) throw new Error('Token invalido');
        } catch (e) {
            localStorage.removeItem('sb_token');
            localStorage.removeItem('sb_user');
            authToken = null;
            userEmail = null;
            checkAuth();
        }
    }
    validateSession();

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

    // Verificar status de conexões
    async function checkConnections() {
        const statusDiv = document.getElementById('connectionStatus');
        if (!statusDiv || !authToken) return;
        let statusText = '';
        try {
            const metaRes = await fetch('/api/meta/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const metaData = await metaRes.json();
            statusText += metaData.connected ? '✅ Meta conectado' : '⚪ Meta desconectado';
        } catch(e) { statusText += '⚪ Meta'; }
        try {
            const ttRes = await fetch('/api/tiktok/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const ttData = await ttRes.json();
            statusText += ' | ' + (ttData.connected ? '✅ TikTok conectado' : '⚪ TikTok desconectado');
        } catch(e) { statusText += ' | ⚪ TikTok'; }
        statusDiv.innerHTML = statusText;
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
    function carregarBrandKit() {
        const tom = localStorage.getItem('brandkit_tom') || '';
        const publico = localStorage.getItem('brandkit_publico') || '';
        const tomEl = document.getElementById('configTomDeVoz');
        const pubEl = document.getElementById('configPublicoAlvo');
        if (tomEl) tomEl.value = tom;
        if (pubEl) pubEl.value = publico;
    }

    const btnSaveConfig = document.getElementById('btnSaveConfig');
    if (btnSaveConfig) {
        btnSaveConfig.addEventListener('click', () => {
            const tom = document.getElementById('configTomDeVoz').value.trim();
            const publico = document.getElementById('configPublicoAlvo').value.trim();
            localStorage.setItem('brandkit_tom', tom);
            localStorage.setItem('brandkit_publico', publico);
            const msg = document.getElementById('configSaveMsg');
            msg.style.display = 'block';
            setTimeout(() => msg.style.display = 'none', 2000);
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

    async function pollJobStatus(jobId, silent = false) {
        const loadingCopilot = document.getElementById('loadingCopilot');
        const resultadoCopilot = document.getElementById('resultadoCopilot');
        const btnGerarMagica = document.getElementById('btnGerarMagica');
        let failCount = 0;
        
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/copilot/status/${jobId}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (!res.ok) throw new Error("Servidor indisponível");
                
                const job = await res.json();
                failCount = 0; 

                // Atualiza estado global
                activeJobs[jobId] = job;
                updateJobsUI();
                
                if (job.status === 'processing' || job.status === 'pending') {
                    if (!silent && loadingCopilot && !loadingCopilot.classList.contains('hidden')) {
                        loadingCopilot.innerHTML = `
                            <div class="fade-in" style="text-align:center;">
                                <div class="spinner" style="margin: 0 auto 32px; width: 80px; height: 80px; border: 2px solid rgba(255,255,255,0.05); border-top-color: var(--accent-gold); border-radius: 50%; animation: spin 1.5s cubic-bezier(0.16, 1, 0.3, 1) infinite;"></div>
                                <h3 class="font-serif" style="font-size: 2.5rem; margin-bottom: 12px; color: var(--accent-gold);">${escapeHTML(job.current_step || 'Processando...')}</h3>
                                <div style="width:100%; max-width:400px; margin: 24px auto; background:rgba(255,255,255,0.03); height:1px; position:relative;">
                                    <div style="width:${job.progress}%; height:1px; background:var(--accent-gold); position:absolute; left:0; top:0; transition: width 0.5s ease;"></div>
                                </div>
                                <p style="font-size:0.7rem; text-transform:uppercase; letter-spacing:0.2em; opacity:0.4;">Arquitetura de Marketing em andamento...</p>
                            </div>
                        `;
                    }
                } else if (job.status === 'completed') {
                    clearInterval(pollInterval);
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
                    console.warn("gerar campanha: 401 — sessao expirada");
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
        historyList.innerHTML = '<p>Carregando campanhas...</p>';
        try {
            const res = await fetch('/api/campanhas/historico', { headers: { 'Authorization': `Bearer ${authToken}` } });
            const data = await res.json();
            historyList.innerHTML = '';
            if (data.campanhas && data.campanhas.length > 0) {
                data.campanhas.forEach(c => {
                    const dataHora = c.created_at ? new Date(c.created_at).toLocaleString('pt-BR') : '';
                    const safeProduct = escapeHTML(c.product);
                    const safeGoal = escapeHTML(c.goal);
                    historyList.innerHTML += `
                        <div class="campaign-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <p><strong>📦 ${safeProduct}</strong></p>
                                <small style="opacity:0.6;">${dataHora}</small>
                            </div>
                            <p style="opacity:0.8; font-size:0.85rem;">🎯 ${safeGoal}</p>
                            <details style="margin-top:10px; cursor:pointer;">
                                <summary>Ver Campanha Completa</summary>
                                <div style="margin-top:10px; font-size:0.9em; opacity:0.85;">
                                    ${renderJsonCards(parseSafeJson(c.result_text), c.id)}
                                </div>
                            </details>
                        </div>
                    `;
                });
            } else {
                historyList.innerHTML = '<p>Você ainda não tem campanhas salvas.</p>';
            }
        } catch(e) {
            historyList.innerHTML = '<p>Erro ao buscar histórico no Supabase.</p>';
        }
    }

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
        let html = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
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
            : `LEGADO · ${meta.fallback_reason ? escapeHTML(String(meta.fallback_reason).slice(0, 80)) : 'fallback'}`;
        const modelsLine = (meta.models_used && meta.models_used.length)
            ? `<div style="font-size:0.7rem; margin-top:6px; opacity:0.75;">${meta.models_used.map(m => escapeHTML(m)).join(' · ')}</div>`
            : '';
        return `<div style="margin-bottom:16px;">
            <span style="background:${bg};color:white;padding:6px 12px;border-radius:6px;font-size:0.75rem;font-weight:600;">${escapeHTML(label)}</span>
            ${modelsLine}
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

    window.publishToMeta = async function(btn) {
        if (!confirm("Enviar para rascunho do Gerenciador de Anúncios Meta?")) return;
        const container = btn.closest('.json-campaign-results');
        const metaCard = container.querySelector('.facebook-card');
        const headline = metaCard ? metaCard.querySelector('.field-headline').value : 'Campanha Copilot IA';
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
        if (!confirm("Enviar este vídeo para o TikTok Ads Manager?")) return;
        const container = btn.closest('.json-campaign-results');
        const videoCard = container.querySelector('.video-card');
        const headline = videoCard ? videoCard.querySelector('.field-hook').value : 'Campanha Copilot IA';
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
                } else { alert("Nenhum lead encontrado."); }
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
if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initApp); } else { initApp(); }
