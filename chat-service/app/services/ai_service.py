from contextlib import asynccontextmanager

import httpx

from app.settings import get_settings


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

            response.raise_for_status()

            return response.json()

    @asynccontextmanager
    async def stream(self, **kwargs):
        """Open a streaming response from the AI service.

        The client must stay open while the caller reads, so this is a context
        manager rather than a plain generator.
        """
        async with httpx.AsyncClient(timeout=300) as client, client.stream(
            "POST",
            f"{self.settings.ai_service_url}/api/v1/chat/stream",
            json=self._payload(**kwargs),
        ) as response:
            response.raise_for_status()
            yield response
