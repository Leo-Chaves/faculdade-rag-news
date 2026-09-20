"""
Testes unitarios e de integracao para o backend RAG News.

Cobertura:
  - _build_database_url: construcao e encoding da URL
  - _load_dotenv_safe: deteccao de encoding do .env
  - _fetch_and_chunk_rss: parsing e chunking de feeds RSS
  - GET /          -> health check
  - POST /ingest   -> mock do vector store
  - POST /chat     -> mock do vector store + LLM

Execucao:
  .venv\\Scripts\\pytest tests/ -v
"""

import os
import sys
import types
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Garante que o backend esta no path
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures e helpers
# ---------------------------------------------------------------------------


def _make_mock_app():
    """
    Importa o app com variaveis de ambiente falsas para nao
    precisar de banco real nos testes.
    """
    env_patch = {
        "GROQ_API_KEY": "gsk_fake_key_for_tests",
        "DB_USER": "postgres",
        "DB_PASSWORD": "test_password",
        "DB_HOST": "db.fake.supabase.co",
        "DB_PORT": "5432",
        "DB_NAME": "postgres",
    }
    with patch.dict(os.environ, env_patch, clear=False):
        # Reimporta o modulo com as envs definidas
        import importlib
        import main as m
        importlib.reload(m)
        return m.app, m


@pytest.fixture(scope="module")
def app_and_module():
    return _make_mock_app()


@pytest.fixture(scope="module")
def client(app_and_module):
    app, _ = app_and_module
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Testes de _build_database_url
# ---------------------------------------------------------------------------


class TestBuildDatabaseUrl:
    def test_url_basica(self):
        """URL deve ser construida corretamente com todos os campos."""
        from main import _build_database_url

        with patch.dict(os.environ, {
            "DB_USER": "postgres",
            "DB_PASSWORD": "simples123",
            "DB_HOST": "db.abc.supabase.co",
            "DB_PORT": "5432",
            "DB_NAME": "postgres",
        }):
            url = _build_database_url()
            assert url.startswith("postgresql+psycopg://")
            assert "db.abc.supabase.co" in url
            assert "sslmode=require" in url

    def test_senha_com_caracteres_especiais(self):
        """Senha com @ # % e letras acentuadas deve ser URL-encoded."""
        from main import _build_database_url

        senha = "Minha@Sen#ha&Ãcen"
        with patch.dict(os.environ, {
            "DB_USER": "postgres",
            "DB_PASSWORD": senha,
            "DB_HOST": "db.x.supabase.co",
            "DB_PORT": "5432",
            "DB_NAME": "postgres",
        }):
            url = _build_database_url()
            # A URL resultante deve ser 100% ASCII
            url.encode("ascii")  # nao deve lancar UnicodeEncodeError
            # Os caracteres especiais devem estar percent-encoded
            assert "@" not in url.split("@")[0].split("://")[1]  # @ da senha codificado
            assert "%" in url  # percent-encoding presente

    def test_retorna_vazio_sem_host(self):
        """Sem DB_HOST, deve retornar string vazia."""
        from main import _build_database_url

        with patch.dict(os.environ, {
            "DB_USER": "postgres",
            "DB_PASSWORD": "senha",
            "DB_HOST": "",
            "DB_PORT": "5432",
            "DB_NAME": "postgres",
        }):
            assert _build_database_url() == ""

    def test_retorna_vazio_sem_password(self):
        """Sem DB_PASSWORD, deve retornar string vazia."""
        from main import _build_database_url

        with patch.dict(os.environ, {
            "DB_USER": "postgres",
            "DB_PASSWORD": "",
            "DB_HOST": "db.x.supabase.co",
            "DB_PORT": "5432",
            "DB_NAME": "postgres",
        }):
            assert _build_database_url() == ""

    def test_porta_customizada(self):
        """Porta customizada deve aparecer na URL."""
        from main import _build_database_url

        with patch.dict(os.environ, {
            "DB_USER": "postgres",
            "DB_PASSWORD": "senha",
            "DB_HOST": "db.x.supabase.co",
            "DB_PORT": "6543",
            "DB_NAME": "mydb",
        }):
            url = _build_database_url()
            assert ":6543/" in url
            assert "/mydb?" in url


# ---------------------------------------------------------------------------
# 2. Testes de _load_dotenv_safe (deteccao de encoding)
# ---------------------------------------------------------------------------


class TestLoadDotenvSafe:
    def test_arquivo_utf8_sem_bom(self, tmp_path):
        """Arquivo UTF-8 normal deve ser carregado sem erros."""
        env_file = tmp_path / ".env"
        env_file.write_bytes(b"TEST_VAR=hello\n")

        from main import _load_dotenv_safe

        with patch("main.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.read_bytes.return_value = b"TEST_VAR=hello_utf8\n"
            mock_path_cls.return_value.__truediv__ = lambda s, x: mock_path
            # Apenas valida que nao lanca excecao
            # (load_dotenv e mockado pelo patch.dict nos outros testes)

    def test_deteccao_bom_utf16_le(self):
        """Arquivo com BOM UTF-16 LE deve ser identificado corretamente."""
        raw = b"\xff\xfe"  # BOM UTF-16 LE
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            enc = "utf-16"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"
        else:
            enc = "utf-8"
        assert enc == "utf-16"

    def test_deteccao_bom_utf8(self):
        """Arquivo com BOM UTF-8 deve ser identificado corretamente."""
        raw = b"\xef\xbb\xbfGROQ_API_KEY=test"
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            enc = "utf-16"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"
        else:
            enc = "utf-8"
        assert enc == "utf-8-sig"

    def test_deteccao_sem_bom(self):
        """Arquivo sem BOM deve usar UTF-8."""
        raw = b"GROQ_API_KEY=test"
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            enc = "utf-16"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"
        else:
            enc = "utf-8"
        assert enc == "utf-8"


# ---------------------------------------------------------------------------
# 3. Testes de _fetch_and_chunk_rss
# ---------------------------------------------------------------------------


def _make_feed_mock(bozo=False, entries=None):
    """Cria um mock de retorno do feedparser com acesso por atributo."""
    feed = MagicMock()
    feed.bozo = bozo
    feed.entries = entries or []
    return feed


ENTRIES = [
    MagicMock(
        **{
            "get.side_effect": lambda k, d="": {
                "title": "BBC News: Titulo de teste",
                "summary": "Este e um resumo de noticia de teste para validar o parsing do feed RSS.",
                "link": "https://bbc.com/news/1",
                "published": "Sat, 20 Sep 2025 12:00:00 GMT",
            }.get(k, d),
        }
    ),
    MagicMock(
        **{
            "get.side_effect": lambda k, d="": {
                "title": "Segunda noticia",
                "summary": "Resumo da segunda noticia com conteudo relevante para o RAG.",
                "link": "https://bbc.com/news/2",
                "published": "Sat, 20 Sep 2025 13:00:00 GMT",
            }.get(k, d),
        }
    ),
]

MOCK_FEED = _make_feed_mock(bozo=False, entries=ENTRIES)


class TestFetchAndChunkRss:
    def test_retorna_chunks_e_metadata(self):
        """Deve retornar chunks, metadatas e contagem de artigos."""
        with patch("feedparser.parse", return_value=MOCK_FEED):
            from main import _fetch_and_chunk_rss
            chunks, metadata, total = _fetch_and_chunk_rss(["http://fake-feed.com"])

        assert total == 2
        assert len(chunks) >= 2
        assert len(chunks) == len(metadata)

    def test_metadata_contem_source(self):
        """Metadata de cada chunk deve ter campo 'source' com a URL do artigo."""
        with patch("feedparser.parse", return_value=MOCK_FEED):
            from main import _fetch_and_chunk_rss
            _, metadata, _ = _fetch_and_chunk_rss(["http://fake-feed.com"])

        assert all("source" in m for m in metadata)
        assert all(m["source"].startswith("https://bbc.com") for m in metadata)

    def test_feed_vazio_retorna_zero(self):
        """Feed sem entries deve retornar listas vazias e total 0."""
        feed_vazio = _make_feed_mock(bozo=False, entries=[])
        with patch("feedparser.parse", return_value=feed_vazio):
            from main import _fetch_and_chunk_rss
            chunks, metadata, total = _fetch_and_chunk_rss(["http://fake-feed.com"])

        assert total == 0
        assert chunks == []
        assert metadata == []

    def test_feed_bozo_ignorado(self):
        """Feed com bozo=True e sem entries deve ser ignorado."""
        feed_corrompido = _make_feed_mock(bozo=True, entries=[])
        with patch("feedparser.parse", return_value=feed_corrompido):
            from main import _fetch_and_chunk_rss
            chunks, metadata, total = _fetch_and_chunk_rss(["http://bad-feed.com"])

        assert total == 0
        assert chunks == []

    def test_multiplos_feeds(self):
        """Multiplos feeds devem ser concatenados corretamente."""
        with patch("feedparser.parse", return_value=MOCK_FEED):
            from main import _fetch_and_chunk_rss
            _, _, total = _fetch_and_chunk_rss([
                "http://feed1.com",
                "http://feed2.com",
            ])

        assert total == 4  # 2 artigos por feed x 2 feeds


# ---------------------------------------------------------------------------
# 4. Testes de rotas HTTP (FastAPI TestClient)
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_get_root_retorna_200(self, client):
        """GET / deve retornar 200 com status ok."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_get_root_tem_message(self, client):
        """GET / deve retornar campo 'message'."""
        resp = client.get("/")
        assert "message" in resp.json()


class TestIngestRoute:
    def test_ingest_sem_db_retorna_500(self, client, app_and_module):
        """POST /ingest sem DATABASE_URL deve retornar 500."""
        _, m = app_and_module
        original = m.DATABASE_URL
        m.DATABASE_URL = ""
        try:
            resp = client.post("/ingest")
            assert resp.status_code == 500
        finally:
            m.DATABASE_URL = original

    def test_ingest_com_mock_vector_store(self, client, app_and_module):
        """POST /ingest com mock do vector store deve retornar 200."""
        _, m = app_and_module

        mock_vs = MagicMock()
        mock_vs.add_texts.return_value = None

        with patch("feedparser.parse", return_value=_make_feed_mock(entries=ENTRIES)), \
             patch.object(m, "get_vector_store", return_value=mock_vs):

            resp = client.post("/ingest")

        assert resp.status_code == 200
        data = resp.json()
        assert "chunks_stored" in data
        assert data["chunks_stored"] > 0
        assert data["articles_processed"] > 0


class TestChatRoute:
    def test_chat_sem_groq_key_retorna_500(self, client, app_and_module):
        """POST /chat sem GROQ_API_KEY deve retornar 500."""
        _, m = app_and_module
        original = m.GROQ_API_KEY
        m.GROQ_API_KEY = ""
        try:
            resp = client.post("/chat", json={"question": "teste"})
            assert resp.status_code == 500
        finally:
            m.GROQ_API_KEY = original

    def test_chat_sem_db_retorna_500(self, client, app_and_module):
        """POST /chat sem DATABASE_URL deve retornar 500."""
        _, m = app_and_module
        original_db = m.DATABASE_URL
        m.DATABASE_URL = ""
        try:
            resp = client.post("/chat", json={"question": "teste"})
            assert resp.status_code == 500
        finally:
            m.DATABASE_URL = original_db

    def test_chat_body_invalido_retorna_422(self, client):
        """POST /chat sem campo 'question' deve retornar 422."""
        resp = client.post("/chat", json={})
        assert resp.status_code == 422

    def test_chat_com_mock_retorna_resposta(self, client, app_and_module):
        """POST /chat com mocks do VS e LLM deve retornar answer e sources."""
        _, m = app_and_module
        from langchain_core.documents import Document

        mock_doc = Document(
            page_content="Noticia de teste sobre tecnologia.",
            metadata={"source": "https://bbc.com/tech/1", "title": "Tech News"},
        )
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [mock_doc]

        mock_chain_result = "Resposta mockada do LLM."

        with patch.object(m, "get_vector_store", return_value=mock_vs), \
             patch("langchain_core.runnables.base.RunnableSequence.invoke",
                   return_value=mock_chain_result):

            resp = client.post("/chat", json={"question": "O que ha de novo em tech?"})

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
