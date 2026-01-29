# TASK-002-CODE: Code Quality Improvements

**Status**: Not Started
**Priority**: MEDIUM-HIGH
**Estimated Effort**: 1 day

## Executive Summary

Code quality review identified areas for improvement including code duplication, missing validation logic, and minor consistency issues. While the overall code quality is excellent (8.5/10), these improvements will enhance maintainability and prevent bugs.

**Code Quality Score: 8.5/10** (Current) → **9.5/10** (Target)

---

## High Priority Issues

### 1. 🟠 Code Duplication in API Layer

**Severity**: MEDIUM
**Impact**: Maintenance burden, potential bugs
**Location**: `api.py` - Multiple occurrences of schema conversion pattern

**Issue**: The pattern for converting database records to ExtractionProfile models is repeated 8 times:

```python
# Repeated in 8 different endpoints:
schema = record.get_schema()
schema['id'] = record.id
return ExtractionProfile(**schema)
```

**Locations**:
- Line 997 - create_extraction_profile()
- Line 1032 - list_extraction_profiles()
- Line 1057 - get_extraction_profile()
- Line 1082 - get_extraction_profile_by_name()
- Line 1127 - update_extraction_profile()
- Line 1231 - rollback_extraction_profile()

**Solution**: Extract to helper function

```python
# In api.py, add near the top after imports

def record_to_profile(record: ExtractionProfileRecord) -> ExtractionProfile:
    """
    Convert database record to ExtractionProfile model.

    Args:
        record: Database record

    Returns:
        ExtractionProfile with ID populated
    """
    schema = record.get_schema()
    schema['id'] = record.id
    schema['created_at'] = record.created_at
    schema['updated_at'] = record.updated_at
    return ExtractionProfile(**schema)

def records_to_profiles(records: list[ExtractionProfileRecord]) -> list[ExtractionProfile]:
    """Convert list of records to ExtractionProfile models."""
    return [record_to_profile(record) for record in records]

# Usage in endpoints:
@app.post("/profiles")
async def create_extraction_profile(...):
    record = create_profile(profile_dict)
    return record_to_profile(record)  # ✓ One line instead of three

@app.get("/profiles")
async def list_extraction_profiles(...):
    records = list_profiles(...)
    return records_to_profiles(records)  # ✓ Clean and DRY

@app.get("/profiles/{profile_id}")
async def get_extraction_profile(...):
    record = get_profile_by_id(profile_id)
    return record_to_profile(record)  # ✓ Consistent
```

**Benefits**:
- Reduces code by ~30 lines
- Single place to update if conversion logic changes
- Easier to add caching or transformations
- More testable

---

### 2. 🟠 Missing Strategy-Config Validation

**Severity**: MEDIUM
**Impact**: Runtime errors, confusing error messages
**Location**: `profiles.py` FieldDefinition class (line 90)

**Issue**: No validation ensures correct config is provided for each strategy:

```python
# Current - No validation
field = FieldDefinition(
    name="total",
    field_type=FieldType.CURRENCY,
    strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
    # ❌ Missing keyword_rule - will fail at extraction time
    coordinate_box=CoordinateBox(x=0.5, y=0.5, width=0.2, height=0.1)  # Wrong config!
)

# This creates a profile but fails later when extracting
```

**Solution**: Add Pydantic model validator

```python
# In profiles.py FieldDefinition class

from pydantic import model_validator

class FieldDefinition(BaseModel):
    """Single field to extract from document"""

    name: str = Field(...)
    label: str = Field(...)
    field_type: FieldType
    required: bool = Field(default=False)
    strategy: ExtractionStrategy

    # Strategy-specific config
    coordinate_box: Optional[CoordinateBox] = None
    keyword_rule: Optional[KeywordRule] = None
    table_column_rule: Optional[TableColumnRule] = None
    regex_pattern: Optional[str] = None
    llm_prompt: Optional[str] = None

    # ... other fields ...

    @model_validator(mode='after')
    def validate_strategy_config(self):
        """Ensure correct config is provided for strategy."""

        strategy_config_map = {
            ExtractionStrategy.COORDINATE: ('coordinate_box', 'coordinate box'),
            ExtractionStrategy.KEYWORD_PROXIMITY: ('keyword_rule', 'keyword rule'),
            ExtractionStrategy.TABLE_COLUMN: ('table_column_rule', 'table column rule'),
            ExtractionStrategy.REGEX_PATTERN: ('regex_pattern', 'regex pattern'),
            ExtractionStrategy.SEMANTIC_LLM: ('llm_prompt', 'LLM prompt'),
        }

        # Get required config for this strategy
        required_field, display_name = strategy_config_map[self.strategy]

        # Check if required config is provided
        if getattr(self, required_field) is None:
            raise ValueError(
                f"Field '{self.name}': Strategy '{self.strategy.value}' requires "
                f"'{required_field}' to be set"
            )

        # Warn if other configs are set (may be user error)
        other_fields = [field for field, _ in strategy_config_map.values() if field != required_field]
        set_others = [field for field in other_fields if getattr(self, field) is not None]

        if set_others:
            # This is a warning, not an error (maybe user plans to change strategy later)
            import warnings
            warnings.warn(
                f"Field '{self.name}': Strategy '{self.strategy.value}' uses '{required_field}', "
                f"but these configs are also set and will be ignored: {set_others}"
            )

        return self
```

**Example Validation**:
```python
# Before - Creates invalid profile
field = FieldDefinition(
    name="total",
    field_type=FieldType.CURRENCY,
    strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
    # Missing keyword_rule
)
# ✓ Creates profile, ❌ Fails at extraction time with cryptic error

# After - Fails at creation with clear error
field = FieldDefinition(
    name="total",
    field_type=FieldType.CURRENCY,
    strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
    # Missing keyword_rule
)
# ❌ Raises: ValidationError: Field 'total': Strategy 'keyword' requires 'keyword_rule' to be set
```

---

### 3. 🟡 Code Duplication in Database Layer

**Severity**: LOW-MEDIUM
**Impact**: Maintenance burden
**Location**: `database.py` - set_schema() and get_schema() methods

**Issue**: Nearly identical base64 JSON encoding/decoding logic in multiple classes:

```python
# ExtractionProfileRecord (lines 250-264)
def set_schema(self, schema_dict: dict):
    json_str = json.dumps(schema_dict, default=str, ensure_ascii=False)
    self.schema_json = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def get_schema(self) -> dict:
    if not self.schema_json:
        return {}
    json_str = base64.b64decode(self.schema_json).decode('utf-8')
    return json.loads(json_str)

# ProfileVersionRecord (lines 304-318) - IDENTICAL CODE
def set_schema(self, schema_dict: dict):
    json_str = json.dumps(schema_dict, default=str, ensure_ascii=False)
    self.schema_json = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def get_schema(self) -> dict:
    if not self.schema_json:
        return {}
    json_str = base64.b64decode(self.schema_json).decode('utf-8')
    return json.loads(json_str)
```

**Solution**: Create mixin class

```python
# In database.py, add after imports

class Base64JSONMixin:
    """Mixin for models that store JSON as base64-encoded text."""

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
        value = getattr(self, field_name)
        if not value:
            return {}

        try:
            json_str = base64.b64decode(value).decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            print(f"Error decoding {field_name}: {e}")
            return {}

# Use in model classes
class ExtractionProfileRecord(Base, Base64JSONMixin):
    __tablename__ = "extraction_profiles"

    # ... columns ...
    schema_json = Column(Text, nullable=False)

    def set_schema(self, schema_dict: dict):
        """Store profile schema."""
        self.set_json_field('schema_json', schema_dict)

    def get_schema(self) -> dict:
        """Retrieve profile schema."""
        return self.get_json_field('schema_json')

class ProfileVersionRecord(Base, Base64JSONMixin):
    __tablename__ = "profile_versions"

    # ... columns ...
    schema_json = Column(Text, nullable=False)

    def set_schema(self, schema_dict: dict):
        """Store version schema."""
        self.set_json_field('schema_json', schema_dict)

    def get_schema(self) -> dict:
        """Retrieve version schema."""
        return self.get_json_field('schema_json')

# Can also use for DocumentRecord
class DocumentRecord(Base, Base64JSONMixin):
    # ... existing code ...

    def set_extracted_fields(self, fields: dict):
        """Store extracted fields."""
        self.set_json_field('extracted_fields_json', fields)

    def get_extracted_fields(self) -> dict:
        """Retrieve extracted fields."""
        return self.get_json_field('extracted_fields_json')
```

**Benefits**:
- Single implementation of encode/decode logic
- Easier to update for PostgreSQL JSONB support
- More testable
- Can add caching or validation in one place

---

### 4. 🟡 HTML Injection Risk in Web UI

**Severity**: MEDIUM (Security)
**Impact**: XSS vulnerability in web interface
**Location**: `api.py` lines 310-326 (UI endpoints)

**Issue**: Building HTML with f-strings and unsanitized user data:

```python
# Current code - HTML injection vulnerability
@app.get("/ui/documents", response_class=HTMLResponse)
async def documents_ui(request: Request):
    records = session.query(DocumentRecord).order_by(DocumentRecord.created_at.desc()).limit(100).all()

    rows = []
    for r in records:
        # ❌ User data directly in HTML (filename could contain <script>)
        rows.append(f"""
            <tr>
                <td>{r.id}</td>
                <td>{r.source_filename[:30]}</td>  <!-- XSS HERE -->
                <td>{r.status}</td>
                ...
            </tr>
        """)
```

**Attack Scenario**:
```python
# Attacker uploads file with malicious name
malicious_filename = "<script>alert('XSS')</script>invoice.pdf"

# Filename is displayed in UI without escaping
# Result: JavaScript executes in user's browser
```

**Solution**: Use Jinja2 templates (already available) or escape HTML

**Option 1: Use Jinja2 (Recommended)**
```python
# Keep using templates (already set up)
@app.get("/ui/documents", response_class=HTMLResponse)
async def documents_ui(request: Request, username: str = Depends(verify_credentials)):
    session = get_session()
    try:
        records = session.query(DocumentRecord)\
            .order_by(DocumentRecord.created_at.desc())\
            .limit(100)\
            .all()

        return templates.TemplateResponse(
            "documents.html",
            {
                "request": request,
                "documents": [r.to_dict() for r in records]  # ✓ Jinja2 auto-escapes
            }
        )
    finally:
        session.close()

# In templates/documents.html
# Jinja2 automatically escapes {{ document.source_filename }}
```

**Option 2: Escape HTML if building strings**
```python
from html import escape

rows = []
for r in records:
    rows.append(f"""
        <tr>
            <td>{r.id}</td>
            <td>{escape(r.source_filename[:30])}</td>  <!-- ✓ Escaped -->
            <td>{escape(r.status)}</td>
            ...
        </tr>
    """)
```

---

### 5. 🟢 Missing Type Hints

**Severity**: LOW
**Impact**: Reduced IDE support, harder to maintain
**Location**: Various functions in `database.py`

**Issue**: Some functions lack complete type hints:

```python
# Current - Missing return type
def get_profile_usage_stats(profile_id: int, days: int = 30):  # ❌ No return type
    """Get usage statistics for a profile."""
    # ...
    return {
        "total_documents": total_docs,
        "success_rate": success_rate,
        # ...
    }
```

**Solution**: Add complete type hints

```python
from typing import Dict, Any

def get_profile_usage_stats(profile_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Get usage statistics for a profile.

    Args:
        profile_id: Profile ID
        days: Number of days to look back

    Returns:
        Dictionary with statistics
    """
    # ...
    return {
        "total_documents": total_docs,
        "success_rate": success_rate,
        # ...
    }
```

---

### 6. 🟢 Inconsistent Error Handling

**Severity**: LOW
**Impact**: Inconsistent error messages
**Location**: `database.py` lines 602, 640

**Issue**: Database layer raises `ValueError` but API layer expects `HTTPException`:

```python
# Database layer
def update_profile(profile_id: int, profile_dict: dict):
    record = session.query(...).first()
    if not record:
        raise ValueError(f"Profile {profile_id} not found")  # ValueError

# API layer has to catch and convert
try:
    record = update_profile(profile_id, profile_dict)
except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))  # Manual conversion
```

**Solution**: Use consistent exception types or create custom exceptions

```python
# Option 1: Create custom exceptions
class ProfileNotFoundError(Exception):
    """Profile not found in database."""
    def __init__(self, profile_id: int):
        self.profile_id = profile_id
        super().__init__(f"Profile {profile_id} not found")

class ProfileValidationError(Exception):
    """Profile data is invalid."""
    pass

# Database layer
def update_profile(profile_id: int, profile_dict: dict):
    record = session.query(...).first()
    if not record:
        raise ProfileNotFoundError(profile_id)  # Custom exception

# API layer - single exception handler
@app.exception_handler(ProfileNotFoundError)
async def profile_not_found_handler(request: Request, exc: ProfileNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Profile {exc.profile_id} not found"}
    )
```

---

## Low Priority Issues

### 7. Missing Docstrings

**Location**: `database.py` DocumentRecord methods (lines 84+)

```python
# Add docstrings to public methods
class DocumentRecord(Base):
    def to_dict(self) -> dict:
        """
        Convert to dictionary for API responses.

        Returns:
            Dictionary with document metadata
        """
        return {...}
```

---

### 8. Enum Value Inconsistency

**Location**: `profiles.py` line 14

**Issue**: Enum names don't match values:
```python
class ExtractionStrategy(str, Enum):
    KEYWORD_PROXIMITY = "keyword"  # ⚠️ Name has _PROXIMITY, value doesn't
```

**Solution**: Align names and values or add comment explaining choice

---

## Implementation Checklist

### Phase 1: High Priority (0.5 days)
- [ ] Extract `record_to_profile()` helper function
- [ ] Add strategy-config validator to FieldDefinition
- [ ] Create Base64JSONMixin class
- [ ] Update all record classes to use mixin
- [ ] Fix HTML injection in UI (use templates or escape)

### Phase 2: Medium Priority (0.25 days)
- [ ] Add missing type hints to all functions
- [ ] Create custom exception classes
- [ ] Add exception handlers to API layer
- [ ] Update all database functions to use custom exceptions

### Phase 3: Low Priority (0.25 days)
- [ ] Add missing docstrings
- [ ] Review and align enum names/values
- [ ] Add code comments where logic is complex
- [ ] Run linter (ruff/pylint) and fix warnings

---

## Testing Requirements

```python
# test_code_quality.py

def test_record_to_profile_helper():
    """Test record conversion helper."""
    record = create_profile(test_profile_dict)
    profile = record_to_profile(record)

    assert isinstance(profile, ExtractionProfile)
    assert profile.id == record.id
    assert profile.name == record.name

def test_strategy_config_validation():
    """Test that strategy config is validated."""
    # Valid: keyword strategy with keyword_rule
    field = FieldDefinition(
        name="test",
        label="Test",
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(keyword="Total:")
    )
    assert field is not None

    # Invalid: keyword strategy without keyword_rule
    with pytest.raises(ValidationError):
        FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            # Missing keyword_rule
        )

def test_html_escaping():
    """Test that HTML is escaped in UI."""
    # Create document with malicious filename
    doc = create_document_record(
        filename="<script>alert('XSS')</script>test.pdf",
        file_bytes=b"test",
        file_type="pdf"
    )
    save_document(doc)

    # Get UI
    response = client.get("/ui/documents", auth=auth)

    # Should escape HTML
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text or "escaped" in response.text.lower()
```

---

## Success Criteria

- ✅ Code duplication reduced by 30+ lines
- ✅ Strategy validation prevents invalid profiles
- ✅ Base64 JSON logic in single place (mixin)
- ✅ HTML injection vulnerability fixed
- ✅ All functions have type hints
- ✅ Consistent exception handling
- ✅ All code quality tests pass
- ✅ Linter reports no warnings

---

## References

- PEP 8: Style Guide for Python Code
- Pydantic Documentation: Model Validators
- OWASP: XSS Prevention Cheat Sheet
- Python Type Hints: PEP 484
