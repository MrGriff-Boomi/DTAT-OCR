# DTAT OCR (Ducktape and Twine OCR)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Swiss Army Knife document processor with OCR fallback. Handles PDFs, Excel, CSV, Word, and images with automatic retry logic and quality scoring.

**Drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision** - outputs in industry-standard formats for seamless migration.

## Features

- **🎯 Multi-format OCR output**: Textract, Google Vision, Azure OCR, or DTAT native format
- **📄 Multi-format document support**: PDF, XLSX, CSV, DOCX, JPG, PNG, TIFF, and more
- **🎢 Intelligent extraction ladder**: Tries cheap methods first, escalates on failure
- **✅ Quality scoring**: Automatically detects failed extractions and retries
- **🤖 LightOnOCR integration**: Local AI-powered OCR for scanned documents
- **📋 Profile-based extraction**: User-defined extraction profiles with 4 strategies (coordinate, keyword, table, regex)
- **🎨 Built-in templates**: Pre-configured profiles for invoices, receipts, W-2s, and driver's licenses
- **🌐 Web UI**: Drag-and-drop processing, document viewer, and settings
- **🔌 REST API**: Easy integration with existing systems
- **🔒 HTTP Basic Authentication**: Secure access control for all endpoints
- **🐳 Docker ready**: CPU and GPU images available
- **⚖️ Fully permissive licensing**: All dependencies are MIT/BSD/Apache 2.0

## Live Demo (AWS Deployment)

**Status:** ✅ Live and operational on AWS g4dn.xlarge

- **URL**: http://54.80.47.194:8000
- **Credentials**: Contact admin for access
- **Deployment**: See `DEPLOYMENT-LOG.md` for full details
- **Cost**: ~$92/month (8hrs/day, 20 days/month)

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
    │ fail/low confidence
    ▼
┌─────────────────────────────────────┐
│ Level 2: LightOnOCR (Local GPU/CPU) │  Images, scanned PDFs
│ Retry up to 2x per level            │
│ Confidence check → pass? → Done ✓   │
└─────────────────────────────────────┘
    │ fail
    ▼
┌─────────────────────────────────────┐
│ Level 3: AWS Textract (DISABLED)    │  Optional paid fallback
└─────────────────────────────────────┘
    │ fail
    ▼
┌─────────────────────────────────────┐
│ Dead Letter Queue                   │  Manual review
└─────────────────────────────────────┘
```

## Multi-Format Output Support

**NEW**: DTAT now outputs OCR results in industry-standard formats, making it a drop-in replacement for commercial OCR services.

### Supported Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **Textract** | AWS Textract-compatible | Drop-in Textract replacement, save $1.50/1000 pages |
| **Google** | Google Cloud Vision-compatible | Migrate from Google Vision OCR |
| **Azure** | Azure Computer Vision-compatible | Migrate from Azure OCR |
| **DTAT** | Native format (backward compatible) | Simple text + tables output |

### Format Selection

**API Parameter**:
```bash
GET /documents/{id}/content?format=textract
GET /documents/{id}/content?format=google
GET /documents/{id}/content?format=azure
GET /documents/{id}/content?format=dtat
```

**Default**: Textract format (most common for enterprise use)

### Example Responses

<details>
<summary><b>Textract Format</b> (AWS-compatible)</summary>

```json
{
  "Blocks": [
    {
      "BlockType": "LINE",
      "Id": "block_0",
      "Text": "Invoice #12345",
      "Confidence": 95.8,
      "Geometry": {
        "BoundingBox": {
          "Left": 0.05,
          "Top": 0.1,
          "Width": 0.3,
          "Height": 0.02
        },
        "Polygon": [
          {"X": 0.05, "Y": 0.1},
          {"X": 0.35, "Y": 0.1},
          {"X": 0.35, "Y": 0.12},
          {"X": 0.05, "Y": 0.12}
        ]
      },
      "Page": 1
    }
  ],
  "DocumentMetadata": {
    "Pages": 1
  }
}
```
</details>

<details>
<summary><b>Google Vision Format</b></summary>

```json
{
  "textAnnotations": [
    {
      "description": "Invoice #12345\nDate: 2024-01-15",
      "boundingPoly": {
        "vertices": [
          {"x": 50, "y": 100},
          {"x": 350, "y": 100},
          {"x": 350, "y": 120},
          {"x": 50, "y": 120}
        ]
      }
    }
  ],
  "fullTextAnnotation": {
    "text": "Invoice #12345\nDate: 2024-01-15",
    "pages": [...]
  }
}
```
</details>

<details>
<summary><b>Azure OCR Format</b></summary>

```json
{
  "status": "succeeded",
  "analyzeResult": {
    "version": "3.2",
    "readResults": [
      {
        "page": 1,
        "width": 1000,
        "height": 1000,
        "lines": [
          {
            "text": "Invoice #12345",
            "boundingBox": [50, 100, 350, 100, 350, 120, 50, 120],
            "words": [...]
          }
        ]
      }
    ]
  }
}
```
</details>

<details>
<summary><b>DTAT Native Format</b> (Simple)</summary>

```json
{
  "status": "completed",
  "extracted_text": "Invoice #12345\nDate: 2024-01-15\nTotal: $1,234.56",
  "extracted_tables": [],
  "confidence_score": 95.8,
  "page_count": 1,
  "metadata": {
    "extraction_method": "native",
    "processing_time_ms": 250
  }
}
```
</details>

### Migration Examples

**From AWS Textract**:
```python
# Before (AWS Textract)
textract = boto3.client('textract')
response = textract.detect_document_text(Document={'S3Object': {'Bucket': 'my-bucket', 'Name': 'doc.pdf'}})

# After (DTAT)
response = requests.get('http://dtat-server:8000/documents/123/content?format=textract', auth=auth)
# Same JSON structure - no code changes needed!
```

**From Google Cloud Vision**:
```python
# Before (Google Vision)
client = vision.ImageAnnotatorClient()
response = client.text_detection(image=image)

# After (DTAT)
response = requests.get('http://dtat-server:8000/documents/123/content?format=google', auth=auth)
# Same JSON structure!
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/NotADevIAmaMeatPopsicle/DTAT-OCR.git
cd DTAT-OCR

# Create virtual environment
uv venv --python 3.12 --seed
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Initialize database
python worker.py init
```

### Run the Web UI

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### Web UI Pages

| Page | Description |
|------|-------------|
| `/` | Process documents (drag & drop upload) |
| `/ui/documents` | View all processed documents |
| `/ui/settings` | Configure extraction pipeline |
| `/docs` | API documentation (Swagger) |

## CLI Usage

```bash
# Initialize database (required first time)
python worker.py init

# Process single document
python worker.py process document.pdf
python worker.py process receipt.jpg --json

# Batch process pending documents
python worker.py batch --limit 20

# Run continuous worker (for async queue)
python worker.py worker --interval 10 --batch-size 5

# View statistics
python worker.py stats

# View failed documents (DLQ)
python worker.py dlq

# View/modify configuration
python worker.py config
python worker.py config --enable-textract
python worker.py config --disable-textract
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/stats` | GET | Processing statistics |
| `/process` | POST | Upload & process (sync) |
| `/process/async` | POST | Upload & queue (async) |
| `/documents` | GET | List all documents |
| `/documents/{id}` | GET | Get document metadata |
| `/documents/{id}/content?format={format}` | GET | Get extracted content in specified format |
| `/documents/{id}/retry` | POST | Retry failed document |
| `/dlq` | GET | View dead letter queue |

**Format Parameter**: `textract` (default), `google`, `azure`, or `dtat`

### Example API Calls

```bash
# Health check
curl http://localhost:8000/health

# Process document (sync)
curl -X POST http://localhost:8000/process \
  -F "file=@document.pdf"

# Process document (async - uses persistent queue)
curl -X POST http://localhost:8000/process/async \
  -F "file=@document.pdf"

# Get extracted content in different formats
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=textract"
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=google"
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=azure"
curl -u "admin:password" "http://localhost:8000/documents/1/content?format=dtat"

# List all documents
curl -u "admin:password" http://localhost:8000/documents
```

## Authentication

All endpoints except `/health` require HTTP Basic Authentication.

### Setting Credentials

Use environment variables to set username and password:

```bash
# Local development
export DTAT_USERNAME=admin
export DTAT_PASSWORD=your-secure-password
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# Docker
docker run -p 8000:8000 \
  -e DTAT_USERNAME=admin \
  -e DTAT_PASSWORD=your-secure-password \
  dtat-ocr:cpu
```

**Default credentials** (change in production):
- Username: `admin`
- Password: `changeme123`

### Using Authentication

**Web Browser**: Browser will prompt for credentials automatically

**curl**:
```bash
curl -u "username:password" http://localhost:8000/stats
```

**Python**:
```python
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('username', 'password')
response = requests.get('http://localhost:8000/stats', auth=auth)
```

**Note**: The `/health` endpoint does not require authentication (for monitoring/health checks)

## Docker

### Build Notes

- **First build**: Takes 5-10 minutes (downloads ~2GB model weights)
- **Subsequent builds**: Much faster due to Docker layer caching
- **Data persistence**: Documents stored in `./data/documents.db` - back up this directory

### CPU Image

```bash
docker build -t dtat-ocr:cpu .
docker run -p 8000:8000 -v $(pwd)/data:/app/data dtat-ocr:cpu
```

### GPU Image

```bash
# Build GPU image
docker build -f Dockerfile.gpu -t dtat-ocr:gpu .

# Run with NVIDIA GPU support
docker run --gpus all -p 8000:8000 -v $(pwd)/data:/app/data dtat-ocr:gpu
```

**Note**: Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

### Docker Compose

```bash
docker-compose up --build      # Build and run
docker-compose up -d           # Run in background
docker-compose logs -f         # View logs
docker-compose down            # Stop
```

## Configuration

Edit `config.py` or use the Web UI at `/ui/settings`:

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_native_extraction` | `True` | Level 1: Free parsing |
| `enable_local_ocr` | `True` | Level 2: LightOnOCR |
| `enable_textract` | `False` | Level 3: AWS Textract |
| `ocr_offline_mode` | `True` | Don't call HF Hub |
| `min_confidence_score` | `60` | Threshold to escalate |
| `max_retries_per_level` | `2` | Retries before escalating |

## Supported Formats

| Format | Method | Notes |
|--------|--------|-------|
| PDF (digital) | Native | pdfplumber - text + tables |
| PDF (scanned) | OCR | LightOnOCR |
| Excel (.xlsx, .xls) | Native | pandas + openpyxl |
| CSV | Native | pandas |
| Word (.docx, .doc) | Native | python-docx |
| Images | OCR | JPG, JPEG, PNG, TIFF, TIF, BMP, GIF, WebP |

## Model Information

- **Model**: [LightOnOCR-1B-1025](https://huggingface.co/lightonai/LightOnOCR-1B-1025)
- **License**: Apache 2.0
- **Size**: ~2GB (bfloat16)
- **Performance**:
  - GPU (H100): ~5.7 pages/sec
  - CPU: ~0.5-1 pages/min

## Project Structure

```
DTAT-OCR/
├── api.py                    # FastAPI REST endpoints + Web UI
├── config.py                 # Configuration and feature toggles
├── database.py               # SQLAlchemy models, base64 storage
├── extraction_pipeline.py    # Retry logic, quality scoring, escalation, normalized format
├── formatters.py             # Multi-format output converters (NEW)
├── worker.py                 # CLI for processing
├── document_processor.py     # Multi-format processor
│
├── templates/                # Web UI templates
│   ├── base.html             # Base layout with nav
│   ├── index.html            # Document processing page
│   ├── documents.html        # Document list page
│   └── settings.html         # Configuration page
│
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   │   └── 001-replace-pymupdf-with-pdfplumber.md
│   ├── tasks/                # Task planning documents
│   │   ├── README.md         # Task roadmap
│   │   ├── TASK-001-Multi-Format-Output-Support.md
│   │   ├── TASK-002-Profile-Schema-Management-System.md
│   │   ├── TASK-003-Structured-Field-Extraction.md
│   │   └── TASK-004-Batch-Processing-Support.md
│   └── OCR-API-FORMATS.md    # Format specifications and comparisons
│
├── Dockerfile                # CPU Docker image
├── Dockerfile.gpu            # GPU Docker image (CUDA)
├── docker-compose.yml        # Local development
└── requirements.txt          # Python dependencies
```

## Roadmap

### Current Status: Enhanced MVP

The core document processing pipeline is fully functional with multi-format output support.

**✅ Completed Features**:
- Multi-format output (Textract, Google Vision, Azure OCR compatible)
- Drop-in replacement for commercial OCR services
- Normalized internal format for future features
- Backward-compatible DTAT native format

**🚧 In Progress** (See `docs/tasks/` for details):
- TASK-002: Profile & Schema Management System (user-defined extraction profiles)
- TASK-003: Structured Field Extraction (AWS Bedrock LLM integration)
- TASK-004: Batch Processing Support (100+ docs in single request)

### Planned Features: AWS Production Deployment

The following features are planned for enterprise-scale AWS deployment:

#### SQS Integration (Job Queuing)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  External   │────▶│  SQS Queue  │────▶│  DTAT OCR   │────▶│   Results   │
│   System    │     │  (intake)   │     │   Workers   │     │  S3 + RDS   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

- **Purpose**: Decouple document intake from processing
- **Benefits**:
  - Handle traffic spikes without losing documents
  - Multiple workers can pull from the same queue
  - Failed jobs return to queue automatically
  - Fire-and-forget from upstream systems

#### PostgreSQL/RDS Support

- **Current**: SQLite (single-file, good for dev/small scale)
- **Planned**: Amazon RDS PostgreSQL
- **Benefits**:
  - Handle concurrent connections from multiple workers
  - Automatic backups and point-in-time recovery
  - Multi-AZ failover for high availability
  - Connection pooling for better performance

#### ECS Fargate Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS VPC                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  ECS Task    │  │  ECS Task    │  │  ECS Task    │       │
│  │  (GPU)       │  │  (GPU)       │  │  (GPU)       │       │
│  │  g4dn.xlarge │  │  g4dn.xlarge │  │  g4dn.xlarge │  ...  │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │                │
│         └─────────────────┴─────────────────┘                │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │   RDS       │                          │
│                    │ PostgreSQL  │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

- **Compute**: ECS Fargate with GPU instances (g4dn.xlarge)
- **Model weights**: Baked into Docker image (no download on startup)
- **Scaling**: Auto-scale based on SQS queue depth

#### Auto-Scaling Configuration

| Metric | Scale Up | Scale Down |
|--------|----------|------------|
| SQS Queue Depth | > 100 messages | < 10 messages |
| Min Instances | 1 | - |
| Max Instances | 10 | - |
| Cooldown | 60 seconds | 300 seconds |

#### CloudWatch Integration

- **Metrics**: Processing time, success rate, queue depth, error rate
- **Logs**: Structured JSON logging for all processing events
- **Alarms**: Alert on DLQ growth, high error rate, processing delays

#### AWS Textract Fallback

- **Status**: Code ready, disabled by default
- **Purpose**: Paid fallback for documents that fail local OCR
- **Cost**: ~$0.015/page
- **Enable**: Set `ENABLE_TEXTRACT=true` in environment

### Planned Architecture Diagram

```
                                    ┌─────────────────┐
                                    │   CloudWatch    │
                                    │   Logs/Metrics  │
                                    └────────▲────────┘
                                             │
┌──────────┐    ┌──────────┐    ┌────────────┴────────────┐    ┌──────────┐
│ External │───▶│   SQS    │───▶│      ECS Fargate        │───▶│   S3     │
│  System  │    │  Queue   │    │  (GPU Workers x N)      │    │  Output  │
└──────────┘    └──────────┘    └────────────┬────────────┘    └──────────┘
                                             │
                                    ┌────────▼────────┐
                                    │   RDS Postgres  │
                                    │   (metadata)    │
                                    └─────────────────┘
```

### Cost Estimates (100K docs/month)

| Component | Estimated Cost |
|-----------|---------------|
| ECS Fargate (g4dn.xlarge, ~100 hrs) | ~$150-200 |
| RDS PostgreSQL (db.t3.medium) | ~$30 |
| SQS (100K messages) | < $1 |
| S3 Storage (100GB) | ~$2 |
| **Total** | **~$200/month** |

*Note: Using local OCR instead of Textract saves ~$1,500/month at this volume.*

## License

This project uses only permissively licensed dependencies:

| Component | License |
|-----------|---------|
| FastAPI | MIT |
| pdfplumber | MIT |
| SQLAlchemy | MIT |
| PyTorch | BSD |
| Transformers | Apache 2.0 |
| LightOnOCR Model | Apache 2.0 |

All dependencies are safe for commercial use.

## Contributing

Contributions are welcome! Please read the ADRs in `docs/adr/` before making architectural changes.

## Acknowledgments

- [LightOn AI](https://huggingface.co/lightonai) for the excellent LightOnOCR model
- [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF extraction
