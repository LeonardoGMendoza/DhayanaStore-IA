# Dhayana Store IA

Os agentes de IA da loja da Dhayana (Trujillo, Peru), que vende pelo Facebook Marketplace e WhatsApp.
O catálogo público fica em [MarketplaceDhayanaNicol](https://github.com/LeonardoGMendoza/MarketplaceDhayanaNicol).

**Regra de ouro (as Leis do Enxame do Nexus):** a IA prepara, a vendedora decide. Preço é calculado pelo código, nunca pela IA.

## O enxame da loja

| Agente | Faz | Status |
|---|---|---|
| ✍️ Redator | Texto do fornecedor → anúncio do Marketplace + bloco do catálogo, com preço e ganho | ✅ v0.1 |
| 📦 Despachante | Painel de pedidos: status, endereço, pagamento, mensagens ao cliente | próximo |
| 💬 Atendente | Responde no WhatsApp com base no catálogo (RAG), passa para a Dhayana quando precisa | planejado |
| 💰 Cobrador | Lembra os repasses do motorizado | planejado |
| 📊 Analista | Resumo do dia; depois ML (risco de desistência, produtos que vendem) | planejado |

## Rodar no computador

**Backend (Python + FastAPI + IA da Oracle, a mesma do VinaCare):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # preencha com as chaves da OCI do VinaCare
uvicorn app.main:app --reload --port 8000
```
Teste: http://localhost:8000/health → `"ia": true` quando a OCI estiver configurada.

Testes: `pip install pytest` e `python -m pytest -q tests`

**Frontend (React + Vite + TypeScript):**
```powershell
cd frontend
npm install
npm run dev
```
Abre em http://127.0.0.1:5173

## Estrutura
```
backend/app/
├── main.py      API (FastAPI): /health, /redator — com limite de pedidos por IP
├── ia.py        Conexão com a OCI Generative AI (Cohere)
├── redator.py   Agente Redator: prompt, validação do JSON, preço, id/slug
└── config.py    Lê o .env
frontend/src/
└── App.tsx      Tela do Redator
```
