console.log("🚀 MKTPilot: Script iniciado com sucesso.");
document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // ESTADO DA APLICAÇÃO E AUTH
    // ==========================================
    let authToken = localStorage.getItem('sb_token');
    let userEmail = localStorage.getItem('sb_user');
    let currentPlatform = "Multicanal"; // Default
    let currentNiche = "";

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
        } else {
            authScreen.classList.remove('hidden');
            appScreen.classList.add('hidden');
            console.log("DEBUG: Tela de Login exibida.");
        }
    }
    checkAuth();

    // Logout
    document.getElementById('btnLogout').addEventListener('click', () => {
        localStorage.removeItem('sb_token');
        localStorage.removeItem('sb_user');
        authToken = null;
        checkAuth();
    });

    // Conectar Meta Ads (passa token do usuário para identificação multiusuário)
    const btnConnectMeta = document.getElementById('btnConnectMeta');
    if (btnConnectMeta) {
        btnConnectMeta.addEventListener('click', () => {
            window.open(`/auth/meta/login?token=${encodeURIComponent(authToken)}`, '_blank');
        });
    }

    // Conectar TikTok Ads (passa token do usuário para identificação multiusuário)
    const btnConnectTikTok = document.getElementById('btnConnectTikTok');
    if (btnConnectTikTok) {
        btnConnectTikTok.addEventListener('click', () => {
            window.open(`/auth/tiktok/login?token=${encodeURIComponent(authToken)}`, '_blank');
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

    // Os listeners de clique serão registrados abaixo, após a definição global
});

// ==========================================
// LOGIN E REGISTRO (GLOBAL PARA EVITAR TRAVAMENTOS)
// ==========================================
window.handleAuth = async function(endpoint) {
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
        authError.innerText = "Preencha e-mail e senha.";
        authError.classList.remove('hidden');
        return;
    }

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: pass })
        });
        const data = await res.json();
        
        if (res.ok) {
            localStorage.setItem('sb_token', data.token);
            localStorage.setItem('sb_user', data.user);
            location.reload(); // Recarrega para iniciar o estado autenticado de forma limpa
        } else {
            authError.innerText = data.erro || "Erro de autenticação";
            authError.classList.remove('hidden');
        }
    } catch (e) {
        console.error("DEBUG: Erro CRÍTICO no fetch", e);
        authError.innerText = "Erro de conexão. Verifique sua internet.";
        authError.classList.remove('hidden');
    }
}

// Vinculação de eventos (Garantindo que funcione mesmo com scripts lentos)
document.addEventListener('click', (e) => {
    if (e.target.id === 'btnLogin') window.handleAuth('/api/auth/login');
    if (e.target.id === 'btnRegister') window.handleAuth('/api/auth/register');
});

    if (passInput) {
        passInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') window.handleAuth('/api/auth/login');
        });
    }

    // ==========================================
    // SISTEMA DE ABAS DO SAAS
    // ==========================================
    const navLinks = document.querySelectorAll('.nav-links li');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navLinks.forEach(l => l.classList.remove('active'));
            tabPanes.forEach(t => t.classList.add('hidden'));
            
            link.classList.add('active');
            const targetTab = link.dataset.tab;
            document.getElementById(`tab-${targetTab}`).classList.remove('hidden');
            
            // Resetar wizard ao clicar em "Nova Campanha"
            if (targetTab === 'wizard') {
                resetWizard();
            }
            // Carregar histórico automaticamente ao clicar na aba
            if (targetTab === 'history') {
                carregarHistorico();
            }
            // Carregar Brand Kit ao clicar na aba
            if (targetTab === 'config') {
                carregarBrandKit();
            }
            if (targetTab === 'automations') {
                carregarAutomacoes();
            }
            if (targetTab === 'calendar') {
                // Opcional: carregar automático ou esperar clique no botão
            }
            if (targetTab === 'hooks') {
                carregarHooksIniciais();
            }
            if (targetTab === 'viral') {
                carregarTendenciasIniciais();
            }
        });
    });

    // ==========================================
    // MÓDULOS PREMIUM (INTEGRAÇÃO)
    // ==========================================

    // 1. Calendário 30 Dias
    const btnGerarCalendario = document.getElementById('btnGerarCalendario');
    if (btnGerarCalendario) {
        btnGerarCalendario.addEventListener('click', async () => {
            const area = document.getElementById('calendarArea');
            const content = document.getElementById('calendarContent');
            btnGerarCalendario.disabled = true;
            btnGerarCalendario.innerText = "⏳ Gerando Plano...";
            
            try {
                const res = await MKTPilot.Calendario.gerar({
                    nicho: currentNiche || "Marketing",
                    objetivo: "Gerar autoridade e vendas",
                    canais: ["ig", "tiktok", "email"]
                });
                area.classList.remove('hidden');
                MKTPilot.Calendario.renderGrid(res.dias, 'calendarContent');
            } catch(e) { alert("Erro ao gerar calendário."); }
            
            btnGerarCalendario.disabled = false;
            btnGerarCalendario.innerText = "⚡ Gerar Plano de 30 Dias Agora";
        });
    }

    // 2. Hooks Virais
    async function carregarHooksIniciais() {
        const container = document.getElementById('hooksContainer');
        if (!container) return;
        container.innerHTML = '<p>Carregando ganchos...</p>';
        try {
            const res = await MKTPilot.Hooks.listar({ nicho: currentNiche || "negócios" });
            container.innerHTML = '';
            res.hooks.forEach(h => {
                const card = document.createElement('div');
                card.className = 'glass-panel';
                card.style.padding = '20px';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                        <span class="tag">${h.angulo}</span>
                        <span style="color:#f59e0b;">🔥 ${h.calor}/5</span>
                    </div>
                    <p style="font-weight:600; font-size:1.1rem; margin-bottom:15px;">"${h.texto}"</p>
                    <div style="font-size:0.8rem; opacity:0.6;">CTR Estimado: ${h.ctr_estimado}%</div>
                    <button class="btn-secondary" style="margin-top:15px; width:100%;" onclick="adaptarHook('${h.texto.replace(/'/g, "\\'")}')">🪄 Adaptar ao meu Produto</button>
                `;
                container.appendChild(card);
            });
        } catch(e) { container.innerHTML = '<p>Erro ao carregar hooks.</p>'; }
    }

    window.adaptarHook = async function(texto) {
        const produto = prompt("Qual o seu produto para adaptarmos este hook?");
        if (!produto) return;
        try {
            const res = await MKTPilot.Hooks.adaptar(texto, produto, currentNiche);
            alert(`Hook Adaptado:\n\n${res.hook_adaptado}`);
        } catch(e) { alert("Erro ao adaptar hook."); }
    }

    // 3. Clonador de Funil
    const btnClonarFunil = document.getElementById('btnClonarFunil');
    if (btnClonarFunil) {
        btnClonarFunil.addEventListener('click', async () => {
            const url = document.getElementById('funnelUrl').value;
            const resDiv = document.getElementById('funnelResult');
            if (!url) return alert("Insira uma URL!");
            
            btnClonarFunil.disabled = true;
            btnClonarFunil.innerText = "⏳ Analisando Funil...";
            
            try {
                const res = await MKTPilot.Funil.analisar(url, "Meu Produto");
                resDiv.classList.remove('hidden');
                resDiv.innerHTML = `
                    <div class="grid-2">
                        <div style="border-right:1px solid rgba(255,255,255,0.1); padding-right:20px;">
                            <h4 style="color:#ef4444;">❌ Concorrente (Score: ${res.concorrente.score})</h4>
                            <p><strong>Headline:</strong> ${res.concorrente.headline}</p>
                            <p><strong>Falhas:</strong> ${res.concorrente.falhas.join(', ')}</p>
                        </div>
                        <div style="padding-left:20px;">
                            <h4 style="color:#10b981;">✅ Sua Versão Superior (Score: ${res.superior.score})</h4>
                            <p><strong>Headline:</strong> ${res.superior.headline}</p>
                            <p><strong>Diferencial:</strong> ${res.superior.diferenciais.join(', ')}</p>
                        </div>
                    </div>
                    <div style="margin-top:20px; padding-top:20px; border-top:1px solid rgba(255,255,255,0.1);">
                        <h5>Copy Completo do Funil:</h5>
                        <div class="resultado-box markdown-body">${converterMarkdown(res.superior.copy_completo)}</div>
                    </div>
                `;
            } catch(e) { alert("Erro ao clonar funil."); }
            
            btnClonarFunil.disabled = false;
            btnClonarFunil.innerText = "🌪️ Analisar e Clonar";
        });
    }

    // 4. Viral em 24h
    async function carregarTendenciasIniciais() {
        // Opcional: auto-carregar ou esperar botão
    }

    const btnViralCheck = document.getElementById('btnViralCheck');
    if (btnViralCheck) {
        btnViralCheck.addEventListener('click', async () => {
            const content = document.getElementById('viralContent');
            btnViralCheck.disabled = true;
            btnViralCheck.innerText = "⏳ Detectando Tendências...";
            
            try {
                const res = await MKTPilot.Viral.tendencias({ nicho: currentNiche });
                content.classList.remove('hidden');
                content.innerHTML = '<div class="cards-grid"></div>';
                const grid = content.querySelector('.cards-grid');
                
                res.tendencias.forEach(t => {
                    const card = document.createElement('div');
                    card.className = 'glass-panel';
                    card.style.padding = '20px';
                    card.innerHTML = `
                        <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                            <span class="tag">${t.canal}</span>
                            <span style="color:#ef4444;">🔥 ${t.calor}/5</span>
                        </div>
                        <h4>${t.titulo}</h4>
                        <p style="font-size:0.9rem; opacity:0.8;">${t.descricao}</p>
                        <div style="font-size:0.8rem; margin-top:10px; color:#10b981;">📈 ${t.views_semana} views</div>
                        <button class="btn-primary" style="margin-top:15px; width:100%;" onclick="criarCampanhaViral(${JSON.stringify(t).replace(/"/g, '&quot;')})">⚡ Surfar Tendência</button>
                    `;
                    grid.appendChild(card);
                });
            } catch(e) { alert("Erro ao carregar tendências."); }
            
            btnViralCheck.disabled = false;
            btnViralCheck.innerText = "🔥 Detectar Tendências Agora";
        });
    }

    window.criarCampanhaViral = async function(tendencia) {
        try {
            const res = await MKTPilot.Viral.criarCampanha(tendencia, "Meu Produto", currentNiche);
            alert(`Campanha Viral Criada!\n\nHeadline: ${res.headline}\n\nMelhor Horário: ${res.melhor_horario}`);
        } catch(e) { alert("Erro ao criar campanha viral."); }
    }

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
                // Envio em segundo plano (não trava o UI)
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

    function resetWizard() {
        currentPlatform = "Multicanal";
        currentNiche = "";
        document.getElementById('wiz-step-1').classList.remove('hidden');
        document.getElementById('wiz-step-2').classList.add('hidden');
        document.getElementById('wiz-step-3').classList.add('hidden');
        document.getElementById('wiz-step-4').classList.add('hidden');
        document.getElementById('loadingCopilot').classList.add('hidden');
        document.getElementById('resultadoCopilot').classList.add('hidden');
        document.getElementById('resultadoCopilot').innerHTML = '';
        document.getElementById('wizProduto').value = "";
        document.getElementById('btnGerarMagica').disabled = false;
        // Reset progress
        document.querySelectorAll('.progress-step').forEach((s, i) => {
            s.classList.toggle('active', i === 0);
        });
    }

    // ==========================================
    // WIZARD ONBOARDING (COPILOTO IDIOT-PROOF)
    // ==========================================
    window.selectPlatform = function(platform) {
        currentPlatform = platform;
        document.getElementById('wiz-step-1').classList.add('hidden');
        document.getElementById('wiz-step-2').classList.remove('hidden');
        // Update progress
        document.querySelectorAll('.progress-step').forEach((s, i) => s.classList.toggle('active', i <= 1));
    }

    window.selectNiche = function(niche) {
        currentNiche = niche;
        document.getElementById('wiz-step-2').classList.add('hidden');
        document.getElementById('wiz-step-3').classList.remove('hidden');
        // Update progress
        document.querySelectorAll('.progress-step').forEach((s, i) => s.classList.toggle('active', i <= 2));
    }

    window.nextWizard = function(step) {
        if (step === 4 && !document.getElementById('wizProduto').value) {
            alert('Descreva o que você vende!'); return;
        }
        document.getElementById('wiz-step-3').classList.add('hidden');
        document.getElementById('wiz-step-4').classList.remove('hidden');
        // Update progress
        document.querySelectorAll('.progress-step').forEach((s, i) => s.classList.toggle('active', i <= 3));
    }

    // Botão Mágico
    const btnGerarMagica = document.getElementById('btnGerarMagica');
    const resultadoCopilot = document.getElementById('resultadoCopilot');
    const loadingCopilot = document.getElementById('loadingCopilot');

    btnGerarMagica.addEventListener('click', async () => {
        const produto = document.getElementById('wizProduto').value;
        const selectedRadio = document.querySelector('input[name="objetivo"]:checked');
        const objetivo = selectedRadio ? selectedRadio.value : 'Aumentar seguidores e criar autoridade no nicho';
        
        if (!produto) { alert('Preencha o produto!'); return; }

        // Ler Spy Mode e Brand Kit
        const concorrenteUrl = document.getElementById('wizConcorrente')?.value || '';
        const tomDeVoz = localStorage.getItem('brandkit_tom') || '';
        const publicoAlvo = localStorage.getItem('brandkit_publico') || '';

        // Esconder wizard steps e mostrar loading
        document.getElementById('wiz-step-4').classList.add('hidden');
        loadingCopilot.classList.remove('hidden');
        resultadoCopilot.classList.add('hidden');
        resultadoCopilot.innerHTML = '';
        btnGerarMagica.disabled = true;

        try {
            const response = await fetch('/api/copilot/gerar', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ 
                    plataforma: currentPlatform, 
                    nicho: currentNiche, 
                    produto: produto, 
                    objetivo: objetivo,
                    concorrenteUrl: concorrenteUrl,
                    tomDeVoz: tomDeVoz,
                    publicoAlvo: publicoAlvo
                })
            });
            const data = await response.json();
            
            loadingCopilot.classList.add('hidden');
            resultadoCopilot.classList.remove('hidden');
            
            if (data.resultado) {
                resultadoCopilot.innerHTML = renderJsonCards(data.resultado, data.id);
                // Gatilho de Automação (Webhook/Make.com)
                dispararAutomacao(data.resultado);
            } else {
                resultadoCopilot.innerText = data.erro || "Erro ao gerar.";
            }
        } catch (e) {
            loadingCopilot.classList.add('hidden');
            resultadoCopilot.classList.remove('hidden');
            resultadoCopilot.innerText = "Erro de conexão.";
        }
        btnGerarMagica.disabled = false;
    });

    // ==========================================
    // HISTÓRICO (Supabase Data)
    // ==========================================
    async function carregarHistorico() {
        const historyList = document.getElementById('historyList');
        historyList.innerHTML = '<p>Carregando campanhas do Banco de Dados...</p>';
        try {
            const res = await fetch('/api/campanhas/historico', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const data = await res.json();
            historyList.innerHTML = '';
            if (data.campanhas && data.campanhas.length > 0) {
                data.campanhas.forEach(c => {
                    const dataHora = c.created_at ? new Date(c.created_at).toLocaleString('pt-BR') : '';
                    historyList.innerHTML += `
                        <div class="campaign-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <p><strong>📦 ${c.product}</strong></p>
                                <small style="opacity:0.6;">${dataHora}</small>
                            </div>
                            <p style="opacity:0.8; font-size:0.85rem;">🎯 ${c.goal}</p>
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

    document.getElementById('btnLoadHistory').addEventListener('click', carregarHistorico);

    // ==========================================
    // EVA BRAIN (MiniMax Contexto Massivo)
    // ==========================================
    const btnOtimizar = document.getElementById('btnOtimizar');
    const resultadoEva = document.getElementById('resultadoEva');
    const loadingEva = document.getElementById('loadingEva');
    const btnAnaliseAuto = document.getElementById('btnAnaliseAuto');
    const btnAnaliseManual = document.getElementById('btnAnaliseManual');
    const manualInputArea = document.getElementById('manualInputArea');
    let evaMode = 'manual'; // 'auto' ou 'manual'

    // Toggle entre modo automático e manual
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

    btnOtimizar.addEventListener('click', async () => {
        const relatorio = document.getElementById('relatorioInput').value;
        
        if (evaMode === 'manual' && !relatorio) {
            alert('Cole os dados de campanha no campo de texto!');
            return;
        }

        loadingEva.classList.remove('hidden');
        resultadoEva.classList.add('hidden');
        btnOtimizar.disabled = true;

        try {
            const payload = evaMode === 'auto' 
                ? { auto: true }
                : { relatorio: relatorio };
            
            const response = await fetch('/api/campanhas/otimizar', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
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

    function converterMarkdown(text) {
        if (typeof text !== 'string') return "";
        let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    function parseSafeJson(text) {
        try {
            if (typeof text === 'object') return text;
            return JSON.parse(text);
        } catch(e) {
            return text;
        }
    }

    function renderJsonCards(campaignData, campaignId = null) {
        if (!campaignData || typeof campaignData !== 'object') return converterMarkdown(String(campaignData));
        
        let html = `<div class="json-campaign-results" data-campaign-id="${campaignId || ''}">`;
        
        // Botões de Ação Superior
        if (campaignId) {
            html += `<div style="text-align:right; margin-bottom:15px; display:flex; gap:10px; justify-content:flex-end;">
                        <button class="btn-secondary" onclick="generateAgencyProposal('${campaignId}')" style="padding: 6px 12px; font-size: 0.8em; border-color: #3b82f6; color: #3b82f6;">📄 Gerar Proposta Comercial</button>
                        <button class="btn-secondary" onclick="saveCampaignEdits('${campaignId}', this)" style="padding: 6px 12px; font-size: 0.8em; border-color: #10b981; color: #10b981;">💾 Salvar Alterações</button>
                    </div>`;
        }

        // TABS DE VARIAÇÃO A/B (GLOBAL)
        html += `
        <div class="variation-tabs" style="margin-bottom:20px; display:flex; gap:10px; justify-content:center;">
            <button class="tab-btn active" onclick="switchVariation('a', this)">🚀 Variacao A (Ganho)</button>
            <button class="tab-btn" onclick="switchVariation('b', this)">⚠️ Variacao B (Medo)</button>
            <button class="tab-btn" onclick="switchVariation('c', this)">🔍 Variacao C (Curiosidade)</button>
        </div>`;

        // 1. FACEBOOK ADS (Com Oracle Score integrado)
        if (campaignData.facebook_ad) {
            const ad = campaignData.facebook_ad;
            html += `<h3>🚀 Meta Ads (A/B Test)</h3>`;
            html += `
            <div class="oracle-score-container glass-panel">
                <div class="score-circular-area">
                    <div class="circular-progress" id="main-score-circle" style="--progress: 0deg;">
                        <span class="score-value" id="main-score-val">--</span>
                    </div>
                    <span class="score-label" id="main-score-status">Pronto</span>
                    
                    <div class="metrics-list">
                        ${renderMetricRow('Clareza', 'score-clareza')}
                        ${renderMetricRow('Urgência', 'score-urgencia', 'orange')}
                        ${renderMetricRow('Emoção', 'score-emocao')}
                        ${renderMetricRow('CTR', 'score-ctr', 'blue')}
                        ${renderMetricRow('Especificidade', 'score-espec')}
                    </div>
                </div>
                
                <div class="editor-area">
                    <label style="font-size:0.8em; opacity:0.7;">Headline:</label>
                    <input type="text" class="draft-edit field-headline ab-content" data-a="${ad.headline_a || ad.headline || ''}" data-b="${ad.headline_b || ''}" data-c="${ad.headline_c || ''}" value="${ad.headline_a || ad.headline || ''}">
                    
                    <label style="font-size:0.8em; opacity:0.7; margin-top:10px;">Texto Principal:</label>
                    <textarea class="draft-edit field-primary-text ab-content" data-a="${ad.primary_text_a || ad.primary_text || ''}" data-b="${ad.primary_text_b || ''}" data-c="${ad.primary_text_c || ''}" rows="6" oninput="debounceScore(this)">${ad.primary_text_a || ad.primary_text || ''}</textarea>
                    
                    <div class="improvement-box">
                        <strong>💡 Sugestão IA:</strong> <span id="score-dica">Escreva algo para analisar...</span>
                    </div>
                    
                    <div class="flex-row" style="margin-top:12px; border-top: 1px solid rgba(255,255,255,0.05); padding-top:10px; justify-content: space-between; align-items:center;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label class="switch">
                                <input type="checkbox" onchange="toggleAutopilot('${campaignId}', this)">
                                <span class="slider round"></span>
                            </label>
                            <span style="font-size:0.75rem; opacity:0.8;">🤖 Modo Autopilot</span>
                        </div>
                        <div id="autopilot-status-${campaignId}" style="font-size:0.7rem; color:#10b981; visibility:hidden;">✨ IA Otimizando...</div>
                    </div>
                    
                    <div class="flex-row" style="margin-top:12px;">
                        <button class="ad-cta" disabled>${ad.cta || 'Saiba Mais'}</button>
                        <button class="btn-publish-meta" onclick="publishToMeta(this)">🚀 Publicar Escolhida</button>
                    </div>
                </div>
            </div>`;
        }

        // 2. INSTAGRAM POSTS (A/B)
        if (campaignData.instagram_posts) {
            html += `<h3>📱 Instagram Posts</h3><div class="cards-grid">`;
            campaignData.instagram_posts.forEach((post, i) => {
                html += `
                <div class="json-card instagram-card" data-index="${i}">
                    <h4>Post ${i+1}</h4>
                    <img src="${post.image_url || ''}" class="post-image" onerror="this.src='https://placehold.co/1024x1024/2c3e50/ffffff?text=Imagem'">
                    <label style="font-size:0.8em; opacity:0.7;">Legenda:</label>
                    <textarea class="draft-edit field-caption" rows="4">${post.caption || ''}</textarea>
                </div>`;
            });
            html += `</div>`;
        }

        // 3. EMAIL (A/B)
        if (campaignData.email) {
            const em = campaignData.email;
            html += `<h3>📧 E-mail Marketing</h3>`;
            html += `
            <div class="json-card email-card">
                <label style="font-size:0.8em; opacity:0.7;">Assunto:</label>
                <input type="text" class="draft-edit field-subject ab-content" data-a="${em.subject_a || em.subject || ''}" data-b="${em.subject_b || ''}" value="${em.subject_a || em.subject || ''}">
                <label style="font-size:0.8em; opacity:0.7; margin-top:10px;">Corpo do E-mail:</label>
                <textarea class="draft-edit field-body ab-content" data-a="${em.body_a || em.body || ''}" data-b="${em.body_b || ''}" rows="6">${em.body_a || em.body || ''}</textarea>
            </div>`;
        }

        // 4. VIDEO SCRIPT
        if (campaignData.video_script) {
            html += `<h3>🎬 Vídeo Gerado por IA</h3>`;
            html += `<div class="json-card video-card">`;
            
            if (campaignData.video_script.video_url) {
                html += `
                <div class="video-player-container">
                    <video controls loop playsinline class="generated-video" preload="metadata">
                        <source src="${campaignData.video_script.video_url}" type="video/mp4">
                        Seu navegador não suporta vídeo HTML5.
                    </video>
                    <a href="${campaignData.video_script.video_url}" download class="btn-download-video" target="_blank">⬇️ Baixar Vídeo</a>
                </div>`;
            } else if (campaignData.video_script.image_url) {
                html += `<img src="${campaignData.video_script.image_url}" class="post-image" alt="Thumbnail Vídeo" onerror="this.src='https://placehold.co/1024x1024/2c3e50/ffffff?text=Thumbnail'">`;
            }

            if (campaignData.video_script.audio_url) {
                html += `
                <div class="audio-player-container" style="margin: 15px 0; padding: 15px; background: rgba(139,92,246,0.1); border-radius: 12px; border: 1px solid rgba(139,92,246,0.3);">
                    <p style="margin-bottom: 8px; font-size: 0.9em; font-weight: 600;">🎙️ Narração em Áudio (Voz IA)</p>
                    <audio controls style="width: 100%; border-radius: 8px;">
                        <source src="${campaignData.video_script.audio_url}" type="audio/mpeg">
                    </audio>
                    <a href="${campaignData.video_script.audio_url}" download style="display:inline-block; margin-top:8px; font-size:0.8em; color: #8b5cf6;">⬇️ Baixar Áudio .mp3</a>
                </div>`;
            }
            
            html += `
                <div class="script-step"><span class="badge red">Gancho (0-3s)</span>
                    <textarea class="draft-edit field-hook" rows="2">${campaignData.video_script.hook || ''}</textarea>
                </div>
                <div class="script-step"><span class="badge blue">Conteúdo</span>
                    <textarea class="draft-edit field-video-body" rows="3">${campaignData.video_script.body || ''}</textarea>
                </div>
                <div class="script-step"><span class="badge green">CTA</span>
                    <textarea class="draft-edit field-video-cta" rows="2">${campaignData.video_script.cta || ''}</textarea>
                </div>
                <div class="flex-row" style="margin-top:15px;">`;
            
            if (campaignData.video_script.video_url) {
                html += `<button class="btn-publish-tiktok" onclick="publishToTikTok(this, '${campaignData.video_script.video_url}')">🎵 Publicar no TikTok Ads</button>`;
            }
            html += `<button class="btn-publish-meta" onclick="publishToMeta(this)">🚀 Publicar no Meta Ads</button>
                </div>
            </div>`;
        }

        html += '</div>';
        return html;
    }

    function renderMetricRow(label, id, colorClass = '') {
        return `
        <div class="metric-row">
            <div class="metric-info">
                <span>${label}</span>
                <span id="${id}-val">0</span>
            </div>
            <div class="metric-bar-bg">
                <div class="metric-bar-fill ${colorClass}" id="${id}-bar" style="width: 0%;"></div>
            </div>
        </div>`;
    }

    window.switchVariation = function(version, btn) {
        // Update active button
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update all fields with data attributes
        document.querySelectorAll('.ab-content').forEach(el => {
            const content = el.dataset[version] || el.dataset['a'];
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                el.value = content;
                if (el.classList.contains('field-primary-text')) {
                    debounceScore(el); // Rescore on switch
                }
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
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ texto: text })
            });
            const data = await res.json();
            
            if (data.score !== undefined) {
                // Update Main Circle
                const circle = document.getElementById('main-score-circle');
                const val = document.getElementById('main-score-val');
                const status = document.getElementById('main-score-status');
                
                if (circle) {
                    circle.style.setProperty('--progress', `${data.score * 3.6}deg`);
                    val.innerText = data.score;
                    status.innerText = data.status || "Bom";
                    status.style.color = data.score > 70 ? '#10b981' : '#f59e0b';
                }

                // Update Metrics
                updateMetric('score-clareza', data.metrics?.clareza);
                updateMetric('score-urgencia', data.metrics?.urgencia);
                updateMetric('score-emocao', data.metrics?.emocao);
                updateMetric('score-ctr', data.metrics?.ctr);
                updateMetric('score-espec', data.metrics?.especificidade);

                // Update Tip
                const tip = document.getElementById('score-dica');
                if (tip) tip.innerText = data.dica || "...";
            }
        } catch (e) {
            console.error("Score failed", e);
        }
    }

    function updateMetric(id, val) {
        const bar = document.getElementById(`${id}-bar`);
        const text = document.getElementById(`${id}-val`);
        if (bar && val !== undefined) {
            bar.style.width = `${val}%`;
            text.innerText = val;
        }
    }

    window.saveCampaignEdits = async function(campaignId, btn) {
        const container = btn.closest('.json-campaign-results');
        const campaignData = {
            instagram_posts: [],
            facebook_ad: {},
            email: {},
            video_script: {}
        };

        // Scrape Instagram Posts
        container.querySelectorAll('.instagram-card').forEach(card => {
            campaignData.instagram_posts.push({
                image_url: card.querySelector('img')?.src || '',
                caption: card.querySelector('.field-caption').value,
                hashtags: card.querySelector('.field-hashtags').value
            });
        });

        // Scrape Meta Ads
        const metaCard = container.querySelector('.facebook-card');
        if (metaCard) {
            campaignData.facebook_ad = {
                headline: metaCard.querySelector('.field-headline').value,
                primary_text: metaCard.querySelector('.field-primary-text').value,
                cta: metaCard.querySelector('.ad-cta').innerText
            };
        }

        // Scrape Email
        const emailCard = container.querySelector('.email-card');
        if (emailCard) {
            campaignData.email = {
                subject: emailCard.querySelector('.field-subject').value,
                body: emailCard.querySelector('.field-body').value
            };
        }

        // Scrape Video Script
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

        btn.disabled = true;
        btn.innerText = "⏳ Salvando...";

        try {
            const res = await fetch('/api/campaigns/update', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ id: campaignId, result_text: campaignData })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) {
            alert("Erro ao salvar alterações.");
        }
        btn.disabled = false;
        btn.innerText = "💾 Salvar Alterações no Banco";
    }

    window.publishToMeta = async function(btn) {
        if (!confirm("Deseja enviar esta campanha para o rascunho do seu Gerenciador de Anúncios da Meta?")) return;
        
        // Excellence: Scrape the edited text
        const container = btn.closest('.json-campaign-results');
        const metaCard = container.querySelector('.facebook-card');
        const headline = metaCard ? metaCard.querySelector('.field-headline').value : 'Campanha Copilot IA';

        try {
            const res = await fetch('/api/campaigns/publish_to_meta', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ action: 'publish', campaign_name: headline })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) {
            alert("Erro ao publicar anúncio.");
        }
    }

    window.publishToTikTok = async function(btn, videoUrl) {
        if (!confirm("Deseja enviar este vídeo para o TikTok Ads Manager?")) return;

        // Excellence: Scrape the edited text
        const container = btn.closest('.json-campaign-results');
        const videoCard = container.querySelector('.video-card');
        const headline = videoCard ? videoCard.querySelector('.field-hook').value : 'Campanha Copilot IA';

        try {
            const res = await fetch('/api/campaigns/publish_to_tiktok', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ video_url: videoUrl, headline: headline })
            });
            const data = await res.json();
            alert(data.mensagem || data.erro);
        } catch (e) {
            alert("Erro ao publicar no TikTok.");
        }
    }

    // ==========================================
    // LEAD HUNTER FRONTEND
    // ==========================================
    const btnBuscarLeads = document.getElementById('btnBuscarLeads');
    if (btnBuscarLeads) {
        btnBuscarLeads.addEventListener('click', async () => {
            const nicho = document.getElementById('leadNicho').value.trim();
            const cidade = document.getElementById('leadCidade').value.trim();
            
            if (!nicho || !cidade) {
                alert("Por favor, preencha o nicho e a cidade.");
                return;
            }

            const loadingLeads = document.getElementById('loadingLeads');
            const leadsListArea = document.getElementById('leadsListArea');
            const leadsTableBody = document.getElementById('leadsTableBody');

            loadingLeads.classList.remove('hidden');
            leadsListArea.classList.add('hidden');
            btnBuscarLeads.disabled = true;

            try {
                const res = await fetch('/api/leads/buscar', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ nicho, cidade })
                });
                const data = await res.json();
                
                leadsTableBody.innerHTML = '';
                if (data.leads && data.leads.length > 0) {
                    data.leads.forEach(lead => {
                        const zapClean = (lead.telefone || '').replace(/\D/g, '');
                        const zapLink = zapClean.length >= 10 ? `https://wa.me/55${zapClean}` : '#';
                        
                        leadsTableBody.innerHTML += `
                            <tr>
                                <td><strong>${lead.nome}</strong><br><small style="opacity:0.6;">Rating: ${lead.nota}</small></td>
                                <td><a href="${zapLink}" target="_blank" class="btn-whatsapp">🟢 ${lead.telefone || 'N/A'}</a></td>
                                <td><a href="${lead.site}" target="_blank" style="color:var(--accent); font-size:0.8em;">${lead.site ? 'Ver Website' : 'N/A'}</a></td>
                                <td>
                                    <div style="font-size:0.75rem; color:#f87171;"><strong>⚠️ Dor:</strong> ${lead.dor || 'Detectando...'}</div>
                                    <div style="font-size:0.75rem; color:#60a5fa;"><strong>💎 Oportunidade:</strong> ${lead.oportunidade}%</div>
                                </td>
                                <td>
                                    <button class="btn-prospect" onclick="prospectarLead('${lead.nome.replace(/'/g, "")}', '${lead.site}')">✨ Prospectar com IA</button>
                                </td>
                            </tr>
                        `;
                    });
                    leadsListArea.classList.remove('hidden');
                } else {
                    alert("Nenhum lead encontrado.");
                }
            } catch (e) {
                alert("Erro ao buscar leads.");
            } finally {
                loadingLeads.classList.add('hidden');
                btnBuscarLeads.disabled = false;
            }
        });
    }

    window.prospectarLead = async function(nome, site) {
        const modalMsg = prompt(`Gerando abordagem para ${nome}. Qual produto você quer oferecer?`, "Marketing Digital e Tráfego Pago");
        if (!modalMsg) return;

        try {
            const res = await fetch('/api/leads/pitch', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ nome, site, meu_produto: modalMsg })
            });
            const data = await res.json();
            
            if (data.pitch) {
                const finalPitch = encodeURIComponent(data.pitch);
                const zapUrl = `https://wa.me/?text=${finalPitch}`;
                window.open(zapUrl, '_blank');
            }
        } catch (e) {
            alert("Erro ao gerar pitch.");
        }
    };

    // ==========================================
    // ELITE FEATURES: CALENDAR & HOOKS
    // ==========================================
    const btnGerarCalendario = document.getElementById('btnGerarCalendario');
    if (btnGerarCalendario) {
        btnGerarCalendario.addEventListener('click', async () => {
            const calendarArea = document.getElementById('calendarArea');
            const calendarContent = document.getElementById('calendarContent');
            
            btnGerarCalendario.disabled = true;
            btnGerarCalendario.innerText = "📅 Gerando Plano Mestre...";

            try {
                const res = await fetch('/api/calendar/generate', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                
                if (data.calendario) {
                    calendarContent.innerHTML = '';
                    data.calendario.forEach(item => {
                        calendarContent.innerHTML += `
                            <div class="glass-panel" style="padding:15px; font-size:0.85rem; border-left:4px solid var(--accent);">
                                <div style="font-weight:700; color:var(--accent);">DIA ${item.dia}</div>
                                <div style="margin:5px 0;">${item.titulo}</div>
                                <div style="font-size:0.7rem; opacity:0.6;">${item.tipo} | ${item.objetivo}</div>
                            </div>
                        `;
                    });
                    calendarArea.classList.remove('hidden');
                }
            } catch (e) {
                alert("Erro ao gerar calendário.");
            } finally {
                btnGerarCalendario.disabled = false;
                btnGerarCalendario.innerText = "⚡ Gerar Plano de 30 Dias Agora";
            }
        });
    }

    // Carregar Hooks ao abrir a aba
    const hooksTab = document.querySelector('[data-tab="hooks"]');
    if (hooksTab) {
        hooksTab.addEventListener('click', async () => {
            const container = document.getElementById('hooksContainer');
            container.innerHTML = '<div class="spinner"></div>';
            
            try {
                const res = await fetch('/api/hooks/list', {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                
                container.innerHTML = '';
                data.hooks.forEach(h => {
                    container.innerHTML += `
                        <div class="glass-panel fade-in" style="padding:20px;">
                            <span class="tag" style="background:rgba(255,255,255,0.05); margin-bottom:10px;">${h.tipo}</span>
                            <p style="font-weight:600; font-size:1.1rem; line-height:1.4;">"${h.hook}"</p>
                            <button class="btn-secondary" style="margin-top:15px; width:100%;" onclick="copyToClipboard('${h.hook.replace(/'/g, "\\'")}')">📋 Copiar Hook</button>
                        </div>
                    `;
                });
            } catch (e) {}
        });
    }

    window.copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        alert("Copiado!");
    }

    // FUNNEL CLONER
    const btnClonarFunil = document.getElementById('btnClonarFunil');
    if (btnClonarFunil) {
        btnClonarFunil.addEventListener('click', async () => {
            const url = document.getElementById('funnelUrl').value;
            const resArea = document.getElementById('funnelResult');
            
            btnClonarFunil.disabled = true;
            btnClonarFunil.innerText = "🌪️ Desconstruindo Funil...";
            
            try {
                const res = await fetch('/api/funnel/clone', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                resArea.innerHTML = converterMarkdown(data.analise);
                resArea.classList.remove('hidden');
            } catch (e) {
                alert("Erro ao clonar funil.");
            } finally {
                btnClonarFunil.disabled = false;
                btnClonarFunil.innerText = "🌪️ Analisar e Clonar";
            }
        });
    }

    // VIRAL MODE
    const btnViralCheck = document.getElementById('btnViralCheck');
    if (btnViralCheck) {
        btnViralCheck.addEventListener('click', async () => {
            const content = document.getElementById('viralContent');
            btnViralCheck.innerText = "⚡ Mapeando tendências...";
            
            try {
                const res = await fetch('/api/viral/trends', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                const data = await res.json();
                
                content.innerHTML = '<h3 style="margin-top:20px;">🔥 Tendências Detectadas (24h)</h3>';
                data.trends.forEach(t => {
                    content.innerHTML += `
                        <div class="glass-panel" style="margin-top:10px; border-left:4px solid #f59e0b;">
                            <strong>${t.tema}</strong>
                            <p style="font-size:0.85rem; opacity:0.8;">${t.oportunidade}</p>
                        </div>
                    `;
                });
                content.classList.remove('hidden');
            } catch (e) {} finally {
                btnViralCheck.innerText = "🔥 Detectar Tendências Agora";
            }
        });
    }

    // MARKETPLACE LOGIC
    window.loadMarketplace = async function() {
        const grid = document.getElementById('marketGrid');
        grid.innerHTML = '<div class="spinner"></div>';
        
        try {
            const res = await fetch('/api/marketplace/list');
            const data = await res.json();
            
            grid.innerHTML = '';
            data.templates.forEach(t => {
                grid.innerHTML += `
                    <div class="glass-panel fade-in" style="padding:20px; display:flex; flex-direction:column; gap:10px;">
                        <div style="font-size:0.7rem; color:var(--accent); text-transform:uppercase; font-weight:700;">${t.niche}</div>
                        <h4 style="margin:0;">${t.title}</h4>
                        <div style="font-size:1.2rem; font-weight:700; margin:10px 0;">€ ${t.price}</div>
                        <div style="font-size:0.8rem; opacity:0.6;">Autor: ${t.author_name || 'MKT Team'}</div>
                        <button class="btn-primary" style="margin-top:auto;" onclick="buyTemplate('${t.id}')">🛒 Clonar Agora</button>
                    </div>
                `;
            });
        } catch (e) { grid.innerHTML = "Erro ao carregar mercado."; }
    }

    window.buyTemplate = (id) => {
        alert("Simulação de Checkout Stripe: Processando pagamento...");
        setTimeout(() => alert("Template Clonado com Sucesso! Verifique suas campanhas."), 1500);
    }

    const marketTab = document.querySelector('[data-tab="marketplace"]');
    if (marketTab) {
        marketTab.addEventListener('click', loadMarketplace);
    }

    // COMPETITOR RADAR
    const btnWatchCompetitor = document.getElementById('btnWatchCompetitor');
    if (btnWatchCompetitor) {
        btnWatchCompetitor.addEventListener('click', async () => {
            const url = document.getElementById('compUrl').value;
            const log = document.getElementById('radarLog');
            const area = document.getElementById('radarTimeline');
            
            btnWatchCompetitor.innerText = "📡 Sincronizando Radar...";
            
            try {
                const res = await fetch('/api/competitors/watch', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();
                
                alert(data.status);
                area.classList.remove('hidden');
                log.innerHTML = `
                    <div class="glass-panel" style="border-left:4px solid #3b82f6;">
                        <strong>📡 Radar Ativo: ${url}</strong>
                        <p style="font-size:0.8rem; margin-top:5px;">Aguardando alterações no site ou novos anúncios...</p>
                    </div>
                `;
            } catch (e) {
                alert("Erro ao ativar radar.");
            } finally {
                btnWatchCompetitor.innerText = "📡 Ativar Radar";
            }
        });
    }

    window.toggleAutopilot = function(id, checkbox) {
        const status = document.getElementById(`autopilot-status-${id}`);
        if (checkbox.checked) {
            status.style.visibility = 'visible';
            alert("🤖 Modo Autopilot Ativado! A IA irá monitorar as métricas e otimizar este anúncio automaticamente a cada 24h.");
        } else {
            status.style.visibility = 'hidden';
        }
    }

    window.generateAgencyProposal = async function(campaignId) {
        try {
            const res = await fetch(`/api/campaigns/proposal/${campaignId}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const data = await res.json();
            
            if (data.html) {
                const win = window.open("", "_blank");
                win.document.write(data.html);
                win.document.close();
            } else {
                alert(data.erro || "Erro ao gerar proposta.");
            }
        } catch (e) {
            alert("Erro de conexão.");
        }
    }
});
