# filepath: src/ingestion/cenace_client.py
"""CENACE API client for fetching PML (Precios Marginales Locales) data."""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.config import build_cenace_url, get_date_range, NODOS

logger = logging.getLogger(__name__)


class CenaceAPIClient:
    """Client for interacting with the CENACE PML API."""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        """Initialize CENACE API client.
        
        Args:
            max_retries: Maximum number of retry attempts for failed requests
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(self, url: str) -> dict[str, Any]:
        """Make HTTP request with retry logic.
        
        Args:
            url: Complete URL for the API request
            
        Returns:
            Parsed JSON response from API
            
        Raises:
            requests.HTTPError: If request fails after retries
        """
        logger.info(f"Fetching data from: {url}")
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def fetch_pml_data(self, nodo: str, days: int = 7) -> list[dict[str, Any]]:
        """Fetch PML data for a specific node over a date range.
        
        Args:
            nodo: Node identifier (e.g., '03CHI-115')
            days: Number of days to look back (default: 7)
            
        Returns:
            List of PML data records
        """
        start_date, end_date = get_date_range(days)
        url = build_cenace_url(nodo, start_date, end_date)
        
        try:
            data = self._make_request(url)
            records = self._parse_response(data, nodo)
            logger.info(f"Fetched {len(records)} records for node {nodo}")
            return records
        except requests.RequestException as e:
            logger.error(f"Failed to fetch data for node {nodo}: {e}")
            raise
    
    def _parse_response(self, data: dict[str, Any], nodo: str) -> list[dict[str, Any]]:
        """Parse CENACE API response into standardized records.
        
        Args:
            data: Raw API response dictionary
            nodo: Node identifier for reference
            
        Returns:
            List of parsed PML records
        """
        records = []
        
        # Navigate the response structure
        # Expected: {"datos":[...], "mensaje": "...", "status": "..."}
        datos = data.get("datos", [])
        
        for item in datos:
            record = {
                "nodo": nodo,
                "fecha": item.get("fecha"),
                "pml": item.get("pml"),
                "pml_energia": item.get("pml_energia"),
                "pml_perdidas": item.get("pml_perdidas"),
                "pml_congestion": item.get("pml_congestion"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            records.append(record)
        
        return records
    
    def fetch_all_nodes(self, days: int = 7) -> list[dict[str, Any]]:
        """Fetch PML data for all configured nodes.
        
        Args:
            days: Number of days to look back (default: 7)
            
        Returns:
            Combined list of PML records from all nodes
        """
        all_records = []
        
        for nodo in NODOS:
            try:
                records = self.fetch_pml_data(nodo, days)
                all_records.extend(records)
                # Small delay to avoid overwhelming the API
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"Skipping node {nodo} due to error: {e}")
                continue
        
        logger.info(f"Total records fetched: {len(all_records)} from {len(NODOS)} nodes")
        return all_records


def fetch_cenace_pml_data(nodos: list[str] | None = None, days: int = 7) -> list[dict[str, Any]]:
    """Convenience function to fetch PML data.
    
    Args:
        nodos: Optional list of specific nodes to fetch. If None, fetches all.
        days: Number of days to look back (default: 7)
        
    Returns:
        List of PML data records
    """
    client = CenaceAPIClient()
    
    if nodos:
        records = []
        for nodo in nodos:
            try:
                records.extend(client.fetch_pml_data(nodo, days))
            except Exception as e:
                logger.warning(f"Failed to fetch {nodo}: {e}")
        return records
    else:
        return client.fetch_all_nodes(days)
