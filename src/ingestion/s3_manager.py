# filepath: src/ingestion/s3_manager.py
"""S3 manager for storing and retrieving PML data."""

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

from src.utils.config import S3_BUCKET, S3_RAW_PREFIX

logger = logging.getLogger(__name__)


class S3Manager:
    """Manager for S3 operations related to PML data storage."""
    
    def __init__(self, bucket: str = S3_BUCKET):
        """Initialize S3 manager.
        
        Args:
            bucket: S3 bucket name
        """
        self.bucket = bucket
        self.s3_client = boto3.client("s3")
    
    def _build_s3_key(self, nodo: str, fecha: str | datetime) -> str:
        """Build S3 key path for a PML record.
        
        Args:
            nodo: Node identifier
            fecha: Date of the record
            
        Returns:
            S3 key path (e.g., raw/pml/2026/03/28/03CHI-115/data.parquet)
        """
        if isinstance(fecha, str):
            dt = datetime.strptime(fecha, "%Y-%m-%d")
        else:
            dt = fecha
        
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
        day = dt.strftime("%d")
        
        return f"{S3_RAW_PREFIX}/{year}/{month}/{day}/{nodo}/data.parquet"
    
    def upload_parquet(
        self,
        records: list[dict[str, Any]],
        nodo: str,
        fecha: str | datetime,
    ) -> bool:
        """Upload records as Parquet file to S3.
        
        Args:
            records: List of PML records to upload
            nodo: Node identifier
            fecha: Date of the records
            
        Returns:
            True if upload successful, False otherwise
        """
        if not records:
            logger.warning(f"No records to upload for node {nodo}")
            return False
        
        s3_key = self._build_s3_key(nodo, fecha)
        
        try:
            # Convert records to Parquet format
            table = pa.Table.from_pylist(records)
            buffer = BytesIO()
            pq.write_table(table, buffer)
            buffer.seek(0)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=buffer.getvalue(),
                ContentType="application/parquet",
            )
            
            logger.info(f"Uploaded {len(records)} records to s3://{self.bucket}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return False
    
    def upload_dataframe(
        self,
        df,
        nodo: str,
        fecha: str | datetime,
    ) -> bool:
        """Upload pandas DataFrame as Parquet file to S3.
        
        Args:
            df: pandas DataFrame with PML records
            nodo: Node identifier
            fecha: Date of the records
            
        Returns:
            True if upload successful, False otherwise
        """
        if df.empty:
            logger.warning(f"Empty DataFrame for node {nodo}")
            return False
        
        s3_key = self._build_s3_key(nodo, fecha)
        
        try:
            buffer = BytesIO()
            df.to_parquet(buffer, engine="pyarrow", index=False)
            buffer.seek(0)
            
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=buffer.getvalue(),
                ContentType="application/parquet",
            )
            
            logger.info(f"Uploaded DataFrame to s3://{self.bucket}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload DataFrame to S3: {e}")
            return False
    
    def read_parquet(
        self,
        nodo: str,
        fecha: str | datetime,
    ) -> list[dict[str, Any]]:
        """Read Parquet file from S3.
        
        Args:
            nodo: Node identifier
            fecha: Date of the records
            
        Returns:
            List of records read from S3
        """
        s3_key = self._build_s3_key(nodo, fecha)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            buffer = BytesIO(response["Body"].read())
            table = pq.read_table(buffer)
            return table.to_pylist()
            
        except Exception as e:
            logger.error(f"Failed to read from S3: {e}")
            return []
    
    def list_objects(self, prefix: str) -> list[str]:
        """List objects in S3 bucket with given prefix.
        
        Args:
            prefix: S3 key prefix to search
            
        Returns:
            List of S3 keys matching the prefix
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )
            contents = response.get("Contents", [])
            return [obj["Key"] for obj in contents]
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")
            return []


def store_pml_data(
    records: list[dict[str, Any]],
    nodo: str,
    fecha: str | datetime,
) -> bool:
    """Convenience function to store PML data in S3.
    
    Args:
        records: List of PML records
        nodo: Node identifier
        fecha: Date of the records
        
    Returns:
        True if storage successful, False otherwise
    """
    manager = S3Manager()
    return manager.upload_parquet(records, nodo, fecha)
