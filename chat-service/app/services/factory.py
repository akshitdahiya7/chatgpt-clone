from app.settings import get_settings


class StorageFactory:

    @staticmethod
    def get_provider():
        settings = get_settings()

        if settings.storage_provider != "s3":
            raise ValueError(
                f"Unsupported storage provider: {settings.storage_provider}"
            )

        if not settings.s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME is required")

        from app.services.s3_storage import S3StorageService

        return S3StorageService()
