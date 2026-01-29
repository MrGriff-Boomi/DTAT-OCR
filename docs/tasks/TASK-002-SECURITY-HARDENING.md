# TASK-002-SECURITY: Security Hardening for Profile Management System

**Status**: Not Started
**Priority**: CRITICAL
**Blocks**: Production Deployment
**Created**: 2026-01-29
**Estimated Effort**: 2-3 days

## Executive Summary

Security review identified **CRITICAL vulnerabilities** that make the current implementation unsuitable for multi-tenant production deployment. Any authenticated user can currently access, modify, or delete profiles belonging to other organizations. This task addresses all security findings.

**Security Risk Score: 6/10** (Current) → **9/10** (Target)

---

## Critical Vulnerabilities (MUST FIX)

### 1. 🔴 Missing Multi-Tenant Authorization Controls

**Severity**: CRITICAL
**Impact**: Complete bypass of multi-tenant isolation
**Location**: `api.py` lines 969-1258 (all profile endpoints)

**Issue**: All profile endpoints check authentication but do NOT verify ownership/authorization. Any authenticated user can:
- Access any organization's profiles by guessing/enumerating profile IDs
- Modify profiles belonging to other organizations
- Delete profiles they don't own
- View version history of other users' profiles

**Attack Scenario**:
```bash
# Attacker enumerates profile IDs
curl -u "attacker:password" "http://localhost:8000/profiles/1"  # Competitor's invoice profile
curl -u "attacker:password" "http://localhost:8000/profiles/2"  # Another user's W-2 profile

# Attacker modifies competitor's profile
curl -u "attacker:password" -X PUT "http://localhost:8000/profiles/1" -d '{"fields": []}'

# Attacker deletes competitor's profile
curl -u "attacker:password" -X DELETE "http://localhost:8000/profiles/1"
```

**Current Vulnerable Code**:
```python
@app.get("/profiles/{profile_id}")
async def get_extraction_profile(
    profile_id: int,
    username: str = Depends(verify_credentials)  # ✅ Authenticated
):
    record = get_profile_by_id(profile_id)  # ❌ No authorization check!
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Returns profile regardless of who owns it
    schema = record.get_schema()
    schema['id'] = record.id
    return ExtractionProfile(**schema)
```

**Solution**:
```python
# 1. Create authorization helper in api.py
def verify_profile_access(
    profile_id: int,
    username: str,
    require_write: bool = False
) -> ExtractionProfileRecord:
    """
    Verify user has access to this profile.

    Args:
        profile_id: Profile ID to check
        username: Current user
        require_write: If True, check write permission

    Returns:
        Profile record if authorized

    Raises:
        HTTPException 403: Access denied
        HTTPException 404: Profile not found
    """
    record = get_profile_by_id(profile_id)
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get user's organization
    user_org = get_user_organization(username)

    # Check access
    if record.is_template:
        # Templates are read-only for everyone
        if require_write:
            raise HTTPException(status_code=403, detail="Cannot modify template profiles")
        return record

    # Check ownership
    is_owner = (
        record.organization_id == user_org or
        record.created_by == username
    )

    if not is_owner:
        raise HTTPException(status_code=403, detail="Access denied")

    return record

# 2. Add user organization lookup
def get_user_organization(username: str) -> str:
    """Get organization ID for username."""
    # TODO: Implement user management system
    # For now, use environment variable or config
    # In production, query from users table
    return os.getenv("DEFAULT_ORGANIZATION_ID", "default-org")

# 3. Update all endpoints to use authorization
@app.get("/profiles/{profile_id}")
async def get_extraction_profile(
    profile_id: int,
    username: str = Depends(verify_credentials)
):
    """Get profile with authorization check."""
    record = verify_profile_access(profile_id, username, require_write=False)
    schema = record.get_schema()
    schema['id'] = record.id
    return ExtractionProfile(**schema)

@app.put("/profiles/{profile_id}")
async def update_extraction_profile(
    profile_id: int,
    profile: ExtractionProfile,
    username: str = Depends(verify_credentials)
):
    """Update profile with write permission check."""
    verify_profile_access(profile_id, username, require_write=True)
    # ... rest of update logic

@app.delete("/profiles/{profile_id}")
async def delete_extraction_profile(
    profile_id: int,
    hard_delete: bool = False,
    username: str = Depends(verify_credentials)
):
    """Delete profile with write permission check."""
    record = verify_profile_access(profile_id, username, require_write=True)

    # Hard delete requires admin role
    if hard_delete and not is_admin_user(username):
        raise HTTPException(status_code=403, detail="Admin required for hard delete")

    delete_profile(profile_id, hard_delete=hard_delete)
    return None
```

**Implementation Steps**:
1. Create `verify_profile_access()` helper function
2. Create `get_user_organization()` function
3. Create `is_admin_user()` function
4. Update all 9 profile endpoints to call `verify_profile_access()`
5. Add organization filter to `list_profiles()` endpoint
6. Write unit tests for authorization logic
7. Write integration tests for authorization bypass attempts

---

### 2. 🔴 No Rate Limiting on Profile Operations

**Severity**: HIGH
**Impact**: API abuse, DoS, storage exhaustion, reconnaissance
**Location**: All API endpoints

**Issue**: No rate limiting exists. An attacker can:
- Enumerate all profile IDs (brute force `/profiles/{id}` from 1 to 1000000)
- Create thousands of profiles to fill database
- Spam version history to create storage exhaustion
- DDoS the API with profile creation requests

**Attack Scenarios**:
```python
# 1. Enumerate all profiles (reconnaissance)
for i in range(1, 100000):
    requests.get(f"http://localhost:8000/profiles/{i}", auth=auth)

# 2. Storage exhaustion attack
for i in range(10000):
    massive_profile = {"name": f"evil-{i}", "fields": [huge_field_list]}
    requests.post("http://localhost:8000/profiles", json=massive_profile, auth=auth)

# 3. Version spam attack
for i in range(1000):
    requests.put(f"http://localhost:8000/profiles/1", json=profile, auth=auth)
```

**Solution**: Implement rate limiting with `slowapi`

```python
# 1. Install slowapi
# pip install slowapi

# 2. Add to api.py imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 3. Initialize limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 4. Apply rate limits to endpoints
@app.post("/profiles", response_model=ExtractionProfile, status_code=201)
@limiter.limit("10/minute")  # Max 10 profile creations per minute
async def create_extraction_profile(
    request: Request,  # Required for slowapi
    profile: ExtractionProfile,
    username: str = Depends(verify_credentials)
):
    ...

@app.get("/profiles/{profile_id}")
@limiter.limit("100/minute")  # Max 100 reads per minute
async def get_extraction_profile(
    request: Request,
    profile_id: int,
    username: str = Depends(verify_credentials)
):
    ...

@app.put("/profiles/{profile_id}")
@limiter.limit("20/minute")  # Max 20 updates per minute
async def update_extraction_profile(
    request: Request,
    profile_id: int,
    profile: ExtractionProfile,
    username: str = Depends(verify_credentials)
):
    ...

@app.delete("/profiles/{profile_id}")
@limiter.limit("10/minute")  # Max 10 deletes per minute
async def delete_extraction_profile(
    request: Request,
    profile_id: int,
    hard_delete: bool = False,
    username: str = Depends(verify_credentials)
):
    ...

@app.get("/profiles")
@limiter.limit("100/minute")  # Max 100 list requests per minute
async def list_extraction_profiles(
    request: Request,
    ...
):
    ...
```

**Rate Limit Configuration**:
| Endpoint | Rate Limit | Reason |
|----------|------------|--------|
| POST /profiles | 10/minute | Prevent profile spam |
| GET /profiles/{id} | 100/minute | Prevent enumeration |
| PUT /profiles/{id} | 20/minute | Prevent version spam |
| DELETE /profiles/{id} | 10/minute | Prevent deletion abuse |
| GET /profiles | 100/minute | Prevent list abuse |
| POST /profiles/{id}/rollback | 5/minute | Expensive operation |
| GET /profiles/{id}/stats | 50/minute | Database-heavy query |

**Implementation Steps**:
1. Add `slowapi` to requirements.txt
2. Initialize limiter in api.py
3. Add rate limit decorators to all endpoints
4. Configure rate limits per endpoint
5. Add custom error message for rate limit exceeded
6. Write tests for rate limiting
7. Document rate limits in API docs

---

### 3. 🔴 Regex Injection (ReDoS) Vulnerability

**Severity**: HIGH
**Impact**: CPU exhaustion, DoS, API slowdown
**Location**: `profiles.py` lines 102, 106 (regex_pattern, validation_pattern)

**Issue**: User-supplied regex patterns are stored and later executed. Malicious regex can cause:
- **ReDoS (Regular Expression Denial of Service)**: Catastrophic backtracking
- **CPU exhaustion**: Complex patterns that take minutes to evaluate
- **Memory exhaustion**: Patterns that allocate huge buffers

**Attack Scenario**:
```json
{
    "name": "evil-profile",
    "display_name": "Evil Profile",
    "document_type": "invoice",
    "fields": [{
        "name": "test",
        "label": "Test Field",
        "field_type": "text",
        "strategy": "regex",
        "regex_pattern": "^(a+)+$",  // ReDoS pattern - causes catastrophic backtracking
        "validation_pattern": "(a|a)*b"  // Another ReDoS pattern
    }]
}

// When this profile processes a document with "aaaaaaaaaa..." text,
// the regex engine will hang for minutes consuming 100% CPU
```

**Vulnerable Patterns**:
- `(a+)+` - Nested quantifiers
- `(a*)*` - Nested quantifiers
- `(a|a)*` - Overlapping alternations
- `(a|ab)*` - Overlapping alternations with different lengths
- `(.*a){x}` for large x - Exponential backtracking

**Solution**: Validate and sandbox regex patterns

```python
# In profiles.py FieldDefinition class

from pydantic import validator
import re
import signal
from typing import Optional

class FieldDefinition(BaseModel):
    # ... existing fields ...

    @validator('regex_pattern', 'validation_pattern')
    def validate_regex_pattern(cls, v: Optional[str]) -> Optional[str]:
        """Validate regex pattern is safe and compilable."""
        if not v:
            return v

        # 1. Length check
        if len(v) > 500:
            raise ValueError("Regex pattern too long (max 500 characters)")

        # 2. Check for dangerous patterns
        dangerous_patterns = [
            r'\*\*',        # **
            r'\+\+',        # ++
            r'\{\d{3,}',    # {100,} or larger
            r'\*\+',        # *+
            r'\+\*',        # +*
            r'\(\.\*\)',    # (.*)
            r'\(\.+\)',     # (.+)
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v):
                raise ValueError(f"Potentially unsafe regex pattern detected: {pattern}")

        # 3. Compile check
        try:
            compiled = re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # 4. ReDoS test with timeout
        if not is_regex_safe(v):
            raise ValueError("Regex pattern failed safety test (possible ReDoS)")

        return v

def is_regex_safe(pattern: str, test_string: str = "a" * 1000, timeout_seconds: int = 1) -> bool:
    """
    Test if regex is safe by running it with a timeout.

    Args:
        pattern: Regex pattern to test
        test_string: Test string (default: 1000 'a's)
        timeout_seconds: Max execution time

    Returns:
        True if safe, False if times out
    """
    import threading

    result = {'completed': False}

    def test_regex():
        try:
            re.search(pattern, test_string)
            result['completed'] = True
        except:
            result['completed'] = False

    thread = threading.Thread(target=test_regex)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)

    return result['completed']
```

**Additional Protection**: Sandbox regex execution at runtime

```python
# In extractors.py (when implementing extraction engine)

import signal
from contextlib import contextmanager

@contextmanager
def timeout(seconds):
    """Context manager for timing out operations."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    # Set signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

class RegexExtractor(FieldExtractor):
    """Extract using regex pattern with timeout protection."""

    def extract(self, field_def, ocr_result, page=1):
        pattern = field_def.regex_pattern
        full_text = ocr_result.get('full_text', '')

        try:
            # Limit regex execution to 2 seconds
            with timeout(2):
                match = re.search(pattern, full_text)
                if not match:
                    return None, 0.0, None

                value = match.group(1) if match.groups() else match.group(0)
                location = self._find_text_location(value, ocr_result)
                return value, 0.8, location

        except TimeoutError:
            # Log suspicious pattern for security review
            logger.warning(f"Regex pattern timed out: {pattern[:50]}...")
            return None, 0.0, None
```

**Implementation Steps**:
1. Add regex validation to `FieldDefinition` model
2. Create `is_regex_safe()` function
3. Add dangerous pattern detection
4. Add timeout wrapper for runtime regex execution
5. Log suspicious patterns for security review
6. Write unit tests with ReDoS patterns
7. Document regex limitations in API docs

---

### 4. 🔴 Template Protection Missing

**Severity**: MEDIUM-HIGH
**Impact**: Built-in templates can be modified/deleted
**Location**: `api.py` PUT and DELETE endpoints

**Issue**: Any authenticated user can update or delete template profiles (built-in profiles that should be read-only).

**Solution**: Add template protection checks

```python
@app.put("/profiles/{profile_id}")
async def update_extraction_profile(
    profile_id: int,
    profile: ExtractionProfile,
    username: str = Depends(verify_credentials)
):
    """Update profile (blocked for templates)."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Block template modification
    if existing.is_template:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify template profiles. Clone to create custom version."
        )

    # Verify write access
    verify_profile_access(profile_id, username, require_write=True)

    # ... rest of update logic

@app.delete("/profiles/{profile_id}")
async def delete_extraction_profile(
    profile_id: int,
    hard_delete: bool = False,
    username: str = Depends(verify_credentials)
):
    """Delete profile (blocked for templates)."""
    existing = get_profile_by_id(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Block template deletion
    if existing.is_template:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete template profiles"
        )

    # ... rest of deletion logic
```

**Implementation Steps**:
1. Add `is_template` check to update endpoint
2. Add `is_template` check to delete endpoint
3. Update error messages with guidance
4. Write tests for template protection
5. Add clone endpoint for templates

---

## Additional Security Improvements

### 5. Audit Logging

**Priority**: HIGH
**Location**: New middleware in api.py

**Implementation**:
```python
from datetime import datetime
import json

# Create audit log table
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    username = Column(String(255), index=True)
    action = Column(String(50))  # CREATE, READ, UPDATE, DELETE
    resource_type = Column(String(50))  # profile, document, etc.
    resource_id = Column(Integer)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    request_method = Column(String(10))
    request_path = Column(String(1000))
    status_code = Column(Integer)
    details = Column(Text)  # JSON with additional context

# Add middleware
@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    """Log all profile operations for audit trail."""

    # Only log profile operations
    if not request.url.path.startswith("/profiles"):
        return await call_next(request)

    # Extract user
    username = None
    if hasattr(request.state, 'user'):
        username = request.state.user

    # Process request
    start_time = datetime.utcnow()
    response = await call_next(request)
    duration = (datetime.utcnow() - start_time).total_seconds()

    # Log to database
    try:
        log_audit_event(
            username=username,
            action=request.method,
            resource_type="profile",
            resource_id=extract_profile_id(request.url.path),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            request_method=request.method,
            request_path=request.url.path,
            status_code=response.status_code,
            details=json.dumps({
                "duration_seconds": duration,
                "query_params": dict(request.query_params)
            })
        )
    except Exception as e:
        # Don't fail request if logging fails
        logger.error(f"Audit log failed: {e}")

    return response

def log_audit_event(username, action, resource_type, resource_id,
                   ip_address, user_agent, request_method,
                   request_path, status_code, details):
    """Save audit event to database."""
    session = get_session()
    try:
        log = AuditLog(
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            status_code=status_code,
            details=details
        )
        session.add(log)
        session.commit()
    finally:
        session.close()
```

---

### 6. HTTPS Enforcement

**Priority**: CRITICAL (Production)
**Location**: api.py middleware

**Implementation**:
```python
@app.middleware("http")
async def enforce_https(request: Request, call_next):
    """Enforce HTTPS in production."""
    if config.environment == "production":
        if request.url.scheme != "https" and request.client.host != "127.0.0.1":
            return JSONResponse(
                status_code=403,
                content={"detail": "HTTPS required in production"}
            )
    return await call_next(request)
```

---

### 7. Request Size Limits

**Priority**: MEDIUM
**Location**: api.py middleware

**Implementation**:
```python
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent abuse."""

    MAX_REQUEST_SIZE = 10_000_000  # 10MB

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            if content_length > self.MAX_REQUEST_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request too large (max {self.MAX_REQUEST_SIZE} bytes)"}
                )
        return await call_next(request)

app.add_middleware(RequestSizeLimitMiddleware)
```

---

### 8. CORS Configuration

**Priority**: HIGH
**Location**: api.py initialization

**Implementation**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dtat-ocr-frontend.com",  # Production frontend
        "http://localhost:3000"            # Development frontend
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600
)
```

---

## Testing Requirements

### Security Test Suite

```python
# test_security.py

import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_authorization_bypass_attempt():
    """Test that users cannot access other org's profiles."""
    # Create profile as user A
    auth_a = ("userA", "passwordA")
    response = client.post("/profiles", json=profile_a, auth=auth_a)
    profile_id = response.json()["id"]

    # Try to access as user B
    auth_b = ("userB", "passwordB")
    response = client.get(f"/profiles/{profile_id}", auth=auth_b)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

def test_rate_limiting():
    """Test that rate limits are enforced."""
    auth = ("user", "password")

    # Make 15 requests (limit is 10/minute)
    responses = []
    for i in range(15):
        response = client.post("/profiles", json=profile_data, auth=auth)
        responses.append(response.status_code)

    # Should have some 429 (Too Many Requests) responses
    assert 429 in responses

def test_redos_prevention():
    """Test that ReDoS patterns are rejected."""
    auth = ("user", "password")

    evil_profile = {
        "name": "evil",
        "document_type": "test",
        "fields": [{
            "name": "test",
            "field_type": "text",
            "strategy": "regex",
            "regex_pattern": "^(a+)+$"  # ReDoS pattern
        }]
    }

    response = client.post("/profiles", json=evil_profile, auth=auth)
    assert response.status_code == 422
    assert "unsafe" in response.json()["detail"].lower()

def test_template_modification_blocked():
    """Test that template profiles cannot be modified."""
    auth = ("user", "password")

    # Try to update template profile
    response = client.put("/profiles/1", json=updated_profile, auth=auth)
    assert response.status_code == 403
    assert "template" in response.json()["detail"].lower()

def test_sql_injection_attempt():
    """Test that SQL injection is prevented."""
    auth = ("user", "password")

    # Try SQL injection in profile name
    response = client.get("/profiles/by-name/test'; DROP TABLE profiles;--", auth=auth)
    assert response.status_code == 404  # Not 500 (server error)
```

---

## Compliance Requirements

### GDPR Compliance

1. **Right to Access** (Article 15):
   ```python
   @app.get("/profiles/export")
   async def export_user_profiles(username: str = Depends(verify_credentials)):
       """Export all profiles created by user."""
       profiles = list_profiles(created_by=username)
       return {"profiles": [p.to_dict() for p in profiles]}
   ```

2. **Right to Erasure** (Article 17):
   ```python
   def anonymize_user_data(username: str):
       """Anonymize user data when account deleted."""
       session = get_session()
       profiles = session.query(ExtractionProfileRecord).filter_by(created_by=username).all()
       for p in profiles:
           p.created_by = "ANONYMIZED"
           p.organization_id = None
       session.commit()
   ```

3. **Audit Trail** (Article 30):
   - Implement audit logging (see section 5)

---

## Implementation Checklist

### Phase 1: Critical Fixes (2 days)
- [ ] Implement `verify_profile_access()` function
- [ ] Add authorization to all 9 profile endpoints
- [ ] Add rate limiting to all endpoints
- [ ] Add regex validation to FieldDefinition
- [ ] Add template protection checks
- [ ] Write security test suite

### Phase 2: Additional Security (1 day)
- [ ] Implement audit logging middleware
- [ ] Add HTTPS enforcement
- [ ] Add request size limits
- [ ] Configure CORS properly
- [ ] Add GDPR compliance endpoints

### Phase 3: Testing & Documentation (0.5 days)
- [ ] Run full security test suite
- [ ] Penetration testing
- [ ] Update API documentation
- [ ] Create security playbook

---

## Success Criteria

- ✅ All security tests pass
- ✅ Authorization bypass attempts return 403
- ✅ Rate limits enforced on all endpoints
- ✅ ReDoS patterns rejected at profile creation
- ✅ Template profiles cannot be modified
- ✅ Audit logs capture all profile operations
- ✅ Security review score improves to 9/10

---

## References

- OWASP Top 10 2021
- OWASP API Security Top 10
- CWE-400: Uncontrolled Resource Consumption (ReDoS)
- GDPR Articles 15, 17, 30
- SOC 2 Trust Services Criteria
