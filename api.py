"""
DTAT OCR - Ducktape and Twine OCR
REST API + Web UI for Document Processing Pipeline

Drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision
with multi-format output support.

API Endpoints:
- POST /process                        - Upload and process a document (sync)
- POST /process/async                  - Upload and queue for processing (async)
- GET  /documents/{id}                 - Get processing result
- GET  /documents/{id}/content?format= - Get extracted content in specified format
- GET  /documents                      - List all documents
- GET  /health                         - Health check
- GET  /stats                          - Processing statistics

Output Formats:
- textract (default) - AWS Textract-compatible
- google            - Google Cloud Vision-compatible
- azure             - Azure Computer Vision-compatible
- dtat              - DTAT native format

Web UI:
- GET  /                 - Process documents
- GET  /ui/documents     - View all documents
- GET  /ui/settings      - Configuration
"""

import os
import sys
import base64
import tempfile
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets

from config import config
from database import (
    init_database, DocumentRecord, ProcessingStatus,
    create_document_record, save_document, get_document,
    get_pending_documents, get_failed_documents, update_document,
    get_session,
    # Profile management functions (TASK-002)
    create_profile, get_profile_by_id, get_profile_by_name, list_profiles,
    update_profile, delete_profile, create_profile_version,
    get_profile_versions, get_profile_version, get_profile_usage_stats
)
from extraction_pipeline import ExtractionPipeline
from formatters import get_formatter
from enum import Enum
# Profile management models (TASK-002)
from profiles import (
    ExtractionProfile, FieldDefinition, ProfileVersion,
    ExtractionStrategy, FieldType
)


# ==================== Helper Functions (TASK-002 Code Quality) ====================

def record_to_profile(record) -> ExtractionProfile:
    """
    Convert database record to ExtractionProfile model.

    Eliminates code duplication across 8 endpoints.

    Args:
        record: ExtractionProfileRecord from database

    Returns:
        ExtractionProfile with ID and timestamps populated
    """
    schema = record.get_schema()
    schema['id'] = record.id
    schema['created_at'] = record.created_at
    schema['updated_at'] = record.updated_at
    return ExtractionProfile(**schema)


def records_to_profiles(records: list) -> list[ExtractionProfile]:
    """
    Convert list of records to ExtractionProfile models.

    Args:
        records: List of ExtractionProfileRecord from database

    Returns:
        List of ExtractionProfile models
    """
    return [record_to_profile(record) for record in records]


# Output format enum
class OutputFormat(str, Enum):
    """Supported output formats for OCR results"""
    TEXTRACT = "textract"  # AWS Textract-compatible
    GOOGLE = "google"      # Google Cloud Vision-compatible
    AZURE = "azure"        # Azure Computer Vision-compatible
    DTAT = "dtat"          # DTAT native format


# Initialize
app = FastAPI(
    title="DTAT OCR",
    description="""
    **Ducktape and Twine OCR** - Swiss Army Knife document processing

    Drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision.

    **Features:**
    - Multi-format OCR output (Textract, Google Vision, Azure OCR, DTAT native)
    - Local GPU/CPU processing (save $1.50/1000 pages vs Textract)
    - Intelligent extraction ladder with retry logic
    - Quality scoring and automatic escalation
    - Support for PDF, Excel, CSV, Word, images

    **Output Formats:**
    - `textract` - AWS Textract-compatible (default)
    - `google` - Google Cloud Vision-compatible
    - `azure` - Azure Computer Vision-compatible
    - `dtat` - DTAT native format
    """,
    version="2.0.0",
    contact={
        "name": "DTAT OCR",
        "url": "https://github.com/NotADevIAmaMeatPopsicle/DTAT-OCR"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Templates
templates = Jinja2Templates(directory="templates")

# Security
security = HTTPBasic()

# Get credentials from environment variables (with defaults for development)
API_USERNAME = os.getenv("DTAT_USERNAME", "admin")
API_PASSWORD = os.getenv("DTAT_PASSWORD", "changeme123")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic Auth credentials"""
    correct_username = secrets.compare_digest(credentials.username.encode("utf8"), API_USERNAME.encode("utf8"))
    correct_password = secrets.compare_digest(credentials.password.encode("utf8"), API_PASSWORD.encode("utf8"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_database()
    print("DTAT OCR started. Database initialized.")


# =============================================================================
# MODELS
# =============================================================================

class ProcessingResponse(BaseModel):
    document_id: int
    status: str
    message: str


class DocumentResponse(BaseModel):
    id: int
    source_filename: str
    file_type: Optional[str]
    status: str
    extraction_method: Optional[str]
    confidence_score: Optional[float]
    page_count: Optional[int]
    char_count: Optional[int]
    table_count: Optional[int]
    processing_time_ms: Optional[int]
    created_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    extracted_content_b64: Optional[str] = None


class DocumentContentResponse(BaseModel):
    id: int
    source_filename: str
    status: str
    extracted_text: Optional[str]
    extracted_tables: Optional[list]
    metadata: Optional[dict]


class StatsResponse(BaseModel):
    total_documents: int
    completed: int
    failed: int
    needs_review: int
    pending: int
    processing: int
    avg_processing_time_ms: Optional[float]
    by_method: dict


class HealthResponse(BaseModel):
    status: str
    database: str
    ocr_model: str
    textract_enabled: bool
    offline_mode: bool


class SettingsUpdate(BaseModel):
    enable_local_ocr: Optional[bool] = None
    enable_textract: Optional[bool] = None
    min_confidence_score: Optional[int] = None
    max_retries_per_level: Optional[int] = None


# =============================================================================
# WEB UI ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def ui_home(request: Request, username: str = Depends(verify_credentials)):
    """Main processing page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_page": "home"
    })


@app.get("/ui/documents", response_class=HTMLResponse)
async def ui_documents(request: Request, username: str = Depends(verify_credentials)):
    """Documents list page."""
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "active_page": "documents"
    })


@app.get("/ui/settings", response_class=HTMLResponse)
async def ui_settings(request: Request, username: str = Depends(verify_credentials)):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_page": "settings",
        "config": config
    })


# =============================================================================
# UI API ENDPOINTS (for HTMX)
# =============================================================================

@app.get("/api/health-badge", response_class=HTMLResponse)
async def health_badge(username: str = Depends(verify_credentials)):
    """Health check badge for navbar."""
    try:
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        status = "healthy"
        color = "green"
    except Exception:
        status = "error"
        color = "red"

    return f'''
        <span class="inline-flex items-center rounded-full bg-{color}-100 px-2.5 py-0.5 text-xs font-medium text-{color}-800">
            <span class="mr-1 h-2 w-2 rounded-full bg-{color}-500"></span>
            {status}
        </span>
    '''


@app.get("/api/stats-cards", response_class=HTMLResponse)
async def stats_cards(username: str = Depends(verify_credentials)):
    """Stats cards for dashboard."""
    from sqlalchemy import func

    session = get_session()
    try:
        total = session.query(DocumentRecord).count()
        completed = session.query(DocumentRecord).filter_by(status=ProcessingStatus.COMPLETED.value).count()
        failed = session.query(DocumentRecord).filter(
            DocumentRecord.status.in_([ProcessingStatus.FAILED.value, ProcessingStatus.NEEDS_REVIEW.value])
        ).count()
        pending = session.query(DocumentRecord).filter_by(status=ProcessingStatus.PENDING.value).count()

        avg_time = session.query(func.avg(DocumentRecord.processing_time_ms))\
            .filter_by(status=ProcessingStatus.COMPLETED.value).scalar() or 0

        return f'''
        <div class="bg-white shadow rounded-lg p-4">
            <p class="text-sm text-gray-500">Total Documents</p>
            <p class="text-2xl font-bold text-gray-900">{total}</p>
        </div>
        <div class="bg-white shadow rounded-lg p-4">
            <p class="text-sm text-gray-500">Completed</p>
            <p class="text-2xl font-bold text-green-600">{completed}</p>
        </div>
        <div class="bg-white shadow rounded-lg p-4">
            <p class="text-sm text-gray-500">Failed / Review</p>
            <p class="text-2xl font-bold text-red-600">{failed}</p>
        </div>
        <div class="bg-white shadow rounded-lg p-4">
            <p class="text-sm text-gray-500">Avg Processing</p>
            <p class="text-2xl font-bold text-gray-900">{avg_time/1000:.1f}s</p>
        </div>
        '''
    finally:
        session.close()


@app.get("/api/recent-documents", response_class=HTMLResponse)
async def recent_documents(username: str = Depends(verify_credentials)):
    """Recent documents table for dashboard."""
    from html import escape

    session = get_session()
    try:
        records = session.query(DocumentRecord)\
            .order_by(DocumentRecord.created_at.desc())\
            .limit(10).all()

        if not records:
            return '<p class="text-gray-500 text-center py-4">No documents yet</p>'

        rows = ""
        for r in records:
            status_color = "green" if r.status == "completed" else ("yellow" if r.status == "pending" else "red")

            # Escape all user-provided data to prevent XSS
            safe_filename = escape(r.source_filename[:30]) + ('...' if len(r.source_filename) > 30 else '')
            safe_file_type = escape(r.file_type) if r.file_type else 'N/A'
            safe_status = escape(r.status)
            safe_method = escape(r.extraction_method) if r.extraction_method else 'N/A'

            rows += f'''
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-900">{r.id}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{safe_filename}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{safe_file_type}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center rounded-full bg-{status_color}-100 px-2 py-0.5 text-xs font-medium text-{status_color}-800">
                        {safe_status}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{safe_method}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.confidence_score:.0f}%</td>
            </tr>
            '''

        return f'''
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Method</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {rows}
            </tbody>
        </table>
        '''
    finally:
        session.close()


@app.get("/api/documents-table", response_class=HTMLResponse)
async def documents_table(status: Optional[str] = None, username: str = Depends(verify_credentials)):
    """Full documents table."""
    from html import escape

    session = get_session()
    try:
        query = session.query(DocumentRecord)
        if status:
            query = query.filter_by(status=status)

        records = query.order_by(DocumentRecord.created_at.desc()).limit(100).all()

        if not records:
            return '<p class="text-gray-500 text-center py-8">No documents found</p>'

        rows = ""
        for r in records:
            status_color = "green" if r.status == "completed" else ("yellow" if r.status in ["pending", "processing"] else "red")
            can_retry = r.status in ["failed", "needs_review"]

            # Escape all user-provided data to prevent XSS
            safe_filename = escape(r.source_filename[:40]) + ('...' if len(r.source_filename) > 40 else '')
            safe_file_type = escape(r.file_type) if r.file_type else 'N/A'
            safe_status = escape(r.status)
            safe_method = escape(r.extraction_method) if r.extraction_method else 'N/A'

            rows += f'''
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-900">{r.id}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{safe_filename}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{safe_file_type}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center rounded-full bg-{status_color}-100 px-2 py-0.5 text-xs font-medium text-{status_color}-800">
                        {safe_status}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{safe_method}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.confidence_score:.0f}% if r.confidence_score else 'N/A'</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.processing_time_ms // 1000 if r.processing_time_ms else 0}s</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else 'N/A'}</td>
                <td class="px-4 py-3 text-sm">
                    <button onclick="viewDocument({r.id})" class="text-blue-600 hover:text-blue-800 mr-2">View</button>
                    {'<button onclick="retryDocument(' + str(r.id) + ')" class="text-yellow-600 hover:text-yellow-800">Retry</button>' if can_retry else ''}
                </td>
            </tr>
            '''

        return f'''
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Method</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {rows}
            </tbody>
        </table>
        '''
    finally:
        session.close()


@app.get("/api/system-info", response_class=HTMLResponse)
async def system_info(username: str = Depends(verify_credentials)):
    """System information for settings page."""
    from html import escape
    import torch

    device = "CUDA" if torch.cuda.is_available() else ("MPS" if torch.backends.mps.is_available() else "CPU")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
    else:
        gpu_name = "N/A"

    # Escape potentially untrusted values
    safe_gpu_name = escape(gpu_name)
    safe_db_url = escape(config.database_url[:50])

    return f'''
    <div class="grid grid-cols-2 gap-4 text-sm">
        <div><span class="text-gray-500">Platform:</span> <span class="font-medium">{platform.system()} {platform.release()}</span></div>
        <div><span class="text-gray-500">Python:</span> <span class="font-medium">{platform.python_version()}</span></div>
        <div><span class="text-gray-500">Compute Device:</span> <span class="font-medium">{device}</span></div>
        <div><span class="text-gray-500">GPU:</span> <span class="font-medium">{safe_gpu_name}</span></div>
        <div><span class="text-gray-500">Database:</span> <span class="font-medium">{safe_db_url}...</span></div>
        <div><span class="text-gray-500">Max File Size:</span> <span class="font-medium">{config.max_file_size_mb} MB</span></div>
    </div>
    '''


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate, username: str = Depends(verify_credentials)):
    """Update configuration settings."""
    if settings.enable_local_ocr is not None:
        config.enable_local_ocr = settings.enable_local_ocr
    if settings.enable_textract is not None:
        config.enable_textract = settings.enable_textract
    if settings.min_confidence_score is not None:
        config.min_confidence_score = settings.min_confidence_score
    if settings.max_retries_per_level is not None:
        config.max_retries_per_level = settings.max_retries_per_level

    return {"status": "ok", "message": "Settings updated"}


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        ocr_model=config.ocr_model_name,
        textract_enabled=config.enable_textract,
        offline_mode=config.ocr_offline_mode
    )


@app.post("/process", response_model=DocumentResponse)
async def process_document_sync(
    file: UploadFile = File(...),
    include_content: bool = Query(False, description="Include extracted content in response"),
    username: str = Depends(verify_credentials)
):
    """
    Upload and process a document synchronously.
    Returns when processing is complete.
    """
    contents = await file.read()
    if len(contents) > config.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {config.max_file_size_mb}MB"
        )

    filename = file.filename or "unknown"
    file_type = Path(filename).suffix.lower().lstrip('.')

    if not file_type:
        raise HTTPException(status_code=400, detail="Could not determine file type")

    record = create_document_record(
        filename=filename,
        file_bytes=contents,
        file_type=file_type,
    )
    doc_id = save_document(record)
    record.id = doc_id

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        pipeline = ExtractionPipeline()
        result = pipeline.process(record, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    response = DocumentResponse(
        id=result.id,
        source_filename=result.source_filename,
        file_type=result.file_type,
        status=result.status,
        extraction_method=result.extraction_method,
        confidence_score=result.confidence_score,
        page_count=result.page_count,
        char_count=result.char_count,
        table_count=result.table_count,
        processing_time_ms=result.processing_time_ms,
        created_at=result.created_at.isoformat() if result.created_at else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        error_message=result.error_message,
    )

    if include_content:
        response.extracted_content_b64 = result.extracted_content_b64

    return response


@app.post("/process/async", response_model=ProcessingResponse)
async def process_document_async(
    file: UploadFile = File(...),
    username: str = Depends(verify_credentials)
):
    """
    Upload a document for async processing.

    Document is saved to database with status=pending.
    Use 'python worker.py worker' to process pending documents.
    Poll GET /documents/{id} to check status.
    """
    contents = await file.read()
    if len(contents) > config.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max: {config.max_file_size_mb}MB")

    filename = file.filename or "unknown"
    file_type = Path(filename).suffix.lower().lstrip('.')

    if not file_type:
        raise HTTPException(status_code=400, detail="Could not determine file type")

    # Save to database with status=pending (persistent queue)
    # Worker process will pick this up and process it
    record = create_document_record(filename=filename, file_bytes=contents, file_type=file_type)
    doc_id = save_document(record)

    return ProcessingResponse(
        document_id=doc_id,
        status="pending",
        message="Document saved to queue. Run 'python worker.py worker' to process. Poll GET /documents/{id} for results."
    )


def process_document_background(doc_id: int, file_bytes: bytes, file_type: str):
    """Background task to process a document."""
    record = get_document(doc_id)
    if not record:
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        pipeline = ExtractionPipeline()
        pipeline.process(record, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document_by_id(
    doc_id: int,
    include_content: bool = Query(False, description="Include extracted content"),
    username: str = Depends(verify_credentials)
):
    """Get document processing result by ID."""
    record = get_document(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    response = DocumentResponse(
        id=record.id,
        source_filename=record.source_filename,
        file_type=record.file_type,
        status=record.status,
        extraction_method=record.extraction_method,
        confidence_score=record.confidence_score,
        page_count=record.page_count,
        char_count=record.char_count,
        table_count=record.table_count,
        processing_time_ms=record.processing_time_ms,
        created_at=record.created_at.isoformat() if record.created_at else None,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
        error_message=record.error_message,
    )

    if include_content:
        response.extracted_content_b64 = record.extracted_content_b64

    return response


@app.get(
    "/documents/{doc_id}/content",
    summary="Get extracted content in specified format",
    description="""
    Retrieve extracted OCR content in industry-standard format.

    **DTAT is a drop-in replacement for commercial OCR services.**

    ### Supported Formats

    - **textract** (default): AWS Textract-compatible format
      - Use this for seamless migration from Textract
      - Saves $1.50/1000 pages vs actual Textract

    - **google**: Google Cloud Vision-compatible format
      - Drop-in replacement for Google Vision OCR
      - Same JSON structure as `text_detection` API

    - **azure**: Azure Computer Vision-compatible format
      - Compatible with Azure Read API responses
      - Matches `analyzeResult` structure

    - **dtat**: DTAT native format (simple)
      - Lightweight format with text and tables
      - Backward compatible with existing integrations

    ### Examples

    ```bash
    # AWS Textract format
    curl -u "admin:password" "http://localhost:8000/documents/1/content?format=textract"

    # Google Vision format
    curl -u "admin:password" "http://localhost:8000/documents/1/content?format=google"

    # Azure OCR format
    curl -u "admin:password" "http://localhost:8000/documents/1/content?format=azure"

    # DTAT native format
    curl -u "admin:password" "http://localhost:8000/documents/1/content?format=dtat"
    ```

    ### Response Structure

    Each format returns a different JSON structure matching the respective API:

    - **Textract**: Contains `Blocks` array with geometry, confidence, relationships
    - **Google**: Contains `textAnnotations` and `fullTextAnnotation`
    - **Azure**: Contains `analyzeResult.readResults` with page-level data
    - **DTAT**: Contains `extracted_text`, `extracted_tables`, `confidence_score`

    ### Migration Guide

    To migrate from commercial OCR services:

    1. Point your existing code to DTAT endpoint
    2. Add `?format=textract` (or google/azure) to your requests
    3. No code changes needed - same JSON structure!

    """,
    responses={
        200: {
            "description": "Extracted content in requested format",
            "content": {
                "application/json": {
                    "examples": {
                        "textract": {
                            "summary": "AWS Textract Format",
                            "value": {
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
                                            }
                                        },
                                        "Page": 1
                                    }
                                ],
                                "DocumentMetadata": {
                                    "Pages": 1
                                }
                            }
                        },
                        "dtat": {
                            "summary": "DTAT Native Format",
                            "value": {
                                "status": "completed",
                                "extracted_text": "Invoice #12345\nDate: 2024-01-15\nTotal: $1,234.56",
                                "extracted_tables": [],
                                "confidence_score": 95.8,
                                "page_count": 1
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Document not ready for retrieval",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Document not ready. Status: processing"
                    }
                }
            }
        },
        404: {
            "description": "Document not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Document not found"
                    }
                }
            }
        }
    },
    tags=["Documents", "OCR Output"]
)
async def get_document_content(
    doc_id: int,
    format: OutputFormat = OutputFormat.TEXTRACT,
    username: str = Depends(verify_credentials)
):
    """
    Get extracted content in specified format.

    See endpoint description for detailed documentation and examples.
    """
    record = get_document(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    if record.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready. Status: {record.status}"
        )

    # Get normalized content from database
    normalized_result = record.get_normalized_content()

    if not normalized_result:
        # Legacy format fallback - convert on the fly
        from extraction_pipeline import convert_extraction_result_to_normalized, ExtractionResult
        content = record.get_extracted_content()

        # Create a temporary ExtractionResult for conversion
        legacy_result = ExtractionResult(
            success=True,
            text_content=content.get("text", ""),
            tables=content.get("tables", []),
            metadata=content.get("metadata", {}),
            confidence_score=record.confidence_score or 0,
            method_used=record.extraction_method or "unknown"
        )

        normalized_result = convert_extraction_result_to_normalized(
            legacy_result,
            page_count=record.page_count or 1
        )

    # Get appropriate formatter and convert
    formatter = get_formatter(format.value)
    formatted_content = formatter.format(normalized_result)

    return formatted_content


@app.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    username: str = Depends(verify_credentials)
):
    """List all documents with optional filtering."""
    session = get_session()
    try:
        query = session.query(DocumentRecord)
        if status:
            query = query.filter_by(status=status)

        total = query.count()
        records = query.order_by(DocumentRecord.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": [
                {
                    "id": r.id,
                    "source_filename": r.source_filename,
                    "file_type": r.file_type,
                    "status": r.status,
                    "extraction_method": r.extraction_method,
                    "confidence_score": r.confidence_score,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
        }
    finally:
        session.close()


@app.get("/stats", response_model=StatsResponse)
async def get_stats(username: str = Depends(verify_credentials)):
    """Get processing statistics."""
    from sqlalchemy import func

    session = get_session()
    try:
        total = session.query(DocumentRecord).count()
        completed = session.query(DocumentRecord).filter_by(status=ProcessingStatus.COMPLETED.value).count()
        failed = session.query(DocumentRecord).filter_by(status=ProcessingStatus.FAILED.value).count()
        needs_review = session.query(DocumentRecord).filter_by(status=ProcessingStatus.NEEDS_REVIEW.value).count()
        pending = session.query(DocumentRecord).filter_by(status=ProcessingStatus.PENDING.value).count()
        processing = session.query(DocumentRecord).filter_by(status=ProcessingStatus.PROCESSING.value).count()

        avg_time = session.query(func.avg(DocumentRecord.processing_time_ms))\
            .filter_by(status=ProcessingStatus.COMPLETED.value).scalar()

        methods = session.query(DocumentRecord.extraction_method, func.count(DocumentRecord.id))\
            .group_by(DocumentRecord.extraction_method).all()
        by_method = {m: c for m, c in methods if m}

        return StatsResponse(
            total_documents=total,
            completed=completed,
            failed=failed,
            needs_review=needs_review,
            pending=pending,
            processing=processing,
            avg_processing_time_ms=avg_time,
            by_method=by_method
        )
    finally:
        session.close()


@app.get("/dlq")
async def get_dead_letter_queue(limit: int = Query(50, ge=1, le=500), username: str = Depends(verify_credentials)):
    """Get documents that need manual review."""
    failed = get_failed_documents(limit=limit)
    return {
        "count": len(failed),
        "documents": [
            {
                "id": r.id,
                "source_filename": r.source_filename,
                "file_type": r.file_type,
                "status": r.status,
                "error_message": r.error_message,
                "extraction_levels_tried": r.extraction_levels_tried,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in failed
        ]
    }


@app.post("/documents/{doc_id}/retry")
async def retry_document(doc_id: int, background_tasks: BackgroundTasks, username: str = Depends(verify_credentials)):
    """Retry processing a failed document."""
    record = get_document(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    if record.status not in [ProcessingStatus.FAILED.value, ProcessingStatus.NEEDS_REVIEW.value]:
        raise HTTPException(status_code=400, detail=f"Can only retry failed documents. Status: {record.status}")

    record.status = ProcessingStatus.PENDING.value
    record.error_message = None
    update_document(record)

    file_bytes = record.get_original_file()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Original file not available")

    background_tasks.add_task(process_document_background, doc_id, file_bytes, record.file_type)

    return ProcessingResponse(document_id=doc_id, status="queued", message="Document queued for retry.")


# =============================================================================
# PROFILE MANAGEMENT API (TASK-002)
# =============================================================================

@app.post(
    "/profiles",
    response_model=ExtractionProfile,
    status_code=201,
    tags=["Profile Management"],
    summary="Create extraction profile",
    description="""
    Create a new extraction profile for structured field extraction.

    Profiles define what fields to extract from specific document types (invoices, receipts, etc.).

    **Example:**
    ```json
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
                    "max_distance": 150
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
                    "pattern": "\\\\$?([0-9,]+\\\\.\\\\d{2})"
                },
                "min_value": 0.0
            }
        ]
    }
    ```
    """
)
async def create_extraction_profile(
    profile: ExtractionProfile,
    username: str = Depends(verify_credentials)
):
    """Create a new extraction profile."""
    # Check if profile name already exists
    existing = get_profile_by_name(profile.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Profile with name '{profile.name}' already exists")

    # Set created_by if not provided
    if not profile.created_by:
        profile.created_by = username

    # Create profile
    profile_dict = profile.model_dump()
    record = create_profile(profile_dict)

    # Create initial version
    create_profile_version(
        record.id,
        version=1,
        schema_dict=profile_dict,
        created_by=username,
        change_description="Initial version"
    )

    # Convert record to ExtractionProfile for response
    return record_to_profile(record)


@app.get(
    "/profiles",
    response_model=list[ExtractionProfile],
    tags=["Profile Management"],
    summary="List extraction profiles",
    description="List all extraction profiles with optional filtering by document type, organization, template status, etc."
)
async def list_extraction_profiles(
    document_type: Optional[str] = Query(None, description="Filter by document type (invoice, receipt, etc.)"),
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    is_template: Optional[bool] = Query(None, description="Filter by template status"),
    active_only: bool = Query(True, description="Only return active profiles"),
    limit: int = Query(100, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    username: str = Depends(verify_credentials)
):
    """List extraction profiles with optional filters."""
    records = list_profiles(
        document_type=document_type,
        organization_id=organization_id,
        is_template=is_template,
        active_only=active_only,
        limit=limit,
        offset=offset
    )

    # Convert records to ExtractionProfile models
    return records_to_profiles(records)


@app.get(
    "/profiles/{profile_id}",
    response_model=ExtractionProfile,
    tags=["Profile Management"],
    summary="Get profile by ID",
    description="Retrieve a specific extraction profile by its ID."
)
async def get_extraction_profile(
    profile_id: int,
    username: str = Depends(verify_credentials)
):
    """Get a specific extraction profile by ID."""
    record = get_profile_by_id(profile_id)
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not record.is_active:
        raise HTTPException(status_code=404, detail="Profile is inactive")

    return record_to_profile(record)


@app.get(
    "/profiles/by-name/{name}",
    response_model=ExtractionProfile,
    tags=["Profile Management"],
    summary="Get profile by name",
    description="Retrieve a specific extraction profile by its unique name."
)
async def get_extraction_profile_by_name(
    name: str,
    username: str = Depends(verify_credentials)
):
    """Get a specific extraction profile by name."""
    record = get_profile_by_name(name)
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not record.is_active:
        raise HTTPException(status_code=404, detail="Profile is inactive")

    return record_to_profile(record)


@app.put(
    "/profiles/{profile_id}",
    response_model=ExtractionProfile,
    tags=["Profile Management"],
    summary="Update extraction profile",
    description="""
    Update an existing profile (creates new version).

    Changes are versioned - previous versions remain accessible for rollback.
    """
)
async def update_extraction_profile(
    profile_id: int,
    profile: ExtractionProfile,
    change_description: Optional[str] = Query(None, description="Description of changes"),
    username: str = Depends(verify_credentials)
):
    """Update an existing profile (creates new version)."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Increment version
    new_version = existing.version + 1
    profile.version = new_version
    profile.id = profile_id

    # Update profile
    profile_dict = profile.model_dump()
    record = update_profile(profile_id, profile_dict)

    # Create version snapshot
    create_profile_version(
        profile_id,
        version=new_version,
        schema_dict=profile_dict,
        created_by=username,
        change_description=change_description or f"Updated to version {new_version}"
    )

    return record_to_profile(record)


@app.delete(
    "/profiles/{profile_id}",
    status_code=204,
    tags=["Profile Management"],
    summary="Delete extraction profile",
    description="""
    Delete or deactivate a profile.

    - `hard_delete=False` (default): Sets is_active=False, preserves data
    - `hard_delete=True`: Permanently deletes profile and versions
    """
)
async def delete_extraction_profile(
    profile_id: int,
    hard_delete: bool = Query(False, description="Permanently delete (true) or deactivate (false)"),
    username: str = Depends(verify_credentials)
):
    """Delete or deactivate a profile."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    delete_profile(profile_id, hard_delete=hard_delete)
    return None  # 204 No Content


@app.get(
    "/profiles/{profile_id}/versions",
    response_model=list[ProfileVersion],
    tags=["Profile Management"],
    summary="Get profile version history",
    description="Get all versions of a profile for audit trail and rollback."
)
async def get_extraction_profile_versions(
    profile_id: int,
    username: str = Depends(verify_credentials)
):
    """Get version history for a profile."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    version_records = get_profile_versions(profile_id)

    # Convert to ProfileVersion models
    versions = []
    for record in version_records:
        schema = record.get_schema()
        versions.append(ProfileVersion(
            id=record.id,
            profile_id=record.profile_id,
            version=record.version,
            profile_schema=schema,
            created_by=record.created_by,
            change_description=record.change_description,
            created_at=record.created_at
        ))

    return versions


@app.post(
    "/profiles/{profile_id}/rollback/{version}",
    response_model=ExtractionProfile,
    tags=["Profile Management"],
    summary="Rollback profile to previous version",
    description="Rollback profile to a previous version (creates a new version with the old schema)."
)
async def rollback_extraction_profile(
    profile_id: int,
    version: int,
    username: str = Depends(verify_credentials)
):
    """Rollback profile to a previous version."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    old_version_record = get_profile_version(profile_id, version)
    if not old_version_record:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    # Get old schema and create new version with it
    old_schema = old_version_record.get_schema()
    new_version = existing.version + 1
    old_schema['version'] = new_version

    # Update profile
    record = update_profile(profile_id, old_schema)

    # Create version snapshot
    create_profile_version(
        profile_id,
        version=new_version,
        schema_dict=old_schema,
        created_by=username,
        change_description=f"Rolled back to version {version}"
    )

    return record_to_profile(record)


@app.get(
    "/profiles/{profile_id}/stats",
    tags=["Profile Management"],
    summary="Get profile usage statistics",
    description="Get usage statistics for a profile including success rate, average confidence, and processing times."
)
async def get_extraction_profile_stats(
    profile_id: int,
    days: int = Query(30, le=365, description="Number of days to look back"),
    username: str = Depends(verify_credentials)
):
    """Get usage statistics for a profile."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    stats = get_profile_usage_stats(profile_id, days=days)

    return {
        "profile_id": profile_id,
        "profile_name": existing.name,
        "stats_period_days": days,
        **stats
    }


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
