# DTAT OCR (Ducktape and Twine OCR)

Swiss Army Knife document processor with OCR fallback. Handles PDFs, Excel, CSV, Word, and images with automatic retry logic and quality scoring.

## Features

- **Multi-format support**: PDF, XLSX, CSV, DOCX, JPG, PNG, TIFF, and more
- **Intelligent extraction ladder**: Tries cheap methods first, escalates on failure
- **Quality scoring**: Automatically detects failed extractions and retries
- **LightOnOCR integration**: Local AI-powered OCR for scanned documents
- **Web UI**: Drag-and-drop processing, document viewer, and settings
- **REST API**: Easy integration with existing systems
- **Docker ready**: CPU and GPU images available
- **Fully permissive licensing**: All dependencies are MIT/BSD/Apache 2.0

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
| `/documents/{id}/content` | GET | Get extracted text/tables |
| `/documents/{id}/retry` | POST | Retry failed document |
| `/dlq` | GET | View dead letter queue |

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

# Get extracted content
curl http://localhost:8000/documents/1/content
```

## Docker

### CPU Image

```bash
docker build -t dtat-ocr:cpu .
docker run -p 8000:8000 -v $(pwd)/data:/app/data dtat-ocr:cpu
```

### GPU Image

```bash
docker build -f Dockerfile.gpu -t dtat-ocr:gpu .
```

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
| Word (.docx) | Native | python-docx |
| Images (JPG, PNG, TIFF, etc.) | OCR | LightOnOCR |

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
├── extraction_pipeline.py    # Retry logic, quality scoring, escalation
├── worker.py                 # CLI for processing
├── document_processor.py     # Multi-format processor
│
├── templates/                # Web UI templates
│   ├── base.html             # Base layout with nav
│   ├── index.html            # Document processing page
│   ├── documents.html        # Document list page
│   └── settings.html         # Configuration page
│
├── docs/adr/                 # Architecture Decision Records
│   └── 001-replace-pymupdf-with-pdfplumber.md
│
├── Dockerfile                # CPU Docker image
├── Dockerfile.gpu            # GPU Docker image (CUDA)
├── docker-compose.yml        # Local development
└── requirements.txt          # Python dependencies
```

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
