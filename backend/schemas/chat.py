from typing import List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Pergunta enviada pelo usuário"
    )


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []