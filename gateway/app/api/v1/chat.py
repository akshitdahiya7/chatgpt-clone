import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.identity import COOKIE_NAME, RateLimiter, new_session_id, sign, verify
from app.settings import get_settings

settings = get_settings()

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

limiter = RateLimiter(
    limit=settings.rate_limit_requests,
    window=settings.rate_limit_window_seconds,
)


def resolve_user(request: Request) -> tuple[str, bool]:
    """Work out who is calling.

    Returns (user_id, is_new_session). A bearer token names a real user; anyone
    else gets an anonymous session tied to a signed cookie, so their documents
    stay separate from everyone else's.
    """
    header = request.headers.get("authorization", "")

    if header.lower().startswith("bearer "):
        user = settings.token_map.get(header[7:].strip())
        if user:
            return user, False

    cookie = request.cookies.get(COOKIE_NAME, "")
    session_id = verify(cookie, settings.session_secret) if cookie else None

    if session_id:
        return f"session-{session_id}", False

    return f"session-{new_session_id()}", True


async def proxy(request: Request, path: str, stream: bool):
    """Forward the request to chat-service, adding the caller's identity.

    The body is passed through untouched so file uploads work without the
    gateway needing to understand multipart.
    """
    user_id, is_new = resolve_user(request)

    if not limiter.allow(user_id):
        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    "Too many requests. You can ask "
                    f"{settings.rate_limit_requests} questions per hour."
                )
            },
            headers={"Retry-After": str(limiter.retry_after(user_id))},
        )

    body = await request.body()

    headers = {
        "content-type": request.headers.get("content-type", ""),
        # chat-service trusts this, which is safe because it is only reachable
        # through the gateway on the internal network.
        "X-User-Id": user_id,
    }

    client = httpx.AsyncClient(timeout=300)

    upstream = await client.send(
        client.build_request(
            "POST",
            f"{settings.chat_service}{path}",
            content=body,
            headers=headers,
        ),
        stream=True,
    )

    def with_cookie(response):
        """Hand a new visitor their session cookie."""
        if is_new:
            response.set_cookie(
                COOKIE_NAME,
                sign(user_id.removeprefix("session-"), settings.session_secret),
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                samesite="lax",
            )
        return response

    # Errors are read in full and returned as-is, so the browser sees the real
    # status and message rather than a broken stream.
    if upstream.status_code >= 400 or not stream:
        content = await upstream.aread()
        await upstream.aclose()
        await client.aclose()

        from fastapi import Response

        return with_cookie(
            Response(
                content=content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type"),
            )
        )

    async def relay():
        try:
            async for piece in upstream.aiter_raw():
                yield piece
        finally:
            await upstream.aclose()
            await client.aclose()

    return with_cookie(
        StreamingResponse(
            relay(),
            media_type=upstream.headers.get("content-type", "text/plain"),
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )
    )


@router.post("")
async def chat(request: Request):
    return await proxy(request, "/api/v1/chat", stream=False)


@router.post("/stream")
async def chat_stream(request: Request):
    return await proxy(request, "/api/v1/chat/stream", stream=True)
