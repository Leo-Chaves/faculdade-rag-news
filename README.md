# 📰 RAG News — Chat com Notícias

🔗 **Acesse o projeto online:** [https://ragnewsbbc.netlify.app/](https://ragnewsbbc.netlify.app/)

Projeto de faculdade: sistema de **Retrieval-Augmented Generation (RAG)** para responder perguntas sobre notícias atuais, usando **LangChain**, **LangGraph**, **OpenRouter** e **PGVector (Supabase)**.

---

## 🗂️ Estrutura do Monorepo

```
faculdade-rag-news/
├── backend/          # FastAPI + LangChain + LangGraph + OpenRouter
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
└── frontend/         # Vue 3 + Tailwind CSS
    ├── src/
    │   ├── App.vue
    │   ├── main.js
    │   ├── style.css
    │   └── components/
    │       ├── ChatSidebar.vue
    │       └── ChatMessage.vue
    ├── index.html
    └── vite.config.js
```

---

## ⚙️ Backend — Setup

### 1. Pré-requisitos
- Python 3.11+
- Chave de API no [OpenRouter](https://openrouter.ai/keys)
- Projeto no [Supabase](https://supabase.com) com extensão **pgvector** habilitada

### 2. Configurar variáveis de ambiente
```bash
cd backend
cp .env.example .env
# Edite o .env com sua OPENROUTER_API_KEY e credenciais do Supabase
```

### 3. Instalar dependências e rodar
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Rotas da API

| Método | Rota      | Descrição                                                                         |
|--------|-----------|-----------------------------------------------------------------------------------|
| GET    | `/`       | Health check e modelos ativos                                                     |
| POST   | `/ingest` | Busca notícias da BBC, gera embeddings e salva no PGVector                       |
| POST   | `/chat`   | Recebe pergunta e gera resposta via LangGraph + OpenRouter                        |
| POST   | `/reset`  | Reseta tabelas do PGVector no Supabase (usar se trocar o modelo de embeddings)   |

---

## 🎨 Frontend — Setup

```bash
cd frontend
npm install
npm run dev
# Acesse: http://localhost:5173
```

> O Vite está configurado com proxy: chamadas para `/chat` e `/ingest`
> são redirecionadas automaticamente para `http://localhost:8000`.

---

## 🚀 Deploy no Render

### Backend
1. Crie um **Web Service** apontando para `/backend`
2. Runtime: **Docker**
3. Adicione as variáveis de ambiente (`OPENROUTER_API_KEY`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`)

### Frontend
1. Crie um **Static Site** apontando para `/frontend`
2. Build command: `npm run build`
3. Publish directory: `dist`

---

## 🛠️ Stack

| Camada       | Tecnologia                                                   |
|--------------|--------------------------------------------------------------|
| LLM          | OpenRouter (`nvidia/nemotron-3.5-super-vl:free`)             |
| Embeddings   | OpenRouter (`nvidia/llama-nemotron-embed-vl-1b-v2:free`)     |
| Vector DB    | PGVector via Supabase                                        |
| Orquestração | LangChain + LangGraph                                        |
| API          | FastAPI + Uvicorn                                            |
| Frontend     | Vue 3 · Tailwind CSS · Vite                                  |
