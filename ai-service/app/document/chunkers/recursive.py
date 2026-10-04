from app.document.chunkers.base import Chunker
from app.document.chunkers.models import Chunk
from app.document.models import DocumentPage


class RecursiveChunker(Chunker):
    """Cuts at the largest natural boundary that fits in the chunk size.

    Tries a paragraph break first, then a line break, then the end of a
    sentence, then a space. Falls back to a hard cut only when the window
    contains none of them.
    """

    SEPARATORS = ("\n\n", "\n", ". ", " ")

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

                if end < len(page.text):
                    for separator in self.SEPARATORS:
                        found = page.text.rfind(separator, start, end)
                        if found > start:
                            end = found + len(separator)
                            break

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
