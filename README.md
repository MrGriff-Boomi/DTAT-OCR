# DTAT OCR (Ducktape and Twine OCR)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Enterprise document processor with AWS Textract integration. Handles PDFs (multi-page), Excel, CSV, Word, and images with automatic extraction, quality scoring, and multi-format output.

**Drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision** — outputs in industry-standard formats for seamless migration.

## Features

- **AWS Textract integration**: ~1-3s per page, 90%+ confidence, multi-page PDF support
- **Multi-format output**: Textract, Google Vision, Azure OCR, or DTAT native format
- **Multi-format input**: PDF, XLSX, CSV, DOCX, JPG, PNG, TIFF, and more
- **Intelligent extraction ladder**: Native parsing first, Textract for images/scanned docs
- **High-volume ready**: 4 concurrent workers, PostgreSQL storage, async job queue
- **Boomi integration**: `/ocr` endpoint for direct binary passthrough (3-shape WSS process)
- **Async processing**: Fire-and-forget `/ocr/async` with PostgreSQL-backed job tracking
- **Web UI**: Drag-and-drop processing, document viewer, and settings
- **REST API**: 15+ endpoints with Swagger documentation
- **Profile-based extraction**: Built-in templates for invoices, receipts, W-2s, driver's licenses
- **Docker ready**: CPU and GPU images available

## Architecture

```
Document In
    │
    ▼
┌─────────────────────────────────────┐
│ Level 1: Native Extraction (FREE)   │  PDF, Excel, CSV, Word
│ pdfplumber, pandas, python-docx     │
│ Confidence check → pass? → Done ✓   │
└─────────────────────────────────────┘
    │ fail/low confidence (or image input)
    ▼
┌─────────────────────────────────────┐
│ Level 2: AWS Textract (DEFAULT)     │  Images, scanned/multi-page PDFs
│ ~1-3 seconds per page               │
│ 90%+ confidence → Done ✓            │
└─────────────────────────────────────┘
    │ fail
    ▼
┌─────────────────────────────────────┐
│ Level 3: LightOnOCR (OPTIONAL)      │  Local GPU/CPU fallback
│ No cloud dependency, offline mode    │
└─────────────────────────────────────┘
    │ fail
    ▼
┌─────────────────────────────────────┐
│ Dead Letter Queue                   │  Manual review
└─────────────────────────────────────┘
```

### Boomi Integration

DTAT-OCR includes a `/ocr` endpoint designed for Boomi passthrough — accepts raw image binary via POST and returns extracted text directly. This enables a simple 3-shape Boomi process (WSS Listener → REST Connector → Return Documents) with no scripting required.

```
Browser → Boomi WSS → REST Connector → DTAT-OCR /ocr → AWS Textract → Response
```

### Performance (Single EC2 t3.medium)

| Path | Throughput | Estimated Daily (8hr) |
|------|------------|----------------------|
| Direct to DTAT | 250 docs/min | ~120,000 docs |
| Through Boomi WSS | 41 docs/min | ~20,000 docs |

50-document burst test: 0 failures, avg 2.4s/doc, P95 3.5s/doc.

## Quick Start

### Installation

```bash
git clone https://github.com/MrGriff-Boomi/DTAT-OCR.git
cd DTAT-OCR

python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
python worker.py init
```

### Run

```bash
# Single worker (development)
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# Multi-worker (production)
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

Open http://localhost:8000 in your browser.

### Environment Variables

```bash
# Required for Textract
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1

# Database (SQLite default, PostgreSQL recommended for production)
DATABASE_URL=sqlite:///documents.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/ocr_demo

# Authentication
DTAT_USERNAME=admin
DTAT_PASSWORD=your-secure-password
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth) |
| `/stats` | GET | Processing statistics |
| `/process` | POST | Upload & process via multipart form (sync) |
| `/ocr` | POST | Raw binary OCR — accepts image bytes, returns text |
| `/ocr/async` | POST | Fire-and-forget OCR — returns job ID immediately |
| `/ocr/jobs/{job_id}` | GET | Poll for async job result |
| `/queue/status` | GET | Job queue depth and avg/p95 processing times |
| `/documents` | GET | List all stored documents |
| `/documents/{id}` | GET | Get document metadata |
| `/documents/{id}/content?format={fmt}` | GET | Get content in Textract/Google/Azure/DTAT format |
| `/documents/{id}/retry` | POST | Retry failed document |
| `/docs` | GET | Swagger API documentation |

### Example Calls

```bash
# Health check
curl http://localhost:8000/health

# OCR an image (raw binary — for Boomi passthrough)
curl -X POST -u admin:password -H "Content-Type: image/png" \
  --data-binary @receipt.png "http://localhost:8000/ocr?format=text"

# OCR async (fire-and-forget)
curl -X POST -u admin:password -H "Content-Type: image/png" \
  --data-binary @receipt.png http://localhost:8000/ocr/async
# Returns: {"job_id": "abc-123", "status": "processing"}

# Poll for result
curl -u admin:password http://localhost:8000/ocr/jobs/abc-123

# Process document (multipart upload)
curl -X POST -u admin:password -F "file=@invoice.pdf" http://localhost:8000/process

# Get extracted content in different formats
curl -u admin:password "http://localhost:8000/documents/1/content?format=textract"
curl -u admin:password "http://localhost:8000/documents/1/content?format=google"
curl -u admin:password "http://localhost:8000/documents/1/content?format=azure"

# Queue monitoring
curl -u admin:password http://localhost:8000/queue/status
```

## Multi-Format Output

Output OCR results in industry-standard formats for drop-in replacement of commercial OCR services.

| Format | Description | Use Case |
|--------|-------------|----------|
| **Textract** | AWS Textract-compatible | Default, enterprise standard |
| **Google** | Google Cloud Vision-compatible | Migrate from Google Vision |
| **Azure** | Azure Computer Vision-compatible | Migrate from Azure OCR |
| **DTAT** | Native format | Simple text + tables + metadata |

## Supported Input Formats

| Format | Method | Multi-Page | Notes |
|--------|--------|------------|-------|
| PDF (digital) | Native | Yes | pdfplumber — text + tables |
| PDF (scanned) | Textract | Yes (up to 5MB) | analyze_document with TABLES+FORMS |
| Excel (.xlsx) | Native | All sheets | pandas + openpyxl |
| CSV | Native | Yes | pandas |
| Word (.docx) | Native | Full document | python-docx |
| Images | Textract | Single image | JPG, PNG, TIFF, BMP, GIF, WebP |

## Docker

```bash
# CPU image
docker build -t dtat-ocr:cpu .
docker run -p 8000:8000 -v $(pwd)/data:/app/data dtat-ocr:cpu

# Docker Compose (includes PostgreSQL)
docker-compose up --build
```

## Configuration

Edit `config.py` or use the Web UI at `/ui/settings`:

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_native_extraction` | `True` | Level 1: Free parsing (PDF, Excel, Word) |
| `enable_textract` | `True` | Level 2: AWS Textract (~1-3s per page) |
| `enable_local_ocr` | `False` | Level 3: LightOnOCR (local, slow on CPU) |
| `min_confidence_score` | `60` | Threshold to escalate to next level |
| `max_retries_per_level` | `2` | Retries before escalating |

## Project Structure

```
DTAT-OCR/
├── api.py                    # FastAPI REST endpoints + Web UI + async job system
├── config.py                 # Configuration and feature toggles
├── database.py               # SQLAlchemy models, PostgreSQL/SQLite support
├── extraction_pipeline.py    # Extraction ladder, Textract, quality scoring
├── formatters.py             # Multi-format output converters
├── worker.py                 # CLI for batch processing
├── profiles.py               # Extraction profile system
├── extractors.py             # Field extraction strategies
├── templates/                # Web UI (Tailwind + HTMX)
├── tests/                    # Test suite (8 files)
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   ├── OCR-API-FORMATS.md    # Format specifications
│   ├── PROFILE-TEMPLATES.md  # Built-in extraction profiles
│   └── TASK-HIGH-VOLUME.md   # High-volume optimization task + results
├── Dockerfile                # CPU Docker image (4 workers)
├── docker-compose.yml        # Local dev with PostgreSQL
└── requirements.txt          # Python dependencies
```

## Roadmap

### Current Status: Production-Ready (v2.1.0)

**Completed:**
- AWS Textract integration (1-3s/page, 90%+ confidence)
- Multi-page PDF support (up to 5MB via sync Textract API)
- Multi-format output (Textract, Google Vision, Azure OCR)
- High-volume: 4 workers, PostgreSQL, async job queue
- Boomi integration via `/ocr` binary passthrough
- Load tested: 50-doc burst, 0 failures, 250 docs/min direct
- Web UI, Swagger docs, profile-based extraction

**Planned:**
- S3-based Textract for PDFs >5MB (async API)
- SQS integration for guaranteed message delivery
- Managed RDS PostgreSQL
- ECS Fargate with auto-scaling
- Boomi Event Streams decoupling for higher WSS throughput

## Architecture Decision Records

| ADR | Decision |
|-----|----------|
| [001](docs/adr/001-replace-pymupdf-with-pdfplumber.md) | Replace PyMuPDF with pdfplumber (licensing) |
| [002](docs/adr/002-high-volume-optimizations.md) | Multi-worker + PostgreSQL + session reuse (10x throughput) |
| [003](docs/adr/003-multi-page-pdf-and-execution-modes.md) | Sync Textract for multi-page PDFs, Bridge mode for Boomi |

## License

MIT — all dependencies are permissively licensed (MIT/BSD/Apache 2.0). Safe for commercial use.
