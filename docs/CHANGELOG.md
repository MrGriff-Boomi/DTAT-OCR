# Changelog

All notable changes to DTAT OCR will be documented in this file.

## [2.0.0] - 2026-01-29

### Added - Multi-Format Output Support (TASK-001 ✅)

**Major Feature**: DTAT is now a drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision.

#### New Files
- **`formatters.py`** (441 lines)
  - Abstract `OutputFormatter` base class
  - `TextractFormatter` - AWS Textract-compatible output
  - `GoogleVisionFormatter` - Google Cloud Vision-compatible output
  - `AzureOCRFormatter` - Azure Computer Vision-compatible output
  - `DTATFormatter` - Native format (backward compatibility)
  - Formatter registry and helper functions

#### Updated Files
- **`extraction_pipeline.py`**
  - Added normalized data structures (175 lines):
    - `Point`, `BoundingBox`, `NormalizedGeometry`
    - `BlockRelationship`, `NormalizedBlock`
    - `DocumentMetadata`, `NormalizedResult`
  - `convert_extraction_result_to_normalized()` - Legacy converter
  - Pipeline now stores normalized format

- **`database.py`**
  - `set_normalized_content()` - Store normalized results
  - `get_normalized_content()` - Retrieve normalized results
  - Backward compatible with legacy format

- **`api.py`**
  - Added `OutputFormat` enum (TEXTRACT, GOOGLE, AZURE, DTAT)
  - Updated `/documents/{id}/content` endpoint with `format` parameter
  - Automatic legacy format conversion for old documents

- **`README.md`**
  - Added "Multi-Format Output Support" section with examples
  - Updated API endpoints table to show format parameter
  - Updated project structure to include formatters.py
  - Added migration examples for Textract and Google Vision
  - Updated roadmap to show TASK-001 complete

- **`CLAUDE.md`**
  - Updated project status to "Enhanced MVP"
  - Added recent improvements section
  - Updated API endpoints with format parameter examples
  - Updated file structure with new files
  - Added key files documentation for multi-format output

#### API Changes
- **New Query Parameter**: `/documents/{id}/content?format={format}`
  - `format=textract` (default) - AWS Textract-compatible
  - `format=google` - Google Cloud Vision-compatible
  - `format=azure` - Azure Computer Vision-compatible
  - `format=dtat` - DTAT native format

#### Examples
```bash
# AWS Textract format (default)
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=textract"

# Google Vision format
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=google"

# Azure OCR format
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=azure"

# DTAT native format
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=dtat"
```

#### Benefits
- **Cost Savings**: Save $1.50/1000 pages vs AWS Textract
- **Easy Migration**: Drop-in replacement for commercial OCR APIs
- **Format Flexibility**: Choose output format based on downstream systems
- **Backward Compatible**: Existing integrations continue working
- **Foundation for Advanced Features**: Normalized format enables profiles, LLM extraction

### Infrastructure
- Created detailed task planning documents in `docs/tasks/`
  - TASK-001: Multi-Format Output Support (✅ COMPLETE)
  - TASK-002: Profile & Schema Management System (🚧 Planned)
  - TASK-003: Structured Field Extraction (🚧 Planned)
  - TASK-004: Batch Processing Support (🚧 Planned)
- Created comprehensive OCR API format research document (`docs/OCR-API-FORMATS.md`)

## [1.0.0] - 2026-01-28

### Initial Release
- Multi-format document support (PDF, Excel, CSV, Word, images)
- Intelligent extraction ladder with retry logic
- Quality scoring and automatic escalation
- LightOnOCR integration for local OCR
- Web UI for document processing
- REST API with authentication
- Docker support (CPU and GPU)
- AWS deployment on EC2
- SQLite storage with base64 encoding

---

## Coming Soon

### [2.1.0] - TASK-002: Profile & Schema Management
- User-defined extraction profiles
- Multiple extraction strategies (coordinate, keyword, table, regex, LLM)
- Built-in templates (invoice, receipt, W-2, etc.)
- Profile versioning and management

### [2.2.0] - TASK-003: Structured Field Extraction
- AWS Bedrock LLM integration
- Intelligent semantic field extraction
- Cost tracking and budget controls
- Enhanced extraction accuracy

### [2.3.0] - TASK-004: Batch Processing
- Multi-file upload support
- Parallel processing with worker pools
- Progress tracking
- Multiple export formats (JSON, CSV, Excel, ZIP)
