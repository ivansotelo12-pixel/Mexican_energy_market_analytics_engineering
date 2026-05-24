# filepath: src/ingestion/data_validator.py
"""Data validation for PML records from CENACE."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Required fields in a PML record
REQUIRED_FIELDS = [
    "nodo",
    "fecha",
    "pml",
    "pml_energia",
    "pml_perdidas",
    "pml_congestion",
]

# Expected data types for PML fields
FIELD_TYPES = {
    "nodo": (str,),
    "fecha": (str,),
    "pml": (int, float),
    "pml_energia": (int, float),
    "pml_perdidas": (int, float),
    "pml_congestion": (int, float),
}

# Valid range for PML values (MXN/MWh)
PML_MIN = 0
PML_MAX = 50000


class ValidationResult:
    """Result of data validation."""
    
    def __init__(self):
        self.valid_records: list[dict[str, Any]] = []
        self.invalid_records: list[dict[str, Any]] = []
        self.errors: list[str] = []
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and len(self.invalid_records) == 0
    
    @property
    def total_valid(self) -> int:
        return len(self.valid_records)
    
    @property
    def total_invalid(self) -> int:
        return len(self.invalid_records)
    
    def add_error(self, message: str):
        self.errors.append(message)


def validate_record(record: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a single PML record.
    
    Args:
        record: PML record dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in record:
            return False, f"Missing required field: {field}"
    
    # Check field types
    for field, expected_types in FIELD_TYPES.items():
        if field in record and record[field] is not None:
            if not isinstance(record[field], expected_types):
                return False, f"Invalid type for {field}: expected {expected_types}, got {type(record[field])}"
    
    # Validate PML ranges (if values are numeric)
    for pml_field in ["pml", "pml_energia", "pml_perdidas", "pml_congestion"]:
        value = record.get(pml_field)
        if value is not None and isinstance(value, (int, float)):
            if value < PML_MIN or value > PML_MAX:
                return False, f"{pml_field} value {value} outside valid range [{PML_MIN}, {PML_MAX}]"
    
    # Validate date format if present
    fecha = record.get("fecha")
    if fecha:
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            return False, f"Invalid date format: {fecha}"
    
    # Validate nodo format (should match pattern like 03CHI-115)
    nodo = record.get("nodo")
    if nodo and not _validate_nodo_format(nodo):
        return False, f"Invalid nodo format: {nodo}"
    
    return True, None


def _validate_nodo_format(nodo: str) -> bool:
    """Validate node identifier format.
    
    Args:
        nodo: Node identifier
        
    Returns:
        True if format is valid
    """
    # Expected format: 2-4 digits followed by 2-4 letters/numbers, dash, digits
    # Examples: 03CHI-115, 03GJA-115, 03MAB1115
    if len(nodo) < 7 or len(nodo) > 10:
        return False
    
    parts = nodo.split("-")
    if len(parts) != 2:
        return False
    
    prefix, suffix = parts
    if not prefix[:2].isdigit():
        return False
    
    if not suffix.isdigit():
        return False
    
    return True


def validate_data_quality(records: list[dict[str, Any]]) -> ValidationResult:
    """Validate a list of PML records.
    
    Args:
        records: List of PML record dictionaries
        
    Returns:
        ValidationResult with valid/invalid records and any errors
    """
    result = ValidationResult()
    
    if not records:
        result.add_error("No records to validate")
        return result
    
    logger.info(f"Validating {len(records)} records...")
    
    for i, record in enumerate(records):
        is_valid, error = validate_record(record)
        
        if is_valid:
            result.valid_records.append(record)
        else:
            result.invalid_records.append(record)
            logger.warning(f"Record {i} invalid: {error} - Record: {record}")
    
    logger.info(
        f"Validation complete: {result.total_valid} valid, "
        f"{result.total_invalid} invalid out of {len(records)} total"
    )
    
    return result


def filter_valid_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filter records into valid and invalid.
    
    Args:
        records: List of PML records
        
    Returns:
        Tuple of (valid_records, invalid_records)
    """
    result = validate_data_quality(records)
    return result.valid_records, result.invalid_records
