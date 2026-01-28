"""
DTAT OCR - Ducktape and Twine OCR
REST API + Web UI for Document Processing Pipeline

API Endpoints:
- POST /process          - Upload and process a document (sync)
- POST /process/async    - Upload and queue for processing (async)
- GET  /documents/{id}   - Get processing result
- GET  /documents        - List all documents
- GET  /health           - Health check
- GET  /stats            - Processing statistics

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

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config import config
from database import (
    init_database, DocumentRecord, ProcessingStatus,
    create_document_record, save_document, get_document,
    get_pending_documents, get_failed_documents, update_document,
    get_session
)
from extraction_pipeline import ExtractionPipeline


# Initialize
app = FastAPI(
    title="DTAT OCR",
    description="Ducktape and Twine OCR - Swiss Army Knife document processing",
    version="1.0.0"
)

# Templates
templates = Jinja2Templates(directory="templates")

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
async def ui_home(request: Request):
    """Main processing page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_page": "home"
    })


@app.get("/ui/documents", response_class=HTMLResponse)
async def ui_documents(request: Request):
    """Documents list page."""
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "active_page": "documents"
    })


@app.get("/ui/settings", response_class=HTMLResponse)
async def ui_settings(request: Request):
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
async def health_badge():
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
async def stats_cards():
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
async def recent_documents():
    """Recent documents table for dashboard."""
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
            rows += f'''
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-900">{r.id}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{r.source_filename[:30]}{'...' if len(r.source_filename) > 30 else ''}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.file_type or 'N/A'}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center rounded-full bg-{status_color}-100 px-2 py-0.5 text-xs font-medium text-{status_color}-800">
                        {r.status}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.extraction_method or 'N/A'}</td>
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
async def documents_table(status: Optional[str] = None):
    """Full documents table."""
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

            rows += f'''
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-900">{r.id}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{r.source_filename[:40]}{'...' if len(r.source_filename) > 40 else ''}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.file_type or 'N/A'}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center rounded-full bg-{status_color}-100 px-2 py-0.5 text-xs font-medium text-{status_color}-800">
                        {r.status}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">{r.extraction_method or 'N/A'}</td>
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
async def system_info():
    """System information for settings page."""
    import torch

    device = "CUDA" if torch.cuda.is_available() else ("MPS" if torch.backends.mps.is_available() else "CPU")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
    else:
        gpu_name = "N/A"

    return f'''
    <div class="grid grid-cols-2 gap-4 text-sm">
        <div><span class="text-gray-500">Platform:</span> <span class="font-medium">{platform.system()} {platform.release()}</span></div>
        <div><span class="text-gray-500">Python:</span> <span class="font-medium">{platform.python_version()}</span></div>
        <div><span class="text-gray-500">Compute Device:</span> <span class="font-medium">{device}</span></div>
        <div><span class="text-gray-500">GPU:</span> <span class="font-medium">{gpu_name}</span></div>
        <div><span class="text-gray-500">Database:</span> <span class="font-medium">{config.database_url[:50]}...</span></div>
        <div><span class="text-gray-500">Max File Size:</span> <span class="font-medium">{config.max_file_size_mb} MB</span></div>
    </div>
    '''


@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
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
    include_content: bool = Query(False, description="Include extracted content in response")
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
    background_tasks: BackgroundTasks = None
):
    """Upload a document for async processing."""
    contents = await file.read()
    if len(contents) > config.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max: {config.max_file_size_mb}MB")

    filename = file.filename or "unknown"
    file_type = Path(filename).suffix.lower().lstrip('.')

    if not file_type:
        raise HTTPException(status_code=400, detail="Could not determine file type")

    record = create_document_record(filename=filename, file_bytes=contents, file_type=file_type)
    doc_id = save_document(record)

    background_tasks.add_task(process_document_background, doc_id, contents, file_type)

    return ProcessingResponse(
        document_id=doc_id,
        status="queued",
        message="Document queued for processing. Poll GET /documents/{id} for results."
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
    include_content: bool = Query(False, description="Include extracted content")
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


@app.get("/documents/{doc_id}/content", response_model=DocumentContentResponse)
async def get_document_content(doc_id: int):
    """Get extracted content (decoded from base64)."""
    record = get_document(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    if record.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"Document not ready. Status: {record.status}")

    content = record.get_extracted_content()

    return DocumentContentResponse(
        id=record.id,
        source_filename=record.source_filename,
        status=record.status,
        extracted_text=content.get("text"),
        extracted_tables=content.get("tables"),
        metadata=content.get("metadata")
    )


@app.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
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
async def get_stats():
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
async def get_dead_letter_queue(limit: int = Query(50, ge=1, le=500)):
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
async def retry_document(doc_id: int, background_tasks: BackgroundTasks):
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
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
