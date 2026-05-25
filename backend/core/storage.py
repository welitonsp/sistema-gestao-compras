"""Cloud Storage Abstraction Layer."""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Any
import os
import shutil
import asyncio
from backend.core.config import settings
from core.logger import get_logger

logger = get_logger("core.storage")

class StorageProvider(ABC):
    @abstractmethod
    async def save_file(self, content: BinaryIO, filename: str, folder: str = "uploads") -> str:
        """Saves a file and returns its access path/URL."""
        pass

    @abstractmethod
    async def get_file_content(self, filename: str, folder: str = "uploads") -> bytes:
        """Returns the file content as bytes."""
        pass

    @abstractmethod
    async def delete_file(self, filename: str, folder: str = "uploads"):
        """Deletes a file from storage."""
        pass

class LocalStorageProvider(StorageProvider):
    """Default provider for local file system storage."""
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)

    async def save_file(self, content: BinaryIO, filename: str, folder: str = "uploads") -> str:
        target_dir = self.base_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        
        with target_path.open("wb") as f:
            shutil.copyfileobj(content, f)
            
        return str(target_path)

    async def get_file_content(self, filename: str, folder: str = "uploads") -> bytes:
        path = self.base_dir / folder / filename
        return path.read_bytes()

    async def delete_file(self, filename: str, folder: str = "uploads"):
        path = self.base_dir / folder / filename
        if path.exists():
            path.unlink()

class S3StorageProvider(StorageProvider):
    """Provider for AWS S3 or MinIO using boto3."""
    def __init__(self):
        import boto3
        from botocore.config import Config
        
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else None,
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint, # For MinIO
            config=Config(signature_version='s3v4')
        )

    async def save_file(self, content: BinaryIO, filename: str, folder: str = "uploads") -> str:
        key = f"{folder}/{filename}"
        await asyncio.to_thread(
            self.client.upload_fileobj, content, self.bucket, key
        )
        return key

    async def get_file_content(self, filename: str, folder: str = "uploads") -> bytes:
        key = f"{folder}/{filename}"
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=key
        )
        return response['Body'].read()

    async def delete_file(self, filename: str, folder: str = "uploads"):
        key = f"{folder}/{filename}"
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=key
        )

def get_storage_provider() -> StorageProvider:
    """Factory to return the configured storage provider."""
    if settings.storage_type == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()
