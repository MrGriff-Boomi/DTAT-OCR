# TASK-003: Structured Field Extraction (Bedrock LLM Integration)

**Status**: Not Started
**Priority**: High
**Depends On**: TASK-001 (Multi-Format Output), TASK-002 (Profile System)
**Created**: 2026-01-29

## Executive Summary

Integrate AWS Bedrock (Claude/other LLMs) to provide intelligent, semantic field extraction from documents. This goes beyond coordinate-based OCR by understanding document context, handling layout variations, and extracting structured data based on natural language descriptions rather than rigid extraction rules.

## Problem Statement

Traditional OCR extraction methods (coordinates, keyword proximity, regex) are brittle:
- Break when document layouts change
- Can't understand semantic context ("extract all line items")
- Require manual mapping for each vendor/format variation
- Struggle with handwritten or low-quality scans
- Miss implicit relationships between fields

LLM-based extraction provides:
- **Semantic understanding**: "Find the invoice total" works regardless of label variations ("Total", "Amount Due", "Balance")
- **Layout flexibility**: Adapts to different document formats automatically
- **Context awareness**: Understands relationships (line items sum to total, dates should be chronological)
- **Multi-lingual**: Handles documents in any language
- **Intelligent fallback**: When traditional OCR fails, LLM can interpret ambiguous text

## Use Cases

### Invoice Processing
```
Input: Scanned invoice (varied layouts)
Prompt: "Extract: invoice_number, date, vendor_name, total_amount, line_items (description, quantity, price)"
Output: Structured JSON with all fields, even if labels differ
```

### Receipt Expense Tracking
```
Input: Crumpled receipt photo
Prompt: "Extract merchant name, date, items purchased, subtotal, tax, tip, total"
Output: Clean structured data for expense reports
```

### Form Filling
```
Input: PDF application form (partially filled)
Prompt: "Extract all filled fields and their values"
Output: Key-value pairs for database import
```

### Contract Analysis
```
Input: Multi-page legal contract
Prompt: "Extract: parties involved, contract date, termination clauses, payment terms"
Output: Summary of key contract terms
```

## Architecture

### High-Level Flow

```
Document (PDF/Image)
    │
    ▼
┌─────────────────────────────┐
│   OCR Engine (LightOnOCR)   │  Extract raw text + geometry
│   - Text blocks              │
│   - Bounding boxes           │
│   - Tables                   │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Text Preparation            │  Format for LLM consumption
│  - Page-by-page text         │
│  - Table markdown            │
│  - Coordinate hints          │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Bedrock API Call            │  Structured extraction
│  - Model: Claude Sonnet 4.5  │
│  - Tool use (structured out) │
│  - Extraction schema         │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Validation & Post-Process   │  Clean and validate
│  - Type coercion             │
│  - Business rules            │
│  - Confidence scoring        │
└─────────────────────────────┘
    │
    ▼
Structured JSON Output
```

### Bedrock Integration Strategy

#### Option 1: Tool Use (Recommended)
```python
# Define extraction schema as tools
tools = [
    {
        "name": "extract_invoice_fields",
        "description": "Extract fields from an invoice document",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "invoice_date": {"type": "string", "format": "date"},
                "vendor_name": {"type": "string"},
                "vendor_address": {"type": "string"},
                "total_amount": {"type": "number"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "total": {"type": "number"}
                        }
                    }
                }
            },
            "required": ["invoice_number", "invoice_date", "total_amount"]
        }
    }
]

# Call Bedrock with tools
response = bedrock.converse(
    modelId="anthropic.claude-sonnet-4-5-20251101-v2:0",
    messages=[
        {
            "role": "user",
            "content": [
                {"text": f"Extract structured data from this invoice:\n\n{ocr_text}"}
            ]
        }
    ],
    toolConfig={"tools": tools}
)

# Parse tool use
tool_call = response['output']['message']['content'][0]['toolUse']
extracted_fields = tool_call['input']
```

#### Option 2: Prompt + JSON Output
```python
# Simpler but less type-safe
prompt = f"""
Extract the following fields from this invoice document:

- invoice_number (string)
- invoice_date (YYYY-MM-DD)
- vendor_name (string)
- total_amount (number)
- line_items (array of objects with description, quantity, unit_price, total)

Document text:
{ocr_text}

Return ONLY valid JSON with extracted fields. If a field is not found, use null.
"""

response = bedrock.converse(
    modelId="anthropic.claude-sonnet-4-5-20251101-v2:0",
    messages=[{"role": "user", "content": [{"text": prompt}]}]
)

extracted_fields = json.loads(response['output']['message']['content'][0]['text'])
```

### Cost Optimization

**Challenge**: Bedrock API costs scale with input/output tokens
- Input: ~$3.00 per million input tokens (Claude Sonnet 4.5)
- Output: ~$15.00 per million output tokens

**Strategies**:
1. **Use Bedrock only when needed**
   - Level 1: Native extraction (free)
   - Level 2: Local OCR (free after setup)
   - Level 3: Bedrock extraction (paid)
   - Only escalate if confidence < threshold

2. **Optimize prompt size**
   - Send only relevant text pages (not full 100-page document)
   - Use page-level extraction for long documents
   - Summarize repetitive content (e.g., "30 more similar line items")

3. **Batch processing**
   - Extract multiple fields in single API call
   - Use tool use for structured output (no JSON parsing retries)
   - Cache common prompts

4. **Model selection**
   - Claude Haiku: Fast, cheap, good for simple extraction ($0.25/$1.25 per MTok)
   - Claude Sonnet: Balanced, recommended ($3/$15 per MTok)
   - Claude Opus: Most capable, use for complex documents ($15/$75 per MTok)

**Estimated Costs**:
```
Single-page invoice (2000 tokens input, 500 tokens output):
- Haiku:  $0.0005 + $0.0006 = $0.0011 per document
- Sonnet: $0.006 + $0.0075 = $0.0135 per document
- Opus:   $0.030 + $0.0375 = $0.0675 per document

1000 invoices/month:
- Haiku:  $1.10/month
- Sonnet: $13.50/month
- Opus:   $67.50/month

Compare to AWS Textract:
- Textract: $1.50 per 1000 pages = $1.50/month
- DTAT + Haiku: ~$1.10/month (comparable!)
```

## Implementation

### Bedrock Client Wrapper

```python
import boto3
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class BedrockExtractor:
    """AWS Bedrock client for document field extraction"""

    def __init__(
        self,
        model_id: str = "anthropic.claude-sonnet-4-5-20251101-v2:0",
        region: str = "us-east-1"
    ):
        self.bedrock = boto3.client('bedrock-runtime', region_name=region)
        self.model_id = model_id

    def extract_fields(
        self,
        document_text: str,
        extraction_schema: Dict[str, Any],
        instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured fields using Bedrock with tool use.

        Args:
            document_text: OCR text from document
            extraction_schema: JSON schema defining fields to extract
            instructions: Optional additional instructions

        Returns:
            Extracted fields as dictionary
        """
        # Convert schema to Bedrock tool definition
        tool = self._schema_to_tool(extraction_schema)

        # Build prompt
        prompt = self._build_extraction_prompt(
            document_text,
            extraction_schema,
            instructions
        )

        # Call Bedrock
        response = self.bedrock.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            toolConfig={"tools": [tool]}
        )

        # Parse tool use response
        return self._parse_tool_response(response)

    def _schema_to_tool(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert extraction schema to Bedrock tool definition"""
        return {
            "toolSpec": {
                "name": "extract_document_fields",
                "description": "Extract structured fields from document text",
                "inputSchema": {
                    "json": schema
                }
            }
        }

    def _build_extraction_prompt(
        self,
        document_text: str,
        schema: Dict[str, Any],
        instructions: Optional[str]
    ) -> str:
        """Build extraction prompt"""
        prompt = "Extract structured data from the following document.\n\n"

        if instructions:
            prompt += f"Instructions: {instructions}\n\n"

        # Add field descriptions
        prompt += "Fields to extract:\n"
        for field_name, field_def in schema.get('properties', {}).items():
            field_type = field_def.get('type', 'string')
            field_desc = field_def.get('description', '')
            prompt += f"- {field_name} ({field_type}): {field_desc}\n"

        prompt += f"\nDocument text:\n{document_text}\n\n"
        prompt += "Use the extract_document_fields tool to return the extracted data."

        return prompt

    def _parse_tool_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Bedrock tool use response"""
        content = response['output']['message']['content']

        # Find tool use block
        for block in content:
            if 'toolUse' in block:
                return block['toolUse']['input']

        raise ValueError("No tool use found in Bedrock response")

    def extract_with_retry(
        self,
        document_text: str,
        schema: Dict[str, Any],
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Extract fields with retry logic"""
        last_error = None

        for attempt in range(max_retries):
            try:
                result = self.extract_fields(document_text, schema)

                # Validate result
                if self._validate_extraction(result, schema):
                    return result

            except Exception as e:
                last_error = e
                continue

        raise Exception(f"Extraction failed after {max_retries} attempts: {last_error}")

    def _validate_extraction(self, result: Dict, schema: Dict) -> bool:
        """Validate extracted data against schema"""
        required = schema.get('required', [])

        # Check required fields
        for field in required:
            if field not in result or result[field] is None:
                return False

        return True
```

### Integration with Profile System

```python
class LLMFieldExtractor(FieldExtractor):
    """LLM-based semantic extraction (from TASK-002)"""

    def __init__(self, bedrock_client: BedrockExtractor):
        self.bedrock = bedrock_client

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Any, float, Optional[Dict]]:
        """
        Extract field using LLM semantic understanding.

        Uses field_def.llm_prompt for custom instructions.
        """
        # Get document text
        full_text = self._get_page_text(ocr_result, page)

        # Build extraction schema for single field
        schema = {
            "type": "object",
            "properties": {
                field_def.name: {
                    "type": self._field_type_to_json_type(field_def.field_type),
                    "description": field_def.label
                }
            },
            "required": [field_def.name] if field_def.required else []
        }

        # Extract using Bedrock
        try:
            result = self.bedrock.extract_fields(
                full_text,
                schema,
                instructions=field_def.llm_prompt
            )

            value = result.get(field_def.name)
            confidence = 0.85  # LLM extraction has high confidence

            # Try to find location in OCR result
            location = self._find_value_location(value, ocr_result)

            return value, confidence, location

        except Exception as e:
            logger.error(f"LLM extraction failed for {field_def.name}: {e}")
            return None, 0.0, None

    def _field_type_to_json_type(self, field_type: FieldType) -> str:
        """Convert FieldType to JSON Schema type"""
        mapping = {
            FieldType.TEXT: "string",
            FieldType.NUMBER: "number",
            FieldType.CURRENCY: "number",
            FieldType.DATE: "string",
            FieldType.EMAIL: "string",
            FieldType.PHONE: "string",
            FieldType.ADDRESS: "string",
            FieldType.BOOLEAN: "boolean"
        }
        return mapping.get(field_type, "string")

    def _get_page_text(self, ocr_result: Dict, page: int) -> str:
        """Extract text for specific page"""
        blocks = [
            b for b in ocr_result.get('blocks', [])
            if b.get('page', 1) == page
        ]
        return '\n'.join(b['text'] for b in blocks)

    def _find_value_location(self, value: Any, ocr_result: Dict) -> Optional[Dict]:
        """Try to locate extracted value in OCR result"""
        value_str = str(value)

        for block in ocr_result.get('blocks', []):
            if value_str in block['text']:
                return block['geometry']['boundingBox']

        return None
```

### Bulk Extraction API

```python
@app.post("/extract-fields")
async def extract_fields_endpoint(
    file: UploadFile,
    schema: Dict[str, Any] = Body(...),
    instructions: Optional[str] = Body(None),
    use_llm: bool = Body(True)
):
    """
    Extract structured fields from document using LLM.

    Example:
    POST /extract-fields
    - file: invoice.pdf
    - schema: {
        "type": "object",
        "properties": {
          "invoice_number": {"type": "string"},
          "total": {"type": "number"}
        },
        "required": ["invoice_number", "total"]
      }
    - instructions: "This is a vendor invoice"

    Response:
    {
        "document_id": 123,
        "extracted_fields": {
            "invoice_number": "INV-2024-001",
            "total": 1234.56
        },
        "confidence": 0.92,
        "processing_time_ms": 2500,
        "cost_usd": 0.0135
    }
    """
    # Run OCR first
    document = await save_uploaded_document(file)
    ocr_result = await run_ocr_pipeline(document.id)

    if not use_llm:
        return {"error": "LLM extraction required for this endpoint"}

    # Extract using Bedrock
    bedrock = BedrockExtractor()
    full_text = extract_full_text(ocr_result)

    start_time = time.time()

    extracted = bedrock.extract_fields(
        document_text=full_text,
        extraction_schema=schema,
        instructions=instructions
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Estimate cost
    input_tokens = count_tokens(full_text)
    output_tokens = count_tokens(json.dumps(extracted))
    cost_usd = calculate_bedrock_cost(
        bedrock.model_id,
        input_tokens,
        output_tokens
    )

    # Save to database
    update_document_extracted_fields(document.id, extracted)

    return {
        "document_id": document.id,
        "extracted_fields": extracted,
        "confidence": 0.85,
        "processing_time_ms": processing_time_ms,
        "cost_usd": round(cost_usd, 4),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens
        }
    }

@app.post("/extract-batch")
async def extract_batch_fields(
    files: List[UploadFile],
    schema: Dict[str, Any] = Body(...),
    instructions: Optional[str] = Body(None)
):
    """
    Extract fields from multiple documents in parallel.

    Uses asyncio to parallelize Bedrock API calls.
    """
    tasks = []

    for file in files:
        task = extract_fields_endpoint(
            file=file,
            schema=schema,
            instructions=instructions
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        "total": len(files),
        "successful": sum(1 for r in results if not isinstance(r, Exception)),
        "failed": sum(1 for r in results if isinstance(r, Exception)),
        "results": results
    }
```

### Cost Tracking

```python
# Add to database schema
ALTER TABLE documents ADD COLUMN bedrock_cost_usd DECIMAL(10, 6);
ALTER TABLE documents ADD COLUMN bedrock_input_tokens INTEGER;
ALTER TABLE documents ADD COLUMN bedrock_output_tokens INTEGER;
ALTER TABLE documents ADD COLUMN bedrock_model VARCHAR(100);

CREATE TABLE bedrock_usage (
    id SERIAL PRIMARY KEY,
    organization_id VARCHAR(255),
    model_id VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10, 6),
    document_count INTEGER,
    date DATE DEFAULT CURRENT_DATE
);

CREATE INDEX idx_bedrock_usage_org_date ON bedrock_usage(organization_id, date DESC);

def calculate_bedrock_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate Bedrock API cost"""
    pricing = {
        "anthropic.claude-3-haiku": (0.00025, 0.00125),
        "anthropic.claude-sonnet-4-5": (0.003, 0.015),
        "anthropic.claude-3-5-sonnet": (0.003, 0.015),
        "anthropic.claude-opus-4-5": (0.015, 0.075)
    }

    input_price, output_price = pricing.get(model_id, (0.003, 0.015))

    cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
    return cost

@app.get("/usage/bedrock")
async def get_bedrock_usage(
    organization_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    Get Bedrock usage and cost statistics.

    Returns daily/monthly aggregated costs.
    """
    query = "SELECT date, SUM(cost_usd), SUM(document_count) FROM bedrock_usage WHERE 1=1"
    params = []

    if organization_id:
        query += " AND organization_id = ?"
        params.append(organization_id)

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " GROUP BY date ORDER BY date DESC"

    results = db.execute(query, params)

    return {
        "usage": [
            {
                "date": row[0],
                "cost_usd": float(row[1]),
                "documents": row[2]
            }
            for row in results
        ],
        "total_cost": sum(float(row[1]) for row in results),
        "total_documents": sum(row[2] for row in results)
    }
```

## Configuration

```python
# config.py additions

# Bedrock LLM extraction
ENABLE_BEDROCK_EXTRACTION = os.getenv('ENABLE_BEDROCK_EXTRACTION', 'false').lower() == 'true'
BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-sonnet-4-5-20251101-v2:0')
BEDROCK_REGION = os.getenv('BEDROCK_REGION', 'us-east-1')

# When to use Bedrock
BEDROCK_MIN_CONFIDENCE_TRIGGER = float(os.getenv('BEDROCK_MIN_CONFIDENCE_TRIGGER', '70'))  # Escalate if OCR confidence < 70%
BEDROCK_DOCUMENT_TYPES = os.getenv('BEDROCK_DOCUMENT_TYPES', 'all')  # 'all', 'invoice,receipt', etc.

# Cost controls
BEDROCK_MAX_COST_PER_DOCUMENT = float(os.getenv('BEDROCK_MAX_COST_PER_DOCUMENT', '0.10'))  # Fail if estimated cost > $0.10
BEDROCK_MONTHLY_BUDGET_USD = float(os.getenv('BEDROCK_MONTHLY_BUDGET_USD', '1000'))

# Optimization
BEDROCK_MAX_INPUT_TOKENS = int(os.getenv('BEDROCK_MAX_INPUT_TOKENS', '100000'))  # Truncate long documents
BEDROCK_USE_HAIKU_FOR_SIMPLE = os.getenv('BEDROCK_USE_HAIKU_FOR_SIMPLE', 'true').lower() == 'true'  # Use Haiku for < 5 fields
```

## Testing Strategy

### Unit Tests
```python
@pytest.fixture
def bedrock_client():
    return BedrockExtractor(model_id="anthropic.claude-3-haiku")

def test_extract_invoice_fields(bedrock_client):
    """Test invoice field extraction"""
    document_text = """
    INVOICE

    Invoice #: INV-2024-001
    Date: January 15, 2024

    Bill To: ACME Corp

    Description              Qty    Price    Total
    Widget A                  10    $50.00   $500.00
    Widget B                   5    $30.00   $150.00

    Subtotal: $650.00
    Tax: $52.00
    Total: $702.00
    """

    schema = {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "date": {"type": "string"},
            "total": {"type": "number"}
        },
        "required": ["invoice_number", "total"]
    }

    result = bedrock_client.extract_fields(document_text, schema)

    assert result['invoice_number'] == 'INV-2024-001'
    assert result['date'] == '2024-01-15'
    assert result['total'] == 702.00

def test_extraction_cost_limit(bedrock_client):
    """Test cost limiting"""
    # Generate huge document
    large_text = "Lorem ipsum " * 100000  # ~200k tokens

    schema = {"type": "object", "properties": {"summary": {"type": "string"}}}

    # Should truncate or fail if cost > limit
    with pytest.raises(Exception, match="exceeds cost limit"):
        bedrock_client.extract_fields(large_text, schema)

@pytest.mark.integration
def test_profile_with_llm_extraction():
    """Test profile using LLM extraction strategy"""
    profile = ExtractionProfile(
        name="test-llm-invoice",
        document_type="invoice",
        fields=[
            FieldDefinition(
                name="vendor_name",
                label="Vendor Name",
                field_type=FieldType.TEXT,
                required=True,
                strategy=ExtractionStrategy.SEMANTIC_LLM,
                llm_prompt="Extract the name of the company that issued this invoice"
            ),
            FieldDefinition(
                name="line_items",
                label="Line Items",
                field_type=FieldType.TEXT,
                required=False,
                strategy=ExtractionStrategy.SEMANTIC_LLM,
                llm_prompt="Extract all line items as an array of objects with fields: description, quantity, unit_price, total"
            )
        ]
    )

    # Process test invoice
    with open('test_invoice.pdf', 'rb') as f:
        result = process_with_profile(f, profile_id=profile.id)

    fields = get_extracted_fields(result['document_id'])

    assert fields['fields']['vendor_name']['value'] is not None
    assert isinstance(fields['fields']['line_items']['value'], list)
```

### Integration Tests
```python
@pytest.mark.integration
@pytest.mark.aws
def test_bedrock_api_connection():
    """Test Bedrock API connectivity"""
    client = BedrockExtractor()

    result = client.extract_fields(
        "Invoice #12345, Total: $100.00",
        {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "number"}
            }
        }
    )

    assert result['invoice_number'] == '12345'
    assert result['total'] == 100.00

@pytest.mark.integration
def test_cost_tracking():
    """Test cost tracking and reporting"""
    # Process document with Bedrock
    with open('sample_invoice.pdf', 'rb') as f:
        result = extract_fields_endpoint(
            file=f,
            schema={"type": "object", "properties": {"total": {"type": "number"}}}
        )

    # Check cost was tracked
    doc = get_document(result['document_id'])
    assert doc.bedrock_cost_usd > 0
    assert doc.bedrock_input_tokens > 0
    assert doc.bedrock_output_tokens > 0

    # Check usage table updated
    usage = get_bedrock_usage(start_date=date.today())
    assert usage['total_cost'] >= doc.bedrock_cost_usd
```

## Implementation Phases

### Phase 1: Bedrock Integration (Week 1-2)
- [ ] BedrockExtractor client wrapper
- [ ] Tool use implementation
- [ ] Cost calculation and tracking
- [ ] Error handling and retries
- [ ] Unit tests

### Phase 2: Profile Integration (Week 3)
- [ ] LLMFieldExtractor implementation
- [ ] Add SEMANTIC_LLM strategy to profiles
- [ ] Update ProfileExtractor orchestrator
- [ ] Integration tests with profiles

### Phase 3: API Endpoints (Week 4)
- [ ] /extract-fields endpoint
- [ ] /extract-batch endpoint
- [ ] /usage/bedrock endpoint
- [ ] API documentation

### Phase 4: Cost Optimization (Week 5)
- [ ] Model selection (Haiku for simple, Sonnet for complex)
- [ ] Token counting and truncation
- [ ] Monthly budget enforcement
- [ ] Cost alerts and notifications

### Phase 5: Advanced Features (Week 6-7)
- [ ] Multi-page document handling
- [ ] Incremental extraction (extract more fields on retry)
- [ ] Extraction confidence tuning
- [ ] A/B testing (OCR vs LLM accuracy)

### Phase 6: Monitoring & Optimization (Week 8)
- [ ] CloudWatch metrics for Bedrock usage
- [ ] Cost dashboards
- [ ] Performance benchmarks
- [ ] Documentation and examples

## Success Metrics

- **Extraction Accuracy**: 95%+ for LLM-based extraction
- **Cost Efficiency**: < $0.02 per document average
- **Performance**: < 5s per document (including Bedrock latency)
- **Reliability**: 99.5% success rate with retry logic
- **Cost Predictability**: Stay within monthly budgets

## Migration from Lexitas Architecture

The Lexitas-OCR reference architecture uses:
1. AWS Textract for OCR
2. Text cleaning in Boomi
3. Bedrock for structured extraction

DTAT improves on this by:
- **Replacing Textract** with free LightOnOCR (save $1.50/1000 pages)
- **Using Bedrock directly** (no intermediate Boomi orchestration)
- **Unified API** (single endpoint for OCR + extraction)
- **Profile system** (reusable extraction schemas vs hardcoded Boomi logic)

**Cost Comparison (1000 invoices/month)**:
```
Lexitas architecture:
- Textract: $1.50
- Bedrock: $13.50 (Sonnet)
- Total: $15.00/month

DTAT architecture:
- LightOnOCR: $0 (local GPU)
- Bedrock: $13.50 (Sonnet)
- Total: $13.50/month (10% savings)

DTAT with Haiku:
- LightOnOCR: $0
- Bedrock: $1.10 (Haiku)
- Total: $1.10/month (93% savings!)
```

## Related Documents
- TASK-001: Multi-Format Output Support
- TASK-002: Profile & Schema Management System
- docs/OCR-API-FORMATS.md
- Client POCs/Lexitas-OCR/ (reference architecture)

## References
- [AWS Bedrock API](https://docs.aws.amazon.com/bedrock/latest/APIReference/)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Claude Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
