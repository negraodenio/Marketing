import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';

// Carrega o conteúdo do app.js
const appJsCode = fs.readFileSync(path.resolve(__dirname, './app.js'), 'utf8');

describe('MKTPilot Elite - Frontend Tests', () => {
  let dom;

  beforeEach(() => {
    // Simula o HTML necessário para o app.js não quebrar
    document.body.innerHTML = `
      <div id="authScreen"></div>
      <div id="appScreen" class="hidden">
        <span id="userEmailDisplay"></span>
        <button id="btnLogout"></button>
        <button id="btnConnectMeta"></button>
        <button id="btnConnectTikTok"></button>
        <div id="connectionStatus"></div>
        <ul class="nav-links"><li data-tab="wizard"></li></ul>
        <div id="tab-wizard" class="tab-pane"></div>
      </div>
      <div id="lp-login">
        <input id="emailInput" value="">
        <input id="passInput" value="">
        <p id="authError" class="hidden"></p>
        <button id="btnLogin"></button>
        <button id="btnRegister"></button>
      </div>
    `;

    // Mock do fetch no mesmo contexto usado pelo script no navegador
    window.fetch = vi.fn();
    global.fetch = window.fetch;
    
    // Mock do localStorage
    const localStorageMock = (() => {
      let store = {};
      return {
        getItem: vi.fn(key => store[key] || null),
        setItem: vi.fn((key, value) => { store[key] = value.toString(); }),
        removeItem: vi.fn(key => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; })
      };
    })();
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });

    // Executa o código do app.js integralmente
    const script = document.createElement('script');
    script.textContent = appJsCode;
    document.body.appendChild(script);

    // Dispara o evento DOMContentLoaded manualmente
    window.document.dispatchEvent(new Event('DOMContentLoaded', {
      bubbles: true,
      cancelable: true
    }));
  });

  it('deve exibir a tela de login se não houver token no localStorage', () => {
    const authScreen = document.getElementById('authScreen');
    const appScreen = document.getElementById('appScreen');
    expect(authScreen.classList.contains('hidden')).toBe(false);
    expect(appScreen.classList.contains('hidden')).toBe(true);
  });

  it('deve realizar login com sucesso via Modo Demo', async () => {
    // Configura inputs
    document.getElementById('emailInput').value = 'demo@mktpilot.io';
    document.getElementById('passInput').value = 'demo123';

    // Mock da resposta do servidor
    fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'test-token', user: 'demo@mktpilot.io' })
    });

    await window.handleAuth('/api/auth/login');

    expect(localStorage.setItem).toHaveBeenCalledWith('sb_token', 'test-token');
    expect(document.getElementById('authScreen').classList.contains('hidden')).toBe(true);
    expect(document.getElementById('appScreen').classList.contains('hidden')).toBe(false);
  });

  it('deve alternar entre as abas corretamente', () => {
    const tabLink = document.querySelector('[data-tab="wizard"]');
    tabLink.click();
    expect(tabLink.classList.contains('active')).toBe(true);
  });
});
