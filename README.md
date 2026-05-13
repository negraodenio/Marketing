# Antigravity Marketing Orchestrator

Este é o cérebro central (construído em Python) para gerenciar o ecossistema de marketing sem a necessidade do n8n.

## Como configurar:

1. **Instale o Python** na sua máquina (se ainda não tiver).
2. **Crie um ambiente virtual (opcional mas recomendado):**
   ```bash
   python -m venv venv
   # Ativar no Windows:
   venv\Scripts\activate
   # Ativar no Mac/Linux:
   source venv/bin/activate
   ```
3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure as chaves de API:**
   - Faça uma cópia do arquivo `.env.example` e renomeie para `.env`.
   - Preencha as chaves verdadeiras (como a do Buffer).
5. **Rode a aplicação:**
   ```bash
   python app.py
   ```

## Testando os Webhooks Localmente

Com o servidor rodando em um terminal, abra outro terminal e rode este comando para simular a chegada de um lead:

```bash
curl -X POST http://localhost:5000/webhook/novo-lead \
-H "Content-Type: application/json" \
-d '{"nome": "Maria Silva", "email": "maria@email.com"}'
```
