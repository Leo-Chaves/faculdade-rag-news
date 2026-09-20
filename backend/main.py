import os
import urllib.parse
from pathlib import Path
# pyrefly: ignore [missing-import]
import feedparser
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter
# pyrefly: ignore [missing-import]
from langchain_huggingface import HuggingFaceEmbeddings
# pyrefly: ignore [missing-import]
from langchain_postgres import PGVector as PGVectorStore
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_core.output_parsers import StrOutputParser
# pyrefly: ignore [missing-import]
from langchain_core.runnables import RunnablePassthrough


def _load_dotenv_safe():
    """
    Carrega o .env detectando automaticamente o encoding pelo BOM.
    O VS Code pode salvar arquivos como UTF-16 LE/BE, o que quebra
    o python-dotenv padrao (UTF-8). Esta funcao corrige isso.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        load_dotenv()
        return

    raw = env_path.read_bytes()

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        enc = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    else:
        enc = "utf-8"

    load_dotenv(dotenv_path=env_path, encoding=enc)


_load_dotenv_safe()

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG News API",
    description="API de RAG para notícias usando Groq + PGVector",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# BBC RSS Feeds (fixos no backend)
# ---------------------------------------------------------------------------

BBC_RSS_URLS: List[str] = [
    "http://feeds.bbci.co.uk/news/rss.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "http://feeds.bbci.co.uk/news/business/rss.xml",
    "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
]

# ---------------------------------------------------------------------------
# Shared resources (lazy-initialized)
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
COLLECTION_NAME = "rag_news"

_embeddings: HuggingFaceEmbeddings | None = None
_vector_store: PGVectorStore | None = None


def _build_database_url() -> str:
    """
    Constrói a DATABASE_URL a partir de variáveis individuais.
    Isso garante que a senha seja URL-encoded corretamente,
    evitando UnicodeDecodeError com caracteres especiais (ã, @, #, etc.).

    Variáveis esperadas no .env:
        DB_USER     - usuário do banco (ex: postgres)
        DB_PASSWORD - senha (pode ter qualquer caractere)
        DB_HOST     - host do Supabase (ex: db.xxxx.supabase.co)
        DB_PORT     - porta (padrão: 5432)
        DB_NAME     - nome do banco (padrão: postgres)
    """
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "postgres")

    if not host or not password:
        return ""

    # urllib.parse.quote garante encoding seguro de qualquer caractere
    encoded_password = urllib.parse.quote(password, safe="")
    # Usa psycopg3 (driver moderno) — sem o bug de encoding do psycopg2
    # sslmode=require obrigatorio no Supabase
    return f"postgresql+psycopg://{user}:{encoded_password}@{host}:{port}/{name}?sslmode=require"


DATABASE_URL = _build_database_url()


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def get_vector_store() -> PGVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = PGVectorStore(
            embeddings=get_embeddings(),
            collection_name=COLLECTION_NAME,
            connection=DATABASE_URL,
            use_jsonb=True,
        )
    return _vector_store


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_and_chunk_rss(urls: List[str]):
    """Busca artigos dos feeds RSS e retorna (chunks, metadatas)."""
    all_docs: List[str] = []
    metadata_list: List[dict] = []

    for url in urls:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", url)
            published = entry.get("published", "")

            content = f"Título: {title}\n\nResumo: {summary}"
            if content.strip():
                all_docs.append(content)
                metadata_list.append(
                    {"source": link, "title": title, "published": published}
                )

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks: List[str] = []
    chunk_metadata: List[dict] = []

    for doc, meta in zip(all_docs, metadata_list):
        parts = splitter.split_text(doc)
        chunks.extend(parts)
        chunk_metadata.extend([meta] * len(parts))

    return chunks, chunk_metadata, len(all_docs)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "RAG News API is running"}


@app.post("/ingest", tags=["Ingestion"])
def ingest():
    """
    Busca os feeds RSS da BBC (fixos no backend), faz chunking
    e persiste os vetores no PGVector.
    """
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL não configurada.")

    chunks, chunk_metadata, total_articles = _fetch_and_chunk_rss(BBC_RSS_URLS)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="Nenhum conteúdo válido encontrado nos feeds da BBC.",
        )

    vs = get_vector_store()
    vs.add_texts(texts=chunks, metadatas=chunk_metadata)

    return {
        "message": "Ingestão dos feeds da BBC concluída com sucesso.",
        "feeds_processados": len(BBC_RSS_URLS),
        "articles_processed": total_articles,
        "chunks_stored": len(chunks),
    }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(body: ChatRequest):
    """
    Recebe uma pergunta, busca contexto relevante no PGVector e
    retorna a resposta gerada pelo Groq (llama3-8b-8192).
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY nao configurada.")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Banco nao configurado. Defina DB_HOST e DB_PASSWORD no .env.")

    vs = get_vector_store()

    # Busca documentos relevantes
    docs = vs.similarity_search(body.question, k=5)
    context = "\n\n".join(doc.page_content for doc in docs)

    # Extrai fontes unicas
    sources = list(
        {
            doc.metadata.get("source", "")
            for doc in docs
            if doc.metadata.get("source")
        }
    )

    # Prompt + LLM via LCEL
    prompt = ChatPromptTemplate.from_template(
        """Voce e um assistente especializado em noticias da BBC. """
        """Use o contexto abaixo para responder a pergunta do usuario de forma clara e objetiva em portugues.\n\n"""
        """Contexto:\n{context}\n\nPergunta: {question}\n\nResposta:"""
    )

    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="openai/gpt-oss-20b",
        temperature=0.3,
    )

    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context, "question": body.question})

    return ChatResponse(answer=answer, sources=sources)
