/**
 * MKTPilot — modules.js
 * Cliente JS para os 6 módulos premium.
 * Inclui este ficheiro na tua página principal e chama MKTPilot.*()
 */

const MKTPilot = (() => {
  const BASE = "/api/modules";
  const headers = { "Content-Type": "application/json" };

  async function post(path, body) {
    // Busca o token do localStorage (padrão do nosso app)
    const token = localStorage.getItem('sb_token');
    const authHeaders = { ...headers };
    if (token) authHeaders["Authorization"] = `Bearer ${token}`;

    const r = await fetch(BASE + path, { 
        method: "POST", 
        headers: authHeaders, 
        body: JSON.stringify(body) 
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function get(path, params = {}) {
    const token = localStorage.getItem('sb_token');
    const authHeaders = { ...headers };
    if (token) authHeaders["Authorization"] = `Bearer ${token}`;

    const qs = new URLSearchParams(params).toString();
    const r = await fetch(BASE + path + (qs ? "?" + qs : ""), {
        headers: authHeaders
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  // ── 1. SCORE ────────────────────────────────────────────────────────────────
  const Score = {
    avaliar: (copy) => post("/score", { copy }),
    melhorar: (copy, target_score = 90) => post("/score/improve", { copy, target_score }),
    ligarTextarea(textareaId, scoreNumId, onUpdate, debounceMs = 500) {
      let timer;
      const el = document.getElementById(textareaId);
      if (!el) return;
      el.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(async () => {
          try {
            const result = await Score.avaliar(this.value);
            if (scoreNumId) {
                const scoreEl = document.getElementById(scoreNumId);
                if (scoreEl) scoreEl.textContent = result.score;
            }
            if (onUpdate) onUpdate(result);
          } catch(e) { console.error("Erro Score:", e); }
        }, debounceMs);
      });
    },
  };

  // ── 2. FUNIL ────────────────────────────────────────────────────────────────
  const Funil = {
    analisar: (url, meu_produto) => post("/funil/analisar", { url, meu_produto }),
  };

  // ── 3. CALENDÁRIO ───────────────────────────────────────────────────────────
  const Calendario = {
    gerar: (opts) => post("/calendario/gerar", opts),
    renderGrid(dias, gridId) {
      const grid = document.getElementById(gridId);
      if (!grid) return;
      grid.innerHTML = "";
      const cores = {
        ig: "#fce7f3", fb: "#dbeafe", tt: "#f3e8ff",
        email: "#fef3c7", tiktok: "#f3e8ff",
      };
      const textCores = {
        ig: "#9d174d", fb: "#1e40af", tt: "#6b21a8",
        email: "#92400e", tiktok: "#6b21a8",
      };
      dias.forEach((d) => {
        const canal = d.canal.toLowerCase().replace("instagram","ig").replace("facebook","fb");
        const bg    = cores[canal]     || "#f1f5f9";
        const tc    = textCores[canal] || "#334155";
        const card  = document.createElement("div");
        card.className = "cal-day";
        card.style.cssText = `border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:12px;min-height:100px;background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);`;
        card.innerHTML = `
          <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.5);margin-bottom:8px;">Dia ${d.dia}</div>
          <span style="font-size:10px;font-weight:600;padding:4px 8px;border-radius:6px;
                       background:${bg};color:${tc};">${d.canal.toUpperCase()} · ${d.tipo}</span>
          <div style="font-size:13px;margin-top:10px;line-height:1.4;color:white;font-weight:500;">${d.titulo}</div>
        `;
        card.title = d.copy_curto || "";
        grid.appendChild(card);
      });
    },
  };

  // ── 4. HOOKS ────────────────────────────────────────────────────────────────
  const Hooks = {
    listar: (params = {}) => get("/hooks/listar", params),
    adaptar: (hook, produto, nicho) => post("/hooks/adaptar", { hook, produto, nicho }),
  };

  // ── 5. A/B GENERATOR ────────────────────────────────────────────────────────
  const AB = {
    gerar: (copy, produto = "", objetivo = "conversão") =>
      post("/ab/gerar", { copy, produto, objetivo }),
    exportarMeta: (variantes, orcamento = 10, duracao_dias = 7) =>
      post("/ab/exportar-meta", { variantes, orcamento, duracao_dias }),
    async exportarEMostrar(variantes, orcamento, duracao) {
      const payload = await AB.exportarMeta(variantes, orcamento, duracao);
      const blob    = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url     = URL.createObjectURL(blob);
      const a       = document.createElement("a");
      a.href        = url;
      a.download    = `mktpilot_ab_${payload.campanha}.json`;
      a.click();
      return payload;
    },
  };

  // ── 6. VIRAL EM 24H ─────────────────────────────────────────────────────────
  const Viral = {
    tendencias: (params = {}) => get("/viral/tendencias", params),
    criarCampanha: (tendencia, produto, nicho) =>
      post("/viral/campanha", { tendencia, produto, nicho }),
  };

  return { Score, Funil, Calendario, Hooks, AB, Viral };
})();
