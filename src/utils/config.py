# filepath: src/utils/config.py
"""Configuration constants for CENACE data ingestion."""

import os
from datetime import datetime, timedelta, timezone

# =============================================================================
# CENACE API Configuration
# =============================================================================
CENACE_BASE_URL = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
CENACE_SISTEMA = "SIN"
CENACE_PROCESO = "MDA"
CENACE_FORMATO = "JSON"

# =============================================================================
# S3 Configuration
# =============================================================================
S3_BUCKET = os.environ.get("S3_BUCKET", "mexican-energy-pml-raw")
S3_RAW_PREFIX = "raw/pml"
S3_PROCESSED_PREFIX = "processed/pml"

# =============================================================================
# Data Retention
# =============================================================================
RAW_RETENTION_DAYS = 90
LOOKBACK_DAYS = 7

# =============================================================================
# Node List (from Nodos.md)
# =============================================================================
NODOS = [
    "03GJA-115", "03ICL-115", "03MGM-230", "03SPA-115", "03SPA-230",
    "03LSA-115", "03MMX-115", "03HND-115", "03HNM-115", "03VTC-115",
    "03VTM-115", "03VT2-115", "03VWS-115", "03AYA-115", "03CAE-115",
    "03CHI-115", "03CIF-115", "03CLF-115", "03CLP-115", "03CLY-115",
    "03COO-115", "03CTI-115", "03CUE-115", "03CYA-115", "03CYI-115",
    "03DHD-115", "03ELR-115", "03EME-115", "03FRA-115", "03GKN-115",
    "03GMC-115", "03GSU-115", "03GTO-115", "03HDA-115", "03CYS-115",
    "03IRP-115", "03LJY-115", "03SPL-115", "03RPI-115", "03VYN-115",
    "03MMH-115", "03IGC-115", "03API-115", "03MTK-115", "03GOC-115",
    "03NUM-115", "03SFT-115", "03MRC-115", "03MTO-115", "03NGA-115",
    "03AMB-115", "03APO-115", "03APS-115", "03IPP-115", "03IRA-115",
    "03IRI-115", "03JEM-115", "03JYU-115", "03LCN-115", "03LDE-230",
    "03LNA-115", "03LNM-115", "03LNN-115", "03LNO-115", "03LNP-115",
    "03LNU-115", "03LPM-115", "03LTL-115", "03LVR-115", "03MAL-115",
    "03MHI-115", "03ABS-115", "03AIL-115", "03RTA-115", "03RYM-115",
    "03SAP-115", "03SCA-115", "03SDD-115", "03SFD-115", "03SFL-115",
    "03SIB-230", "03SIL-115", "03SJI-115", "03SMS-115", "03SRQ-115",
    "03STF-115", "03URG-115", "03VAS-115", "03VEL-115", "03PGM-115",
    "03PIR-115", "03PNJ-115", "03PNV-115", "03PRT-115", "03PTI-115",
    "03SDP-115", "03TRJ-115", "03MAB1115", "03MRA1115", "03PAP1115",
]

# =============================================================================
# Helper Functions
# =============================================================================
def get_date_range(days: int = LOOKBACK_DAYS) -> tuple[datetime, datetime]:
    """Calculate date range for API queries.
    
    Returns:
        Tuple of (start_date, end_date) for the last N days.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def format_cenace_date(dt: datetime) -> str:
    """Format datetime for CENACE API URL."""
    return dt.strftime("%Y/%m/%d")


def build_cenace_url(nodo: str, start_date: datetime, end_date: datetime) -> str:
    """Build CENACE API URL for a specific node and date range.
    
    Args:
        nodo: Node identifier (e.g., '03CHI-115')
        start_date: Start of date range
        end_date: End of date range
    
    Returns:
        Complete URL string for CENACE API
    """
    start_str = format_cenace_date(start_date)
    end_str = format_cenace_date(end_date)
    
    return (
        f"{CENACE_BASE_URL}/{CENACE_SISTEMA}/{CENACE_PROCESO}/{nodo}/"
        f"{start_str}/{end_str}/{CENACE_FORMATO}"
    )
