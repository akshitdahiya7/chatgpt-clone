from app.document.chunkers.base import Chunker
from app.document.chunkers.models import Chunk
from app.document.models import DocumentPage


class FixedChunker(Chunker):

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size, "
                f"got overlap={chunk_overlap} size={chunk_size}"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, pages: list[DocumentPage]) -> list[Chunk]:

        chunks: list[Chunk] = []
        index = 0

        for page in pages:

            start = 0

            while start < len(page.text):

                end = start + self.chunk_size

                # End on a space so words are not cut in half.
                if end < len(page.text):
                    space = page.text.rfind(" ", start, end)
                    if space > start:
                        end = space

                text = page.text[start:end].strip()

                if text:
                    chunks.append(
                        Chunk(
                            index=index,
                            page=page.page,
                            text=text,
                        )
                    )
                    index += 1

                # max() keeps us moving forward even if the chunk came out short.
                start = max(end - self.chunk_overlap, start + 1)

        return chunks
