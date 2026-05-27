# filepath: src/ingestion/main.py
"""Lambda handler for CENACE PML data ingestion.

This module serves as the entry point for the AWS Lambda function
that ingests daily PML data from CENACE.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.ingestion.cenace_client import CenaceAPIClient
from src.ingestion.data_validator import validate_data_quality
from src.ingestion.s3_manager import S3Manager
from src.utils.config import LOOKBACK_DAYS, NODOS, S3_BUCKET, get_date_range

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for daily PML data ingestion.
    
    Args:
        event: Lambda event (unused for EventBridge triggers)
        context: Lambda context object
        
    Returns:
        Dictionary with status and details of the ingestion
    """
    start_time = datetime.now(timezone.utc)
    logger.info("Starting CENACE PML data ingestion Lambda")
    
    # Configuration
    bucket = os.environ.get("S3_BUCKET", S3_BUCKET)
    days = int(os.environ.get("LOOKBACK_DAYS", LOOKBACK_DAYS))
    specific_nodes = os.environ.get("NODOS", "")  # Optional: comma-separated list
    
    # Parse specific nodes if provided
    nodos = None
    if specific_nodes:
        nodos = [n.strip() for n in specific_nodes.split(",")]
        logger.info(f"Fetching data for specific nodes: {nodos}")
    else:
        nodos = NODOS
        logger.info(f"Fetching data for all {len(NODOS)} nodes")
    
    # Initialize components
    api_client = CenaceAPIClient()
    s3_manager = S3Manager(bucket=bucket)
    
    # Track results
    results = {
        "status": "success",
        "start_time": start_time.isoformat(),
        "nodes_processed": 0,
        "nodes_failed": 0,
        "total_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "s3_uploads": 0,
        "errors": [],
    }
    
    failed_nodes = []
    
    # Calculate date range
    start_date, end_date = get_date_range(days)
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    
    # Process each node
    for nodo in nodos:
        try:
            # Fetch data from CENACE
            logger.info(f"Fetching data for node: {nodo}")
            records = api_client.fetch_pml_data(nodo, days)
            
            if not records:
                logger.warning(f"No records returned for node {nodo}")
                results["nodes_failed"] += 1
                failed_nodes.append(nodo)
                continue
            
            results["total_records"] += len(records)
            
            # Validate data quality
            validation_result = validate_data_quality(records)
            results["valid_records"] += validation_result.total_valid
            results["invalid_records"] += validation_result.total_invalid
            
            if validation_result.errors:
                for error in validation_result.errors:
                    results["errors"].append(f"{nodo}: {error}")
            
            # Group records by date for proper partitioning
            records_by_date: dict[str, list[dict]] = {}
            for record in validation_result.valid_records:
                fecha = record.get("fecha")
                if fecha:
                    if fecha not in records_by_date:
                        records_by_date[fecha] = []
                    records_by_date[fecha].append(record)
            
            # Upload each date's records to S3
            for fecha, date_records in records_by_date.items():
                success = s3_manager.upload_parquet(date_records, nodo, fecha)
                if success:
                    results["s3_uploads"] += 1
            
            results["nodes_processed"] += 1
            
            # Small delay to avoid API rate limiting
            import time
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Failed to process node {nodo}: {e}")
            results["nodes_failed"] += 1
            failed_nodes.append(nodo)
            results["errors"].append(f"{nodo}: {str(e)}")
    
    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    # Final status
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration
    results["failed_nodes"] = failed_nodes
    
    if results["nodes_failed"] > 0:
        results["status"] = "partial"
    
    logger.info(
        f"Ingestion complete. Processed: {results['nodes_processed']}, "
        f"Failed: {results['nodes_failed']}, Duration: {duration:.2f}s"
    )
    
    return results


def main() -> None:
    """Local execution entry point for testing."""
    print("Running local ingestion test...")
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
