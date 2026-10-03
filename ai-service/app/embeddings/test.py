import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


from app.embeddings.service import EmbeddingService  # noqa: E402

service = EmbeddingService()

vector = service.embed(
    "The quick brown fox jumps over the lazy dog."
)

print(vector)