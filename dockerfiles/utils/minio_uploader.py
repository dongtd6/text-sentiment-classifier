import os
from typing import Optional

from loguru import logger
from minio import Minio
from minio.error import S3Error


class MinioUploader:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: Optional[str] = None,
    ) -> None:
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

    def ensure_bucket(self, bucket_name: str) -> None:
        try:
            if not self.client.bucket_exists(bucket_name=bucket_name):
                self.client.make_bucket(bucket_name=bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
            else:
                logger.info(f"Bucket already exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket {bucket_name}: {e}")
            raise

    def upload_file(
        self,
        bucket_name: str,
        local_file: str,
        object_name: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None:
        if object_name is None:
            object_name = os.path.basename(local_file)

        if not os.path.isfile(local_file):
            raise FileNotFoundError(f"Local file does not exist: {local_file}")

        try:
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name.replace("\\", "/"),
                file_path=local_file,
                content_type=content_type,
            )
            logger.info(f"Uploaded file {local_file} -> s3://{bucket_name}/{object_name}")
        except S3Error as e:
            logger.error(f"Failed to upload {local_file} to {bucket_name}/{object_name}: {e}")
            raise

    def upload_directory(
        self,
        bucket_name: str,
        local_dir: str,
        dest_prefix: str = "",
    ) -> None:
        if not os.path.isdir(local_dir):
            raise NotADirectoryError(f"Local path is not a directory: {local_dir}")

        local_dir = os.path.abspath(local_dir)
        dest_prefix = dest_prefix.strip("/")

        for root, _, files in os.walk(local_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, local_dir)
                object_name = (
                    f"{dest_prefix}/{rel_path}" if dest_prefix else rel_path
                ).replace("\\", "/")
                self.upload_file(bucket_name, fpath, object_name)


