from openai import OpenAI

from app.embeddings.providers.base import BaseProvider


class OpenAIEmbeddingProvider(BaseProvider):

    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        batch_size: int,
        base_url: str = "",
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url or None)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = []

        for start in range(0, len(texts), self.batch_size):
            response = self.client.embeddings.create(
                model=self.model,
                input=texts[start:start + self.batch_size],
                dimensions=self.dimensions,
            )
            vectors.extend(normalize(item.embedding) for item in response.data)

        return vectors


def normalize(vector: list[float]) -> list[float]:
    """Scale to unit length, which cosine similarity search expects.

    Needed because shortening an embedding with `dimensions` loses the
    unit length OpenAI returns at the model's native size.
    """
    length = sum(value * value for value in vector) ** 0.5

    if length == 0:
        return vector

    return [value / length for value in vector]
