# ADR-002: High Volume Optimizations (Application-Level)

## Status

Accepted

## Date

2026-04-01

## Context

DTAT-OCR currently runs a single uvicorn worker with synchronous Textract calls and SQLite storage. This limits throughput to ~20-30 docs/minute with only 1 concurrent request. For client demos and production pilot workloads, we need 100+ docs/minute without moving to full AWS infrastructure (ECS, SQS, RDS).

The EC2 instance (t3.medium, 2 vCPU, 8GB RAM) has headroom — Textract processing is network-bound (not CPU-bound), so additional workers can run concurrently without saturating the CPU.

## Decision

Implement application-level optimizations in this order:

1. **Multi-worker uvicorn** — Run 4 workers to handle concurrent requests
2. **PostgreSQL storage** — Replace SQLite (single-writer lock) with PostgreSQL (already installed on EC2)
3. **boto3 session reuse** — Share Textract client across requests instead of creating per-request
4. **Async OCR endpoint** — Make `/ocr` truly async with `aioboto3`
5. **Fire-and-forget endpoint** — Add `/ocr/async` that returns job ID immediately, client polls for result
6. **In-process queue** — `asyncio.Queue` with background workers to absorb burst traffic

These changes stay within the single EC2 instance. Full AWS infrastructure (ECS auto-scaling, SQS, managed RDS) is a separate future effort.

## Consequences

### Positive

- **10x throughput improvement** measured: 250 docs/min direct, 41 docs/min via Boomi (from ~25)
- 50 concurrent requests with 0 failures (from 1)
- PostgreSQL enables concurrent writes — zero contention under load
- Async job system with PostgreSQL-backed state (works across all 4 workers)
- Queue monitoring with avg/p95 processing time metrics
- No new AWS services or cost increase
- Backward compatible — all existing endpoints continue to work
- Estimated ~20,000 docs/day through Boomi, ~120,000 docs/day direct

### Negative

- PostgreSQL adds a service to manage on the EC2 (already installed, minor overhead)
- Multiple workers consume more RAM (~240MB total vs ~60MB single)
- `aioboto3` and `psycopg2-binary` add dependencies

### Neutral

- Docker images updated for multi-worker config
- systemd service updated with `--workers 4`
- `.env` updated with PostgreSQL connection string
- Boomi WSS throughput limited by synchronous request handling (~41 docs/min)
