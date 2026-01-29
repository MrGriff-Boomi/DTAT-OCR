# TASK-001: Multi-Format Output Support

**Status**: Planned
**Priority**: HIGH
**Estimated Effort**: 2-3 days
**Dependencies**: None
**Related ADR**: TBD

---

## Executive Summary

Implement industry-standard OCR response formats to make DTAT a drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision. Users can specify their desired output format via API parameter.

**Business Value**: Eliminates integration friction - companies can switch from cloud OCR providers to DTAT without changing their existing code.

---

## Problem Statement

Currently, DTAT returns a custom JSON format:
```json
{
  "status": "completed",
  "extracted_text": "raw text blob",
  "extracted_tables": [...],
  "confidence_score": 95.0
}
```

Companies using Textract, Google Vision, or Azure have code expecting those specific formats. To be a true "Swiss Army Knife" OCR solution, DTAT must support multiple output formats.

---

## Requirements

### Functional Requirements

1. **FR-1**: Support output format selection via query parameter `?format=textract|google|azure|dtat`
2. **FR-2**: Default format is "textract" (most common)
3. **FR-3**: Implement Textract-compatible response structure
4. **FR-4**: Implement Google Cloud Vision-compatible response structure
5. **FR-5**: Implement Azure Computer Vision-compatible response structure
6. **FR-6**: Preserve existing "dtat" format for backward compatibility
7. **FR-7**: Store extracted content internally in normalized format
8. **FR-8**: Convert to requested format at response time (lazy conversion)

### Non-Functional Requirements

1. **NFR-1**: Format conversion must add < 50ms latency
2. **NFR-2**: All formats must pass JSON schema validation
3. **NFR-3**: Maintain 100% API backward compatibility
4. **NFR-4**: Document all format differences in API docs

---

## Proposed Solution

### Architecture

```
┌────────────────────────┐
│   Extraction Pipeline  │
│   (LightOnOCR, etc.)  │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  Internal Storage      │  ← Store in normalized format (Textract-like)
│  (Database/JSON)       │    Uses normalized coordinates (0.0-1.0)
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  Format Converters     │  ← Convert at response time
│  - TextractFormatter   │
│  - GoogleFormatter     │
│  - AzureFormatter      │
│  - DTATFormatter       │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│   API Response         │
└────────────────────────┘
```

### Data Flow

1. **Document Processing**: LightOnOCR/pdfplumber extracts text, coordinates, confidence
2. **Normalization**: Convert to internal format with normalized coordinates
3. **Storage**: Store normalized format in database (base64 JSON)
4. **Retrieval**: Fetch from database when requested
5. **Conversion**: Transform to requested format (Textract/Google/Azure/DTAT)
6. **Response**: Return formatted JSON

---

## Implementation Plan

### Phase 1: Internal Format Definition

**File**: `extraction_pipeline.py`

Define normalized internal format:

```python
@dataclass
class NormalizedBlock:
    """Internal block format (Textract-inspired)"""
    block_type: str  # WORD, LINE, PAGE, TABLE, CELL
    text: Optional[str]
    confidence: float  # 0-100
    geometry: NormalizedGeometry
    relationships: List[BlockRelationship]
    page: int

@dataclass
class NormalizedGeometry:
    """Normalized coordinates (0.0-1.0)"""
    bounding_box: BoundingBox  # left, top, width, height (0.0-1.0)
    polygon: List[Point]  # [(x, y), ...] all 0.0-1.0

@dataclass
class NormalizedResult:
    """Complete extraction result"""
    blocks: List[NormalizedBlock]
    document_metadata: DocumentMetadata
    page_count: int
    confidence_score: float
```

### Phase 2: Format Converters

**New File**: `formatters.py`

Create formatter classes:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class OutputFormatter(ABC):
    """Base class for output formatters"""

    @abstractmethod
    def format(self, normalized_result: NormalizedResult) -> Dict[str, Any]:
        """Convert normalized result to specific format"""
        pass

class TextractFormatter(OutputFormatter):
    """AWS Textract format"""

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        return {
            "Blocks": [self._convert_block(b) for b in result.blocks],
            "DocumentMetadata": {
                "Pages": result.page_count
            },
            "DetectDocumentTextModelVersion": "1.0"
        }

    def _convert_block(self, block: NormalizedBlock) -> Dict:
        return {
            "BlockType": block.block_type.upper(),
            "Text": block.text,
            "Confidence": block.confidence,
            "Geometry": {
                "BoundingBox": {
                    "Left": block.geometry.bounding_box.left,
                    "Top": block.geometry.bounding_box.top,
                    "Width": block.geometry.bounding_box.width,
                    "Height": block.geometry.bounding_box.height
                },
                "Polygon": [
                    {"X": p.x, "Y": p.y} for p in block.geometry.polygon
                ]
            },
            "Id": block.id,
            "Relationships": [
                {"Type": r.type, "Ids": r.ids}
                for r in block.relationships
            ] if block.relationships else None,
            "Page": block.page
        }

class GoogleVisionFormatter(OutputFormatter):
    """Google Cloud Vision format"""

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        # Convert normalized coords to absolute pixels (assume 1000x1000)
        page_width, page_height = 1000, 1000

        return {
            "textAnnotations": self._build_text_annotations(
                result, page_width, page_height
            ),
            "fullTextAnnotation": self._build_full_text(
                result, page_width, page_height
            )
        }

    def _to_absolute_coords(self, normalized_box, page_width, page_height):
        """Convert 0.0-1.0 to absolute pixels"""
        return {
            "x": int(normalized_box.left * page_width),
            "y": int(normalized_box.top * page_height)
        }

class AzureOCRFormatter(OutputFormatter):
    """Azure Computer Vision Read API format"""

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        return {
            "status": "succeeded",
            "analyzeResult": {
                "version": "3.2",
                "readResults": self._build_read_results(result)
            }
        }

    def _build_read_results(self, result: NormalizedResult):
        pages = []
        for page_num in range(1, result.page_count + 1):
            page_blocks = [b for b in result.blocks if b.page == page_num]
            pages.append({
                "page": page_num,
                "angle": 0,
                "width": 1000,  # Assume standard size
                "height": 1000,
                "unit": "pixel",
                "lines": self._build_lines(page_blocks)
            })
        return pages

    def _convert_to_8point(self, polygon):
        """Convert polygon to 8-point array [x1,y1,x2,y2,x3,y3,x4,y4]"""
        coords = []
        for point in polygon[:4]:  # Take first 4 points
            coords.extend([int(point.x * 1000), int(point.y * 1000)])
        return coords

class DTATFormatter(OutputFormatter):
    """DTAT native format (current format)"""

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        # Extract text from LINE blocks
        text_lines = [
            b.text for b in result.blocks
            if b.block_type == "LINE" and b.text
        ]

        # Extract tables from TABLE blocks
        tables = self._extract_tables(result.blocks)

        return {
            "status": "completed",
            "extracted_text": "\n".join(text_lines),
            "extracted_tables": tables,
            "confidence_score": result.confidence_score,
            "page_count": result.page_count,
            "char_count": sum(len(line) for line in text_lines),
            "metadata": {
                "extraction_method": result.extraction_method,
                "processing_time_ms": result.processing_time_ms
            }
        }
```

### Phase 3: API Integration

**File**: `api.py`

Update endpoints to support format parameter:

```python
from enum import Enum
from formatters import (
    TextractFormatter, GoogleVisionFormatter,
    AzureOCRFormatter, DTATFormatter
)

class OutputFormat(str, Enum):
    TEXTRACT = "textract"
    GOOGLE = "google"
    AZURE = "azure"
    DTAT = "dtat"

# Formatter registry
FORMATTERS = {
    OutputFormat.TEXTRACT: TextractFormatter(),
    OutputFormat.GOOGLE: GoogleVisionFormatter(),
    OutputFormat.AZURE: AzureOCRFormatter(),
    OutputFormat.DTAT: DTATFormatter()
}

@app.get("/documents/{doc_id}/content")
async def get_document_content(
    doc_id: int,
    format: OutputFormat = OutputFormat.TEXTRACT,  # Default to Textract
    username: str = Depends(verify_credentials)
):
    """Get extracted content in specified format"""
    record = get_document(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    if record.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready. Status: {record.status}"
        )

    # Decode normalized content from storage
    normalized_result = record.get_normalized_content()

    # Convert to requested format
    formatter = FORMATTERS[format]
    formatted_content = formatter.format(normalized_result)

    return formatted_content

@app.post("/process")
async def process_document_sync(
    file: UploadFile = File(...),
    format: OutputFormat = OutputFormat.TEXTRACT,
    username: str = Depends(verify_credentials)
):
    """Process document and return in specified format"""
    # ... existing processing logic ...

    # After processing
    normalized_result = record.get_normalized_content()
    formatter = FORMATTERS[format]
    formatted_content = formatter.format(normalized_result)

    return {
        "document_id": record.id,
        "status": record.status,
        "content": formatted_content
    }
```

### Phase 4: LightOnOCR Integration

**File**: `extraction_pipeline.py`

Update OCR extraction to produce normalized format:

```python
@classmethod
def _extract_with_lighton_ocr(cls, file_path: Path, record: DocumentRecord) -> DocumentRecord:
    """Level 2: LightOnOCR for scanned documents - returns normalized format"""

    # ... existing OCR logic ...

    # Convert OCR results to normalized format
    normalized_blocks = []

    for line_idx, line_text in enumerate(extracted_lines):
        block = NormalizedBlock(
            id=f"line_{line_idx}",
            block_type="LINE",
            text=line_text,
            confidence=line_confidence,  # From OCR model
            geometry=NormalizedGeometry(
                bounding_box=BoundingBox(
                    left=bbox[0] / page_width,  # Normalize to 0.0-1.0
                    top=bbox[1] / page_height,
                    width=bbox[2] / page_width,
                    height=bbox[3] / page_height
                ),
                polygon=[Point(x/page_width, y/page_height) for x, y in poly]
            ),
            page=page_num,
            relationships=[]
        )
        normalized_blocks.append(block)

    normalized_result = NormalizedResult(
        blocks=normalized_blocks,
        document_metadata=DocumentMetadata(pages=page_count),
        page_count=page_count,
        confidence_score=overall_confidence
    )

    # Store normalized format
    record.extracted_content_b64 = base64.b64encode(
        json.dumps(normalized_result.to_dict()).encode()
    ).decode()

    return record
```

---

## Testing Plan

### Unit Tests

**File**: `tests/test_formatters.py`

```python
import pytest
from formatters import TextractFormatter, GoogleVisionFormatter, AzureOCRFormatter
from extraction_pipeline import NormalizedResult, NormalizedBlock

def test_textract_formatter():
    """Test Textract format conversion"""
    result = create_sample_normalized_result()
    formatter = TextractFormatter()
    output = formatter.format(result)

    assert "Blocks" in output
    assert "DocumentMetadata" in output
    assert output["DocumentMetadata"]["Pages"] == result.page_count
    assert all(b["BlockType"] in ["WORD", "LINE", "PAGE"] for b in output["Blocks"])
    assert all(0 <= b["Confidence"] <= 100 for b in output["Blocks"])

def test_google_vision_formatter():
    """Test Google Vision format conversion"""
    result = create_sample_normalized_result()
    formatter = GoogleVisionFormatter()
    output = formatter.format(result)

    assert "textAnnotations" in output
    assert "fullTextAnnotation" in output
    assert isinstance(output["textAnnotations"], list)
    assert all("boundingPoly" in ann for ann in output["textAnnotations"])

def test_azure_formatter():
    """Test Azure OCR format conversion"""
    result = create_sample_normalized_result()
    formatter = AzureOCRFormatter()
    output = formatter.format(result)

    assert output["status"] == "succeeded"
    assert "analyzeResult" in output
    assert "readResults" in output["analyzeResult"]

    for page in output["analyzeResult"]["readResults"]:
        assert "lines" in page
        for line in page["lines"]:
            assert len(line["boundingBox"]) == 8  # 8-point array
```

### Integration Tests

**File**: `tests/test_api_formats.py`

```python
def test_textract_format_endpoint(test_client):
    """Test /documents/{id}/content?format=textract"""
    # Upload and process document
    response = test_client.post(
        "/process",
        files={"file": ("test.pdf", open("samples/invoice.pdf", "rb"))}
    )
    doc_id = response.json()["document_id"]

    # Request Textract format
    response = test_client.get(f"/documents/{doc_id}/content?format=textract")
    assert response.status_code == 200

    data = response.json()
    validate_textract_format(data)

def test_format_parameter_validation(test_client):
    """Test invalid format parameter"""
    response = test_client.get("/documents/1/content?format=invalid")
    assert response.status_code == 422  # Validation error
```

### Manual Testing

1. **Textract Compatibility**: Use existing Textract client code against DTAT endpoint
2. **Google Vision Compatibility**: Test with Google Vision client libraries
3. **Azure Compatibility**: Verify Azure SDK can parse responses
4. **Performance**: Measure format conversion overhead (target < 50ms)

---

## API Documentation

### OpenAPI Schema Updates

**File**: `api.py`

```python
@app.get(
    "/documents/{doc_id}/content",
    response_model=Union[TextractResponse, GoogleResponse, AzureResponse, DTATResponse],
    summary="Get document content in specified format",
    description="""
    Retrieve extracted content in industry-standard format.

    **Supported Formats:**
    - `textract`: AWS Textract-compatible (default)
    - `google`: Google Cloud Vision-compatible
    - `azure`: Azure Computer Vision-compatible
    - `dtat`: DTAT native format

    **Example:**
    ```
    GET /documents/123/content?format=textract
    ```
    """,
    responses={
        200: {
            "description": "Extracted content in requested format",
            "content": {
                "application/json": {
                    "examples": {
                        "textract": {"$ref": "#/components/examples/TextractExample"},
                        "google": {"$ref": "#/components/examples/GoogleExample"},
                        "azure": {"$ref": "#/components/examples/AzureExample"}
                    }
                }
            }
        }
    }
)
async def get_document_content(...):
    ...
```

---

## Migration Plan

### Backward Compatibility

**Existing behavior (no format parameter)**:
- Return DTAT native format (current behavior)

**New behavior (format parameter)**:
- Default to `textract` format for new clients
- Provide `dtat` format explicitly for backward compatibility

### Rollout Strategy

1. **Phase 1**: Deploy formatters with feature flag (disabled by default)
2. **Phase 2**: Enable for beta users, collect feedback
3. **Phase 3**: Make available to all users, update docs
4. **Phase 4**: Change default to `textract` (breaking change - major version bump)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Format conversion adds latency | Medium | Low | Cache converted formats, lazy load |
| Coordinate conversion inaccuracies | High | Medium | Extensive testing, validate against samples |
| Breaking changes for existing users | High | Low | Maintain backward compat, version API |
| Incomplete format support | Medium | Medium | Prioritize Textract (most common) |

---

## Success Criteria

1. ✅ All three formats (Textract, Google, Azure) pass schema validation
2. ✅ Format conversion adds < 50ms latency (measured via load tests)
3. ✅ 100% backward compatibility maintained (existing clients unaffected)
4. ✅ API documentation includes examples for all formats
5. ✅ Integration tests pass with real-world documents
6. ✅ At least 1 external user successfully migrates from Textract to DTAT

---

## Future Enhancements

1. **Custom Format Profiles**: Allow users to define custom output formats
2. **Streaming Responses**: Support chunked responses for large documents
3. **Format Validation**: Validate outputs against official schemas
4. **Performance Optimization**: Pre-compute common formats at processing time
5. **Additional Formats**: Support Tesseract, EasyOCR formats

---

## References

- [AWS Textract DetectDocumentText API](https://docs.aws.amazon.com/textract/latest/dg/API_DetectDocumentText.html)
- [Google Cloud Vision OCR](https://cloud.google.com/vision/docs/ocr)
- [Azure Computer Vision Read API](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/call-read-api)
- [OCR API Formats Research](../OCR-API-FORMATS.md)
