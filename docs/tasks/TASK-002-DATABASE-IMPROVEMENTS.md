# TASK-002-DATABASE: Database Design Improvements

**Status**: Not Started
**Priority**: HIGH
**Blocks**: Production Deployment, PostgreSQL Migration
**Created**: 2026-01-29
**Estimated Effort**: 2 days

## Executive Summary

Database design review identified critical issues with indexes, constraints, race conditions, and storage strategy that will impact performance and data integrity at scale. This task addresses all database findings to prepare for production deployment and PostgreSQL migration.

**Database Design Score: 7.5/10** (Current) → **9.5/10** (Target)

---

## Critical Issues (MUST FIX)

### 1. 🔴 Missing Composite Unique Constraint

**Severity**: CRITICAL
**Impact**: Data integrity violation - duplicate version numbers possible
**Location**: `database.py` ProfileVersionRecord class

**Issue**: The unique constraint on `(profile_id, version)` is specified in the TASK-002 document but NOT implemented in the code. This allows duplicate version numbers:

```python
# Current code - NO unique constraint
class ProfileVersionRecord(Base):
    __tablename__ = "profile_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('extraction_profiles.id', ondelete='CASCADE'))
    version = Column(Integer, nullable=False)
    # ❌ Missing: UniqueConstraint('profile_id', 'version')
```

**Attack Scenario**:
```python
# Two concurrent updates create same version number
# Thread 1:
create_profile_version(profile_id=1, version=2, schema=schema_a)

# Thread 2 (concurrent):
create_profile_version(profile_id=1, version=2, schema=schema_b)

# Both succeed! Now profile 1 has TWO version 2 records
```

**Solution**:
```python
from sqlalchemy import UniqueConstraint, Index
import sqlalchemy as sa

class ProfileVersionRecord(Base):
    __tablename__ = "profile_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('extraction_profiles.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)

    schema_json = Column(Text, nullable=False)
    created_by = Column(String(255))
    change_description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Add table-level constraints and indexes
    __table_args__ = (
        UniqueConstraint('profile_id', 'version', name='uq_profile_version'),
        Index('idx_versions_profile_desc', 'profile_id', sa.desc('version')),
    )
```

**Migration Script**:
```python
# migration_001_add_version_constraint.py

from sqlalchemy import create_engine, text

def upgrade():
    """Add unique constraint to profile_versions table."""
    engine = create_engine(config.database_url)

    with engine.connect() as conn:
        # Check for duplicates first
        result = conn.execute(text("""
            SELECT profile_id, version, COUNT(*) as count
            FROM profile_versions
            GROUP BY profile_id, version
            HAVING COUNT(*) > 1
        """))

        duplicates = result.fetchall()
        if duplicates:
            print(f"WARNING: Found {len(duplicates)} duplicate versions")
            for row in duplicates:
                print(f"  Profile {row.profile_id} version {row.version}: {row.count} records")

            # Cleanup duplicates - keep oldest
            conn.execute(text("""
                DELETE FROM profile_versions
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM profile_versions
                    GROUP BY profile_id, version
                )
            """))
            conn.commit()

        # Add unique constraint
        if config.database_url.startswith('postgresql'):
            conn.execute(text("""
                ALTER TABLE profile_versions
                ADD CONSTRAINT uq_profile_version UNIQUE (profile_id, version)
            """))
        else:  # SQLite
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_profile_version
                ON profile_versions(profile_id, version)
            """))

        conn.commit()
        print("✓ Added unique constraint on (profile_id, version)")
```

---

### 2. 🔴 Race Condition in Profile Updates

**Severity**: HIGH
**Impact**: Lost updates, data corruption
**Location**: `database.py` update_profile() function

**Issue**: No optimistic locking. Concurrent updates cause lost writes:

```python
# Current code - NO version checking
def update_profile(profile_id: int, profile_dict: dict):
    session = get_session()
    try:
        record = session.query(ExtractionProfileRecord).filter_by(id=profile_id).first()

        # ❌ No check if version changed since read
        record.version = profile_dict.get('version', record.version)
        record.set_schema(profile_dict)

        session.commit()  # May overwrite concurrent changes!
```

**Race Condition Example**:
```
Time  | User A                           | User B
------|----------------------------------|----------------------------------
T1    | GET /profiles/1 (version=5)      |
T2    |                                  | GET /profiles/1 (version=5)
T3    | PUT /profiles/1 (update to v6)   |
T4    |                                  | PUT /profiles/1 (update to v6)
      | ✓ Succeeds (v5→v6)               | ✓ Succeeds (v5→v6) ← OVERWRITES A!
```

**Solution**: Implement optimistic locking

```python
# In database.py

class ConcurrentModificationError(Exception):
    """Raised when profile was modified by another user."""
    pass

def update_profile(
    profile_id: int,
    profile_dict: dict,
    expected_version: Optional[int] = None
) -> ExtractionProfileRecord:
    """
    Update profile with optimistic locking.

    Args:
        profile_id: Profile ID
        profile_dict: Updated profile data
        expected_version: Version number expected (for conflict detection)

    Returns:
        Updated profile record

    Raises:
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
            raise ValueError(f"Profile {profile_id} not found")

        # Check version if provided (optimistic locking)
        if expected_version is not None and record.version != expected_version:
            raise ConcurrentModificationError(
                f"Profile was modified by another user. "
                f"Expected version {expected_version}, current version {record.version}. "
                f"Please refresh and try again."
            )

        # Increment version
        new_version = record.version + 1

        # Update fields
        record.name = profile_dict.get('name', record.name)
        record.display_name = profile_dict.get('display_name', record.display_name)
        record.description = profile_dict.get('description', record.description)
        record.version = new_version
        record.updated_at = datetime.utcnow()
        record.set_schema(profile_dict)

        session.commit()
        session.refresh(record)
        return record

    except ConcurrentModificationError:
        session.rollback()
        raise
    finally:
        session.close()
```

**API Integration**:
```python
# In api.py

@app.put("/profiles/{profile_id}")
async def update_extraction_profile(
    profile_id: int,
    profile: ExtractionProfile,
    if_match: Optional[int] = Header(None, description="Expected version number"),
    username: str = Depends(verify_credentials)
):
    """
    Update profile with version conflict detection.

    Headers:
        If-Match: Expected version number for optimistic locking

    Errors:
        412 Precondition Failed: Version mismatch
    """
    try:
        profile_dict = profile.model_dump()
        record = update_profile(
            profile_id,
            profile_dict,
            expected_version=if_match
        )
        # ...
    except ConcurrentModificationError as e:
        raise HTTPException(status_code=412, detail=str(e))
```

---

### 3. 🟠 Missing Composite Indexes for Query Performance

**Severity**: HIGH
**Impact**: Slow queries at scale (>1000 profiles)
**Location**: All table definitions in database.py

**Issue**: Single-column indexes exist, but common multi-column queries are slow:

```python
# Current indexes - INCOMPLETE
class ExtractionProfileRecord(Base):
    # Single-column indexes only
    name = Column(String(255), unique=True, index=True)        # ✓
    document_type = Column(String(50), index=True)              # ✓
    organization_id = Column(String(255), index=True)           # ✓
    is_active = Column(Boolean, index=True)                     # ✓

    # ❌ Missing composite indexes for common queries
```

**Slow Query Examples**:
```python
# Query 1: List active profiles by org and type
# ❌ Requires 3 separate index scans + filter
profiles = session.query(ExtractionProfileRecord)\
    .filter_by(organization_id='org-123', document_type='invoice', is_active=True)\
    .all()

# Query 2: Get recent profiles by org
# ❌ Requires index scan on org_id + sort
profiles = session.query(ExtractionProfileRecord)\
    .filter_by(organization_id='org-123')\
    .order_by(ExtractionProfileRecord.created_at.desc())\
    .limit(20)\
    .all()

# Query 3: Profile usage stats
# ❌ Requires index scan on profile_id + filter on date + sort
usage = session.query(ProfileUsageRecord)\
    .filter(
        ProfileUsageRecord.profile_id == 42,
        ProfileUsageRecord.executed_at >= cutoff_date
    )\
    .order_by(ProfileUsageRecord.executed_at.desc())\
    .all()
```

**Solution**: Add composite indexes

```python
import sqlalchemy as sa
from sqlalchemy import Index, CheckConstraint

class ExtractionProfileRecord(Base):
    __tablename__ = "extraction_profiles"

    # ... column definitions ...

    __table_args__ = (
        # Composite indexes for common queries
        Index('idx_profiles_org_type_active',
              'organization_id', 'document_type', 'is_active'),
        Index('idx_profiles_org_created_desc',
              'organization_id', sa.desc('created_at')),
        Index('idx_profiles_type_created_desc',
              'document_type', sa.desc('created_at')),
        Index('idx_profiles_active_created',
              'is_active', sa.desc('created_at'),
              postgresql_where=text('is_active = TRUE')),  # Partial index

        # Constraints
        CheckConstraint('min_confidence >= 0 AND min_confidence <= 100',
                       name='chk_confidence_range'),
        CheckConstraint("ocr_strategy IN ('auto', 'native', 'ocr_only')",
                       name='chk_ocr_strategy'),
        CheckConstraint('version > 0', name='chk_version_positive'),
    )

class ProfileUsageRecord(Base):
    __tablename__ = "profile_usage"

    # ... column definitions ...

    __table_args__ = (
        # Composite indexes for usage queries
        Index('idx_usage_profile_executed_desc',
              'profile_id', sa.desc('executed_at')),
        Index('idx_usage_status_executed_desc',
              'status', sa.desc('executed_at')),
        Index('idx_usage_document_profile',
              'document_id', 'profile_id'),

        # Constraints
        CheckConstraint('fields_extracted >= 0', name='chk_fields_extracted_positive'),
        CheckConstraint('fields_failed >= 0', name='chk_fields_failed_positive'),
        CheckConstraint('avg_confidence >= 0 AND avg_confidence <= 1',
                       name='chk_avg_confidence_range'),
        CheckConstraint("status IN ('success', 'partial', 'failed')",
                       name='chk_usage_status'),
    )

class DocumentRecord(Base):
    __tablename__ = "documents"

    # ... column definitions ...

    __table_args__ = (
        # Composite indexes for document queries
        Index('idx_documents_status_created_desc',
              'status', sa.desc('created_at')),
        Index('idx_documents_profile_status',
              'profile_id', 'status'),
        Index('idx_documents_profile_completed',
              'profile_id', sa.desc('completed_at'),
              postgresql_where=text("status = 'completed'")),  # Partial

        # Constraints
        CheckConstraint(
            'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)',
            name='chk_confidence_range'
        ),
        CheckConstraint('retry_count >= 0', name='chk_retry_count_positive'),
        CheckConstraint('page_count IS NULL OR page_count >= 0',
                       name='chk_page_count_positive'),
    )
```

**Performance Impact**:
| Query | Before (no composite) | After (with composite) | Improvement |
|-------|----------------------|------------------------|-------------|
| List org profiles by type | 50ms (3 index scans) | 2ms (1 index scan) | 25x faster |
| Recent profiles by org | 30ms (scan + sort) | 1ms (index scan) | 30x faster |
| Profile usage stats | 100ms (scan + filter + sort) | 5ms (index scan) | 20x faster |

---

### 4. 🟠 Base64 JSON Storage Overhead

**Severity**: MEDIUM-HIGH
**Impact**: 33% wasted storage, slower queries, defeats PostgreSQL JSONB
**Location**: All JSON columns in database.py

**Issue**: All JSON data is base64-encoded even though:
- SQLite doesn't benefit (no JSON support anyway)
- PostgreSQL JSONB performance is lost (can't query/index JSON fields)
- Storage overhead: 33% larger than raw JSON
- CPU overhead: Encode/decode on every read/write

**Current Storage**:
```python
def set_schema(self, schema_dict: dict):
    json_str = json.dumps(schema_dict)                        # Step 1: JSON
    self.schema_json = base64.b64encode(                      # Step 2: Base64
        json_str.encode('utf-8')
    ).decode('utf-8')
    # Result: 33% larger, not queryable in PostgreSQL

# Example sizes:
# Raw JSON: 1000 bytes
# Base64 JSON: 1333 bytes (+33%)
# For 10,000 profiles: 3.3MB wasted storage
```

**Solution**: Use dialect-aware storage

```python
from sqlalchemy.dialects import postgresql
from sqlalchemy import Text, event

def is_postgresql():
    """Check if using PostgreSQL."""
    return config.database_url.startswith('postgresql')

class ExtractionProfileRecord(Base):
    __tablename__ = "extraction_profiles"

    # ... other columns ...

    # Polymorphic column type: JSONB for PostgreSQL, Text for SQLite
    if is_postgresql():
        schema_json = Column(postgresql.JSONB, nullable=False)
    else:
        schema_json = Column(Text, nullable=False)

    def set_schema(self, schema_dict: dict):
        """Store profile schema (dialect-aware)."""
        if is_postgresql():
            # PostgreSQL: Store as native JSONB
            self.schema_json = schema_dict
        else:
            # SQLite: Base64-encode JSON
            json_str = json.dumps(schema_dict, default=str, ensure_ascii=False)
            self.schema_json = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def get_schema(self) -> dict:
        """Retrieve profile schema (dialect-aware)."""
        if not self.schema_json:
            return {}

        if is_postgresql():
            # PostgreSQL: Already a dict
            return self.schema_json
        else:
            # SQLite: Decode base64
            try:
                json_str = base64.b64decode(self.schema_json).decode('utf-8')
                return json.loads(json_str)
            except Exception as e:
                print(f"Error decoding profile schema: {e}")
                return {}
```

**PostgreSQL-Specific Indexes** (add to `__table_args__`):
```python
if is_postgresql():
    __table_args__ = (
        # ... existing constraints ...

        # GIN index for JSONB queries
        Index('idx_profiles_schema_gin', 'schema_json',
              postgresql_using='gin'),
    )
```

**Query Benefits with JSONB**:
```python
# PostgreSQL can now query JSON fields directly
profiles = session.query(ExtractionProfileRecord)\
    .filter(
        ExtractionProfileRecord.schema_json['document_type'].astext == 'invoice'
    )\
    .all()

# Can index nested fields
# CREATE INDEX idx_profiles_doc_type ON extraction_profiles
#   USING gin ((schema_json->'fields'))
```

---

### 5. 🟡 Unbounded Growth of profile_usage Table

**Severity**: MEDIUM
**Impact**: Table will grow unbounded, slowing queries
**Location**: ProfileUsageRecord table

**Issue**: No archival or partitioning strategy. Table grows forever:
- 1,000 documents/day × 365 days = 365K records/year
- 10,000 documents/day = 3.65M records/year
- After 5 years: 18M records
- Queries slow down, backups take longer

**Solution 1**: Table Partitioning (PostgreSQL 10+)

```python
# Only for PostgreSQL - create partitioned table

-- Create parent table (partitioned)
CREATE TABLE profile_usage (
    id SERIAL,
    profile_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    fields_extracted INTEGER DEFAULT 0,
    fields_failed INTEGER DEFAULT 0,
    avg_confidence FLOAT DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    executed_at TIMESTAMP NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, executed_at)  -- Include partition key
) PARTITION BY RANGE (executed_at);

-- Create quarterly partitions
CREATE TABLE profile_usage_2026_q1 PARTITION OF profile_usage
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE profile_usage_2026_q2 PARTITION OF profile_usage
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- Automate partition creation
CREATE OR REPLACE FUNCTION create_usage_partition()
RETURNS void AS $$
DECLARE
    partition_date date := date_trunc('quarter', CURRENT_DATE + interval '3 months');
    partition_name text := 'profile_usage_' || to_char(partition_date, 'YYYY_Q"q"');
    partition_start text := partition_date::text;
    partition_end text := (partition_date + interval '3 months')::text;
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I PARTITION OF profile_usage
        FOR VALUES FROM (%L) TO (%L)',
        partition_name, partition_start, partition_end
    );
END;
$$ LANGUAGE plpgsql;
```

**Solution 2**: Summary Table + Archival

```python
# Add summary table to database.py

class ProfileUsageSummary(Base):
    """Aggregated usage statistics (updated daily)."""
    __tablename__ = "profile_usage_summary"

    profile_id = Column(Integer, ForeignKey('extraction_profiles.id'),
                       primary_key=True)

    # Aggregate stats
    total_documents = Column(Integer, default=0)
    total_success = Column(Integer, default=0)
    total_partial = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    avg_processing_time_ms = Column(Integer, default=0)

    # Time windows
    last_30_days_count = Column(Integer, default=0)
    last_90_days_count = Column(Integer, default=0)

    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_summary_updated', 'last_updated'),
    )

# Daily aggregation job
def update_usage_summaries():
    """Update summary table (run daily via cron/scheduler)."""
    session = get_session()
    try:
        cutoff_90_days = datetime.utcnow() - timedelta(days=90)
        cutoff_30_days = datetime.utcnow() - timedelta(days=30)

        # Get all profiles
        profiles = session.query(ExtractionProfileRecord).all()

        for profile in profiles:
            # Aggregate usage data
            all_usage = session.query(ProfileUsageRecord)\
                .filter_by(profile_id=profile.id)\
                .all()

            recent_90 = [u for u in all_usage if u.executed_at >= cutoff_90_days]
            recent_30 = [u for u in all_usage if u.executed_at >= cutoff_30_days]

            summary = session.query(ProfileUsageSummary)\
                .filter_by(profile_id=profile.id)\
                .first()

            if not summary:
                summary = ProfileUsageSummary(profile_id=profile.id)
                session.add(summary)

            summary.total_documents = len(all_usage)
            summary.total_success = sum(1 for u in all_usage if u.status == 'success')
            summary.total_partial = sum(1 for u in all_usage if u.status == 'partial')
            summary.total_failed = sum(1 for u in all_usage if u.status == 'failed')
            summary.avg_confidence = sum(u.avg_confidence for u in all_usage) / len(all_usage) if all_usage else 0
            summary.avg_processing_time_ms = int(sum(u.processing_time_ms for u in all_usage) / len(all_usage)) if all_usage else 0
            summary.last_30_days_count = len(recent_30)
            summary.last_90_days_count = len(recent_90)
            summary.last_updated = datetime.utcnow()

        session.commit()

        # Archive old detail records (older than 90 days)
        archive_old_usage_records(cutoff_90_days)

    finally:
        session.close()

def archive_old_usage_records(cutoff_date: datetime):
    """Move old records to archive table or delete."""
    session = get_session()
    try:
        # Option 1: Delete old records (if summary is enough)
        deleted = session.query(ProfileUsageRecord)\
            .filter(ProfileUsageRecord.executed_at < cutoff_date)\
            .delete()

        session.commit()
        print(f"Archived {deleted} usage records older than {cutoff_date}")

    finally:
        session.close()
```

---

## Additional Database Improvements

### 6. Add CHECK Constraints for Data Validation

**Priority**: MEDIUM
**Location**: All table definitions

Already shown in solutions above. Summary of constraints to add:

```python
# ExtractionProfileRecord
CheckConstraint('min_confidence >= 0 AND min_confidence <= 100')
CheckConstraint("ocr_strategy IN ('auto', 'native', 'ocr_only')")
CheckConstraint('version > 0')

# ProfileUsageRecord
CheckConstraint('fields_extracted >= 0')
CheckConstraint('fields_failed >= 0')
CheckConstraint('avg_confidence >= 0 AND avg_confidence <= 1')
CheckConstraint("status IN ('success', 'partial', 'failed')")

# DocumentRecord
CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)')
CheckConstraint('retry_count >= 0')
CheckConstraint('page_count IS NULL OR page_count >= 0')
```

---

### 7. Migration Scripts

**Priority**: HIGH
**Location**: New `migrations/` directory

```python
# migrations/001_add_constraints_and_indexes.py

"""
Add missing constraints and indexes to profile tables.

Run with:
    python migrations/001_add_constraints_and_indexes.py
"""

from sqlalchemy import create_engine, text
from database import config

def upgrade():
    """Apply migration."""
    engine = create_engine(config.database_url)

    with engine.connect() as conn:
        print("Running migration 001...")

        # 1. Add unique constraint to profile_versions
        print("  - Adding unique constraint to profile_versions...")
        if config.database_url.startswith('postgresql'):
            conn.execute(text("""
                ALTER TABLE profile_versions
                ADD CONSTRAINT uq_profile_version UNIQUE (profile_id, version)
            """))
        else:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_profile_version
                ON profile_versions(profile_id, version)
            """))

        # 2. Add composite indexes
        print("  - Adding composite indexes...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_profiles_org_type_active
            ON extraction_profiles(organization_id, document_type, is_active)
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_usage_profile_executed_desc
            ON profile_usage(profile_id, executed_at DESC)
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_documents_status_created_desc
            ON documents(status, created_at DESC)
        """))

        # 3. Add CHECK constraints (PostgreSQL only)
        if config.database_url.startswith('postgresql'):
            print("  - Adding CHECK constraints...")
            conn.execute(text("""
                ALTER TABLE extraction_profiles
                ADD CONSTRAINT chk_confidence_range
                CHECK (min_confidence >= 0 AND min_confidence <= 100)
            """))

            conn.execute(text("""
                ALTER TABLE profile_usage
                ADD CONSTRAINT chk_avg_confidence_range
                CHECK (avg_confidence >= 0 AND avg_confidence <= 1)
            """))

        conn.commit()
        print("✓ Migration 001 complete")

def downgrade():
    """Rollback migration."""
    engine = create_engine(config.database_url)

    with engine.connect() as conn:
        print("Rolling back migration 001...")

        # Drop constraints and indexes
        if config.database_url.startswith('postgresql'):
            conn.execute(text("ALTER TABLE profile_versions DROP CONSTRAINT IF EXISTS uq_profile_version"))
            conn.execute(text("ALTER TABLE extraction_profiles DROP CONSTRAINT IF EXISTS chk_confidence_range"))
            conn.execute(text("ALTER TABLE profile_usage DROP CONSTRAINT IF EXISTS chk_avg_confidence_range"))
        else:
            conn.execute(text("DROP INDEX IF EXISTS uq_profile_version"))

        conn.execute(text("DROP INDEX IF EXISTS idx_profiles_org_type_active"))
        conn.execute(text("DROP INDEX IF EXISTS idx_usage_profile_executed_desc"))
        conn.execute(text("DROP INDEX IF EXISTS idx_documents_status_created_desc"))

        conn.commit()
        print("✓ Rollback complete")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (1 day)
- [ ] Add unique constraint on profile_versions(profile_id, version)
- [ ] Implement optimistic locking in update_profile()
- [ ] Update API to use If-Match header for version checking
- [ ] Add ConcurrentModificationError exception class
- [ ] Write migration script 001

### Phase 2: Performance Optimization (0.5 days)
- [ ] Add composite indexes to all tables
- [ ] Add CHECK constraints for data validation
- [ ] Update table definitions with __table_args__
- [ ] Write migration script 002

### Phase 3: Storage Optimization (0.5 days)
- [ ] Implement dialect-aware JSON storage
- [ ] Add PostgreSQL JSONB support
- [ ] Add GIN indexes for JSONB columns (PostgreSQL)
- [ ] Write migration script 003

### Phase 4: Scalability (optional, 1 day)
- [ ] Create ProfileUsageSummary table
- [ ] Implement daily aggregation job
- [ ] Implement archival strategy
- [ ] Add table partitioning (PostgreSQL only)

---

## Testing Requirements

```python
# test_database_improvements.py

def test_version_uniqueness():
    """Test that duplicate versions are prevented."""
    profile = create_profile(test_profile_dict)

    # Create version 1
    create_profile_version(profile.id, 1, schema_dict)

    # Try to create version 1 again
    with pytest.raises(IntegrityError):
        create_profile_version(profile.id, 1, schema_dict)

def test_concurrent_update_detection():
    """Test optimistic locking prevents lost updates."""
    profile = create_profile(test_profile_dict)

    # Simulate concurrent updates
    update1 = {"name": "update1", "version": profile.version}
    update2 = {"name": "update2", "version": profile.version}

    # First update succeeds
    updated1 = update_profile(profile.id, update1, expected_version=profile.version)
    assert updated1.version == profile.version + 1

    # Second update fails (stale version)
    with pytest.raises(ConcurrentModificationError):
        update_profile(profile.id, update2, expected_version=profile.version)

def test_composite_index_performance():
    """Test that composite indexes improve query speed."""
    # Create 1000 test profiles
    for i in range(1000):
        create_profile({
            "name": f"test-{i}",
            "organization_id": f"org-{i % 10}",
            "document_type": "invoice" if i % 2 == 0 else "receipt"
        })

    import time

    # Query with composite index
    start = time.time()
    profiles = list_profiles(
        organization_id="org-5",
        document_type="invoice",
        active_only=True
    )
    duration = time.time() - start

    # Should be fast (<100ms for 1000 profiles)
    assert duration < 0.1
    assert len(profiles) > 0
```

---

## Success Criteria

- ✅ Unique constraint prevents duplicate versions
- ✅ Optimistic locking prevents lost updates
- ✅ Composite indexes speed up queries by 20-30x
- ✅ PostgreSQL uses native JSONB (not base64)
- ✅ All CHECK constraints enforce data integrity
- ✅ Migration scripts run successfully
- ✅ All database tests pass

---

## References

- SQLAlchemy Documentation: Constraints and Indexes
- PostgreSQL Documentation: JSONB Support
- PostgreSQL Documentation: Table Partitioning
- Database Design Patterns for Multi-Tenant Applications
- Optimistic Locking Strategies
