from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.rag.service import RAGService

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

# Built once at startup, not per request.
rag = RAGService()


def prepare(request: dict) -> dict:
    """Ingest any attached files and build the arguments for a chat call."""

    user_id = request.get("user_id", "demo-user")

    document_ids = []

    for file in request.get("files", []):
        try:
            document_ids.append(
                rag.ingestion_service.ingest(file["sas_url"], user_id=user_id)
            )
        except ValueError as exc:
            # Tell the user which file failed and why, rather than a 500.
            raise HTTPException(
                status_code=400,
                detail=f"{file.get('filename', 'file')}: {exc}",
            ) from exc

    return {
        "question": request["question"],
        "model": request["model"],
        "top_k": request["top_k"],
        "temperature": request["temperature"],
        "top_p": request["top_p"],
        "max_tokens": request["max_tokens"],
        "user_id": user_id,
        # Files came with this question, so answer from those documents only.
        # Without files, search everything this user has uploaded before.
        "document_ids": document_ids or None,
    }


@router.post("")
async def chat(request: dict):

    response = rag.chat(**prepare(request))

    return {
        "response": response.content,
        "model": response.model,
    }


@router.post("/stream")
async def chat_stream(request: dict):

    return StreamingResponse(
        rag.chat_stream(**prepare(request)),
        media_type="text/plain; charset=utf-8",
    )
