from fastapi import APIRouter, File, Form, UploadFile

from app.services.ai_service import AIService
from app.services.factory import StorageFactory

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

storage_service = StorageFactory.get_provider()
ai_service = AIService()


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
    print("CHAT SERVICE REQUEST:", question)
    print("FILES:", len(files))

    uploaded_files = []

    # Upload every file to object storage
    for file in files:

        uploaded_file = await storage_service.upload_file(file)

        uploaded_files.append(uploaded_file)

        print(
            "UPLOADED:",
            uploaded_file,
        )

    # Send all file metadata to AI Service
    response = await ai_service.chat(
        question=question,
        model=model,
        top_k=top_k,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        files=uploaded_files,
    )

    return response