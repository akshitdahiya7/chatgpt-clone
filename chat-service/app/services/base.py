from abc import ABC, abstractmethod


class BaseStorageService(ABC):

    @abstractmethod
    def generate_sas_url(self, blob_name: str, expiry_minutes: int = 60) -> str:
        """Return a time-limited read URL for a stored file."""
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, file) -> dict:
        """Store an upload and return its metadata.

        Keys: blob_name, filename, content_type, url, sas_url.
        """
        raise NotImplementedError
