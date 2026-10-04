import httpx
from fastapi import HTTPException

from app.settings import get_settings


def _detail(body: bytes) -> str:
    """Pull the message out of a FastAPI error response."""
    try:
        import json

        return json.loads(body).get("detail", "The AI service rejected the request.")
    except Exception:
        return "The AI service rejected the request."


class AIService:

    settings = get_settings()

    def _payload(
        self,
        question: str,
        model: str,
        top_k: int,
        temperature: float,
        top_p: float,
        max_tokens: int,
        files: list[dict] | None,
    ) -> dict:
        return {
            "question": question,
            "model": model,
            "top_k": top_k,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "files": files,
        }

    async def chat(self, **kwargs):

        async with httpx.AsyncClient(timeout=300) as client:

            response = await client.post(
                f"{self.settings.ai_service_url}/api/v1/chat",
                json=self._payload(**kwargs),
            )

            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=_detail(response.content),
                )

            return response.json()

    async def open_stream(self, **kwargs):
        """Start a streaming response and return (client, response).

        The status is checked before anything is streamed, so a rejected
        upload still produces a normal error response rather than an error
        halfway through a stream the browser has already started reading.

        The caller owns both objects and must close them.
        """
        client = httpx.AsyncClient(timeout=300)

        request = client.build_request(
            "POST",
            f"{self.settings.ai_service_url}/api/v1/chat/stream",
            json=self._payload(**kwargs),
        )

        response = await client.send(request, stream=True)

        if response.status_code >= 400:
            body = await response.aread()
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=response.status_code,
                detail=_detail(body),
            )

        return client, response
