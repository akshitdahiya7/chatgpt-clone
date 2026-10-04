import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


def read_files():
    from app.document.factory import DocumentFactory

    files = ["sample/test.pdf"]

    for file in files:
        full = f"{PROJECT_ROOT}/app/document/tests/{file}"
        reader_cls = DocumentFactory.get_reader(full)
        print(reader_cls.read(full))


def ingest_file():
    from app.document.service import IngestionService

    service = IngestionService()

    document_id = service.ingest(
        "https://icrrd.com/public/media/15-05-2021-084550The-Alchemist-Paulo-Coelho.pdf"
    )

    print(f"Ingested as {document_id}")


def create_index():
    from app.vectordb.service import VectorStoreService

    VectorStoreService().create_index(recreate=True)


if __name__ == "__main__":
    ingest_file()
