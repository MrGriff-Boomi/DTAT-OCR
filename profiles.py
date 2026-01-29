"""
Profile and Schema Management System

Defines data models for user-defined extraction profiles that specify
what fields to extract from specific document types (invoices, receipts, forms, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator


class ExtractionStrategy(str, Enum):
    """How to locate a field in the document"""
    COORDINATE = "coordinate"        # Fixed position (x, y, width, height)
    KEYWORD_PROXIMITY = "keyword"    # Near a keyword (e.g., "Total:" followed by number)
    TABLE_COLUMN = "table_column"    # Specific column in detected table
    REGEX_PATTERN = "regex"          # Pattern matching in text
    SEMANTIC_LLM = "semantic"        # LLM-based extraction with prompt


class FieldType(str, Enum):
    """Data type for extracted field"""
    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    BOOLEAN = "boolean"


class CoordinateBox(BaseModel):
    """Normalized coordinates (0.0 - 1.0)"""
    x: float = Field(..., ge=0, le=1, description="Left position (0-1)")
    y: float = Field(..., ge=0, le=1, description="Top position (0-1)")
    width: float = Field(..., ge=0, le=1, description="Box width (0-1)")
    height: float = Field(..., ge=0, le=1, description="Box height (0-1)")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")

    class Config:
        json_schema_extra = {
            "example": {
                "x": 0.5,
                "y": 0.1,
                "width": 0.3,
                "height": 0.05,
                "page": 1
            }
        }


class KeywordRule(BaseModel):
    """Keyword proximity extraction"""
    keyword: str = Field(..., description="Keyword to search for (e.g., 'Total:', 'Invoice #:')")
    direction: str = Field(default="right", description="Direction to look for value: right, left, above, below")
    max_distance: int = Field(default=100, description="Maximum distance in pixels")
    pattern: Optional[str] = Field(None, description="Optional regex to match value")

    class Config:
        json_schema_extra = {
            "example": {
                "keyword": "Total:",
                "direction": "right",
                "max_distance": 150,
                "pattern": r"\$?([0-9,]+\.\d{2})"
            }
        }


class TableColumnRule(BaseModel):
    """Table column extraction"""
    table_index: int = Field(default=0, description="Which table (0 = first)")
    column_name: Optional[str] = Field(None, description="Column header name")
    column_index: Optional[int] = Field(None, description="Or column position (0-indexed)")
    row_filter: Optional[Dict[str, Any]] = Field(None, description="Filter rows by field values")

    class Config:
        json_schema_extra = {
            "example": {
                "table_index": 0,
                "column_name": "Amount",
                "row_filter": {"status": "paid"}
            }
        }


class FieldDefinition(BaseModel):
    """Single field to extract from document"""
    name: str = Field(..., description="Field identifier (e.g., 'invoice_number', 'total_amount')")
    label: str = Field(..., description="Human-readable label (e.g., 'Invoice Number')")
    field_type: FieldType
    required: bool = Field(default=False, description="Must be present for valid extraction")
    strategy: ExtractionStrategy

    # Strategy-specific config (only one should be populated based on strategy)
    coordinate_box: Optional[CoordinateBox] = None
    keyword_rule: Optional[KeywordRule] = None
    table_column_rule: Optional[TableColumnRule] = None
    regex_pattern: Optional[str] = None
    llm_prompt: Optional[str] = None

    # Validation rules
    validation_pattern: Optional[str] = Field(None, description="Additional regex validation")
    min_value: Optional[float] = Field(None, description="Minimum numeric value")
    max_value: Optional[float] = Field(None, description="Maximum numeric value")
    allowed_values: Optional[List[str]] = Field(None, description="Whitelist of allowed values")

    # Transformation
    format_string: Optional[str] = Field(None, description="Output format (e.g., '{:.2f}', '%Y-%m-%d')")
    default_value: Optional[Any] = Field(None, description="Default if extraction fails")

    @model_validator(mode='after')
    def validate_strategy_config(self):
        """Ensure correct config is provided for strategy."""

        strategy_config_map = {
            ExtractionStrategy.COORDINATE: ('coordinate_box', 'coordinate box'),
            ExtractionStrategy.KEYWORD_PROXIMITY: ('keyword_rule', 'keyword rule'),
            ExtractionStrategy.TABLE_COLUMN: ('table_column_rule', 'table column rule'),
            ExtractionStrategy.REGEX_PATTERN: ('regex_pattern', 'regex pattern'),
            ExtractionStrategy.SEMANTIC_LLM: ('llm_prompt', 'LLM prompt'),
        }

        # Get required config for this strategy
        required_field, display_name = strategy_config_map[self.strategy]

        # Check if required config is provided
        if getattr(self, required_field) is None:
            raise ValueError(
                f"Field '{self.name}': Strategy '{self.strategy.value}' requires "
                f"'{required_field}' to be set"
            )

        # Warn if other configs are set (may be user error)
        other_fields = [field for field, _ in strategy_config_map.values() if field != required_field]
        set_others = [field for field in other_fields if getattr(self, field) is not None]

        if set_others:
            # This is a warning, not an error (maybe user plans to change strategy later)
            import warnings
            warnings.warn(
                f"Field '{self.name}': Strategy '{self.strategy.value}' uses '{required_field}', "
                f"but these configs are also set and will be ignored: {set_others}"
            )

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "name": "total_amount",
                "label": "Total Amount",
                "field_type": "currency",
                "required": True,
                "strategy": "keyword",
                "keyword_rule": {
                    "keyword": "Total:",
                    "direction": "right",
                    "max_distance": 150,
                    "pattern": r"\$?([0-9,]+\.\d{2})"
                },
                "min_value": 0.0
            }
        }


class ExtractionProfile(BaseModel):
    """Complete extraction profile for a document type"""
    id: Optional[int] = None
    name: str = Field(..., description="Unique profile identifier (e.g., 'acme-corp-invoice')")
    display_name: str = Field(..., description="Human-readable name (e.g., 'ACME Corp Invoice')")
    description: Optional[str] = Field(None, description="Profile description")
    document_type: str = Field(..., description="Document category: invoice, receipt, w2, etc.")
    version: int = Field(default=1, ge=1, description="Profile version number")

    fields: List[FieldDefinition] = Field(..., description="Fields to extract")

    # Profile metadata
    created_by: Optional[str] = Field(None, description="User who created the profile")
    organization_id: Optional[str] = Field(None, description="Organization identifier")
    is_template: bool = Field(default=False, description="Built-in template profile")
    is_active: bool = Field(default=True, description="Profile enabled for use")

    # Processing hints
    min_confidence: float = Field(default=60.0, ge=0, le=100, description="Minimum confidence threshold")
    ocr_strategy: str = Field(default="auto", description="OCR strategy: auto, native, ocr_only")

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "generic-invoice",
                "display_name": "Generic Invoice",
                "description": "Standard invoice extraction profile",
                "document_type": "invoice",
                "fields": [
                    {
                        "name": "invoice_number",
                        "label": "Invoice Number",
                        "field_type": "text",
                        "required": True,
                        "strategy": "keyword",
                        "keyword_rule": {
                            "keyword": "Invoice #:",
                            "direction": "right",
                            "max_distance": 150
                        }
                    }
                ],
                "min_confidence": 60.0,
                "ocr_strategy": "auto"
            }
        }


class ProfileVersion(BaseModel):
    """Version history for profile changes"""
    id: Optional[int] = None
    profile_id: int
    version: int
    profile_schema: Dict[str, Any] = Field(..., description="Serialized profile at this version")
    created_by: Optional[str] = Field(None, description="User who created this version")
    change_description: Optional[str] = Field(None, description="What changed in this version")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "profile_id": 1,
                "version": 2,
                "profile_schema": {"name": "invoice-v2", "fields": []},
                "created_by": "user@example.com",
                "change_description": "Added tax field",
                "created_at": "2026-01-29T10:00:00Z"
            }
        }


class ProfileUsageStats(BaseModel):
    """Statistics for profile usage"""
    id: Optional[int] = None
    profile_id: int
    document_id: int

    # Extraction results
    fields_extracted: int = Field(default=0, description="Number of fields successfully extracted")
    fields_failed: int = Field(default=0, description="Number of fields that failed extraction")
    avg_confidence: float = Field(default=0.0, description="Average confidence score")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")

    # Outcome
    status: str = Field(default="success", description="success, partial, failed")
    error_message: Optional[str] = None

    executed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "profile_id": 1,
                "document_id": 123,
                "fields_extracted": 5,
                "fields_failed": 1,
                "avg_confidence": 0.87,
                "processing_time_ms": 1250,
                "status": "partial",
                "executed_at": "2026-01-29T10:00:00Z"
            }
        }


class ExtractedFieldResult(BaseModel):
    """Result of extracting a single field"""
    value: Any = Field(..., description="Extracted and transformed value")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    location: Optional[Dict[str, Any]] = Field(None, description="Bounding box where value was found")
    raw_value: Optional[str] = Field(None, description="Original text before transformation")
    field_type: str = Field(..., description="Field type from profile")

    class Config:
        json_schema_extra = {
            "example": {
                "value": 1234.56,
                "confidence": 0.95,
                "location": {"x": 0.8, "y": 0.9, "width": 0.15, "height": 0.04},
                "raw_value": "$1,234.56",
                "field_type": "currency"
            }
        }


class ExtractionValidation(BaseModel):
    """Validation results for extraction"""
    is_valid: bool = Field(..., description="All required fields extracted and valid")
    missing_required: List[str] = Field(default_factory=list, description="Required fields not found")
    invalid_fields: List[Dict[str, Any]] = Field(default_factory=list, description="Fields that failed validation")

    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": False,
                "missing_required": ["invoice_date"],
                "invalid_fields": [
                    {
                        "field": "total_amount",
                        "error": "Value -100.0 < minimum 0.0",
                        "value": -100.0
                    }
                ]
            }
        }


class ExtractionStats(BaseModel):
    """Statistics for extraction attempt"""
    total_fields: int = Field(..., description="Total fields in profile")
    extracted: int = Field(..., description="Successfully extracted fields")
    failed: int = Field(..., description="Failed extractions")
    avg_confidence: float = Field(..., description="Average confidence across extracted fields")

    class Config:
        json_schema_extra = {
            "example": {
                "total_fields": 10,
                "extracted": 9,
                "failed": 1,
                "avg_confidence": 0.87
            }
        }


class ProfileExtractionResult(BaseModel):
    """Complete result of profile-based extraction"""
    fields: Dict[str, ExtractedFieldResult] = Field(..., description="Extracted field values")
    validation: ExtractionValidation = Field(..., description="Validation results")
    extraction_stats: ExtractionStats = Field(..., description="Extraction statistics")

    class Config:
        json_schema_extra = {
            "example": {
                "fields": {
                    "invoice_number": {
                        "value": "INV-2024-001",
                        "confidence": 0.95,
                        "location": {"x": 0.7, "y": 0.1, "width": 0.2, "height": 0.05},
                        "raw_value": "INV-2024-001",
                        "field_type": "text"
                    },
                    "total_amount": {
                        "value": 1234.56,
                        "confidence": 0.98,
                        "location": {"x": 0.8, "y": 0.9, "width": 0.15, "height": 0.04},
                        "raw_value": "$1,234.56",
                        "field_type": "currency"
                    }
                },
                "validation": {
                    "is_valid": True,
                    "missing_required": [],
                    "invalid_fields": []
                },
                "extraction_stats": {
                    "total_fields": 5,
                    "extracted": 5,
                    "failed": 0,
                    "avg_confidence": 0.92
                }
            }
        }
