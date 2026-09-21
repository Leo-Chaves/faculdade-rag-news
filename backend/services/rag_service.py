from typing import Callable


def process_chat(question: str, rag_runner: Callable) -> dict:
    """
    Camada de integração entre a API e o módulo RAG.
    A API não precisa conhecer os detalhes internos do LangGraph.
    """
    resultado = rag_runner(
        {
            "pergunta": question,
            "top_k": 5,
        }
    )

    docs = resultado.get("documentos_recuperados", [])

    sources = list(
        {
            doc.metadata.get("source", "")
            for doc in docs
            if doc.metadata.get("source")
        }
    )

    return {
        "answer": resultado["resposta"],
        "sources": sources,
    }