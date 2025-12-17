import os
import logging
from pathlib import Path
from typing import Optional, List
from google.cloud import storage

logger = logging.getLogger(__name__)


class GCSManager:
    """
    Google Cloud Storage Manager for uploading Gold layer to GCS.
    Simplified version for production use in Kubernetes.
    """

    def __init__(self, credential_path: Optional[str] = None):
        """
        Initialize GCS client.
        
        Args:
            credential_path: Path to GCS service account JSON file.
                            If None, uses GOOGLE_APPLICATION_CREDENTIALS env var.
        """
        if credential_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path
        
        self.client = storage.Client()
        logger.info("GCSManager initialized")

    def create_bucket(
        self,
        bucket_name: str,
        location: str = "asia-southeast1"
    ):
        """
        Create a GCS bucket if it doesn't exist.
        """
        try:
            bucket = self.client.bucket(bucket_name)
            
            if bucket.exists():
                logger.info(f"Bucket {bucket_name} already exists")
                return bucket
            
            bucket = self.client.create_bucket(bucket, location=location)
            logger.info(f"Bucket created → gs://{bucket_name} (location={location})")
            return bucket
            
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise

    def upload_file(
        self,
        local_file: str,
        bucket_name: str,
        remote_path: str
    ):
        """
        Upload a single file to GCS.
        """
        bucket = self.client.bucket(bucket_name)
        
        local_path = Path(local_file)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_file}")
        
        remote_path = remote_path.replace("\\", "/")
        
        blob = bucket.blob(remote_path)
        blob.upload_from_filename(str(local_path))
        
        logger.debug(f"Uploaded → {local_file} → gs://{bucket_name}/{remote_path}")
        return f"gs://{bucket_name}/{remote_path}"

    def upload_folder(
        self,
        source_folder: str,
        bucket_name: str,
        destination_prefix: str = ""
    ):
        """
        Upload entire folder recursively to GCS (single-threaded).
        """
        bucket = self.client.bucket(bucket_name)
        
        src = Path(source_folder)
        if not src.exists():
            raise FileNotFoundError(f"Folder not found: {source_folder}")
        
        logger.info(f"Uploading folder recursively → {src}")
        
        uploaded_count = 0
        for file_path in src.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(src)
                remote_path = f"{destination_prefix}/{rel}".replace("\\", "/") if destination_prefix else str(rel).replace("\\", "/")
                
                blob = bucket.blob(remote_path)
                blob.upload_from_filename(str(file_path))
                
                uploaded_count += 1
                if uploaded_count % 100 == 0:
                    logger.info(f"  Uploaded {uploaded_count} files...")
        
        logger.info(f"Folder upload completed: {uploaded_count} files → gs://{bucket_name}/{destination_prefix}/")
        return uploaded_count

    def upload_tree_parallel(
        self,
        root_folder: str,
        bucket_name: str,
        destination_prefix: str = "",
        workers: int = 16,
        use_threads: bool = True  # Default to True (threads work better with GCS client)
    ):
        """
        Upload entire nested directory tree in parallel using ThreadPoolExecutor.
        
        Note: ThreadPoolExecutor is used instead of ProcessPoolExecutor because:
        1. GCS client object cannot be pickled across processes
        2. Threads are sufficient for I/O-bound operations like uploads
        3. Avoids pickle errors with nested functions
        """
        bucket = self.client.bucket(bucket_name)
        
        root = Path(root_folder)
        if not root.exists():
            raise FileNotFoundError(f"Folder not found: {root_folder}")
        
        # Scan all files
        file_paths = []
        blob_paths = []
        
        for fp in root.rglob("*"):
            if fp.is_file():
                file_paths.append(str(fp))
                rel = fp.relative_to(root)
                blob_name = f"{destination_prefix}/{rel}".replace("\\", "/") if destination_prefix else str(rel).replace("\\", "/")
                blob_paths.append(blob_name)
        
        logger.info(f"Files found: {len(file_paths)}")
        
        if not file_paths:
            logger.warning("No files discovered to upload.")
            return 0
        
        logger.info(f"Starting parallel upload with {workers} workers (ThreadPoolExecutor)...")
        
        # Parallel upload with ThreadPoolExecutor (I/O-bound operations)
        from concurrent.futures import ThreadPoolExecutor
        
        def _upload_one(job):
            local_file, blob_name = job
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_file)
            logger.debug(f"✔ Uploaded {blob_name}")
            return blob_name
        
        jobs = list(zip(file_paths, blob_paths))
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_upload_one, jobs))
        
        logger.info(f"Parallel upload completed: {len(results)} files → gs://{bucket_name}/{destination_prefix}/")
        return len(results)

