# RAG News

🔗 **Acesse o projeto online:** [https://ragnewsbbc.netlify.app/](https://ragnewsbbc.netlify.app/)

Projeto universitário com login por e-mail, manchetes da BBC e chat em português. Em **Manchetes**, use **Ler na BBC** para abrir a matéria original ou **Perguntar ao chat** para conversar usando o título e o resumo daquele item do RSS. O chat geral consulta o índice no pgvector.

---

## 🗂️ Estrutura do Monorepo

```
faculdade-rag-news/
├── backend/          # FastAPI + LangChain + LangGraph + OpenRouter
│   ├── main.py
│   ├── auth.py
│   ├── news.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
└── frontend/         # Vue 3 + Tailwind CSS
    ├── src/
    │   ├── App.vue
    │   ├── main.js
    │   ├── style.css
    │   └── components/
    │       ├── AuthForm.vue
    │       ├── ChatMessage.vue
    │       └── NewsCard.vue
    ├── index.html
    └── vite.config.js
```

---

## ⚙️ Backend — Setup

### 1. Pré-requisitos
- Python 3.11+
- Chave de API no [OpenRouter](https://openrouter.ai/keys)
- Projeto no [Supabase](https://supabase.com) com extensão **pgvector** habilitada
- Node.js 24 para compilar o frontend

### 2. Configurar variáveis de ambiente
```bash
cd backend
cp .env.example .env
# Preencha as variáveis usando o .env.example como referência.
```

No Supabase, habilite o provedor **Email** em Authentication. Use a URL do projeto e a chave **Publishable** (`sb_publishable_…`) para `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`. Em **URL Configuration**, informe a URL do frontend e autorize `http://localhost:5173` e o domínio publicado como URLs de redirecionamento. Com confirmação por e-mail ativa, o cadastro informa que o usuário deve verificar a caixa de entrada.

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
| GET    | `/auth/config` | URL e chave pública para iniciar o Supabase Auth |
| GET    | `/news` | Manchetes da BBC por data de publicação, com cache de cinco minutos |
| POST   | `/ingest` | Atualiza o índice do pgvector com os feeds da BBC |
| POST   | `/chat` | Recebe `question` e, opcionalmente, `article_url`. Retorna resposta e matérias consultadas |
| POST   | `/reset` | Recria o índice na próxima ingestão. A chamada exige o cabeçalho `X-Admin-Key` correspondente a `RAG_ADMIN_KEY` |

As rotas `/news`, `/ingest` e `/chat` exigem `Authorization: Bearer <access_token>` do Supabase Auth. Para popular o índice, entre no site e use **Chat → Atualizar índice de busca**.

---

## 🎨 Frontend — Setup

```bash
cd frontend
npm ci
npm run dev
# Acesse: http://localhost:5173
```

Durante o desenvolvimento, o Vite encaminha as chamadas para a API local em `http://127.0.0.1:8000`.

---

## 🚀 Publicação no Render e no Netlify

### Backend
1. Crie um **Web Service** apontando para `/backend`
2. Runtime: **Docker**
3. Configure as variáveis de OpenRouter, conexão com o banco e Supabase Auth descritas em [backend/.env.example](backend/.env.example).
4. Em `CORS_ORIGINS`, informe o domínio do frontend publicado. Inclua a origem da prévia se for testá-la.

### Frontend
1. No Netlify, configure `frontend` como diretório base e selecione a branch a publicar.
2. Defina `VITE_API_URL` com a URL HTTPS do backend no Render antes da compilação.
3. Use `npm run build` como comando de build e `dist` como diretório de publicação.
4. Abra o site, faça login e teste uma manchete com **Perguntar ao chat**. No chat geral, atualize o índice antes da primeira consulta.

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
