# TASK: High Volume Optimizations

**Branch:** `feature/high-volume`
**ADR:** [002-high-volume-optimizations](adr/002-high-volume-optimizations.md)
**Target:** 100-150 docs/minute on single EC2 (up from ~20-30)

---

## Phase 1: Quick Wins (45 min)

### 1.1 Multi-Worker Uvicorn
- [ ] Update systemd service: `--workers 4`
- [ ] Update Dockerfile CMD: `--workers 4`
- [ ] Update docker-compose.yml
- [ ] Test: 4 concurrent requests succeed simultaneously
- **Expected gain:** 4x throughput

### 1.2 PostgreSQL Migration
- [ ] Add `psycopg2-binary` to requirements.txt
- [ ] Update `config.py` with PostgreSQL connection string support
- [ ] Update `database.py` — ensure engine supports PostgreSQL URL
- [ ] Create `scripts/migrate_to_postgres.py` (copy SQLite data to PostgreSQL)
- [ ] Update `.env` template with `DATABASE_URL=postgresql://...`
- [ ] Test: CRUD operations work against PostgreSQL
- [ ] Test: Concurrent writes don't block
- **Expected gain:** Removes single-writer bottleneck

### 1.3 boto3 Session Reuse
- [ ] Create shared `boto3.Session` + `textract` client at module level in `extraction_pipeline.py`
- [ ] Reuse client across `TextractExtractor.extract()` calls (no per-request `boto3.client()`)
- [ ] Test: Multiple sequential requests share session
- **Expected gain:** ~20% faster per request (skip client init)

---

## Phase 2: Async Processing (2 hours)

### 2.1 Async /ocr Endpoint
- [ ] Add `aioboto3` to requirements.txt
- [ ] Create async Textract client wrapper
- [ ] Convert `/ocr` endpoint to use `async def` with `aioboto3`
- [ ] Test: Endpoint no longer blocks uvicorn worker thread during Textract call
- **Expected gain:** +50% throughput (workers freed while waiting on Textract network I/O)

### 2.2 Fire-and-Forget Endpoint
- [ ] Add `POST /ocr/async` endpoint — accepts image, returns `{"job_id": "...", "status": "queued"}`
- [ ] Add `GET /ocr/jobs/{job_id}` — returns status + result when complete
- [ ] Process OCR in `BackgroundTasks` (FastAPI built-in)
- [ ] Test: Submit 10 jobs rapidly, all return job IDs, all complete within 30s
- **Expected gain:** Enables burst absorption, client doesn't block

---

## Phase 3: Queue & Resilience (2 hours)

### 3.1 In-Process Job Queue
- [ ] Implement `asyncio.Queue` with configurable max size (default: 50)
- [ ] Background worker pool (4 consumers) pulling from queue
- [ ] Return 429 Too Many Requests when queue is full
- [ ] Add `/queue/status` endpoint — current depth, processing count, errors
- [ ] Test: Submit 20 jobs in 2 seconds, all eventually complete
- **Expected gain:** Handles traffic bursts without dropping requests

### 3.2 Health & Monitoring
- [ ] Add worker count to `/health` response
- [ ] Add queue depth to `/stats` response
- [ ] Add avg/p95/p99 processing time tracking
- [ ] Add Textract API call count and error rate
- **Expected gain:** Operational visibility

---

## Validation Criteria

| Metric | Before | Target | Actual (Measured) |
|--------|--------|--------|-------------------|
| Concurrent requests | 1 | 8-12 | **50 concurrent (0 failures)** |
| Docs/minute (direct) | ~25 | 100-150 | **250 docs/min (4.1 docs/sec)** |
| Docs/minute (Boomi WSS) | ~25 | 40-60 | **41 docs/min (0.68 docs/sec)** |
| Burst handling | Timeout at 2+ | 50 doc burst | **50 docs in 12s direct, 73s via Boomi** |
| DB write contention | Locks on 2+ writes | None | **0 contention (PostgreSQL)** |
| Avg processing time | 2-3s | 1.5-2s | **2.4s avg, 3.5s p95** |
| Estimated daily (8hr, Boomi) | ~12,000 | 20,000+ | **~20,000 docs/day** |
| Estimated daily (8hr, direct) | ~12,000 | 50,000+ | **~120,000 docs/day** |

### Load Test Results (2026-04-01)

**50-doc burst test (direct to DTAT):**
- 50 jobs submitted in 7s, all completed in 12s total
- 0 failures, avg 2.4s, p95 3.5s

**50-doc burst test (through Boomi WSS):**
- 5 batches of 10 concurrent requests
- All 50 returned HTTP 200 with 390 chars extracted text
- Per-batch time: 13-16s (Boomi WSS processes synchronously)
- Total: 73s, 0 failures

---

## Out of Scope (Future AWS Work)

- ECS/Fargate auto-scaling (for 1000+ docs/min)
- SQS job queuing (for guaranteed delivery)
- RDS managed PostgreSQL (for HA/backups)
- S3 document storage (for large files)
- CloudWatch logging
- Multi-AZ availability

These are tracked separately and depend on client commitment to production deployment.
