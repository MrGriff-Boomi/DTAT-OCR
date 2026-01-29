"""
Database models for document storage.
Stores extracted content as base64 in SQL.
"""

import base64
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, Enum as SQLEnum, LargeBinary, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
import sqlalchemy as sa

from config import config

Base = declarative_base()


# ==================== Mixins (TASK-002 Code Quality) ====================

class Base64JSONMixin:
    """
    Mixin for models that store JSON as base64-encoded text.

    Eliminates code duplication across ExtractionProfileRecord,
    ProfileVersionRecord, and DocumentRecord.
    """

    def set_json_field(self, field_name: str, data: dict):
        """
        Store dictionary as base64-encoded JSON in specified field.

        Args:
            field_name: Column name to store data
            data: Dictionary to store
        """
        json_str = json.dumps(data, default=str, ensure_ascii=False)
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        setattr(self, field_name, encoded)

    def get_json_field(self, field_name: str) -> dict:
        """
        Retrieve dictionary from base64-encoded JSON field.

        Args:
            field_name: Column name to retrieve data from

        Returns:
            Dictionary or empty dict if field is empty
        """
        value = getattr(self, field_name, None)
        if not value:
            return {}

        try:
            json_str = base64.b64decode(value).decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            print(f"Error decoding {field_name}: {e}")
            return {}


# ==================== Custom Exceptions (TASK-002 Code Quality) ====================

class ProfileNotFoundError(Exception):
    """Profile not found in database."""
    def __init__(self, profile_id: int):
        self.profile_id = profile_id
        super().__init__(f"Profile {profile_id} not found")


class ConcurrentModificationError(Exception):
    """Profile was modified by another user (optimistic locking violation)."""
    def __init__(self, expected_version: int, current_version: int):
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Profile was modified by another user. "
            f"Expected version {expected_version}, current version {current_version}. "
            f"Please refresh and try again."
        )


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"  # In DLQ


class ExtractionMethod(Enum):
    NATIVE = "native"           # PyMuPDF, pandas, python-docx
    LOCAL_OCR = "local_ocr"     # LightOnOCR
    TEXTRACT = "textract"       # AWS Textract
    MANUAL = "manual"           # Human review


class DocumentRecord(Base, Base64JSONMixin):
    """Main document record - stores processing results."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source info
    source_filename = Column(String(500), nullable=False)
    source_path = Column(String(1000))
    file_type = Column(String(50))  # pdf, xlsx, docx, jpg, etc.
    file_size_bytes = Column(Integer)

    # Original file (base64 encoded)
    original_file_b64 = Column(Text)  # Base64 of original document

    # Extracted content (base64 encoded JSON)
    extracted_content_b64 = Column(Text)  # Base64 of extracted text/tables JSON

    # Processing metadata
    status = Column(String(50), default=ProcessingStatus.PENDING.value)
    extraction_method = Column(String(50))  # Which method succeeded
    extraction_levels_tried = Column(String(200))  # JSON list of methods tried
    confidence_score = Column(Float)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_time_ms = Column(Integer)

    # Error tracking
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Document metadata (extracted)
    page_count = Column(Integer)
    char_count = Column(Integer)
    table_count = Column(Integer)
    detected_language = Column(String(10))

    # Profile-based extraction (TASK-002)
    profile_id = Column(Integer, ForeignKey('extraction_profiles.id'), nullable=True, index=True)
    extracted_fields_json = Column(Text)  # Base64-encoded JSON of extracted fields

    # Table constraints and indexes (TASK-002 Database Improvements)
    __table_args__ = (
        # Composite indexes for query performance
        Index('idx_documents_status_created_desc', 'status', sa.desc('created_at')),
        Index('idx_documents_profile_status', 'profile_id', 'status'),

        # CHECK constraints for data validation
        CheckConstraint(
            'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)',
            name='chk_doc_confidence_range'
        ),
        CheckConstraint('retry_count >= 0', name='chk_doc_retry_count_positive'),
        CheckConstraint('page_count IS NULL OR page_count >= 0', name='chk_doc_page_count_positive'),
    )

    def set_original_file(self, file_bytes: bytes):
        """Store original file as base64."""
        self.original_file_b64 = base64.b64encode(file_bytes).decode('utf-8')
        self.file_size_bytes = len(file_bytes)

    def get_original_file(self) -> bytes:
        """Retrieve original file from base64."""
        if self.original_file_b64:
            return base64.b64decode(self.original_file_b64)
        return b""

    def set_extracted_content(self, content: dict):
        """Store extracted content as base64-encoded JSON."""
        json_str = json.dumps(content, default=str, ensure_ascii=False)
        self.extracted_content_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def get_extracted_content(self) -> dict:
        """Retrieve extracted content from base64-encoded JSON."""
        if self.extracted_content_b64:
            json_str = base64.b64decode(self.extracted_content_b64).decode('utf-8')
            return json.loads(json_str)
        return {}

    def set_normalized_content(self, normalized_result):
        """
        Store normalized extraction result.

        Args:
            normalized_result: NormalizedResult object (from extraction_pipeline)
        """
        # Convert to dict and store as base64-encoded JSON
        content_dict = normalized_result.to_dict()
        json_str = json.dumps(content_dict, default=str, ensure_ascii=False)
        self.extracted_content_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def get_normalized_content(self):
        """
        Retrieve normalized extraction result.

        Returns:
            NormalizedResult object or None if not available
        """
        if not self.extracted_content_b64:
            return None

        try:
            # Import here to avoid circular dependency
            from extraction_pipeline import NormalizedResult

            json_str = base64.b64decode(self.extracted_content_b64).decode('utf-8')
            content_dict = json.loads(json_str)

            # Check if this is normalized format (has 'blocks' key)
            if 'blocks' in content_dict:
                return NormalizedResult.from_dict(content_dict)
            else:
                # Legacy format - return None (caller should handle conversion)
                return None

        except Exception as e:
            print(f"Error decoding normalized content: {e}")
            return None

    def set_extracted_fields(self, fields: dict):
        """
        Store extracted fields from profile-based extraction.

        Args:
            fields: Dictionary of extracted field results
        """
        self.set_json_field('extracted_fields_json', fields)

    def get_extracted_fields(self) -> dict:
        """
        Retrieve extracted fields from profile-based extraction.

        Returns:
            Dictionary of extracted fields or empty dict
        """
        return self.get_json_field('extracted_fields_json')

    @property
    def extracted_fields(self) -> dict:
        """Property for accessing extracted fields."""
        return self.get_extracted_fields()

    @extracted_fields.setter
    def extracted_fields(self, value: dict):
        """Property setter for extracted fields."""
        self.set_extracted_fields(value)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "source_filename": self.source_filename,
            "file_type": self.file_type,
            "status": self.status,
            "extraction_method": self.extraction_method,
            "confidence_score": self.confidence_score,
            "page_count": self.page_count,
            "char_count": self.char_count,
            "table_count": self.table_count,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class ProcessingLog(Base):
    """Detailed log of each processing attempt."""

    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)

    # Attempt info
    attempt_number = Column(Integer)
    extraction_method = Column(String(50))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)

    # Result
    success = Column(Boolean)
    confidence_score = Column(Float)
    error_message = Column(Text)

    # Debug info
    chars_extracted = Column(Integer)
    tables_extracted = Column(Integer)


class ExtractionProfileRecord(Base, Base64JSONMixin):
    """Extraction profile for structured field extraction (TASK-002)."""

    __tablename__ = "extraction_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic info
    name = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    document_type = Column(String(50), nullable=False, index=True)
    version = Column(Integer, default=1)

    # Profile definition (stored as JSON - works with both SQLite and PostgreSQL)
    # For PostgreSQL, this will automatically use JSONB for better performance
    schema_json = Column(Text, nullable=False)  # Base64-encoded JSON

    # Metadata
    created_by = Column(String(255))
    organization_id = Column(String(255), index=True)
    is_template = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Processing hints
    min_confidence = Column(Float, default=60.0)
    ocr_strategy = Column(String(20), default='auto')

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Table constraints and indexes (TASK-002 Database Improvements)
    __table_args__ = (
        # Composite indexes for query performance
        Index('idx_profiles_org_type_active', 'organization_id', 'document_type', 'is_active'),
        Index('idx_profiles_org_created_desc', 'organization_id', sa.desc('created_at')),
        Index('idx_profiles_type_created_desc', 'document_type', sa.desc('created_at')),

        # CHECK constraints for data validation
        CheckConstraint('min_confidence >= 0 AND min_confidence <= 100',
                       name='chk_profile_confidence_range'),
        CheckConstraint("ocr_strategy IN ('auto', 'native', 'ocr_only')",
                       name='chk_profile_ocr_strategy'),
        CheckConstraint('version > 0', name='chk_profile_version_positive'),
    )

    def set_schema(self, schema_dict: dict):
        """Store profile schema using mixin."""
        self.set_json_field('schema_json', schema_dict)

    def get_schema(self) -> dict:
        """Retrieve profile schema using mixin."""
        return self.get_json_field('schema_json')

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "document_type": self.document_type,
            "version": self.version,
            "created_by": self.created_by,
            "organization_id": self.organization_id,
            "is_template": self.is_template,
            "is_active": self.is_active,
            "min_confidence": self.min_confidence,
            "ocr_strategy": self.ocr_strategy,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "fields": self.get_schema().get("fields", [])
        }


class ProfileVersionRecord(Base, Base64JSONMixin):
    """Version history for profile changes (TASK-002)."""

    __tablename__ = "profile_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('extraction_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    # Snapshot of profile at this version
    schema_json = Column(Text, nullable=False)  # Base64-encoded JSON

    # Metadata
    created_by = Column(String(255))
    change_description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Table constraints and indexes (TASK-002 Database Improvements)
    __table_args__ = (
        # CRITICAL: Unique constraint on (profile_id, version)
        UniqueConstraint('profile_id', 'version', name='uq_profile_version'),

        # Index for efficient version queries
        Index('idx_versions_profile_desc', 'profile_id', sa.desc('version')),
    )

    def set_schema(self, schema_dict: dict):
        """Store version schema using mixin."""
        self.set_json_field('schema_json', schema_dict)

    def get_schema(self) -> dict:
        """Retrieve version schema using mixin."""
        return self.get_json_field('schema_json')


class ProfileUsageRecord(Base):
    """Track profile usage and performance (TASK-002)."""

    __tablename__ = "profile_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('extraction_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)

    # Extraction results
    fields_extracted = Column(Integer, default=0)
    fields_failed = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    processing_time_ms = Column(Integer, default=0)

    # Outcome
    status = Column(String(20), default='success')  # success, partial, failed
    error_message = Column(Text)

    executed_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Table constraints and indexes (TASK-002 Database Improvements)
    __table_args__ = (
        # Composite indexes for usage queries
        Index('idx_usage_profile_executed_desc', 'profile_id', sa.desc('executed_at')),
        Index('idx_usage_status_executed_desc', 'status', sa.desc('executed_at')),
        Index('idx_usage_document_profile', 'document_id', 'profile_id'),

        # CHECK constraints for data validation
        CheckConstraint('fields_extracted >= 0', name='chk_usage_fields_extracted_positive'),
        CheckConstraint('fields_failed >= 0', name='chk_usage_fields_failed_positive'),
        CheckConstraint('avg_confidence >= 0 AND avg_confidence <= 1',
                       name='chk_usage_avg_confidence_range'),
        CheckConstraint("status IN ('success', 'partial', 'failed')",
                       name='chk_usage_status'),
    )


# Database connection management
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.database_url,
            echo=False,  # Set True for SQL debugging
            pool_pre_ping=True
        )
    return _engine


def get_session():
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_database():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Database initialized: {config.database_url}")


def seed_templates():
    """
    Seed built-in templates into the database.

    This function inserts the built-in templates if they don't already exist.
    Safe to call multiple times - will skip existing templates.
    """
    from profile_templates import get_all_templates

    templates = get_all_templates()
    db = get_session()

    try:
        seeded = 0
        skipped = 0

        for template in templates:
            # Check if template already exists
            existing = db.query(ExtractionProfileRecord).filter_by(name=template.name).first()

            if existing:
                skipped += 1
                continue

            # Create new record
            record = ExtractionProfileRecord(
                name=template.name,
                display_name=template.display_name,
                description=template.description,
                document_type=template.document_type,
                organization_id=template.organization_id,
                is_template=True,
                is_active=True,
                version=1
            )
            record.set_schema(template.model_dump(exclude={'id', 'created_at', 'updated_at'}))

            db.add(record)
            seeded += 1

        db.commit()
        print(f"Template seeding complete: {seeded} seeded, {skipped} skipped")

    except Exception as e:
        db.rollback()
        print(f"Error seeding templates: {e}")
        raise
    finally:
        db.close()


def create_document_record(
    filename: str,
    file_bytes: bytes,
    file_type: str,
    source_path: Optional[str] = None
) -> DocumentRecord:
    """Create a new document record ready for processing."""
    record = DocumentRecord(
        source_filename=filename,
        source_path=source_path,
        file_type=file_type,
        status=ProcessingStatus.PENDING.value,
    )

    if config.store_original_file:
        record.set_original_file(file_bytes)
    else:
        record.file_size_bytes = len(file_bytes)

    return record


def save_document(record: DocumentRecord) -> int:
    """Save document record to database."""
    session = get_session()
    try:
        session.add(record)
        session.commit()
        doc_id = record.id
        return doc_id
    finally:
        session.close()


def update_document(record: DocumentRecord):
    """Update existing document record."""
    session = get_session()
    try:
        session.merge(record)
        session.commit()
    finally:
        session.close()


def get_document(doc_id: int) -> Optional[DocumentRecord]:
    """Retrieve document by ID."""
    session = get_session()
    try:
        return session.query(DocumentRecord).filter_by(id=doc_id).first()
    finally:
        session.close()


def get_pending_documents(limit: int = 100) -> list[DocumentRecord]:
    """Get documents waiting to be processed."""
    session = get_session()
    try:
        return session.query(DocumentRecord)\
            .filter_by(status=ProcessingStatus.PENDING.value)\
            .limit(limit)\
            .all()
    finally:
        session.close()


def get_failed_documents(limit: int = 100) -> list[DocumentRecord]:
    """Get documents that need review (DLQ)."""
    session = get_session()
    try:
        return session.query(DocumentRecord)\
            .filter(DocumentRecord.status.in_([
                ProcessingStatus.FAILED.value,
                ProcessingStatus.NEEDS_REVIEW.value
            ]))\
            .limit(limit)\
            .all()
    finally:
        session.close()


def log_processing_attempt(
    document_id: int,
    attempt_number: int,
    method: str,
    success: bool,
    duration_ms: int,
    confidence: float = 0,
    chars: int = 0,
    tables: int = 0,
    error: str = None
):
    """Log a processing attempt for debugging."""
    session = get_session()
    try:
        log = ProcessingLog(
            document_id=document_id,
            attempt_number=attempt_number,
            extraction_method=method,
            completed_at=datetime.utcnow(),
            duration_ms=duration_ms,
            success=success,
            confidence_score=confidence,
            chars_extracted=chars,
            tables_extracted=tables,
            error_message=error
        )
        session.add(log)
        session.commit()
    finally:
        session.close()


# ==================== Profile Management Functions (TASK-002) ====================

def create_profile(profile_dict: dict) -> ExtractionProfileRecord:
    """
    Create a new extraction profile.

    Args:
        profile_dict: Dictionary with profile data (from ExtractionProfile pydantic model)

    Returns:
        Created profile record
    """
    session = get_session()
    try:
        record = ExtractionProfileRecord(
            name=profile_dict['name'],
            display_name=profile_dict['display_name'],
            description=profile_dict.get('description'),
            document_type=profile_dict['document_type'],
            version=profile_dict.get('version', 1),
            created_by=profile_dict.get('created_by'),
            organization_id=profile_dict.get('organization_id'),
            is_template=profile_dict.get('is_template', False),
            is_active=profile_dict.get('is_active', True),
            min_confidence=profile_dict.get('min_confidence', 60.0),
            ocr_strategy=profile_dict.get('ocr_strategy', 'auto')
        )

        # Store the full profile schema
        record.set_schema(profile_dict)

        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    finally:
        session.close()


def get_profile_by_id(profile_id: int) -> Optional[ExtractionProfileRecord]:
    """Get profile by ID."""
    session = get_session()
    try:
        return session.query(ExtractionProfileRecord).filter_by(id=profile_id).first()
    finally:
        session.close()


def get_profile_by_name(name: str) -> Optional[ExtractionProfileRecord]:
    """Get profile by unique name."""
    session = get_session()
    try:
        return session.query(ExtractionProfileRecord).filter_by(name=name).first()
    finally:
        session.close()


def list_profiles(
    document_type: Optional[str] = None,
    organization_id: Optional[str] = None,
    is_template: Optional[bool] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
) -> list[ExtractionProfileRecord]:
    """
    List profiles with optional filtering.

    Args:
        document_type: Filter by document type
        organization_id: Filter by organization
        is_template: Filter by template status
        active_only: Only return active profiles
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of profile records
    """
    session = get_session()
    try:
        query = session.query(ExtractionProfileRecord)

        if document_type:
            query = query.filter_by(document_type=document_type)
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        if is_template is not None:
            query = query.filter_by(is_template=is_template)
        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(ExtractionProfileRecord.created_at.desc())\
                   .limit(limit)\
                   .offset(offset)\
                   .all()
    finally:
        session.close()


def update_profile(
    profile_id: int,
    profile_dict: dict,
    expected_version: Optional[int] = None
) -> ExtractionProfileRecord:
    """
    Update existing profile with optimistic locking.

    Args:
        profile_id: Profile ID
        profile_dict: Updated profile data
        expected_version: Expected version number (for conflict detection)

    Returns:
        Updated profile record

    Raises:
        ProfileNotFoundError: Profile not found
        ConcurrentModificationError: Profile was modified since read
    """
    session = get_session()
    try:
        # Lock row for update
        record = session.query(ExtractionProfileRecord)\
            .filter_by(id=profile_id)\
            .with_for_update()\
            .first()

        if not record:
            raise ProfileNotFoundError(profile_id)

        # Check version if provided (optimistic locking)
        if expected_version is not None and record.version != expected_version:
            raise ConcurrentModificationError(expected_version, record.version)

        # Increment version
        new_version = record.version + 1

        # Update fields
        record.name = profile_dict.get('name', record.name)
        record.display_name = profile_dict.get('display_name', record.display_name)
        record.description = profile_dict.get('description', record.description)
        record.document_type = profile_dict.get('document_type', record.document_type)
        record.version = new_version
        record.created_by = profile_dict.get('created_by', record.created_by)
        record.organization_id = profile_dict.get('organization_id', record.organization_id)
        record.is_template = profile_dict.get('is_template', record.is_template)
        record.is_active = profile_dict.get('is_active', record.is_active)
        record.min_confidence = profile_dict.get('min_confidence', record.min_confidence)
        record.ocr_strategy = profile_dict.get('ocr_strategy', record.ocr_strategy)
        record.updated_at = datetime.utcnow()

        # Update schema
        record.set_schema(profile_dict)

        session.commit()
        session.refresh(record)
        return record

    except (ProfileNotFoundError, ConcurrentModificationError):
        session.rollback()
        raise
    finally:
        session.close()


def delete_profile(profile_id: int, hard_delete: bool = False):
    """
    Delete or deactivate a profile.

    Args:
        profile_id: Profile ID
        hard_delete: If True, permanently delete. If False, just deactivate.
    """
    session = get_session()
    try:
        record = session.query(ExtractionProfileRecord).filter_by(id=profile_id).first()
        if not record:
            raise ValueError(f"Profile {profile_id} not found")

        if hard_delete:
            session.delete(record)
        else:
            record.is_active = False
            record.updated_at = datetime.utcnow()

        session.commit()
    finally:
        session.close()


def create_profile_version(
    profile_id: int,
    version: int,
    schema_dict: dict,
    created_by: Optional[str] = None,
    change_description: Optional[str] = None
) -> ProfileVersionRecord:
    """
    Create a version snapshot of a profile.

    Args:
        profile_id: Profile ID
        version: Version number
        schema_dict: Profile schema at this version
        created_by: User who created this version
        change_description: What changed

    Returns:
        Created version record
    """
    session = get_session()
    try:
        record = ProfileVersionRecord(
            profile_id=profile_id,
            version=version,
            created_by=created_by,
            change_description=change_description
        )
        record.set_schema(schema_dict)

        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    finally:
        session.close()


def get_profile_versions(profile_id: int) -> list[ProfileVersionRecord]:
    """Get all versions for a profile."""
    session = get_session()
    try:
        return session.query(ProfileVersionRecord)\
                     .filter_by(profile_id=profile_id)\
                     .order_by(ProfileVersionRecord.version.desc())\
                     .all()
    finally:
        session.close()


def get_profile_version(profile_id: int, version: int) -> Optional[ProfileVersionRecord]:
    """Get specific version of a profile."""
    session = get_session()
    try:
        return session.query(ProfileVersionRecord)\
                     .filter_by(profile_id=profile_id, version=version)\
                     .first()
    finally:
        session.close()


def log_profile_usage(
    profile_id: int,
    document_id: int,
    fields_extracted: int,
    fields_failed: int,
    avg_confidence: float,
    processing_time_ms: int,
    status: str = 'success',
    error_message: Optional[str] = None
) -> ProfileUsageRecord:
    """
    Log profile usage statistics.

    Args:
        profile_id: Profile ID
        document_id: Document ID
        fields_extracted: Number of successfully extracted fields
        fields_failed: Number of failed fields
        avg_confidence: Average confidence score
        processing_time_ms: Processing time
        status: success, partial, or failed
        error_message: Error details if failed

    Returns:
        Created usage record
    """
    session = get_session()
    try:
        record = ProfileUsageRecord(
            profile_id=profile_id,
            document_id=document_id,
            fields_extracted=fields_extracted,
            fields_failed=fields_failed,
            avg_confidence=avg_confidence,
            processing_time_ms=processing_time_ms,
            status=status,
            error_message=error_message
        )

        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    finally:
        session.close()


def get_profile_usage_stats(profile_id: int, days: int = 30) -> dict:
    """
    Get usage statistics for a profile.

    Args:
        profile_id: Profile ID
        days: Number of days to look back

    Returns:
        Dictionary with statistics
    """
    session = get_session()
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        records = session.query(ProfileUsageRecord)\
                        .filter(
                            ProfileUsageRecord.profile_id == profile_id,
                            ProfileUsageRecord.executed_at >= cutoff_date
                        )\
                        .all()

        if not records:
            return {
                "total_documents": 0,
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_processing_time_ms": 0,
                "total_fields_extracted": 0,
                "total_fields_failed": 0
            }

        total_docs = len(records)
        successful = sum(1 for r in records if r.status == 'success')

        return {
            "total_documents": total_docs,
            "success_rate": (successful / total_docs * 100) if total_docs > 0 else 0.0,
            "avg_confidence": sum(r.avg_confidence for r in records) / total_docs,
            "avg_processing_time_ms": int(sum(r.processing_time_ms for r in records) / total_docs),
            "total_fields_extracted": sum(r.fields_extracted for r in records),
            "total_fields_failed": sum(r.fields_failed for r in records)
        }
    finally:
        session.close()
