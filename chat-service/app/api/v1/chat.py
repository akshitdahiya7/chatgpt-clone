from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.services.ai_service import AIService
from app.services.factory import StorageFactory

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

storage_service = StorageFactory.get_provider()
ai_service = AIService()


async def upload_all(files: list[UploadFile]) -> list[dict]:
    uploaded = []

    for file in files:
        uploaded.append(await storage_service.upload_file(file))
        print("UPLOADED:", file.filename)

    return uploaded


@router.post("")
async def chat(
    question: str = Form(...),
    model: str = Form("gpt-4o-mini"),
    top_k: int = Form(5),
    temperature: float = Form(0.2),
    top_p: float = Form(0.9),
    max_tokens: int = Form(512),
    files: list[UploadFile] = File(default=[]),
):
    return await ai_service.chat(
        question=question,
        model=model,
        top_k=top_k,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        files=await upload_all(files),
    )


@router.post("/stream")
async def chat_stream(
    question: str = Form(...),
    model: str = Form("gpt-4o-mini"),
    top_k: int = Form(5),
    temperature: float = Form(0.2),
    top_p: float = Form(0.9),
    max_tokens: int = Form(512),
    files: list[UploadFile] = File(default=[]),
):
    # Uploads finish before streaming starts, so the files are in storage by
    # the time the AI service is asked to read them.
    uploaded = await upload_all(files)

    # Raises before any streaming begins if the AI service rejects the
    # request, so the browser gets a normal error response.
    client, response = await ai_service.open_stream(
        question=question,
        model=model,
        top_k=top_k,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        files=uploaded,
    )

    async def relay():
        try:
            async for piece in response.aiter_text():
                yield piece
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type="text/plain; charset=utf-8",
        # Stop proxies buffering the stream into one lump.
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
