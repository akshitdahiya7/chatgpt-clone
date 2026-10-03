import httpx

from app.settings import get_settings


class AIService:

    settings = get_settings()

    async def chat(
        self,
        question: str,
        model: str,
        top_k: int,
        temperature: float,
        top_p: float,
        max_tokens: int,
        files: list[dict] | None = None,
    ):

        payload = {
            "question": question,
            "model": model,
            "top_k": top_k,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "files": files,
        }

        async with httpx.AsyncClient(timeout=120) as client:

            response = await client.post(
                f"{self.settings.ai_service_url}/api/v1/chat",
                json=payload,
            )

            response.raise_for_status()

            return response.json()