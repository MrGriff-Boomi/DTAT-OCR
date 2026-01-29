# TASK-002 Phase 7 Follow-Up: Critical Fixes and Testing

**Status:** 🔴 Pending
**Created:** 2026-01-29
**Priority:** Critical
**Estimated Effort:** 4 weeks (80-120 hours)
**Dependencies:** Phase 7 implementation complete

## Overview

Phase 7 successfully integrated profile-based extraction into the document processing pipeline. However, comprehensive code reviews identified **7 critical issues**, **13 high-priority improvements**, and **45+ missing test scenarios** that must be addressed before production deployment.

This task tracks all follow-up work required to bring Phase 7 to production-ready quality.

---

## 🔴 Critical Issues (Week 1 - Must Fix Immediately)

### Issue #1: Missing Form Import - API Will Crash
**Severity:** 🔴 Critical
**File:** `api.py` line 650
**Impact:** Runtime crash when endpoint is called
**Effort:** 5 minutes

**Problem:**
```python
# Line 650 uses Form but it's not imported
profile_id: Optional[int] = Form(None)
```

**Fix:**
```python
# Line 39 - Add Form to imports
from fastapi import (
    FastAPI, File, UploadFile, HTTPException,
    BackgroundTasks, Query, Request, Depends,
    Form  # ← ADD THIS
)
```

**Test:** Call `/process-with-profile` endpoint and verify no ImportError

---

### Issue #2: Response Model Mismatch
**Severity:** 🔴 Critical
**File:** `api.py` lines 753-754
**Impact:** Pydantic validation error at runtime
**Effort:** 2 hours

**Problem:**
```python
# Lines 753-754 - These fields don't exist in DocumentResponse
response = DocumentResponse(
    ...
    profile_id=record.profile_id,        # ← Field doesn't exist
    extracted_fields=record.extracted_fields  # ← Field doesn't exist
)
```

**Fix Option A:** Add fields to DocumentResponse (Quick)
```python
# database.py or api.py models
class DocumentResponse(BaseModel):
    # ... existing fields ...
    profile_id: Optional[int] = None
    extracted_fields: Optional[Dict[str, Any]] = None
```

**Fix Option B:** Create new response model (Better)
```python
class ProfileDocumentResponse(BaseModel):
    """Response for profile-based document processing"""
    # Standard document fields
    id: int
    source_filename: str
    file_type: Optional[str]
    status: str
    extraction_method: Optional[str]
    confidence_score: Optional[float]
    page_count: Optional[int]
    processing_time_ms: Optional[int]
    created_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]

    # Profile-specific fields
    profile_id: int
    profile_name: str
    extracted_fields: Optional[Dict[str, Any]]

    # Validation summary
    validation_summary: Optional[Dict[str, Any]] = None
```

**Test:**
- Call `/process-with-profile` endpoint
- Verify response validates against model
- Check OpenAPI schema is correct

---

### Issue #3: No Document Validation After Reload
**Severity:** 🔴 Critical
**File:** `api.py` line 732
**Impact:** NoneType crash if document not found
**Effort:** 15 minutes

**Problem:**
```python
# Line 732 - get_document() could return None
record = get_document(doc_id)
# No null check here
pipeline = ExtractionPipeline()
record = pipeline.process(record, tmp_path)  # ← Crash if record is None
```

**Fix:**
```python
# After line 732
record = get_document(doc_id)
if not record:
    tmp_path.unlink(missing_ok=True)
    raise HTTPException(
        status_code=500,
        detail=f"Document {doc_id} not found after save. This should not happen."
    )

pipeline = ExtractionPipeline()
record = pipeline.process(record, tmp_path)
```

**Test:**
- Mock `get_document()` to return None
- Verify HTTPException raised, not NoneType error
- Verify temp file cleaned up

---

### Issue #4: Circular Import Risk
**Severity:** 🔴 Critical
**File:** `extraction_pipeline.py` lines 930-932
**Impact:** Hidden import failures until runtime
**Effort:** 4-6 hours

**Problem:**
```python
# Lines 930-932 - Local imports inside function
def _extract_with_profile(self, document, ocr_result):
    from database import get_profile_by_id, log_profile_usage
    from extractors import ProfileExtractor
    from profiles import ExtractionProfile
    # ... function body ...
```

**Why This Is Bad:**
1. Import failures won't surface until a document with profile is processed
2. Unclear module dependency graph
3. Makes testing harder (can't easily mock imports)
4. Indicates architectural coupling issue

**Fix Option A:** Move imports to module level (Quick but fragile)
```python
# Top of extraction_pipeline.py
from database import get_profile_by_id, log_profile_usage
from extractors import ProfileExtractor
from profiles import ExtractionProfile
```

**Fix Option B:** Create integration module (Better - breaks circular dependency)
```python
# Create new file: profile_integration.py
"""
Profile extraction integration layer.
Breaks circular dependency between extraction_pipeline and extractors.
"""
from database import get_profile_by_id, log_profile_usage
from extractors import ProfileExtractor
from profiles import ExtractionProfile

class ProfileExtractionIntegrator:
    """Handles profile-based extraction integration."""

    def extract_with_profile(self, document, ocr_result):
        """Extract fields using assigned profile."""
        # Implementation from _extract_with_profile
        pass

# Then in extraction_pipeline.py:
from profile_integration import ProfileExtractionIntegrator

def _finalize_success(self, document, result, levels_tried):
    # ... existing code ...

    if document.profile_id:
        integrator = ProfileExtractionIntegrator()
        integrator.extract_with_profile(document, normalized_result)
```

**Test:**
- Restart Python interpreter and import extraction_pipeline
- Verify no ImportError
- Process document with profile
- Verify extraction works

**Decision:** Recommend Option B for long-term maintainability

---

### Issue #5: Type Mismatch - ocr_result Parameter
**Severity:** 🔴 Critical
**File:** `extraction_pipeline.py` line 917
**Impact:** Type confusion, potential AttributeError
**Effort:** 1-2 hours

**Problem:**
```python
# Line 917 - Type hint says dict but code passes NormalizedResult
def _extract_with_profile(
    self,
    document: DocumentRecord,
    ocr_result: dict  # ← Says dict
) -> None:
    # ...

# Line 892 - Caller passes NormalizedResult
normalized_result = convert_extraction_result_to_normalized(...)
self._extract_with_profile(document, normalized_result)  # ← Passes object, not dict
```

**Fix:**
```python
# Option A: Accept NormalizedResult and convert
def _extract_with_profile(
    self,
    document: DocumentRecord,
    normalized_result: NormalizedResult  # ← Correct type
) -> None:
    """Extract with profile using normalized OCR result."""

    # Convert to dict for ProfileExtractor
    ocr_result_dict = {
        'blocks': normalized_result.blocks,
        'tables': normalized_result.tables,
        'page_count': normalized_result.page_count,
        # ... other fields ...
    }

    extraction_results = extractor.extract_all_fields(profile, ocr_result_dict)

# Option B: Accept dict and update caller
def _extract_with_profile(
    self,
    document: DocumentRecord,
    ocr_result: dict  # ← Keep as dict
) -> None:
    # ... existing implementation ...

# Then update caller (line 892)
normalized_result = convert_extraction_result_to_normalized(...)
ocr_result_dict = normalized_result.to_dict()  # ← Convert here
self._extract_with_profile(document, ocr_result_dict)
```

**Test:**
- Add type checking with mypy: `mypy extraction_pipeline.py`
- Verify no type errors
- Process document and verify extraction works

**Decision:** Recommend Option B (accept dict, convert at call site)

---

### Issue #6: Tempfile Leaks in Worker
**Severity:** 🔴 Critical
**File:** `worker.py` lines 177-200
**Impact:** Disk space exhaustion, file descriptor leaks
**Effort:** 1 hour

**Problem:**
```python
# Lines 177-200 - No cleanup on exception
tmp_path = Path(tempfile.mktemp(suffix=f".{record.file_type}"))
with open(tmp_path, 'wb') as f:
    f.write(record.get_original_file())

# Process here - if exception occurs, file never deleted
pipeline = ExtractionPipeline()
result = pipeline.process(record, tmp_path)
```

**Fix:**
```python
# Lines 177-200 - Add try/finally
tmp_path = Path(tempfile.mktemp(suffix=f".{record.file_type}"))
try:
    with open(tmp_path, 'wb') as f:
        f.write(record.get_original_file())

    # Process
    pipeline = ExtractionPipeline()
    result = pipeline.process(record, tmp_path)
finally:
    # Always cleanup
    tmp_path.unlink(missing_ok=True)
```

**Test:**
- Mock `pipeline.process()` to raise exception
- Check that temp file is deleted
- Run batch process with 100 documents
- Verify no temp files left in /tmp

---

### Issue #7: Unsafe Exception Catching
**Severity:** 🔴 Critical
**File:** `extraction_pipeline.py` line 998
**Impact:** Catches system exceptions like KeyboardInterrupt
**Effort:** 5 minutes

**Problem:**
```python
# Line 998 - Bare except catches EVERYTHING
try:
    log_profile_usage(...)
except:  # ← Catches KeyboardInterrupt, SystemExit, etc.
    pass
```

**Fix:**
```python
# Line 998 - Only catch Exception
try:
    log_profile_usage(...)
except Exception as e:  # ← Only catch normal exceptions
    logger.warning(f"Failed to log profile usage: {e}")
    # Don't re-raise - logging failure shouldn't crash pipeline
```

**Test:**
- Simulate SIGINT during processing
- Verify KeyboardInterrupt propagates (process stops)
- Simulate database error during log_profile_usage
- Verify it's caught and logged

---

## 🟡 High-Priority Issues (Week 2-3)

### Issue #8: No API Endpoint Tests
**Severity:** 🟡 High
**Files:** None (tests missing)
**Impact:** REST interface completely untested
**Effort:** 16-20 hours

**What's Missing:**
```
test_phase7_api.py - 15+ tests needed:
- test_process_with_profile_by_name()
- test_process_with_profile_by_id()
- test_process_with_profile_both_params_error()
- test_process_with_profile_no_params_error()
- test_process_with_profile_invalid_profile()
- test_process_with_profile_file_too_large()
- test_process_with_profile_auth_required()
- test_get_extracted_fields_success()
- test_get_extracted_fields_no_profile()
- test_get_extracted_fields_not_processed()
- test_get_extracted_fields_not_found()
- test_get_extracted_fields_auth_required()
- test_extracted_fields_structure()
- test_extracted_fields_statistics()
- test_extracted_fields_validation_status()
```

**Implementation Plan:**
1. Create `test_phase7_api.py`
2. Use `httpx.AsyncClient` for testing
3. Mock file uploads with multipart/form-data
4. Test all success and error paths
5. Verify response structures
6. Check authentication enforcement

**Acceptance Criteria:**
- [ ] All 15+ tests pass
- [ ] Code coverage >90% for new endpoints
- [ ] All error codes verified (200, 400, 401, 404, 413)
- [ ] Response schemas validated

---

### Issue #9: Code Duplication - Profile Resolution
**Severity:** 🟡 High
**Files:** `worker.py:58-76`, `api.py:676-704`
**Impact:** Maintenance burden, inconsistent behavior
**Effort:** 2-3 hours

**Problem:**
Profile resolution logic duplicated with different error handling:
- worker.py prints error and returns {}
- api.py raises HTTPException

**Fix:**
Create shared helper in `database.py`:

```python
def resolve_profile(
    profile_id: Optional[int] = None,
    profile_name: Optional[str] = None,
    require_active: bool = True
) -> Tuple[Optional[int], Optional[ExtractionProfileRecord], Optional[str]]:
    """
    Resolve profile from ID or name with validation.

    Returns:
        (resolved_profile_id, profile_record, error_message)

    Example:
        profile_id, record, error = resolve_profile(profile_name="invoice")
        if error:
            # Handle error
        else:
            # Use profile_id and record
    """
    # Validation
    if not profile_id and not profile_name:
        return None, None, "Must specify either profile_id or profile_name"

    if profile_id and profile_name:
        return None, None, "Specify only one: profile_id OR profile_name"

    # Resolve by ID or name
    if profile_id:
        profile_record = get_profile_by_id(profile_id)
        if not profile_record:
            return None, None, f"Profile ID {profile_id} not found"
    else:
        profile_record = get_profile_by_name(profile_name)
        if not profile_record:
            return None, None, f"Profile '{profile_name}' not found"

    # Check active status
    if require_active and not profile_record.is_active:
        return None, None, f"Profile '{profile_record.name}' is inactive"

    return profile_record.id, profile_record, None
```

Then update both callers to use this function.

**Test:**
- Test all parameter combinations
- Test inactive profile handling
- Verify consistent behavior in CLI and API

---

### Issue #10: No Proper Logging
**Severity:** 🟡 High
**Files:** `extraction_pipeline.py`, `worker.py`, multiple locations
**Impact:** Production debugging will be difficult
**Effort:** 3-4 hours

**Problem:**
Code uses `print()` statements instead of proper logging:
```python
print(f"[ERROR] Profile extraction failed: {error_msg}")
print(f"[PROFILE] Extracted {stats['extracted']}/{stats['total_fields']} fields")
```

**Issues:**
- Can't control log levels in production
- Can't route to files/syslog/CloudWatch
- Makes testing harder
- No timestamps
- No context (thread ID, request ID, etc.)

**Fix:**
Replace all print statements with logging:

```python
# At top of each file
import logging
logger = logging.getLogger(__name__)

# Replace prints:
logger.info(f"Extracted {stats['extracted']}/{stats['total_fields']} fields from document {document.id}")
logger.error(f"Profile extraction failed for document {document.id}", exc_info=True)
logger.warning(f"Profile {profile_id} not found for document {document.id}")
logger.debug(f"Processing document {document.id} with profile {profile_id}")
```

**Add Configuration:**
```python
# config.py
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'dtat-ocr.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
            'level': 'DEBUG'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

**Files to Update:**
- extraction_pipeline.py (~5 print statements)
- worker.py (~10 print statements)
- database.py (~3 print statements)
- api.py (~2 print statements)

**Test:**
- Run processing and verify logs appear in file
- Check log levels work (DEBUG vs INFO)
- Verify structured logging with timestamps

---

### Issue #11: No Transaction Rollback
**Severity:** 🟡 High
**File:** `extraction_pipeline.py:890-894`
**Impact:** Partial data persisted on failure
**Effort:** 4-6 hours

**Problem:**
```python
# Lines 890-894
document.set_normalized_content(normalized_result)

if document.profile_id:
    self._extract_with_profile(document, normalized_result)

update_document(document)  # ← If this fails, what happens to changes?
```

**Issue:**
- `set_normalized_content()` modifies document in memory
- `_extract_with_profile()` sets `extracted_fields` in memory
- If `update_document()` fails, changes are lost but no error

**Fix:**
Wrap entire finalization in transaction:

```python
def _finalize_success(self, document, result, levels_tried):
    """Finalize with transaction."""
    from database import get_session

    # Prepare all changes
    document.status = ProcessingStatus.COMPLETED.value
    document.completed_at = datetime.utcnow()
    # ... other fields ...

    normalized_result = convert_extraction_result_to_normalized(...)
    document.set_normalized_content(normalized_result)

    # Profile extraction
    if document.profile_id:
        self._extract_with_profile(document, normalized_result)

    # Save everything in transaction
    session = get_session()
    try:
        session.merge(document)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save document {document.id}: {e}", exc_info=True)

        # Set error status
        document.status = ProcessingStatus.NEEDS_REVIEW.value
        document.error_message = f"Save failed: {str(e)}"

        # Try to save error state
        try:
            session.merge(document)
            session.commit()
        except:
            logger.error(f"Failed to save error state for document {document.id}")

        raise
    finally:
        session.close()

    return document
```

**Test:**
- Mock `session.commit()` to raise exception
- Verify rollback occurs
- Verify document status reflects error
- Check no partial data persisted

---

### Issue #12: Database Session Management
**Severity:** 🟡 High
**Files:** `database.py` multiple functions
**Impact:** Connection leaks, resource exhaustion
**Effort:** 6-8 hours

**Problem:**
Sessions could leak if exception occurs before try block:

```python
# Current pattern in database.py
def some_function():
    session = get_session()  # ← If exception here, no cleanup
    try:
        # ... work ...
        session.commit()
    finally:
        session.close()
```

**Fix:**
Update `get_session()` to return context manager:

```python
# database.py
from contextlib import contextmanager

@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Then update all functions:
def create_profile(profile_dict: dict):
    with get_db_session() as session:
        record = ExtractionProfileRecord(...)
        session.add(record)
        session.flush()
        session.refresh(record)
        return record
```

**Files to Update:**
- `create_profile()`
- `update_profile()`
- `get_profile_by_id()`
- `get_profile_by_name()`
- `list_profiles()`
- `log_profile_usage()`
- ~20 more functions

**Test:**
- Monitor open connections: `SELECT count(*) FROM pg_stat_activity`
- Run 1000 operations
- Verify connections don't accumulate
- Cause exceptions in various places
- Verify sessions always closed

---

### Issue #13: Profile Version Race Condition
**Severity:** 🟡 High
**File:** `api.py:1343-1364`
**Impact:** Concurrent updates could violate unique constraint
**Effort:** 2-3 hours

**Problem:**
```python
# Lines 1348-1350
new_version = existing.version + 1
profile.version = new_version

# Two concurrent requests both read version=5, both try to create version=6
record = update_profile(profile_id, profile_dict)
```

**Fix:**
Add retry logic with IntegrityError handling:

```python
from sqlalchemy.exc import IntegrityError

@app.put("/profiles/{profile_id}")
async def update_extraction_profile(
    profile_id: int,
    profile: ExtractionProfile,
    max_retries: int = 3,
    username: str = Depends(verify_credentials)
):
    """Update profile with optimistic locking and retry."""

    for attempt in range(max_retries):
        try:
            # Get current version
            existing = get_profile_by_id(profile_id)
            if not existing:
                raise HTTPException(404, "Profile not found")

            # Increment version
            new_version = existing.version + 1
            profile.version = new_version

            # Update
            record = update_profile(profile_id, profile_dict)

            # Create version record
            create_profile_version(
                profile_id=profile_id,
                version=new_version,
                schema=profile_dict,
                change_description=f"Updated by {username}"
            )

            return record_to_profile(record)

        except IntegrityError as e:
            if attempt < max_retries - 1:
                # Retry with fresh version
                continue
            else:
                # Max retries exceeded
                raise HTTPException(
                    status_code=409,
                    detail="Profile was modified by another user. Please refresh and try again."
                )
```

**Test:**
- Launch 10 concurrent update requests
- Verify some succeed, some get 409
- Verify final version is correct
- Verify no duplicate versions in database

---

## 📋 Testing Tasks (Weeks 2-4)

### Test Suite #1: API Endpoint Tests
**File:** `test_phase7_api.py`
**Effort:** 16-20 hours
**Priority:** 🔴 Critical

**Tests to Implement:**

```python
# Authentication Tests (2 tests)
async def test_api_auth_required()
async def test_api_invalid_credentials()

# POST /process-with-profile Tests (8 tests)
async def test_process_with_profile_name()
async def test_process_with_profile_id()
async def test_process_with_both_params_error()
async def test_process_with_no_params_error()
async def test_process_with_invalid_profile_name()
async def test_process_with_invalid_profile_id()
async def test_process_with_inactive_profile()
async def test_process_file_too_large()

# GET /documents/{id}/extracted-fields Tests (7 tests)
async def test_get_extracted_fields_success()
async def test_get_extracted_fields_no_profile()
async def test_get_extracted_fields_not_processed()
async def test_get_extracted_fields_not_found()
async def test_extracted_fields_structure()
async def test_extracted_fields_statistics()
async def test_extracted_fields_validation_status()
```

**Setup Required:**
```python
import pytest
from httpx import AsyncClient
from api import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def auth():
    return ("admin", "password")

@pytest.fixture
def sample_pdf():
    # Create minimal valid PDF
    return b"%PDF-1.4\n%Test PDF\n%%EOF"
```

---

### Test Suite #2: Concurrency & Transaction Tests
**File:** `test_phase7_transactions.py`
**Effort:** 8-12 hours
**Priority:** 🔴 Critical

**Tests to Implement:**

```python
# Concurrent Processing (3 tests)
def test_concurrent_profile_extraction()
def test_concurrent_document_processing()
def test_concurrent_profile_updates()

# Transaction Rollback (3 tests)
def test_ocr_success_extraction_failure()
def test_save_failure_rollback()
def test_partial_extraction_consistency()

# Session Management (2 tests)
def test_no_session_leaks()
def test_session_cleanup_on_error()

# Race Conditions (2 tests)
def test_profile_version_race_condition()
def test_document_status_race_condition()
```

**Example Implementation:**
```python
import threading
from concurrent.futures import ThreadPoolExecutor

def test_concurrent_profile_extraction():
    """10 documents using same profile simultaneously"""
    init_database()
    seed_templates()
    profile = get_profile_by_name("template-generic-invoice")

    def process_doc(i):
        record = create_test_document()
        record.profile_id = profile.id
        doc_id = save_document(record)

        # Process
        result = pipeline.process(record, test_file_path)
        return result.extracted_fields is not None

    # Process 10 docs concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process_doc, range(10)))

    # Verify all succeeded
    assert all(results)

    # Verify 10 usage records created
    usage = get_profile_usage_stats(profile.id)
    assert usage['total_uses'] == 10
```

---

### Test Suite #3: Error Scenario Tests
**File:** `test_phase7_errors.py`
**Effort:** 8-10 hours
**Priority:** 🔴 Critical

**Tests to Implement:**

```python
# Profile Errors (4 tests)
def test_profile_deleted_during_processing()
def test_profile_schema_invalid()
def test_profile_not_found()
def test_inactive_profile_rejection()

# Extraction Errors (4 tests)
def test_extractor_key_error()
def test_extractor_value_error()
def test_extractor_attribute_error()
def test_extraction_timeout()

# Database Errors (2 tests)
def test_database_connection_lost()
def test_save_document_fails()

# Resource Errors (2 tests)
def test_tempfile_cleanup_on_error()
def test_out_of_memory_handling()
```

---

### Test Suite #4: Data Integrity Tests
**File:** `test_phase7_integrity.py`
**Effort:** 4-6 hours
**Priority:** 🟡 High

**Tests to Implement:**

```python
# End-to-End Data Flow (2 tests)
def test_full_data_flow_integrity()
def test_data_isolation_between_documents()

# Field Validation (2 tests)
def test_required_field_validation()
def test_field_type_validation()

# Statistics Accuracy (2 tests)
def test_usage_statistics_accuracy()
def test_confidence_score_calculation()
```

---

## 🔧 Code Quality Improvements (Week 3-4)

### Improvement #1: Standardize API Parameters
**Effort:** 2-3 hours
**Impact:** Consistency, better developer experience

**Change:** Use Query parameters instead of Form:
```python
@app.post("/process-with-profile")
async def process_document_with_profile(
    file: UploadFile = File(...),
    profile_id: Optional[int] = Query(None),  # ← Change from Form
    profile_name: Optional[str] = Query(None),  # ← Change from Form
    username: str = Depends(verify_credentials)
)
```

URL becomes: `POST /process-with-profile?profile_name=invoice-template`

---

### Improvement #2: Add Async Processing Variant
**Effort:** 4-6 hours
**Impact:** Better user experience for large documents

**Implementation:**
```python
@app.post("/process-with-profile/async")
async def process_with_profile_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    profile_id: Optional[int] = Query(None),
    profile_name: Optional[str] = Query(None),
    webhook_url: Optional[str] = Query(None),
    username: str = Depends(verify_credentials)
):
    """Queue document for async processing with profile."""

    # Resolve profile
    resolved_id, profile_record, error = resolve_profile(profile_id, profile_name)
    if error:
        raise HTTPException(400, error)

    # Save document
    contents = await file.read()
    record = create_document_record(...)
    record.profile_id = resolved_id
    doc_id = save_document(record)

    # Queue processing
    background_tasks.add_task(
        process_document_background,
        doc_id, contents, file_type
    )

    return {
        "document_id": doc_id,
        "status": "queued",
        "message": "Document queued for processing",
        "poll_url": f"/documents/{doc_id}"
    }
```

---

### Improvement #3: Add Field Filtering
**Effort:** 2-3 hours
**Impact:** Better API for clients that only need specific fields

**Implementation:**
```python
@app.get("/documents/{doc_id}/extracted-fields")
async def get_extracted_fields(
    doc_id: int,
    fields: Optional[List[str]] = Query(None),
    include_metadata: bool = Query(True),
    username: str = Depends(verify_credentials)
):
    """Get extracted fields with optional filtering."""

    record = get_document(doc_id)
    # ... validation ...

    extracted = record.extracted_fields

    # Filter fields if requested
    if fields:
        filtered_fields = {
            k: v for k, v in extracted['fields'].items()
            if k in fields
        }
        extracted['fields'] = filtered_fields

    # Remove metadata if not requested
    if not include_metadata:
        for field_data in extracted['fields'].values():
            field_data.pop('location', None)
            field_data.pop('strategy', None)

    return {
        "document_id": record.id,
        "profile_id": record.profile_id,
        "extracted_fields": extracted
    }
```

Usage: `GET /documents/123/extracted-fields?fields=invoice_number,total_amount`

---

## 📊 Progress Tracking

### Week 1: Critical Fixes
- [ ] Issue #1: Add Form import (5 min)
- [ ] Issue #2: Fix response model (2 hrs)
- [ ] Issue #3: Add document validation (15 min)
- [ ] Issue #4: Fix circular imports (4-6 hrs)
- [ ] Issue #5: Fix type mismatch (1-2 hrs)
- [ ] Issue #6: Fix tempfile leaks (1 hr)
- [ ] Issue #7: Fix bare except (5 min)

**Total Week 1:** 8-12 hours

### Week 2: High-Priority Fixes
- [ ] Issue #8: Add API endpoint tests (16-20 hrs)
- [ ] Issue #9: Refactor profile resolution (2-3 hrs)
- [ ] Issue #10: Add proper logging (3-4 hrs)
- [ ] Issue #11: Add transaction rollback (4-6 hrs)

**Total Week 2:** 25-33 hours

### Week 3: Remaining High-Priority + Testing
- [ ] Issue #12: Fix session management (6-8 hrs)
- [ ] Issue #13: Fix version race condition (2-3 hrs)
- [ ] Test Suite #2: Concurrency tests (8-12 hrs)
- [ ] Test Suite #3: Error tests (8-10 hrs)

**Total Week 3:** 24-33 hours

### Week 4: Code Quality + Final Testing
- [ ] Test Suite #4: Integrity tests (4-6 hrs)
- [ ] Improvement #1: Standardize params (2-3 hrs)
- [ ] Improvement #2: Add async variant (4-6 hrs)
- [ ] Improvement #3: Add field filtering (2-3 hrs)
- [ ] Integration testing with real documents (8 hrs)
- [ ] Performance testing (4 hrs)

**Total Week 4:** 24-30 hours

---

## ✅ Acceptance Criteria

### Before Production Deployment

**Code Quality:**
- [ ] All 7 critical issues fixed
- [ ] All 13 high-priority issues fixed
- [ ] No print() statements (all use logging)
- [ ] All functions have type hints
- [ ] No circular imports

**Testing:**
- [ ] Test coverage >85% for new code
- [ ] All 45+ tests passing
- [ ] Load tested with 1000+ documents
- [ ] Concurrent processing tested (50+ simultaneous)
- [ ] No memory leaks detected

**API:**
- [ ] All endpoints documented in OpenAPI
- [ ] Response models match actual responses
- [ ] Error codes consistent and documented
- [ ] Authentication working on all endpoints

**Database:**
- [ ] No session leaks
- [ ] Transaction rollback working
- [ ] Migration from old schema tested
- [ ] Referential integrity verified

**Monitoring:**
- [ ] Logging configured for production
- [ ] Error tracking integrated (Sentry/Rollbar)
- [ ] Performance metrics available
- [ ] Profile usage statistics accurate

---

## 🚀 Deployment Checklist

- [ ] All acceptance criteria met
- [ ] Code reviewed by team
- [ ] Security review completed
- [ ] Database migration script prepared
- [ ] Rollback plan documented
- [ ] Monitoring dashboards created
- [ ] Documentation updated
- [ ] API changelog published
- [ ] Load testing passed (500 req/min)
- [ ] Disaster recovery tested

---

## 📈 Success Metrics

**After 1 Week in Production:**
- [ ] Zero critical bugs reported
- [ ] API error rate <1%
- [ ] Profile extraction success rate >95%
- [ ] Average processing time <10s per document
- [ ] No session leak incidents

**After 1 Month in Production:**
- [ ] Profile usage by >50% of documents
- [ ] User satisfaction score >8/10
- [ ] Test coverage maintained >85%
- [ ] No data loss incidents
- [ ] Performance SLA met 99.9% of time

---

## 📚 Related Documentation

- [Phase 7 Summary](TASK-002-PHASE-7-SUMMARY.md)
- [Code Quality Review](../review-reports/phase7-code-quality.md)
- [Integration Testing Review](../review-reports/phase7-testing.md)
- [API Design Review](../review-reports/phase7-api-design.md)
- [Error Handling Review](../ERROR-HANDLING-REVIEW.md)

---

**Last Updated:** 2026-01-29
**Next Review:** After Week 1 completion
**Owner:** Development Team
**Reviewers:** Code review team, QA team
