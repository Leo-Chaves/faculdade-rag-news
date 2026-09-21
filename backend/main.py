import os
import gc
import logging
import urllib.parse
from pathlib import Path
# pyrefly: ignore [missing-import]
import feedparser
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, TypedDict, Literal
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Reduz uso de memória do PyTorch (essencial pro Render free 512MB)
# ---------------------------------------------------------------------------
try:
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    logger.info("PyTorch configurado com 1 thread para economia de RAM.")
except Exception:
    pass

app = FastAPI(
    title="RAG News API",
    description="API de RAG para notícias usando Groq + PGVector",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
# Shared resources
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
        logger.info("Carregando modelo de embeddings...")
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        # Libera lixo do carregamento do PyTorch
        gc.collect()
        logger.info("Modelo de embeddings carregado com sucesso.")
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
# Startup: pré-carrega o modelo para evitar OOM durante requests
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_preload():
    """
    Pré-carrega o modelo de embeddings no startup ao invés de
    carregar na primeira request. No Render free (512MB), carregar
    durante uma request pode causar pico de memória + timeout.
    """
    logger.info("=== Startup: pré-carregando modelo de embeddings ===")
    try:
        get_embeddings()
        gc.collect()
        logger.info("=== Startup concluído com sucesso ===")
    except Exception as exc:
        logger.error("Falha ao pré-carregar embeddings: %s", exc)
        # Não levanta exceção — deixa o app iniciar mesmo sem embeddings
        # para que o health check funcione e o Render não fique em loop


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


def _get_existing_sources() -> set:
    """
    Consulta o banco para retornar os links de artigos já ingeridos.
    Isso evita re-inserir notícias duplicadas no PGVector.
    """
    if not DATABASE_URL:
        return set()

    # psycopg3 direto usa 'postgresql://' em vez de 'postgresql+psycopg://'
    conn_str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT cmetadata->>'source'
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = %s AND cmetadata->>'source' IS NOT NULL
                """, (COLLECTION_NAME,))
                return {row[0] for row in cur.fetchall()}
    except Exception as exc:
        logger.warning("Não foi possível consultar fontes existentes: %s", exc)
        return set()


def _fetch_and_chunk_rss(urls: List[str], existing_sources: set | None = None):
    """
    Busca artigos dos feeds RSS e retorna (chunks, metadatas).
    Artigos cujo link já está em existing_sources são ignorados.
    """
    if existing_sources is None:
        existing_sources = set()

    all_docs: List[str] = []
    metadata_list: List[dict] = []
    skipped = 0

    for url in urls:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", url)
            published = entry.get("published", "")

            # Deduplicação: pula artigos já ingeridos
            if link in existing_sources:
                skipped += 1
                continue

            content = f"Título: {title}\n\nResumo: {summary}"
            if content.strip():
                all_docs.append(content)
                metadata_list.append(
                    {"source": link, "title": title, "published": published}
                )

    if skipped:
        logger.info("Deduplicação: %d artigos já existentes foram ignorados.", skipped)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks: List[str] = []
    chunk_metadata: List[dict] = []

    for doc, meta in zip(all_docs, metadata_list):
        parts = splitter.split_text(doc)
        chunks.extend(parts)
        chunk_metadata.extend([meta] * len(parts))

    return chunks, chunk_metadata, len(all_docs), skipped


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
    Artigos já ingeridos são ignorados automaticamente (deduplicação).
    """
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL não configurada.")

    # Busca links já existentes para evitar duplicatas
    existing = _get_existing_sources()
    logger.info("Fontes já existentes no banco: %d", len(existing))

    chunks, chunk_metadata, total_articles, skipped = _fetch_and_chunk_rss(
        BBC_RSS_URLS, existing_sources=existing
    )

    if not chunks:
        if skipped > 0:
            return {
                "message": "Todas as notícias já estão atualizadas no banco.",
                "feeds_processados": len(BBC_RSS_URLS),
                "articles_processed": 0,
                "chunks_stored": 0,
                "skipped": skipped,
            }
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
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Grafo RAG com LangGraph
# ---------------------------------------------------------------------------

class EstadoRAG(TypedDict):
    pergunta: str
    top_k: int
    documentos_recuperados: list
    score_maximo: float
    contexto: str
    resposta: str

def no_recuperar(estado: EstadoRAG):
    vs = get_vector_store()
    docs_scores = vs.similarity_search_with_relevance_scores(estado["pergunta"], k=estado["top_k"])
    
    if docs_scores:
        score_max = max(score for doc, score in docs_scores)
        docs = [doc for doc, score in docs_scores]
    else:
        score_max = 0.0
        docs = []
        
    return {"documentos_recuperados": docs, "score_maximo": score_max}

def no_montar_contexto(estado: EstadoRAG):
    docs = estado["documentos_recuperados"]
    partes = []
    for i, doc in enumerate(docs, 1):
        titulo = doc.metadata.get("title", f"Fonte {i}")
        partes.append(f"[{titulo}]\n{doc.page_content}")
    contexto = "\n\n".join(partes)
    return {"contexto": contexto}

def no_gerar_resposta(estado: EstadoRAG):
    prompt = ChatPromptTemplate.from_template(
        "Você é o Assistente RAG News, uma Inteligência Artificial especializada em análise de notícias, "
        "desenvolvido como um projeto universitário de IA Generativa.\n\n"
        "Sua missão é ler as fontes jornalísticas e entregar respostas precisas.\n"
        "Regras Absolutas:\n"
        "1. Baseie sua resposta EXCLUSIVAMENTE no contexto fornecido.\n"
        "2. Se a informação não estiver no contexto, diga claramente: 'Não encontrei informações suficientes nas notícias de hoje para responder a isso.' Jamais invente dados.\n"
        "3. Responda em Português do Brasil (PT-BR). Se a notícia for sobre um assunto leve e descontraído (ex: curiosidades, entretenimento), sinta-se à vontade para fazer uma piada rápida e inteligente no final da resposta. Se for um assunto sério (tragédias, política pesada), mantenha a postura profissional e neutra.\n\n"
        "Contexto:\n{contexto}\n\nPergunta: {pergunta}\n\nResposta:"
    )
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="qwen/qwen3.8-27b",
        temperature=0.3,
    )
    chain = prompt | llm | StrOutputParser()
    resposta = chain.invoke({"contexto": estado["contexto"], "pergunta": estado["pergunta"]})
    return {"resposta": resposta}

def no_sem_evidencia(estado: EstadoRAG):
    return {"resposta": "Não encontrei essa informação nas notícias de hoje.", "documentos_recuperados": []}

def decidir_evidencia(estado: EstadoRAG) -> Literal["com_evidencia", "sem_evidencia"]:
    # Threshold calibrado (0.05): Mantém a lógica condicional do LangGraph funcionando 
    # (barra absurdos/ruídos com score muito baixo), mas permite que buscas cross-lingual (PT->EN) passem.
    if estado.get("score_maximo", -1.0) >= 0.05:
        return "com_evidencia"
    return "sem_evidencia"

grafo = StateGraph(EstadoRAG)
grafo.add_node("recuperar", no_recuperar)
grafo.add_node("montar_contexto", no_montar_contexto)
grafo.add_node("gerar_resposta", no_gerar_resposta)
grafo.add_node("sem_evidencia", no_sem_evidencia)

grafo.add_edge(START, "recuperar")
grafo.add_conditional_edges(
    "recuperar",
    decidir_evidencia,
    {
        "com_evidencia": "montar_contexto",
        "sem_evidencia": "sem_evidencia"
    }
)
grafo.add_edge("montar_contexto", "gerar_resposta")
grafo.add_edge("gerar_resposta", END)
grafo.add_edge("sem_evidencia", END)

grafo_rag = grafo.compile()

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(body: ChatRequest):
    """
    Recebe uma pergunta, usa LangGraph para buscar contexto
    com verificação condicional e retorna a resposta.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY nao configurada.")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Banco nao configurado. Defina DB_HOST e DB_PASSWORD no .env.")

    # Invoca o grafo
    resultado = grafo_rag.invoke({"pergunta": body.question, "top_k": 5})
    
    docs = resultado.get("documentos_recuperados", [])
    sources = list({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})
    
    return ChatResponse(answer=resultado["resposta"], sources=sources)
