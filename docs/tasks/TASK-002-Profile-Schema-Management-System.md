# TASK-002: Profile & Schema Management System

**Status**: Not Started
**Priority**: High
**Depends On**: TASK-001 (Multi-Format Output Support)
**Created**: 2026-01-29

## Executive Summary

Implement a flexible profile/schema management system that allows users to define custom output formats and field extraction rules. This transforms DTAT from a generic OCR service into a configurable document intelligence platform where users can create reusable extraction profiles for specific document types (invoices, receipts, forms, etc.).

## Problem Statement

Current OCR solutions force users to:
1. Parse unstructured text output manually
2. Write custom code to extract specific fields
3. Maintain brittle extraction logic in their applications
4. Repeat this for every document type they process

Users need a way to:
- Define what fields they want extracted from specific document types
- Specify validation rules and data types for fields
- Reuse profiles across multiple documents
- Version and manage extraction schemas
- Apply transformations and normalizations to extracted data

## User Stories

**As a developer**, I want to:
- Create extraction profiles via API without writing code
- Define field locations using visual coordinates or semantic rules
- Validate extracted data against JSON schemas
- Version profiles and rollback if needed
- Share profiles across my organization

**As a business user**, I want to:
- Extract structured data from invoices automatically
- Define what an "invoice" looks like once and reuse it
- Get consistent JSON output I can load into my database
- Handle variations in vendor invoice formats

**As a platform operator**, I want to:
- Store thousands of profiles efficiently
- Allow users to manage their own profiles
- Audit profile usage and performance
- Provide profile templates for common document types

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                   Profile Management                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Profile CRUD API         Profile Validator             │
│  ├─ Create                ├─ JSON Schema validation     │
│  ├─ Read                  ├─ Field type checking        │
│  ├─ Update (versioned)    └─ Rule consistency          │
│  ├─ Delete                                              │
│  └─ List/Search           Profile Templates             │
│                           ├─ Invoice (generic)          │
│  Profile Storage          ├─ Receipt (retail)           │
│  ├─ PostgreSQL (metadata) ├─ W-2 (tax form)            │
│  ├─ JSONB (schema)        ├─ Passport                   │
│  └─ Versioning            └─ Driver's License           │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Extraction Engine                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Field Extractors         Data Transformers             │
│  ├─ Coordinate-based      ├─ Currency normalization     │
│  ├─ Keyword proximity     ├─ Date parsing               │
│  ├─ Table column          ├─ Number formatting          │
│  ├─ Regex pattern         ├─ Address parsing            │
│  └─ LLM semantic          └─ Name splitting             │
│                                                          │
│  Validation & Scoring     Post-Processing               │
│  ├─ Required field check  ├─ Confidence filtering       │
│  ├─ Type validation       ├─ Multi-value aggregation    │
│  ├─ Format validation     └─ Fallback strategies        │
│  └─ Business rules                                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Data Model

#### Profile Schema

```python
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

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
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    width: float = Field(..., ge=0, le=1)
    height: float = Field(..., ge=0, le=1)
    page: int = Field(default=1, ge=1)

class KeywordRule(BaseModel):
    """Keyword proximity extraction"""
    keyword: str                          # "Total:", "Invoice #:", etc.
    direction: str = "right"              # right, left, above, below
    max_distance: int = 100               # pixels
    pattern: Optional[str] = None         # regex to match value

class TableColumnRule(BaseModel):
    """Table column extraction"""
    table_index: int = 0                  # Which table (0 = first)
    column_name: Optional[str] = None     # Column header
    column_index: Optional[int] = None    # Or column position
    row_filter: Optional[Dict] = None     # {"status": "paid"}

class FieldDefinition(BaseModel):
    """Single field to extract"""
    name: str                                    # "invoice_number", "total_amount"
    label: str                                   # Human-readable "Invoice Number"
    field_type: FieldType
    required: bool = False
    strategy: ExtractionStrategy

    # Strategy-specific config
    coordinate_box: Optional[CoordinateBox] = None
    keyword_rule: Optional[KeywordRule] = None
    table_column_rule: Optional[TableColumnRule] = None
    regex_pattern: Optional[str] = None
    llm_prompt: Optional[str] = None

    # Validation
    validation_pattern: Optional[str] = None     # Additional regex validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[str]] = None

    # Transformation
    format_string: Optional[str] = None          # "{:.2f}", "%Y-%m-%d"
    default_value: Optional[Any] = None

class ExtractionProfile(BaseModel):
    """Complete extraction profile for a document type"""
    id: Optional[int] = None
    name: str                                    # "acme-corp-invoice"
    display_name: str                            # "ACME Corp Invoice"
    description: Optional[str] = None
    document_type: str                           # "invoice", "receipt", "w2"
    version: int = 1

    fields: List[FieldDefinition]

    # Profile metadata
    created_by: Optional[str] = None
    organization_id: Optional[str] = None
    is_template: bool = False                    # Built-in template
    is_active: bool = True

    # Processing hints
    min_confidence: float = 60.0
    ocr_strategy: str = "auto"                   # "auto", "native", "ocr_only"

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ProfileVersion(BaseModel):
    """Version history for profile changes"""
    profile_id: int
    version: int
    schema: Dict[str, Any]                       # Serialized profile
    created_by: str
    change_description: Optional[str] = None
    created_at: datetime
```

#### Database Schema (PostgreSQL)

```sql
-- Profiles table
CREATE TABLE extraction_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    document_type VARCHAR(50) NOT NULL,
    version INTEGER DEFAULT 1,

    -- Profile definition (JSONB for flexibility)
    schema JSONB NOT NULL,

    -- Metadata
    created_by VARCHAR(255),
    organization_id VARCHAR(255),
    is_template BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Processing hints
    min_confidence FLOAT DEFAULT 60.0,
    ocr_strategy VARCHAR(20) DEFAULT 'auto',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    CONSTRAINT valid_ocr_strategy CHECK (ocr_strategy IN ('auto', 'native', 'ocr_only'))
);

CREATE INDEX idx_profiles_document_type ON extraction_profiles(document_type);
CREATE INDEX idx_profiles_organization ON extraction_profiles(organization_id);
CREATE INDEX idx_profiles_active ON extraction_profiles(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_profiles_schema ON extraction_profiles USING GIN(schema);

-- Profile versions (audit trail)
CREATE TABLE profile_versions (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES extraction_profiles(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    schema JSONB NOT NULL,
    created_by VARCHAR(255),
    change_description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(profile_id, version)
);

CREATE INDEX idx_versions_profile ON profile_versions(profile_id, version DESC);

-- Profile usage statistics
CREATE TABLE profile_usage (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES extraction_profiles(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,

    -- Extraction results
    fields_extracted INTEGER,
    fields_failed INTEGER,
    avg_confidence FLOAT,
    processing_time_ms INTEGER,

    -- Outcome
    status VARCHAR(20),  -- success, partial, failed
    error_message TEXT,

    executed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_usage_profile ON profile_usage(profile_id, executed_at DESC);
CREATE INDEX idx_usage_document ON profile_usage(document_id);

-- Link profiles to documents
ALTER TABLE documents ADD COLUMN profile_id INTEGER REFERENCES extraction_profiles(id);
ALTER TABLE documents ADD COLUMN extracted_fields JSONB;
CREATE INDEX idx_documents_profile ON documents(profile_id);
```

### API Endpoints

```python
from fastapi import FastAPI, HTTPException, Depends, Query
from typing import List, Optional

app = FastAPI()

# ==================== Profile Management ====================

@app.post("/profiles", response_model=ExtractionProfile, status_code=201)
async def create_profile(profile: ExtractionProfile):
    """
    Create a new extraction profile.

    Example:
    POST /profiles
    {
        "name": "acme-invoice",
        "display_name": "ACME Corp Invoice",
        "document_type": "invoice",
        "fields": [
            {
                "name": "invoice_number",
                "label": "Invoice Number",
                "field_type": "text",
                "required": true,
                "strategy": "keyword",
                "keyword_rule": {
                    "keyword": "Invoice #:",
                    "direction": "right",
                    "max_distance": 100
                }
            },
            {
                "name": "total_amount",
                "label": "Total Amount",
                "field_type": "currency",
                "required": true,
                "strategy": "keyword",
                "keyword_rule": {
                    "keyword": "Total:",
                    "direction": "right",
                    "pattern": "\\$?([0-9,]+\\.\\d{2})"
                }
            }
        ]
    }
    """
    # Validate profile schema
    validate_profile_schema(profile)

    # Save to database
    db_profile = save_profile(profile)

    # Create initial version
    create_profile_version(db_profile.id, profile.dict(), "Initial version")

    return db_profile

@app.get("/profiles", response_model=List[ExtractionProfile])
async def list_profiles(
    document_type: Optional[str] = None,
    organization_id: Optional[str] = None,
    is_template: Optional[bool] = None,
    active_only: bool = True,
    limit: int = Query(100, le=500),
    offset: int = 0
):
    """List all extraction profiles with optional filters."""
    return query_profiles(
        document_type=document_type,
        organization_id=organization_id,
        is_template=is_template,
        active_only=active_only,
        limit=limit,
        offset=offset
    )

@app.get("/profiles/{profile_id}", response_model=ExtractionProfile)
async def get_profile(profile_id: int):
    """Get a specific extraction profile by ID."""
    profile = get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.get("/profiles/by-name/{name}", response_model=ExtractionProfile)
async def get_profile_by_name(name: str):
    """Get a specific extraction profile by name."""
    profile = find_profile_by_name(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.put("/profiles/{profile_id}", response_model=ExtractionProfile)
async def update_profile(
    profile_id: int,
    profile: ExtractionProfile,
    change_description: Optional[str] = None
):
    """
    Update an existing profile (creates new version).

    Changes are versioned - previous versions remain accessible.
    """
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Validate new schema
    validate_profile_schema(profile)

    # Increment version
    new_version = existing.version + 1
    profile.version = new_version
    profile.id = profile_id

    # Save new version
    create_profile_version(
        profile_id,
        profile.dict(),
        change_description or f"Updated to version {new_version}"
    )

    # Update current profile
    updated = update_profile_record(profile_id, profile)
    return updated

@app.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, hard_delete: bool = False):
    """
    Delete or deactivate a profile.

    - hard_delete=False (default): Sets is_active=False, preserves data
    - hard_delete=True: Permanently deletes profile and versions
    """
    if hard_delete:
        delete_profile_permanent(profile_id)
    else:
        deactivate_profile(profile_id)

@app.get("/profiles/{profile_id}/versions", response_model=List[ProfileVersion])
async def get_profile_versions(profile_id: int):
    """Get version history for a profile."""
    return get_versions_for_profile(profile_id)

@app.post("/profiles/{profile_id}/rollback/{version}", response_model=ExtractionProfile)
async def rollback_profile(profile_id: int, version: int):
    """
    Rollback profile to a previous version.

    Creates a new version with the old schema.
    """
    old_version = get_profile_version(profile_id, version)
    if not old_version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Create new version with old schema
    profile_dict = old_version.schema
    profile_dict['version'] = get_profile_by_id(profile_id).version + 1

    profile = ExtractionProfile(**profile_dict)
    return update_profile(
        profile_id,
        profile,
        f"Rolled back to version {version}"
    )

# ==================== Profile Templates ====================

@app.get("/templates", response_model=List[ExtractionProfile])
async def list_templates():
    """List built-in profile templates."""
    return query_profiles(is_template=True)

@app.post("/templates/{template_name}/instantiate", response_model=ExtractionProfile)
async def create_from_template(
    template_name: str,
    customization: Dict[str, Any] = {}
):
    """
    Create a new profile from a built-in template.

    Example:
    POST /templates/generic-invoice/instantiate
    {
        "name": "my-custom-invoice",
        "display_name": "My Custom Invoice",
        "organization_id": "org-123"
    }
    """
    template = find_profile_by_name(template_name)
    if not template or not template.is_template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Clone template and apply customizations
    new_profile = template.copy()
    new_profile.id = None
    new_profile.is_template = False
    new_profile.version = 1

    for key, value in customization.items():
        if hasattr(new_profile, key):
            setattr(new_profile, key, value)

    return create_profile(new_profile)

# ==================== Document Processing with Profiles ====================

@app.post("/process-with-profile", status_code=202)
async def process_with_profile(
    file: UploadFile,
    profile_id: Optional[int] = None,
    profile_name: Optional[str] = None,
    return_format: str = "structured"  # "structured", "textract", "google", "azure"
):
    """
    Process document with extraction profile.

    Returns both raw OCR output and structured extracted fields.

    Example:
    POST /process-with-profile
    - file: (binary)
    - profile_id: 42
    - return_format: structured

    Response:
    {
        "document_id": 123,
        "status": "completed",
        "profile": {
            "id": 42,
            "name": "acme-invoice"
        },
        "extracted_fields": {
            "invoice_number": {
                "value": "INV-2024-001",
                "confidence": 0.95,
                "location": {"x": 0.7, "y": 0.1, "width": 0.2, "height": 0.05}
            },
            "total_amount": {
                "value": 1234.56,
                "confidence": 0.98,
                "raw_text": "$1,234.56",
                "location": {"x": 0.8, "y": 0.9, "width": 0.15, "height": 0.04}
            },
            "line_items": [
                {
                    "description": "Widget A",
                    "quantity": 10,
                    "unit_price": 50.00,
                    "total": 500.00
                }
            ]
        },
        "validation": {
            "is_valid": true,
            "required_fields_present": true,
            "errors": []
        },
        "raw_ocr": { ... },  # Full Textract/Google/Azure format
        "processing_time_ms": 1250
    }
    """
    # Resolve profile
    if profile_id:
        profile = get_profile_by_id(profile_id)
    elif profile_name:
        profile = find_profile_by_name(profile_name)
    else:
        raise HTTPException(status_code=400, detail="Must specify profile_id or profile_name")

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Save uploaded file
    document = save_uploaded_document(file, profile_id=profile.id)

    # Queue for processing
    queue_document_extraction(document.id, profile.id)

    return {
        "document_id": document.id,
        "status": "queued",
        "profile": {
            "id": profile.id,
            "name": profile.name
        }
    }

@app.get("/documents/{doc_id}/extracted-fields")
async def get_extracted_fields(doc_id: int):
    """
    Get structured extracted fields for a document.

    Only returns data if document was processed with a profile.
    """
    document = get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.profile_id:
        raise HTTPException(
            status_code=400,
            detail="Document was not processed with a profile"
        )

    return {
        "document_id": doc_id,
        "profile": get_profile_by_id(document.profile_id),
        "fields": document.extracted_fields,
        "status": document.status
    }

# ==================== Profile Statistics ====================

@app.get("/profiles/{profile_id}/stats")
async def get_profile_stats(
    profile_id: int,
    days: int = Query(30, le=365)
):
    """
    Get usage statistics for a profile.

    Returns:
    - Total documents processed
    - Success rate
    - Average confidence per field
    - Most common errors
    - Processing time trends
    """
    stats = calculate_profile_statistics(profile_id, days)
    return stats
```

### Extraction Engine

```python
from typing import Dict, Any, List, Optional, Tuple
import re
from datetime import datetime

class FieldExtractor:
    """Base class for field extraction strategies"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Any, float, Optional[Dict]]:
        """
        Extract field value from OCR result.

        Returns:
            (value, confidence, location_dict)
        """
        raise NotImplementedError

class CoordinateExtractor(FieldExtractor):
    """Extract text from specific coordinates"""

    def extract(self, field_def, ocr_result, page=1):
        box = field_def.coordinate_box

        # Find blocks within bounding box
        matching_blocks = []
        for block in ocr_result.get('blocks', []):
            if block.get('page') != box.page:
                continue

            block_box = block['geometry']['boundingBox']
            if self._boxes_overlap(box, block_box):
                matching_blocks.append(block)

        if not matching_blocks:
            return None, 0.0, None

        # Concatenate text
        text = ' '.join(b['text'] for b in matching_blocks)
        confidence = sum(b['confidence'] for b in matching_blocks) / len(matching_blocks)

        return text, confidence, box.dict()

    def _boxes_overlap(self, box1, box2):
        """Check if two bounding boxes overlap"""
        return not (
            box1.x + box1.width < box2['left'] or
            box2['left'] + box2['width'] < box1.x or
            box1.y + box1.height < box2['top'] or
            box2['top'] + box2['height'] < box1.y
        )

class KeywordProximityExtractor(FieldExtractor):
    """Extract value near a keyword"""

    def extract(self, field_def, ocr_result, page=1):
        rule = field_def.keyword_rule
        blocks = ocr_result.get('blocks', [])

        # Find keyword block
        keyword_block = None
        for block in blocks:
            if rule.keyword.lower() in block['text'].lower():
                keyword_block = block
                break

        if not keyword_block:
            return None, 0.0, None

        # Find adjacent block in specified direction
        target_block = self._find_adjacent_block(
            keyword_block,
            blocks,
            direction=rule.direction,
            max_distance=rule.max_distance
        )

        if not target_block:
            return None, 0.0, None

        text = target_block['text']

        # Apply regex pattern if specified
        if rule.pattern:
            match = re.search(rule.pattern, text)
            if match:
                text = match.group(1) if match.groups() else match.group(0)
            else:
                return None, 0.0, None

        return text, target_block['confidence'], target_block['geometry']['boundingBox']

    def _find_adjacent_block(self, anchor, blocks, direction, max_distance):
        """Find block adjacent to anchor in specified direction"""
        ax, ay = anchor['geometry']['boundingBox']['left'], anchor['geometry']['boundingBox']['top']

        candidates = []
        for block in blocks:
            if block == anchor:
                continue

            bx, by = block['geometry']['boundingBox']['left'], block['geometry']['boundingBox']['top']
            distance = abs(bx - ax) + abs(by - ay)

            if distance > max_distance / 1000:  # Normalized coordinates
                continue

            # Check direction
            if direction == 'right' and bx > ax and abs(by - ay) < 0.02:
                candidates.append((distance, block))
            elif direction == 'left' and bx < ax and abs(by - ay) < 0.02:
                candidates.append((distance, block))
            elif direction == 'below' and by > ay and abs(bx - ax) < 0.02:
                candidates.append((distance, block))
            elif direction == 'above' and by < ay and abs(bx - ax) < 0.02:
                candidates.append((distance, block))

        if not candidates:
            return None

        # Return closest candidate
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

class TableColumnExtractor(FieldExtractor):
    """Extract data from table column"""

    def extract(self, field_def, ocr_result, page=1):
        rule = field_def.table_column_rule
        tables = ocr_result.get('tables', [])

        if not tables or rule.table_index >= len(tables):
            return None, 0.0, None

        table = tables[rule.table_index]

        # Find column index
        col_idx = rule.column_index
        if col_idx is None and rule.column_name:
            # Find by header name
            headers = table.get('headers', [])
            for i, header in enumerate(headers):
                if rule.column_name.lower() in header.lower():
                    col_idx = i
                    break

        if col_idx is None:
            return None, 0.0, None

        # Extract column values
        values = []
        rows = table.get('rows', [])
        for row in rows:
            if len(row) > col_idx:
                # Apply row filter if specified
                if rule.row_filter:
                    matches = all(
                        row.get(k) == v
                        for k, v in rule.row_filter.items()
                    )
                    if not matches:
                        continue

                values.append(row[col_idx])

        if not values:
            return None, 0.0, None

        # Return all values or first value depending on field type
        result = values if len(values) > 1 else values[0]
        confidence = 0.9  # Table extraction is generally high confidence

        return result, confidence, table.get('geometry')

class RegexExtractor(FieldExtractor):
    """Extract using regex pattern"""

    def extract(self, field_def, ocr_result, page=1):
        pattern = field_def.regex_pattern
        full_text = ocr_result.get('full_text', '')

        match = re.search(pattern, full_text)
        if not match:
            return None, 0.0, None

        value = match.group(1) if match.groups() else match.group(0)

        # Try to find location of matched text
        location = self._find_text_location(value, ocr_result)

        return value, 0.8, location  # Regex confidence is medium

    def _find_text_location(self, text, ocr_result):
        """Find bounding box of text in OCR result"""
        for block in ocr_result.get('blocks', []):
            if text in block['text']:
                return block['geometry']['boundingBox']
        return None

class SemanticLLMExtractor(FieldExtractor):
    """Extract using LLM with semantic understanding"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def extract(self, field_def, ocr_result, page=1):
        prompt = field_def.llm_prompt
        full_text = ocr_result.get('full_text', '')

        # Build extraction prompt
        extraction_prompt = f"""
Extract the following field from this document text:

Field: {field_def.label}
Type: {field_def.field_type}
Instructions: {prompt}

Document text:
{full_text}

Return ONLY the extracted value, no explanation.
If the field is not found, return "NOT_FOUND".
"""

        response = self.llm.complete(extraction_prompt)
        value = response.strip()

        if value == "NOT_FOUND":
            return None, 0.0, None

        return value, 0.85, None  # LLM confidence is generally good

# Extraction orchestrator
class ProfileExtractor:
    """Orchestrates extraction using a profile"""

    def __init__(self, llm_client=None):
        self.extractors = {
            ExtractionStrategy.COORDINATE: CoordinateExtractor(),
            ExtractionStrategy.KEYWORD_PROXIMITY: KeywordProximityExtractor(),
            ExtractionStrategy.TABLE_COLUMN: TableColumnExtractor(),
            ExtractionStrategy.REGEX_PATTERN: RegexExtractor(),
            ExtractionStrategy.SEMANTIC_LLM: SemanticLLMExtractor(llm_client) if llm_client else None
        }
        self.transformers = FieldTransformers()
        self.validators = FieldValidators()

    def extract_all_fields(
        self,
        profile: ExtractionProfile,
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract all fields defined in profile.

        Returns:
        {
            "fields": {
                "field_name": {
                    "value": <extracted_value>,
                    "confidence": 0.95,
                    "location": {...},
                    "raw_value": "<original_text>",
                    "field_type": "currency"
                }
            },
            "validation": {
                "is_valid": true,
                "missing_required": [],
                "invalid_fields": []
            },
            "extraction_stats": {
                "total_fields": 10,
                "extracted": 9,
                "failed": 1,
                "avg_confidence": 0.87
            }
        }
        """
        extracted = {}
        missing_required = []
        invalid_fields = []

        for field_def in profile.fields:
            # Extract field
            extractor = self.extractors.get(field_def.strategy)
            if not extractor:
                if field_def.required:
                    missing_required.append(field_def.name)
                continue

            value, confidence, location = extractor.extract(field_def, ocr_result)

            # Handle missing required field
            if value is None and field_def.required:
                missing_required.append(field_def.name)
                continue

            # Apply transformations
            if value is not None:
                raw_value = value
                value = self.transformers.transform(value, field_def)

                # Validate
                is_valid, error = self.validators.validate(value, field_def)
                if not is_valid:
                    invalid_fields.append({
                        "field": field_def.name,
                        "error": error,
                        "value": value
                    })
                    if field_def.required:
                        continue

                extracted[field_def.name] = {
                    "value": value,
                    "confidence": confidence,
                    "location": location,
                    "raw_value": raw_value,
                    "field_type": field_def.field_type.value
                }

        # Calculate stats
        stats = {
            "total_fields": len(profile.fields),
            "extracted": len(extracted),
            "failed": len(profile.fields) - len(extracted),
            "avg_confidence": (
                sum(f["confidence"] for f in extracted.values()) / len(extracted)
                if extracted else 0.0
            )
        }

        return {
            "fields": extracted,
            "validation": {
                "is_valid": len(missing_required) == 0 and len(invalid_fields) == 0,
                "missing_required": missing_required,
                "invalid_fields": invalid_fields
            },
            "extraction_stats": stats
        }

class FieldTransformers:
    """Data type transformations"""

    def transform(self, value: Any, field_def: FieldDefinition) -> Any:
        """Apply transformations based on field type"""

        if field_def.field_type == FieldType.NUMBER:
            return self._to_number(value)
        elif field_def.field_type == FieldType.CURRENCY:
            return self._to_currency(value)
        elif field_def.field_type == FieldType.DATE:
            return self._to_date(value, field_def.format_string)
        elif field_def.field_type == FieldType.PHONE:
            return self._normalize_phone(value)
        elif field_def.field_type == FieldType.EMAIL:
            return value.lower().strip()
        elif field_def.field_type == FieldType.BOOLEAN:
            return self._to_boolean(value)

        return value

    def _to_number(self, value: str) -> float:
        """Parse number from string"""
        cleaned = re.sub(r'[^\d.-]', '', str(value))
        return float(cleaned) if cleaned else 0.0

    def _to_currency(self, value: str) -> float:
        """Parse currency amount"""
        cleaned = re.sub(r'[^\d.]', '', str(value))
        return float(cleaned) if cleaned else 0.0

    def _to_date(self, value: str, format_string: Optional[str]) -> str:
        """Parse and normalize date"""
        # Try common formats
        formats = [
            '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
            '%Y/%m/%d', '%B %d, %Y', '%d %B %Y'
        ]

        if format_string:
            formats.insert(0, format_string)

        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.strftime('%Y-%m-%d')  # Normalize to ISO format
            except ValueError:
                continue

        return value  # Return as-is if parsing fails

    def _normalize_phone(self, value: str) -> str:
        """Normalize phone number"""
        digits = re.sub(r'\D', '', value)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        return value

    def _to_boolean(self, value: str) -> bool:
        """Parse boolean from string"""
        value_lower = str(value).lower().strip()
        return value_lower in ('yes', 'true', '1', 'y', 'checked', 'x')

class FieldValidators:
    """Field validation"""

    def validate(self, value: Any, field_def: FieldDefinition) -> Tuple[bool, Optional[str]]:
        """Validate extracted value against field definition"""

        # Pattern validation
        if field_def.validation_pattern:
            if not re.match(field_def.validation_pattern, str(value)):
                return False, f"Does not match pattern {field_def.validation_pattern}"

        # Range validation
        if field_def.min_value is not None:
            if float(value) < field_def.min_value:
                return False, f"Value {value} < minimum {field_def.min_value}"

        if field_def.max_value is not None:
            if float(value) > field_def.max_value:
                return False, f"Value {value} > maximum {field_def.max_value}"

        # Allowed values
        if field_def.allowed_values:
            if value not in field_def.allowed_values:
                return False, f"Value must be one of {field_def.allowed_values}"

        return True, None
```

## Built-in Profile Templates

### 1. Generic Invoice

```python
TEMPLATE_GENERIC_INVOICE = ExtractionProfile(
    name="template-generic-invoice",
    display_name="Generic Invoice Template",
    description="Standard invoice fields (works with most vendors)",
    document_type="invoice",
    is_template=True,
    fields=[
        FieldDefinition(
            name="invoice_number",
            label="Invoice Number",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Invoice #",
                direction="right",
                max_distance=150
            )
        ),
        FieldDefinition(
            name="invoice_date",
            label="Invoice Date",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Date:",
                direction="right",
                max_distance=150
            )
        ),
        FieldDefinition(
            name="vendor_name",
            label="Vendor Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.0, y=0.0, width=0.5, height=0.15, page=1)
        ),
        FieldDefinition(
            name="total_amount",
            label="Total Amount",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Total",
                direction="right",
                max_distance=200,
                pattern=r"\$?([0-9,]+\.\d{2})"
            ),
            min_value=0.0
        ),
        FieldDefinition(
            name="line_items",
            label="Line Items",
            field_type=FieldType.TEXT,
            required=False,
            strategy=ExtractionStrategy.TABLE_COLUMN,
            table_column_rule=TableColumnRule(
                table_index=0
            )
        )
    ]
)
```

### 2. Retail Receipt

```python
TEMPLATE_RETAIL_RECEIPT = ExtractionProfile(
    name="template-retail-receipt",
    display_name="Retail Receipt Template",
    description="Point-of-sale receipts (restaurants, retail)",
    document_type="receipt",
    is_template=True,
    fields=[
        FieldDefinition(
            name="merchant_name",
            label="Merchant Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.2, y=0.0, width=0.6, height=0.1)
        ),
        FieldDefinition(
            name="transaction_date",
            label="Date",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.REGEX_PATTERN,
            regex_pattern=r"(\d{1,2}/\d{1,2}/\d{4})"
        ),
        FieldDefinition(
            name="subtotal",
            label="Subtotal",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Subtotal", direction="right", max_distance=100)
        ),
        FieldDefinition(
            name="tax",
            label="Tax",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Tax", direction="right", max_distance=100)
        ),
        FieldDefinition(
            name="total",
            label="Total",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Total", direction="right", max_distance=100),
            min_value=0.0
        )
    ]
)
```

### 3. W-2 Tax Form

```python
TEMPLATE_W2_TAX_FORM = ExtractionProfile(
    name="template-w2-tax-form",
    display_name="W-2 Wage and Tax Statement",
    description="IRS Form W-2 (standardized layout)",
    document_type="tax_form",
    is_template=True,
    fields=[
        FieldDefinition(
            name="employee_ssn",
            label="Employee SSN",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.15, width=0.3, height=0.05),
            validation_pattern=r"\d{3}-\d{2}-\d{4}"
        ),
        FieldDefinition(
            name="employer_ein",
            label="Employer EIN",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.22, width=0.3, height=0.05),
            validation_pattern=r"\d{2}-\d{7}"
        ),
        FieldDefinition(
            name="wages_box1",
            label="Wages, tips, other compensation (Box 1)",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.35, width=0.2, height=0.05),
            min_value=0.0
        ),
        FieldDefinition(
            name="federal_tax_withheld_box2",
            label="Federal income tax withheld (Box 2)",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.8, y=0.35, width=0.2, height=0.05),
            min_value=0.0
        )
    ]
)
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Database schema and migrations
- [ ] Profile CRUD API endpoints
- [ ] Pydantic models and validation
- [ ] Basic profile storage (PostgreSQL + JSONB)
- [ ] Profile versioning system
- [ ] Unit tests for models and API

### Phase 2: Extraction Strategies (Week 3-4)
- [ ] Coordinate-based extractor
- [ ] Keyword proximity extractor
- [ ] Table column extractor
- [ ] Regex pattern extractor
- [ ] Field transformers (currency, date, phone, etc.)
- [ ] Field validators
- [ ] Integration tests for extractors

### Phase 3: Profile Templates (Week 5)
- [ ] Generic invoice template
- [ ] Retail receipt template
- [ ] W-2 tax form template
- [ ] Driver's license template
- [ ] Template instantiation API
- [ ] Template documentation

### Phase 4: Document Processing Integration (Week 6-7)
- [ ] Integrate profile extractor with main pipeline
- [ ] Update document processing workflow
- [ ] Profile-based retry logic
- [ ] Validation and error handling
- [ ] End-to-end tests

### Phase 5: Advanced Features (Week 8-9)
- [ ] LLM semantic extraction (Bedrock integration)
- [ ] Profile usage statistics
- [ ] Profile performance analytics
- [ ] Profile recommendation system
- [ ] Multi-profile processing (try multiple profiles)

### Phase 6: UI & Polish (Week 10)
- [ ] Web UI for profile management
- [ ] Visual profile editor (click-to-define fields)
- [ ] Profile testing interface
- [ ] Documentation and examples
- [ ] Migration guide

## Testing Strategy

### Unit Tests
```python
def test_create_profile():
    """Test profile creation"""
    profile = ExtractionProfile(
        name="test-invoice",
        display_name="Test Invoice",
        document_type="invoice",
        fields=[
            FieldDefinition(
                name="total",
                label="Total",
                field_type=FieldType.CURRENCY,
                required=True,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(keyword="Total:", direction="right")
            )
        ]
    )

    saved = create_profile(profile)
    assert saved.id is not None
    assert saved.version == 1

def test_profile_versioning():
    """Test profile version management"""
    # Create profile
    profile = create_profile(sample_profile)
    v1_id = profile.id

    # Update profile
    profile.fields.append(new_field)
    updated = update_profile(v1_id, profile, "Added new field")

    assert updated.version == 2

    # Get versions
    versions = get_profile_versions(v1_id)
    assert len(versions) == 2

def test_coordinate_extractor():
    """Test coordinate-based extraction"""
    extractor = CoordinateExtractor()
    field_def = FieldDefinition(
        name="test",
        label="Test",
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.COORDINATE,
        coordinate_box=CoordinateBox(x=0.5, y=0.5, width=0.2, height=0.1)
    )

    ocr_result = {
        'blocks': [
            {
                'text': 'Target text',
                'confidence': 0.95,
                'geometry': {
                    'boundingBox': {
                        'left': 0.5, 'top': 0.5,
                        'width': 0.2, 'height': 0.1
                    }
                }
            }
        ]
    }

    value, confidence, location = extractor.extract(field_def, ocr_result)
    assert value == 'Target text'
    assert confidence == 0.95

def test_field_transformers():
    """Test data type transformations"""
    transformers = FieldTransformers()

    # Currency
    assert transformers._to_currency("$1,234.56") == 1234.56
    assert transformers._to_currency("€ 999.99") == 999.99

    # Phone
    assert transformers._normalize_phone("5551234567") == "(555) 123-4567"

    # Boolean
    assert transformers._to_boolean("yes") == True
    assert transformers._to_boolean("no") == False
```

### Integration Tests
```python
@pytest.mark.integration
def test_end_to_end_extraction():
    """Test complete extraction workflow"""
    # Create profile
    profile = create_profile(TEMPLATE_GENERIC_INVOICE)

    # Process document
    with open('sample_invoice.pdf', 'rb') as f:
        result = process_with_profile(f, profile_id=profile.id)

    doc_id = result['document_id']

    # Wait for processing
    wait_for_document(doc_id, timeout=30)

    # Get extracted fields
    fields = get_extracted_fields(doc_id)

    assert fields['validation']['is_valid'] == True
    assert 'invoice_number' in fields['fields']
    assert 'total_amount' in fields['fields']
    assert fields['fields']['total_amount']['value'] > 0
```

## Migration Strategy

### Backward Compatibility
- Profile extraction is opt-in
- Existing documents continue working without profiles
- Add `profile_id` column to documents (nullable)
- Keep `extracted_content_b64` for raw OCR output
- Add `extracted_fields` JSONB column for structured data

### Gradual Rollout
1. Deploy profile management APIs (disabled by default)
2. Test with internal documents
3. Create profiles for common document types
4. Enable for pilot customers
5. Full rollout with templates

## Success Metrics

- **Profile Creation**: 100+ profiles created by users
- **Extraction Accuracy**: 95%+ for structured fields
- **Performance**: < 2s overhead per document
- **Adoption**: 50%+ of documents processed with profiles
- **User Satisfaction**: 4.5+ star rating

## Future Enhancements

### Visual Profile Editor
- Drag-and-drop field positioning
- Real-time preview with sample document
- Auto-suggest extraction strategies
- Visual validation feedback

### Machine Learning
- Learn extraction patterns from user corrections
- Auto-generate profiles from examples
- Confidence scoring improvements
- Anomaly detection

### Advanced Extraction
- Cross-field validation (e.g., line items sum to total)
- Multi-page field correlation
- Hierarchical data structures (nested objects)
- Conditional extraction rules

### Integration
- Webhook notifications for extraction events
- Zapier/Make.com integration
- Export profiles to JSON Schema
- Import from other OCR platforms

## Related Documents
- TASK-001: Multi-Format Output Support (normalized format required for extraction)
- TASK-003: Structured Field Extraction (Bedrock LLM integration)
- docs/OCR-API-FORMATS.md (coordinate systems and field structures)

## References
- [Zapier Custom Apps](https://platform.zapier.com/)
- [Segment Protocols](https://segment.com/docs/protocols/)
- [AWS Textract Queries](https://docs.aws.amazon.com/textract/latest/dg/API_Query.html)
- [JSON Schema](https://json-schema.org/)
