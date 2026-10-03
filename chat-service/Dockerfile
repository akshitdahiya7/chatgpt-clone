FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencies first, so this layer is cached independently of application code.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY . .

# Use the venv directly, so the container does not re-sync on every start.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
