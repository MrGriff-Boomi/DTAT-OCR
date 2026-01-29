# DTAT-OCR Task Roadmap

## Vision

Transform DTAT-OCR from a simple OCR service into a **Swiss Army Knife document intelligence platform** that serves as a drop-in replacement for AWS Textract, Google Cloud Vision, and Azure Computer Vision while offering superior flexibility, lower costs, and user-defined extraction profiles.

## Architecture Evolution

### Current State (v1.0)
```
Document → LightOnOCR → Raw Text + Tables → JSON
```

### Target State (v2.0)
```
Document → Multi-Strategy OCR → Normalized Format → Format Converters → Multiple Output Formats
                                        ↓
                                 Profile Extractor → Structured Fields
                                        ↓
                                   LLM Semantic → Enhanced Extraction
```

## Task Overview

| Task | Title | Priority | Status | Depends On | Est. Duration |
|------|-------|----------|--------|------------|---------------|
| [TASK-001](TASK-001-Multi-Format-Output-Support.md) | Multi-Format Output Support | High | Not Started | - | 3-4 weeks |
| [TASK-002](TASK-002-Profile-Schema-Management-System.md) | Profile & Schema Management | High | Not Started | TASK-001 | 6-8 weeks |
| [TASK-003](TASK-003-Structured-Field-Extraction.md) | Structured Field Extraction (Bedrock) | High | Not Started | TASK-001, TASK-002 | 4-6 weeks |
| [TASK-004](TASK-004-Batch-Processing-Support.md) | Batch Processing | Medium | Not Started | TASK-001, TASK-002 | 3-4 weeks |

**Total Estimated Duration**: 16-22 weeks (4-5 months)

## Detailed Task Breakdown

### TASK-001: Multi-Format Output Support
**Goal**: Enable DTAT to output in Textract, Google Vision, Azure OCR, and native formats

**Key Features**:
- Normalized internal format (coordinate system, block types)
- Format converters for each major OCR provider
- API parameter to select output format
- Backward compatibility with existing clients

**Business Value**:
- Drop-in replacement for AWS Textract (save $1.50/1000 pages)
- Easy migration from Google/Azure (no code changes)
- Future-proof architecture for new formats

**Technical Highlights**:
- Abstract `OutputFormatter` base class
- Coordinate normalization (0.0-1.0)
- Block type mapping (LINE → TEXT_LINE → line)
- Confidence score normalization

**Deliverables**:
- `TextractFormatter`, `GoogleVisionFormatter`, `AzureOCRFormatter`
- `/documents/{id}/content?format=textract` API endpoint
- Migration guide for existing integrations
- Unit tests for each formatter

---

### TASK-002: Profile & Schema Management System
**Goal**: Allow users to define reusable extraction profiles for specific document types

**Key Features**:
- Profile CRUD API (create, read, update, delete)
- Multiple extraction strategies:
  - Coordinate-based (fixed positions)
  - Keyword proximity ("Total:" followed by number)
  - Table column extraction
  - Regex pattern matching
  - LLM semantic extraction
- Field validation and transformation
- Profile versioning (audit trail)
- Built-in templates (invoice, receipt, W-2, etc.)

**Business Value**:
- Structured data extraction without custom code
- Reusable profiles across organizations
- Reduced time-to-value for new document types
- Self-service for business users

**Technical Highlights**:
- PostgreSQL JSONB for flexible schema storage
- Pydantic models for type safety
- Profile inheritance (clone and customize templates)
- Usage analytics per profile

**Deliverables**:
- Database schema with versioning
- Profile management API (10+ endpoints)
- 5+ built-in templates
- Field extractors for each strategy
- Visual profile editor (future phase)

---

### TASK-003: Structured Field Extraction (Bedrock Integration)
**Goal**: Use AWS Bedrock (Claude) for intelligent semantic field extraction

**Key Features**:
- Bedrock API integration (Converse API + Tool Use)
- LLM-based field extraction
- Cost optimization (Haiku vs Sonnet vs Opus)
- Fallback strategy (OCR → LLM only on low confidence)
- Cost tracking and budget enforcement

**Business Value**:
- Extract fields without rigid rules
- Handle layout variations automatically
- Multilingual support
- Competitive pricing vs Textract + post-processing

**Cost Analysis**:
```
1000 invoices/month:
- DTAT + Haiku:  $1.10/month (93% cheaper than Textract alone)
- DTAT + Sonnet: $13.50/month (comparable to Textract)
- Textract alone: $1.50/month (but no structured extraction)
- Textract + Bedrock (Lexitas approach): $15/month
```

**Technical Highlights**:
- Tool use for structured output (no JSON parsing)
- Token counting for cost estimation
- Model selection based on complexity
- Batch processing for efficiency

**Deliverables**:
- `BedrockExtractor` client wrapper
- `LLMFieldExtractor` strategy in profiles
- Cost tracking tables
- `/extract-fields` and `/extract-batch` endpoints
- Usage dashboards

---

### TASK-004: Batch Processing Support
**Goal**: Enable bulk document processing in single API request

**Key Features**:
- Multi-file upload (up to 1000 documents)
- ZIP file extraction
- Parallel processing (GPU utilization)
- Progress tracking (real-time status)
- Multiple export formats (JSON, CSV, Excel, ZIP)
- Auto-profile detection

**Business Value**:
- Enterprise scalability
- Efficient resource utilization
- Better user experience (upload once, get all results)
- Cost savings (batch Bedrock calls)

**Technical Highlights**:
- Async worker pool with semaphore
- FastAPI background tasks
- SQS integration (optional for scale)
- Result aggregation and export

**Deliverables**:
- Batch job management API
- Worker pool implementation
- Export functions (4 formats)
- Progress tracking UI
- Cleanup jobs for old batches

---

## Implementation Strategy

### Phase 1: Foundation (Months 1-2)
**Focus**: TASK-001 + Core infrastructure

```
Week 1-2:  Design normalized format, coordinate mapping
Week 3-4:  Implement TextractFormatter
Week 5-6:  Implement GoogleVisionFormatter, AzureOCRFormatter
Week 7-8:  Testing, documentation, migration guide
```

**Milestone**: DTAT can output in any major OCR format

### Phase 2: Profiles (Months 2-4)
**Focus**: TASK-002 + Profile system

```
Week 9-10:   Database schema, models, API
Week 11-12:  Extraction strategies (coordinate, keyword, table, regex)
Week 13-14:  Built-in templates, validation
Week 15-16:  Testing, profile documentation
```

**Milestone**: Users can create custom extraction profiles

### Phase 3: Intelligence (Months 4-5)
**Focus**: TASK-003 + Bedrock integration

```
Week 17-18:  Bedrock client, tool use implementation
Week 19-20:  LLM extraction strategy, cost tracking
Week 21-22:  Optimization (model selection, token limits)
Week 23-24:  Testing, cost analysis, documentation
```

**Milestone**: Intelligent semantic extraction available

### Phase 4: Scale (Month 5-6)
**Focus**: TASK-004 + Batch processing

```
Week 25-26:  Batch API, worker pool
Week 27-28:  Export formats, progress tracking
Week 29-30:  Testing, optimization
Week 31-32:  Polish, documentation, launch
```

**Milestone**: Production-ready batch processing

---

## Success Metrics

### Performance
- **Throughput**: 1000+ pages/hour (with GPU)
- **Latency**: < 2s per page (OCR) + < 3s (profile extraction)
- **Reliability**: 99.5% success rate
- **GPU Utilization**: 70%+ during batch processing

### Cost
- **OCR Cost**: $0 (local GPU) vs $1.50/1000 pages (Textract)
- **LLM Cost**: $0.001-$0.02 per document (Haiku-Sonnet)
- **Total Cost**: 85-95% cheaper than Textract + commercial OCR

### Adoption
- **Profiles Created**: 100+ custom profiles
- **Monthly Documents**: 10,000+ processed
- **Format Mix**: 40% Textract, 30% Google, 20% Azure, 10% native
- **User Satisfaction**: 4.5+ stars

---

## Dependencies & Prerequisites

### Infrastructure
- [ ] AWS EC2 g4dn.xlarge instance (Tesla T4 GPU)
- [ ] PostgreSQL database (for profiles)
- [ ] AWS Bedrock access (for LLM extraction)
- [ ] S3 bucket (optional for large batches)

### Technical
- [ ] Python 3.12+
- [ ] FastAPI
- [ ] SQLAlchemy + Alembic (migrations)
- [ ] boto3 (Bedrock client)
- [ ] pandas, openpyxl (export formats)

### Development
- [ ] Git workflow (feature branches)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Testing framework (pytest)
- [ ] Documentation (Sphinx or MkDocs)

---

## Risk Management

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LightOnOCR quality issues | High | Medium | Fallback to Textract, model fine-tuning |
| Bedrock API rate limits | Medium | Low | Request increase, implement caching |
| GPU memory constraints | High | Medium | Batch size optimization, model quantization |
| Profile complexity explosion | Medium | Medium | Template library, validation rules |

### Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Cost overruns (Bedrock) | High | Medium | Budget alerts, Haiku model default |
| User adoption low | High | Low | Templates, documentation, demos |
| Competition (new OCR services) | Medium | Medium | Focus on flexibility, profiles |

---

## Future Enhancements (Post-MVP)

### Visual Profile Editor
- Drag-and-drop field positioning on document preview
- Real-time extraction preview
- Auto-suggest extraction strategies

### Machine Learning
- Learn extraction patterns from corrections
- Auto-generate profiles from examples
- Anomaly detection

### Advanced Features
- Cross-field validation (line items sum to total)
- Multi-page correlation
- Hierarchical data (nested objects)
- Conditional extraction rules

### Integrations
- Webhook notifications
- Zapier/Make.com connectors
- Export to popular formats (QuickBooks, Xero)
- Slack/Teams notifications

---

## Reference Documents

### Internal
- [OCR API Formats](../OCR-API-FORMATS.md) - Detailed comparison of Textract/Google/Azure
- [DEPLOYMENT-LOG.md](../../DEPLOYMENT-LOG.md) - AWS deployment history
- [README.md](../../README.md) - Project overview
- [CLAUDE.md](../../CLAUDE.md) - Project instructions

### External Reference
- [Lexitas-OCR](../../../../Client%20POCs/Lexitas-OCR/) - Reference architecture for Textract + Bedrock pipeline

### API Documentation
- [AWS Textract API](https://docs.aws.amazon.com/textract/latest/dg/API_Reference.html)
- [Google Cloud Vision API](https://cloud.google.com/vision/docs/reference/rest)
- [Azure Computer Vision API](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)
- [AWS Bedrock API](https://docs.aws.amazon.com/bedrock/latest/APIReference/)

---

## Getting Started

To begin implementation:

1. **Review all task documents** to understand full scope
2. **Set up development environment** (GPU instance, PostgreSQL)
3. **Create feature branch** for TASK-001
4. **Implement normalized format** as foundation
5. **Build incrementally** with tests at each step

For questions or clarifications, refer to:
- Task-specific documents in `docs/tasks/`
- API format research in `docs/OCR-API-FORMATS.md`
- Deployment logs in `DEPLOYMENT-LOG.md`

---

**Last Updated**: 2026-01-29
**Status**: Planning Complete, Ready for Implementation
**Next Step**: Begin TASK-001 (Multi-Format Output Support)
