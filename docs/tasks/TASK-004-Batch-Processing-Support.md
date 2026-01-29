# TASK-004: Batch Processing Support

**Status**: Not Started
**Priority**: Medium
**Depends On**: TASK-001 (Multi-Format Output), TASK-002 (Profile System)
**Created**: 2026-01-29

## Executive Summary

Enable efficient batch processing of multiple documents in a single API request. This is critical for enterprise use cases where users need to process hundreds or thousands of documents (invoices, receipts, forms) in bulk, potentially with different profiles for each document type.

## Problem Statement

Current API is document-centric (single document per request):
- Users must make N API calls for N documents
- No automatic parallelization
- Difficult to track batch jobs
- No bulk error handling
- Can't optimize GPU utilization across documents

Users need:
- **Bulk upload**: Submit 100+ documents in single request
- **Automatic routing**: Apply different profiles based on document type detection
- **Progress tracking**: Monitor batch job status (50/100 completed)
- **Parallel processing**: Utilize GPU efficiently
- **Bulk results**: Download all results as single archive
- **Error handling**: Continue processing even if some documents fail

## Use Cases

### Accounts Payable Automation
```
User uploads folder of 500 invoices (mixed vendors)
→ Auto-detect invoice format
→ Apply appropriate profile per vendor
→ Extract all structured data
→ Export to CSV for ERP import
```

### Expense Report Processing
```
Employee uploads 30 receipt photos
→ Extract merchant, date, total from each
→ Validate against policy rules
→ Generate expense report spreadsheet
```

### Form Digitization
```
HR uploads 200 job applications (PDF forms)
→ Extract candidate info from each
→ Deduplicate applicants
→ Import to applicant tracking system
```

### Archive Migration
```
Digitize 10,000 historical documents
→ Run OCR on all
→ Index for full-text search
→ Store in document management system
```

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────┐
│         Batch Upload API                    │
│  - Multi-file upload (zip/folder)           │
│  - Auto-detect document types               │
│  - Create batch job                         │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Job Queue (SQS or in-memory)        │
│  - Batch ID: 12345                          │
│  - Documents: 500                           │
│  - Status: queued → processing → completed  │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Worker Pool (parallel)              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ Worker 1│ │ Worker 2│ │ Worker 3│       │
│  │ GPU 30% │ │ GPU 30% │ │ GPU 30% │       │
│  └─────────┘ └─────────┘ └─────────┘       │
│  - Processes documents concurrently         │
│  - Updates batch status                     │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Results Aggregator                  │
│  - Collect all extracted data               │
│  - Generate CSV/JSON/Excel export           │
│  - Package as zip                           │
└─────────────────────────────────────────────┘
```

### Data Model

```python
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class BatchStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BatchJob(BaseModel):
    """Batch processing job"""
    id: Optional[int] = None
    name: Optional[str] = None
    status: BatchStatus = BatchStatus.QUEUED

    # Document tracking
    total_documents: int
    completed_documents: int = 0
    failed_documents: int = 0

    # Configuration
    profile_id: Optional[int] = None          # Single profile for all docs
    profile_mapping: Optional[Dict[str, int]] = None  # Map doc type → profile
    auto_detect_profiles: bool = False         # Detect profile from content
    output_format: str = "textract"            # textract, google, azure, dtat
    export_format: str = "json"                # json, csv, excel, zip

    # Processing options
    parallel_workers: int = 3
    continue_on_error: bool = True

    # Results
    results_url: Optional[str] = None          # S3 URL or local path
    error_summary: Optional[str] = None

    # Metadata
    created_by: Optional[str] = None
    organization_id: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None

    # Cost tracking
    total_cost_usd: float = 0.0

class BatchDocument(BaseModel):
    """Individual document in a batch"""
    id: Optional[int] = None
    batch_id: int
    document_id: Optional[int] = None          # Links to documents table
    filename: str
    file_size_bytes: int

    status: str = "queued"                     # queued, processing, completed, failed
    profile_id: Optional[int] = None
    error_message: Optional[str] = None

    processing_time_ms: Optional[int] = None
    cost_usd: float = 0.0

    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Database Schema

```sql
-- Batch jobs table
CREATE TABLE batch_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',

    -- Document tracking
    total_documents INTEGER NOT NULL,
    completed_documents INTEGER DEFAULT 0,
    failed_documents INTEGER DEFAULT 0,

    -- Configuration
    profile_id INTEGER REFERENCES extraction_profiles(id),
    profile_mapping JSONB,  -- {"invoice": 1, "receipt": 2}
    auto_detect_profiles BOOLEAN DEFAULT FALSE,
    output_format VARCHAR(20) DEFAULT 'textract',
    export_format VARCHAR(20) DEFAULT 'json',

    -- Processing
    parallel_workers INTEGER DEFAULT 3,
    continue_on_error BOOLEAN DEFAULT TRUE,

    -- Results
    results_url TEXT,
    error_summary TEXT,

    -- Metadata
    created_by VARCHAR(255),
    organization_id VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_time_ms INTEGER,

    -- Cost
    total_cost_usd DECIMAL(10, 6) DEFAULT 0.0,

    CONSTRAINT valid_status CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX idx_batch_jobs_org ON batch_jobs(organization_id);
CREATE INDEX idx_batch_jobs_created ON batch_jobs(created_at DESC);

-- Individual documents in batch
CREATE TABLE batch_documents (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES batch_jobs(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id),
    filename VARCHAR(500),
    file_size_bytes BIGINT,

    status VARCHAR(20) DEFAULT 'queued',
    profile_id INTEGER REFERENCES extraction_profiles(id),
    error_message TEXT,

    processing_time_ms INTEGER,
    cost_usd DECIMAL(10, 6) DEFAULT 0.0,

    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    CONSTRAINT valid_doc_status CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'skipped'))
);

CREATE INDEX idx_batch_documents_batch ON batch_documents(batch_id, status);
CREATE INDEX idx_batch_documents_doc ON batch_documents(document_id);

-- Batch events log
CREATE TABLE batch_events (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES batch_jobs(id) ON DELETE CASCADE,
    event_type VARCHAR(50),  -- started, document_completed, document_failed, completed, cancelled
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_batch_events_batch ON batch_events(batch_id, created_at DESC);
```

### API Endpoints

```python
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
import asyncio
import zipfile
import io

app = FastAPI()

# ==================== Batch Job Management ====================

@app.post("/batch/upload", status_code=202)
async def create_batch_job(
    files: List[UploadFile] = File(...),
    name: Optional[str] = None,
    profile_id: Optional[int] = None,
    auto_detect_profiles: bool = False,
    output_format: str = "textract",
    export_format: str = "json",
    parallel_workers: int = 3,
    background_tasks: BackgroundTasks = None
):
    """
    Create a batch job and upload multiple documents.

    Example:
    POST /batch/upload
    - files: [invoice1.pdf, invoice2.pdf, invoice3.pdf]
    - profile_id: 42
    - output_format: textract
    - export_format: json

    Response:
    {
        "batch_id": 123,
        "status": "queued",
        "total_documents": 3,
        "estimated_completion_time_sec": 45
    }
    """
    # Create batch job
    batch = BatchJob(
        name=name or f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        total_documents=len(files),
        profile_id=profile_id,
        auto_detect_profiles=auto_detect_profiles,
        output_format=output_format,
        export_format=export_format,
        parallel_workers=parallel_workers
    )

    batch_record = save_batch_job(batch)
    batch_id = batch_record.id

    # Save uploaded files
    for file in files:
        # Save file to disk/S3
        file_path = save_batch_file(batch_id, file)

        # Create batch document record
        batch_doc = BatchDocument(
            batch_id=batch_id,
            filename=file.filename,
            file_size_bytes=len(await file.read()),
            profile_id=profile_id
        )
        save_batch_document(batch_doc)

    # Start processing in background
    background_tasks.add_task(process_batch_job, batch_id)

    return {
        "batch_id": batch_id,
        "status": "queued",
        "total_documents": len(files),
        "estimated_completion_time_sec": estimate_processing_time(len(files))
    }

@app.post("/batch/upload-zip", status_code=202)
async def create_batch_from_zip(
    file: UploadFile = File(...),
    profile_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Create batch job from uploaded ZIP file.

    Extracts all documents from ZIP and processes them.
    """
    # Extract ZIP
    zip_bytes = await file.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        filenames = [f for f in zf.namelist() if not f.endswith('/')]

        # Create batch
        batch = BatchJob(
            name=f"Batch from {file.filename}",
            total_documents=len(filenames),
            profile_id=profile_id
        )
        batch_record = save_batch_job(batch)
        batch_id = batch_record.id

        # Extract and save each file
        for filename in filenames:
            file_data = zf.read(filename)
            file_path = save_batch_file_bytes(batch_id, filename, file_data)

            batch_doc = BatchDocument(
                batch_id=batch_id,
                filename=filename,
                file_size_bytes=len(file_data),
                profile_id=profile_id
            )
            save_batch_document(batch_doc)

    # Start processing
    background_tasks.add_task(process_batch_job, batch_id)

    return {
        "batch_id": batch_id,
        "status": "queued",
        "total_documents": len(filenames)
    }

@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: int):
    """
    Get batch job status and progress.

    Example response:
    {
        "batch_id": 123,
        "name": "Invoice batch 2024-01",
        "status": "processing",
        "progress": {
            "total": 500,
            "completed": 342,
            "failed": 8,
            "remaining": 150,
            "percent": 68.4
        },
        "processing_time_sec": 245,
        "estimated_completion_sec": 115,
        "results_url": null,
        "costs": {
            "total_usd": 6.84,
            "per_document_usd": 0.02
        }
    }
    """
    batch = get_batch_job(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Calculate progress
    progress_pct = (batch.completed_documents / batch.total_documents * 100) if batch.total_documents > 0 else 0

    # Estimate completion time
    if batch.status == BatchStatus.PROCESSING and batch.started_at:
        elapsed_sec = (datetime.now() - batch.started_at).total_seconds()
        if batch.completed_documents > 0:
            avg_time_per_doc = elapsed_sec / batch.completed_documents
            remaining_docs = batch.total_documents - batch.completed_documents
            estimated_completion_sec = int(remaining_docs * avg_time_per_doc)
        else:
            estimated_completion_sec = None
    else:
        elapsed_sec = batch.processing_time_ms / 1000 if batch.processing_time_ms else 0
        estimated_completion_sec = None

    return {
        "batch_id": batch.id,
        "name": batch.name,
        "status": batch.status,
        "progress": {
            "total": batch.total_documents,
            "completed": batch.completed_documents,
            "failed": batch.failed_documents,
            "remaining": batch.total_documents - batch.completed_documents - batch.failed_documents,
            "percent": round(progress_pct, 1)
        },
        "processing_time_sec": int(elapsed_sec),
        "estimated_completion_sec": estimated_completion_sec,
        "results_url": batch.results_url,
        "costs": {
            "total_usd": float(batch.total_cost_usd),
            "per_document_usd": float(batch.total_cost_usd / batch.total_documents) if batch.total_documents > 0 else 0
        }
    }

@app.get("/batch/{batch_id}/documents")
async def list_batch_documents(
    batch_id: int,
    status: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0
):
    """
    List documents in a batch with optional status filter.

    Returns paginated list of documents with their processing status.
    """
    documents = get_batch_documents(
        batch_id=batch_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return {
        "batch_id": batch_id,
        "documents": documents,
        "count": len(documents),
        "limit": limit,
        "offset": offset
    }

@app.get("/batch/{batch_id}/results")
async def get_batch_results(batch_id: int):
    """
    Get aggregated results for all documents in batch.

    Returns:
    {
        "batch_id": 123,
        "status": "completed",
        "results": [
            {
                "filename": "invoice1.pdf",
                "document_id": 456,
                "status": "completed",
                "extracted_fields": {...}
            },
            ...
        ]
    }
    """
    batch = get_batch_job(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    documents = get_batch_documents(batch_id, limit=10000)

    results = []
    for doc in documents:
        if doc.document_id:
            extracted = get_document_extracted_fields(doc.document_id)
            results.append({
                "filename": doc.filename,
                "document_id": doc.document_id,
                "status": doc.status,
                "extracted_fields": extracted.get('fields') if extracted else None,
                "error": doc.error_message
            })

    return {
        "batch_id": batch_id,
        "status": batch.status,
        "results": results
    }

@app.get("/batch/{batch_id}/export")
async def export_batch_results(
    batch_id: int,
    format: str = Query("json", pattern="^(json|csv|excel|zip)$")
):
    """
    Export batch results in requested format.

    - json: Single JSON file with all results
    - csv: CSV file with flattened fields
    - excel: Excel workbook with one row per document
    - zip: Archive with individual JSON files per document

    Returns: FileResponse with downloadable file
    """
    batch = get_batch_job(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status not in [BatchStatus.COMPLETED, BatchStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Batch not ready for export")

    # Generate export file
    if format == "json":
        file_path = export_batch_json(batch_id)
        media_type = "application/json"
        filename = f"batch_{batch_id}_results.json"

    elif format == "csv":
        file_path = export_batch_csv(batch_id)
        media_type = "text/csv"
        filename = f"batch_{batch_id}_results.csv"

    elif format == "excel":
        file_path = export_batch_excel(batch_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"batch_{batch_id}_results.xlsx"

    elif format == "zip":
        file_path = export_batch_zip(batch_id)
        media_type = "application/zip"
        filename = f"batch_{batch_id}_results.zip"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@app.post("/batch/{batch_id}/cancel")
async def cancel_batch_job(batch_id: int):
    """
    Cancel a running batch job.

    Stops processing new documents but completes in-progress documents.
    """
    batch = get_batch_job(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status not in [BatchStatus.QUEUED, BatchStatus.PROCESSING]:
        raise HTTPException(status_code=400, detail="Batch cannot be cancelled")

    # Mark as cancelled
    update_batch_status(batch_id, BatchStatus.CANCELLED)

    # Stop workers (implementation-specific)
    cancel_batch_workers(batch_id)

    return {
        "batch_id": batch_id,
        "status": "cancelled",
        "completed_documents": batch.completed_documents,
        "total_documents": batch.total_documents
    }

@app.delete("/batch/{batch_id}")
async def delete_batch_job(batch_id: int):
    """
    Delete a batch job and all associated documents.

    WARNING: This is permanent and cannot be undone.
    """
    batch = get_batch_job(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Delete all batch documents
    delete_batch_documents(batch_id)

    # Delete batch record
    delete_batch_job_record(batch_id)

    return {"status": "deleted", "batch_id": batch_id}

@app.get("/batch")
async def list_batch_jobs(
    status: Optional[str] = None,
    organization_id: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0
):
    """
    List all batch jobs with optional filters.
    """
    batches = query_batch_jobs(
        status=status,
        organization_id=organization_id,
        limit=limit,
        offset=offset
    )

    return {
        "batches": batches,
        "count": len(batches),
        "limit": limit,
        "offset": offset
    }

# ==================== Batch Processing Engine ====================

async def process_batch_job(batch_id: int):
    """
    Process all documents in a batch using parallel workers.

    This runs in background task.
    """
    batch = get_batch_job(batch_id)
    if not batch:
        return

    # Update status
    update_batch_status(batch_id, BatchStatus.PROCESSING)
    update_batch_started_time(batch_id, datetime.now())

    # Log event
    log_batch_event(batch_id, "started", f"Starting batch with {batch.total_documents} documents")

    try:
        # Get all documents
        documents = get_batch_documents(batch_id, status="queued", limit=100000)

        # Process in parallel
        workers = batch.parallel_workers
        semaphore = asyncio.Semaphore(workers)

        async def process_one(doc):
            async with semaphore:
                try:
                    await process_batch_document(batch_id, doc)
                except Exception as e:
                    logger.error(f"Failed to process {doc.filename}: {e}")

        # Run all documents
        await asyncio.gather(*[process_one(doc) for doc in documents])

        # Mark batch complete
        batch = get_batch_job(batch_id)
        if batch.failed_documents == 0:
            final_status = BatchStatus.COMPLETED
        elif batch.completed_documents > 0:
            final_status = BatchStatus.COMPLETED  # Partial success
        else:
            final_status = BatchStatus.FAILED

        update_batch_status(batch_id, final_status)
        update_batch_completed_time(batch_id, datetime.now())

        # Generate results file
        results_path = export_batch_json(batch_id)
        update_batch_results_url(batch_id, results_path)

        log_batch_event(
            batch_id,
            "completed",
            f"Batch completed: {batch.completed_documents} succeeded, {batch.failed_documents} failed"
        )

    except Exception as e:
        logger.error(f"Batch {batch_id} failed: {e}")
        update_batch_status(batch_id, BatchStatus.FAILED)
        update_batch_error(batch_id, str(e))

async def process_batch_document(batch_id: int, batch_doc: BatchDocument):
    """
    Process a single document in a batch.
    """
    try:
        # Update status
        update_batch_document_status(batch_doc.id, "processing")

        # Load file
        file_path = get_batch_file_path(batch_id, batch_doc.filename)

        # Determine profile
        profile_id = batch_doc.profile_id
        if not profile_id:
            batch = get_batch_job(batch_id)
            if batch.auto_detect_profiles:
                profile_id = detect_profile_for_document(file_path)
            else:
                profile_id = batch.profile_id

        # Process document
        start_time = time.time()

        with open(file_path, 'rb') as f:
            result = await process_document_with_profile(
                file=f,
                filename=batch_doc.filename,
                profile_id=profile_id,
                output_format=batch.output_format
            )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update batch document
        update_batch_document_completed(
            batch_doc.id,
            document_id=result['document_id'],
            processing_time_ms=processing_time_ms,
            cost_usd=result.get('cost_usd', 0)
        )

        # Increment batch counters
        increment_batch_completed(batch_id)
        increment_batch_cost(batch_id, result.get('cost_usd', 0))

        log_batch_event(
            batch_id,
            "document_completed",
            f"Completed {batch_doc.filename}",
            metadata={"document_id": result['document_id']}
        )

    except Exception as e:
        logger.error(f"Failed to process {batch_doc.filename}: {e}")

        # Update as failed
        update_batch_document_failed(batch_doc.id, str(e))
        increment_batch_failed(batch_id)

        log_batch_event(
            batch_id,
            "document_failed",
            f"Failed {batch_doc.filename}: {str(e)}"
        )

        # Check if batch should continue
        batch = get_batch_job(batch_id)
        if not batch.continue_on_error:
            raise

# ==================== Export Functions ====================

def export_batch_json(batch_id: int) -> str:
    """Export batch results as JSON file"""
    batch = get_batch_job(batch_id)
    documents = get_batch_documents(batch_id, limit=100000)

    results = []
    for doc in documents:
        if doc.document_id:
            extracted = get_document_extracted_fields(doc.document_id)
            results.append({
                "filename": doc.filename,
                "status": doc.status,
                "extracted_fields": extracted.get('fields') if extracted else None,
                "confidence": extracted.get('validation', {}).get('is_valid') if extracted else None
            })

    output = {
        "batch_id": batch_id,
        "batch_name": batch.name,
        "status": batch.status,
        "total_documents": batch.total_documents,
        "completed": batch.completed_documents,
        "failed": batch.failed_documents,
        "results": results
    }

    # Save to file
    output_path = f"/tmp/batch_{batch_id}_results.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    return output_path

def export_batch_csv(batch_id: int) -> str:
    """Export batch results as CSV file"""
    import csv

    documents = get_batch_documents(batch_id, limit=100000)

    # Collect all field names
    all_fields = set()
    for doc in documents:
        if doc.document_id:
            extracted = get_document_extracted_fields(doc.document_id)
            if extracted and extracted.get('fields'):
                all_fields.update(extracted['fields'].keys())

    # Write CSV
    output_path = f"/tmp/batch_{batch_id}_results.csv"
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['filename', 'status'] + sorted(all_fields)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for doc in documents:
            row = {
                'filename': doc.filename,
                'status': doc.status
            }

            if doc.document_id:
                extracted = get_document_extracted_fields(doc.document_id)
                if extracted and extracted.get('fields'):
                    for field_name, field_data in extracted['fields'].items():
                        row[field_name] = field_data.get('value')

            writer.writerow(row)

    return output_path

def export_batch_excel(batch_id: int) -> str:
    """Export batch results as Excel file"""
    import pandas as pd

    documents = get_batch_documents(batch_id, limit=100000)

    # Build dataframe
    rows = []
    for doc in documents:
        row = {
            'filename': doc.filename,
            'status': doc.status
        }

        if doc.document_id:
            extracted = get_document_extracted_fields(doc.document_id)
            if extracted and extracted.get('fields'):
                for field_name, field_data in extracted['fields'].items():
                    row[field_name] = field_data.get('value')

        rows.append(row)

    df = pd.DataFrame(rows)

    # Write Excel
    output_path = f"/tmp/batch_{batch_id}_results.xlsx"
    df.to_excel(output_path, index=False, engine='openpyxl')

    return output_path

def export_batch_zip(batch_id: int) -> str:
    """Export batch results as ZIP with individual JSON files"""
    documents = get_batch_documents(batch_id, limit=100000)

    output_path = f"/tmp/batch_{batch_id}_results.zip"

    with zipfile.ZipFile(output_path, 'w') as zf:
        for doc in documents:
            if doc.document_id:
                extracted = get_document_extracted_fields(doc.document_id)
                if extracted:
                    # Save as individual JSON
                    json_filename = f"{Path(doc.filename).stem}_results.json"
                    zf.writestr(json_filename, json.dumps(extracted, indent=2))

    return output_path
```

## Configuration

```python
# config.py additions

# Batch processing
ENABLE_BATCH_PROCESSING = os.getenv('ENABLE_BATCH_PROCESSING', 'true').lower() == 'true'
BATCH_MAX_DOCUMENTS = int(os.getenv('BATCH_MAX_DOCUMENTS', '1000'))
BATCH_MAX_SIZE_MB = int(os.getenv('BATCH_MAX_SIZE_MB', '500'))

# Parallel processing
BATCH_PARALLEL_WORKERS = int(os.getenv('BATCH_PARALLEL_WORKERS', '3'))
BATCH_WORKER_TIMEOUT_SEC = int(os.getenv('BATCH_WORKER_TIMEOUT_SEC', '300'))

# Storage
BATCH_STORAGE_PATH = os.getenv('BATCH_STORAGE_PATH', '/app/data/batches')
BATCH_RESULTS_RETENTION_DAYS = int(os.getenv('BATCH_RESULTS_RETENTION_DAYS', '30'))

# Queue (SQS optional)
BATCH_USE_SQS = os.getenv('BATCH_USE_SQS', 'false').lower() == 'true'
BATCH_SQS_QUEUE_URL = os.getenv('BATCH_SQS_QUEUE_URL', '')
```

## Testing Strategy

### Unit Tests
```python
@pytest.fixture
def sample_batch():
    return BatchJob(
        name="Test batch",
        total_documents=3,
        profile_id=1
    )

def test_create_batch_job(sample_batch):
    """Test batch job creation"""
    batch = save_batch_job(sample_batch)
    assert batch.id is not None
    assert batch.status == BatchStatus.QUEUED

def test_batch_progress_tracking():
    """Test progress calculation"""
    batch = create_test_batch(total=100)

    # Simulate processing
    for i in range(50):
        increment_batch_completed(batch.id)

    batch = get_batch_job(batch.id)
    assert batch.completed_documents == 50

    progress = calculate_progress_percent(batch)
    assert progress == 50.0
```

### Integration Tests
```python
@pytest.mark.integration
async def test_batch_processing_end_to_end():
    """Test complete batch workflow"""
    # Create batch with 10 documents
    files = [create_test_pdf(f"doc_{i}.pdf") for i in range(10)]

    response = await create_batch_job(
        files=files,
        profile_id=1,
        parallel_workers=3
    )

    batch_id = response['batch_id']

    # Wait for completion
    await wait_for_batch_completion(batch_id, timeout=60)

    # Check results
    batch = get_batch_job(batch_id)
    assert batch.status == BatchStatus.COMPLETED
    assert batch.completed_documents == 10
    assert batch.failed_documents == 0

    # Export results
    csv_path = export_batch_csv(batch_id)
    assert os.path.exists(csv_path)
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Database schema and models
- [ ] Batch job CRUD operations
- [ ] File storage management

### Phase 2: API Endpoints (Week 2)
- [ ] Upload endpoints (multi-file, ZIP)
- [ ] Status and progress tracking
- [ ] Results retrieval

### Phase 3: Processing Engine (Week 3)
- [ ] Parallel worker pool
- [ ] Document processing orchestration
- [ ] Error handling and retry logic

### Phase 4: Export Formats (Week 4)
- [ ] JSON export
- [ ] CSV export
- [ ] Excel export
- [ ] ZIP export

### Phase 5: Advanced Features (Week 5)
- [ ] Auto-profile detection
- [ ] Cost tracking per batch
- [ ] Batch analytics dashboard

### Phase 6: Optimization (Week 6)
- [ ] SQS integration (optional)
- [ ] Result caching
- [ ] Cleanup jobs (delete old batches)

## Success Metrics

- **Throughput**: Process 1000+ documents per hour
- **Reliability**: 99.9% batch completion rate
- **Performance**: < 5% overhead vs single document processing
- **Cost**: No additional infrastructure costs (vs single processing)

## Related Documents
- TASK-001: Multi-Format Output Support
- TASK-002: Profile & Schema Management System
- TASK-003: Structured Field Extraction

## References
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [AWS SQS](https://aws.amazon.com/sqs/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
