from uuid import uuid4

import boto3

from app.services.base import BaseStorageService
from app.settings import get_settings


class S3StorageService(BaseStorageService):

    def __init__(self):
        self.settings = get_settings()
        self.bucket = self.settings.s3_bucket_name

        self.client = boto3.client(
            "s3",
            region_name=self.settings.aws_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
        )

    def generate_sas_url(
        self,
        blob_name: str,
        expiry_minutes: int = 60,
    ) -> str:
        # ExpiresIn is in seconds.
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": blob_name,
            },
            ExpiresIn=expiry_minutes * 60,
        )

    async def upload_file(self, file):

        extension = ""

        if file.filename and "." in file.filename:
            extension = "." + file.filename.rsplit(".", 1)[-1]

        blob_name = f"{uuid4().hex}{extension}"

        content = await file.read()

        self.client.put_object(
            Bucket=self.bucket,
            Key=blob_name,
            Body=content,
            # boto3 rejects ContentType=None, which UploadFile can hand us.
            ContentType=file.content_type or "application/octet-stream",
        )

        url = (
            f"https://{self.bucket}.s3."
            f"{self.settings.aws_region}.amazonaws.com/{blob_name}"
        )

        sas_url = self.generate_sas_url(
            blob_name=blob_name,
            expiry_minutes=60,
        )

        return {
            "blob_name": blob_name,
            "filename": file.filename,
            "content_type": file.content_type,
            # Not fetchable on its own: the bucket blocks unsigned reads.
            "url": url,
            "sas_url": sas_url,
        }
