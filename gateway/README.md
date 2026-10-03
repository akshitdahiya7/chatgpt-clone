# Gateway

API gateway for the ChatGPT clone. Fronts `chat-service`.

Run locally:

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Configuration lives in `.env` (see `.env.example`).
