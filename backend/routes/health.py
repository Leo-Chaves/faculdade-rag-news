from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
def root():
    return {
        "status": "ok",
        "message": "RAG News API is running"
    }


@router.get("/health")
def health_check():
    return {"status": "ok"}