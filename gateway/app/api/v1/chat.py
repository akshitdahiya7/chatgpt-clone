import httpx
from fastapi import APIRouter

from app.api.schemas.chat import ChatRequest, ChatResponse
from app.settings import get_settings

settings = get_settings()

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.chat_service}/api/v1/chat",
            json=request.model_dump(),
        )

    response.raise_for_status()

    return ChatResponse.model_validate(response.json())