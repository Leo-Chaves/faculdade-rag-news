# 📰 RAG News — Chat com Notícias

Projeto de faculdade: sistema de **Retrieval-Augmented Generation (RAG)** para responder perguntas sobre notícias atuais, usando **LangChain**, **Groq** e **PGVector (Supabase)**.

---

## 🗂️ Estrutura do Monorepo

```
faculdade-rag-news/
├── backend/          # FastAPI + LangChain + Groq
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
- Conta no [Groq](https://console.groq.com) (chave grátis)
- Projeto no [Supabase](https://supabase.com) com extensão **pgvector** habilitada

### 2. Configurar variáveis de ambiente
```bash
cd backend
cp .env.example .env
# Edite o .env com suas chaves
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

| Método | Rota      | Descrição                                       |
|--------|-----------|-------------------------------------------------|
| GET    | `/`       | Health check                                    |
| POST   | `/ingest` | Recebe URLs RSS e salva chunks no PGVector      |
| POST   | `/chat`   | Recebe pergunta e retorna resposta via Groq RAG |

#### Exemplo — `/ingest`
```json
POST /ingest
{
  "urls": [
    "https://feeds.bbci.co.uk/portuguese/rss.xml",
    "https://g1.globo.com/dynamo/tecnologia/rss2.xml"
  ]
}
```

#### Exemplo — `/chat`
```json
POST /chat
{ "question": "aconteceu algo no brasil?" }
```

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
3. Adicione as variáveis de ambiente (`GROQ_API_KEY`, `DATABASE_URL`)

### Frontend
1. Crie um **Static Site** apontando para `/frontend`
2. Build command: `npm run build`
3. Publish directory: `dist`
4. Defina a variável `VITE_API_URL` se necessário

---

## 🛠️ Stack

| Camada     | Tecnologia                          |
|------------|-------------------------------------|
| LLM        | Groq — `llama3-8b-8192`             |
| Embeddings | HuggingFace `all-MiniLM-L6-v2`      |
| Vector DB  | PGVector via Supabase               |
| Orquestração | LangChain (RetrievalQA)           |
| API        | FastAPI + Uvicorn                   |
| Frontend   | Vue 3 · Tailwind CSS · Vite         |
