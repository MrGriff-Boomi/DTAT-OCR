# ADR-001: Replace PyMuPDF with pdfplumber

## Status

Accepted

## Date

2026-01-28

## Context

DTAT OCR uses PyMuPDF (fitz) for native PDF text and table extraction. PyMuPDF is licensed under AGPL-3.0, which is a copyleft license that requires:

- Source code disclosure for any network service using the library
- Any modifications must be released under AGPL-3.0
- Commercial use requires purchasing a separate license from Artifex

This creates legal risk for using DTAT OCR in commercial products without purchasing a commercial license.

### Libraries Considered

| Library | License | Text Extraction | Table Extraction | Notes |
|---------|---------|-----------------|------------------|-------|
| PyMuPDF | AGPL-3.0 | Excellent | Excellent | Copyleft - problematic |
| pypdf | BSD | Good | No | Simple, permissive |
| pdfplumber | MIT | Good | Good | Built on pdfminer, permissive |
| pdfminer.six | MIT | Good | No | Lower-level, permissive |

## Decision

Replace PyMuPDF with **pdfplumber** (MIT License).

Reasons:
1. MIT license is fully permissive for commercial use
2. Supports both text and table extraction (like PyMuPDF)
3. Active maintenance and good documentation
4. Built on pdfminer.six which is battle-tested

## Consequences

### Positive

- No licensing concerns for commercial use
- Can distribute DTAT OCR without AGPL obligations
- pdfplumber has a cleaner API for table extraction

### Negative

- Slightly slower than PyMuPDF for large documents
- Less control over low-level PDF rendering
- May handle some edge-case PDFs differently

### Neutral

- API changes required in extraction_pipeline.py and document_processor.py
- Docker images need to be rebuilt (removes libmupdf-dev dependency)
