import os
from typing import Any, Iterable, List, Mapping, Optional

import pandas as pd
from deltalake import DeltaTable
from deltalake.writer import write_deltalake
from loguru import logger

try:
    # Optional: MinioUploader available in this repo
    from src.utils.minio_uploader import MinioUploader
except Exception:  # pragma: no cover
    MinioUploader = None  # type: ignore


def _record_to_dict(rec: Any) -> Mapping[str, Any]:
    """Best-effort conversion of API model/object to a plain dict."""
    if isinstance(rec, dict):
        return rec
    if hasattr(rec, "to_dict") and callable(getattr(rec, "to_dict")):
        return rec.to_dict()
    if hasattr(rec, "model_dump") and callable(getattr(rec, "model_dump")):
        return rec.model_dump(by_alias=True, exclude_none=True)
    if hasattr(rec, "dict") and callable(getattr(rec, "dict")):
        return rec.dict()
    # Fallback: use __dict__ if available
    if hasattr(rec, "__dict__"):
        return dict(rec.__dict__)
    raise TypeError("Unsupported record type; cannot convert to dict")


def api_results_to_dataframe(records: Iterable[Any], columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Convert API results (list of models/objects/dicts) into a pandas DataFrame.

    Args:
        records: Iterable of API results
        columns: Optional list of columns to project/keep

    Returns:
        pandas DataFrame
    """
    rows = [_record_to_dict(r) for r in records]
    df = pd.DataFrame(rows)
    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            logger.warning(f"Missing columns in data: {missing}")
        df = df[[c for c in columns if c in df.columns]]
    logger.info(f"Created DataFrame: shape={df.shape}")
    return df


def write_dataframe_to_delta(
    df: pd.DataFrame,
    delta_path: str,
    mode: str = "append",
    partition_by: Optional[List[str]] = None,
) -> str:
    """
    Write DataFrame to a local Delta Lake table path.

    Args:
        df: DataFrame to write
        delta_path: Local folder path for Delta table
        mode: Delta write mode (e.g., 'append', 'overwrite', 'ignore')
        partition_by: Optional partition columns

    Returns:
        The Delta table path
    """
    os.makedirs(delta_path, exist_ok=True)
    try:
        # Fast path: let deltalake handle pandas -> Arrow conversion
        write_deltalake(delta_path, df, mode=mode, partition_by=partition_by)
    except ImportError as e:
        # Handle environments with older pyarrow (pandas >=2.3 may require pyarrow>=14)
        if "pyarrow" not in str(e).lower():
            raise
        # Fallback: explicitly convert via pyarrow to avoid pandas' __arrow_c_stream__ requirement
        import pyarrow as pa  # type: ignore

        table = pa.Table.from_pandas(df, preserve_index=False)
        write_deltalake(delta_path, table, mode=mode, partition_by=partition_by)
    logger.info(f"Wrote DataFrame to Delta: path={delta_path}, mode={mode}, rows={len(df)}")
    return delta_path


def verify_delta(delta_path: str) -> DeltaTable:
    """Open and return the DeltaTable for verification/inspection."""
    dt = DeltaTable(delta_path)
    logger.info(f"Delta table loaded: {delta_path}")
    return dt


def upload_delta_to_minio(
    delta_path: str,
    uploader: "MinioUploader",
    bucket: str,
    dest_prefix: str,
) -> None:
    """
    Upload the whole Delta folder (including _delta_log and data files) to MinIO.
    """
    if MinioUploader is None:
        raise RuntimeError("MinioUploader is not available. Ensure src.utils.minio_uploader exists.")
    uploader.ensure_bucket(bucket)
    uploader.upload_directory(bucket, delta_path, dest_prefix)
    logger.info(f"Uploaded Delta folder to s3://{bucket}/{dest_prefix}")


