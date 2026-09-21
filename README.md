# 📰 RAG News — Chat com Notícias

🔗 **Acesse o projeto online:** https://ragnewsbbc.netlify.app/

Projeto de faculdade: sistema de **Retrieval-Augmented Generation (RAG)** para responder perguntas sobre notícias atuais, utilizando **LangGraph**, **Groq**, **PGVector (Supabase)** e **FastAPI**.

---

## 🗂️ Estrutura do Monorepo

```text
faculdade-rag-news/
├── backend/
│   ├── main.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── health.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── chat.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── rag_service.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
└── frontend/
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

- Python 3.11 ou 3.12
- Conta no Groq para obtenção da API Key
- Projeto no Supabase com a extensão **pgvector** habilitada

> Recomenda-se Python 3.12 para execução local do projeto.

### 2. Configurar variáveis de ambiente

```bash
cd backend

cp .env.example .env
```

Edite o arquivo `.env` com as credenciais necessárias para o projeto.

### 3. Criar e ativar o ambiente virtual

```bash
python -m venv .venv
```

#### Windows

```bash
.venv\Scripts\activate
```

#### Linux / macOS / GitHub Codespaces

```bash
source .venv/bin/activate
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Executar a API

```bash
uvicorn main:app --reload --port 8000
```

A documentação interativa do FastAPI pode ser acessada em:

```text
http://localhost:8000/docs
```

---

## 🔌 Rotas da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Verifica se a API está em execução |
| GET | `/health` | Health check da API |
| POST | `/ingest` | Processa os feeds RSS configurados e armazena os chunks no banco vetorial |
| POST | `/chat` | Recebe uma pergunta e retorna a resposta do sistema RAG |

### Health Check

```http
GET /health
```

Resposta:

```json
{
  "status": "ok"
}
```

---

## 📥 Ingestão de notícias

### `POST /ingest`

Executa a ingestão dos feeds RSS configurados no backend.

```http
POST /ingest
```

O processo de ingestão realiza a coleta das notícias, preparação do conteúdo, divisão em chunks e armazenamento das representações vetoriais no PGVector.

Os feeds RSS utilizados são configurados diretamente no backend.

---

## 💬 Chat

### `POST /chat`

Recebe uma pergunta e encaminha a requisição para o fluxo RAG.

### Request

```json
{
  "question": "What are the latest technology news?"
}
```

O campo `question`:

- é obrigatório;
- deve possuir no mínimo 1 caractere;
- aceita no máximo 2000 caracteres.

### Response

```json
{
  "answer": "Resposta gerada pelo sistema RAG.",
  "sources": [
    "https://..."
  ]
}
```

A propriedade `sources` contém as fontes recuperadas pelo sistema que foram utilizadas como contexto para a resposta.

### Validação

Requisições inválidas retornam automaticamente erro HTTP `422`.

Exemplo inválido:

```json
{
  "question": ""
}
```

---

## 🧠 Fluxo RAG

De forma simplificada, o sistema segue o seguinte fluxo:

```text
Feeds RSS
    ↓
Coleta das notícias
    ↓
Limpeza e preparação
    ↓
Chunking
    ↓
Embeddings
    ↓
PGVector / Supabase
    ↓
Pergunta do usuário
    ↓
Recuperação de documentos relevantes
    ↓
Montagem do contexto
    ↓
LangGraph
    ↓
Groq
    ↓
Resposta + fontes
```

O **LangGraph** é utilizado para organizar e executar o fluxo do RAG, enquanto o modelo externo é utilizado na etapa de geração da resposta.

---

## 🎨 Frontend — Setup

```bash
cd frontend

npm install

npm run dev
```

Por padrão, o frontend do Vite fica disponível em:

```text
http://localhost:5173
```

O frontend realiza chamadas para a API responsável pelo chat e pela integração com o sistema RAG.

---

## 🚀 Deploy

### Backend — Render

1. Crie um **Web Service** apontando para `/backend`.
2. Utilize o **Dockerfile** do backend.
3. Configure as variáveis de ambiente necessárias, incluindo:
   - `GROQ_API_KEY`
   - configurações do banco de dados/Supabase.

### Frontend

O frontend pode ser publicado como aplicação estática.

Para gerar o build:

```bash
npm run build
```

O diretório de saída padrão do Vite é:

```text
dist
```

Configure `VITE_API_URL` quando necessário para apontar o frontend para a URL do backend publicado.

---

## 🛠️ Stack

| Camada | Tecnologia |
|--------|------------|
| LLM | Groq — `openai/gpt-oss-20b` |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector DB | PGVector via Supabase |
| Orquestração | LangGraph |
| API | FastAPI + Uvicorn |
| Frontend | Vue 3 · Tailwind CSS · Vite |

---

## 📚 Documentação da API

Com o backend em execução, o FastAPI disponibiliza automaticamente a documentação Swagger em:

```text
/docs
```

Nela é possível visualizar e testar os endpoints da API diretamente pelo navegador.