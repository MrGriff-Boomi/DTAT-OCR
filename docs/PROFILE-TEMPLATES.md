# Profile Templates

Built-in extraction profiles for common document types. These templates provide pre-configured field definitions and extraction strategies that work out-of-the-box for standard documents.

## Available Templates

### 1. Generic Invoice (`template-generic-invoice`)

Standard invoice fields that work with most vendors.

**Document Type:** `invoice`

**Fields:**
- **invoice_number** (TEXT, required) - Invoice number using keyword proximity ("Invoice #")
- **invoice_date** (DATE, required) - Invoice date using keyword proximity ("Date:")
- **vendor_name** (TEXT, required) - Vendor name from document header (coordinate-based)
- **total_amount** (CURRENCY, required) - Total amount with pattern matching and min value validation
- **line_items** (TEXT, optional) - Line items extracted from first table

**Best For:** General invoices, purchase orders, billing statements

**Example Usage:**
```python
from profile_templates import get_template_by_name

template = get_template_by_name("template-generic-invoice")
# Use with ProfileExtractor or instantiate for customization
```

---

### 2. Retail Receipt (`template-retail-receipt`)

Point-of-sale receipts from restaurants, retail stores, etc.

**Document Type:** `receipt`

**Fields:**
- **merchant_name** (TEXT, required) - Merchant name from top of receipt
- **transaction_date** (DATE, required) - Date using regex pattern matching
- **subtotal** (CURRENCY, optional) - Subtotal using keyword proximity
- **tax** (CURRENCY, optional) - Tax amount using keyword proximity
- **total** (CURRENCY, required) - Total with min value validation

**Best For:** Restaurant receipts, retail receipts, gas station receipts

**Example Usage:**
```python
from profile_templates import get_template_by_name

template = get_template_by_name("template-retail-receipt")
```

---

### 3. W-2 Tax Form (`template-w2-tax-form`)

IRS Form W-2 (Wage and Tax Statement) with standardized layout.

**Document Type:** `tax_form`

**Fields:**
- **employee_ssn** (TEXT, required) - SSN with pattern validation (###-##-####)
- **employer_ein** (TEXT, required) - EIN with pattern validation (##-#######)
- **employee_name** (TEXT, required) - Employee name
- **employer_name** (TEXT, required) - Employer name
- **wages_box1** (CURRENCY, required) - Box 1: Wages, tips, other compensation
- **federal_tax_withheld_box2** (CURRENCY, required) - Box 2: Federal income tax withheld
- **social_security_wages_box3** (CURRENCY, optional) - Box 3: Social security wages
- **medicare_wages_box5** (CURRENCY, optional) - Box 5: Medicare wages and tips

**Best For:** W-2 forms (standardized government form)

**Example Usage:**
```python
from profile_templates import get_template_by_name

template = get_template_by_name("template-w2-tax-form")
```

---

### 4. Driver's License (`template-drivers-license`)

US driver's license with standard fields.

**Document Type:** `identification`

**Fields:**
- **license_number** (TEXT, required) - License number using keyword proximity ("DL")
- **full_name** (TEXT, required) - Full name from document
- **date_of_birth** (DATE, required) - DOB using keyword proximity
- **expiration_date** (DATE, required) - Expiration date using keyword proximity
- **address** (ADDRESS, optional) - Address from document
- **sex** (TEXT, optional) - Sex with allowed values [M, F, X]
- **height** (TEXT, optional) - Height using keyword proximity
- **eyes** (TEXT, optional) - Eye color with allowed values [BLK, BLU, BRO, GRY, GRN, HAZ, MAR, PNK]
- **state** (TEXT, required) - Issuing state from document header

**Best For:** US driver's licenses, state ID cards

**Example Usage:**
```python
from profile_templates import get_template_by_name

template = get_template_by_name("template-drivers-license")
```

---

## Using Templates

### Option 1: Use Template Directly

Use the template as-is for document processing:

```python
from profile_templates import get_template_by_name
from extractors import ProfileExtractor

# Get template
template = get_template_by_name("template-generic-invoice")

# Extract fields from document
extractor = ProfileExtractor()
results = extractor.extract_all_fields(template, ocr_result)

print(results['fields']['invoice_number']['value'])
print(results['fields']['total_amount']['value'])
```

### Option 2: Instantiate and Customize

Create a custom profile based on a template:

```python
from profile_templates import instantiate_template
from database import create_profile

# Create custom profile from template
custom_profile = instantiate_template(
    template_name="template-generic-invoice",
    new_name="acme-invoice",
    customizations={
        "display_name": "Acme Corp Invoice",
        "organization_id": "org-123",
        "description": "Invoice format for Acme Corp with custom fields"
    }
)

# Save to database
record = create_profile(custom_profile)
print(f"Created profile ID: {record.id}")

# Now you can modify the profile further:
# - Add new fields
# - Adjust coordinate boxes
# - Change validation rules
```

### Option 3: API Endpoints

Use the REST API to work with templates:

**List all templates:**
```bash
curl http://localhost:8000/templates
```

**Get specific template:**
```bash
curl http://localhost:8000/templates/template-generic-invoice
```

**Get templates by document type:**
```bash
curl http://localhost:8000/templates/by-type/invoice
```

**Create profile from template:**
```bash
curl -X POST "http://localhost:8000/templates/template-generic-invoice/instantiate?new_name=my-invoice" \
  -H "Content-Type: application/json" \
  -u "admin:password" \
  -d '{
    "display_name": "My Custom Invoice",
    "organization_id": "org-456",
    "description": "Custom invoice profile"
  }'
```

---

## Seeding Templates into Database

Templates can be seeded into the database for use via API:

```bash
# Initialize database (if not already done)
python worker.py init

# Seed built-in templates
python worker.py seed-templates
```

This creates 4 template profiles in the database with `is_template=True`. Running multiple times is safe - existing templates will be skipped.

---

## Customizing Templates

After instantiating a template, you can customize it:

### 1. Adjust Field Configurations

```python
from profile_templates import instantiate_template

profile = instantiate_template(
    template_name="template-generic-invoice",
    new_name="custom-invoice"
)

# Adjust coordinate boxes for your specific invoice layout
for field in profile.fields:
    if field.name == "vendor_name":
        field.coordinate_box.y = 0.05  # Move up slightly
        field.coordinate_box.height = 0.10  # Make taller

# Adjust keyword rules
for field in profile.fields:
    if field.name == "invoice_number":
        field.keyword_rule.keyword = "Invoice No."  # Different keyword
        field.keyword_rule.max_distance = 200  # Increase search distance
```

### 2. Add New Fields

```python
from profiles import FieldDefinition, FieldType, ExtractionStrategy, KeywordRule

# Add PO number field
po_field = FieldDefinition(
    name="po_number",
    label="Purchase Order Number",
    field_type=FieldType.TEXT,
    required=False,
    strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
    keyword_rule=KeywordRule(
        keyword="PO #",
        direction="right",
        max_distance=150
    )
)

profile.fields.append(po_field)
```

### 3. Modify Validation Rules

```python
# Adjust min/max values
for field in profile.fields:
    if field.name == "total_amount":
        field.min_value = 100.0  # Require minimum $100
        field.max_value = 10000.0  # Cap at $10,000

# Add allowed values
for field in profile.fields:
    if field.name == "payment_terms":
        field.allowed_values = ["Net 30", "Net 60", "Due on Receipt"]
```

### 4. Save Customizations

```python
from database import create_profile, update_profile

# For new profile
record = create_profile(profile)

# For updating existing profile
record = update_profile(profile.id, profile)
```

---

## Template Development Tips

### When to Use Each Strategy

**COORDINATE** - Use when field is always in same location:
- Logo/header information (company name, address)
- Form boxes (W-2, driver's license)
- Structured tables with fixed positions

**KEYWORD_PROXIMITY** - Use when field has consistent label:
- "Invoice #: 12345"
- "Date: 2024-01-15"
- "Total: $1,234.56"

**TABLE_COLUMN** - Use for tabular data:
- Line items on invoice
- Transaction history
- Product lists

**REGEX_PATTERN** - Use for known patterns:
- Phone numbers: `\d{3}-\d{3}-\d{4}`
- SSN: `\d{3}-\d{2}-\d{4}`
- Invoice numbers: `INV-\d{5}`

**SEMANTIC_LLM** - Use when context matters:
- Ambiguous fields ("amount due" vs "amount paid")
- Unstructured text
- Fields requiring interpretation

### Coordinate System

All coordinates are normalized (0.0 to 1.0):
- `x=0.0` is left edge, `x=1.0` is right edge
- `y=0.0` is top edge, `y=1.0` is bottom edge
- `width` and `height` are also 0.0-1.0 scale

Example:
```python
CoordinateBox(
    x=0.1,      # 10% from left
    y=0.2,      # 20% from top
    width=0.3,  # 30% of page width
    height=0.1, # 10% of page height
    page=1      # First page
)
```

### Field Types and Transformations

Each field type has automatic transformations:

| Field Type | Transformation | Example Input | Example Output |
|------------|----------------|---------------|----------------|
| TEXT | None | "ABC-123" | "ABC-123" |
| NUMBER | Parse number | "1,234.56" | 1234.56 |
| CURRENCY | Parse to Decimal | "$1,234.56" | Decimal("1234.56") |
| DATE | Parse to datetime | "01/15/2024" | datetime(2024, 1, 15) |
| EMAIL | None | "test@example.com" | "test@example.com" |
| PHONE | Normalize | "(555) 123-4567" | "+1-555-123-4567" |
| ADDRESS | None | "123 Main St" | "123 Main St" |
| BOOLEAN | Parse bool | "yes" | True |

---

## Testing Templates

### Unit Tests

```python
from profile_templates import get_template_by_name

# Test template exists
template = get_template_by_name("template-generic-invoice")
assert template is not None
assert template.is_template == True
assert len(template.fields) > 0

# Test field configuration
invoice_num = next(f for f in template.fields if f.name == "invoice_number")
assert invoice_num.required == True
assert invoice_num.field_type == FieldType.TEXT
```

### Integration Tests

```python
from profile_templates import get_template_by_name
from extractors import ProfileExtractor

# Mock OCR result
ocr_result = {
    'blocks': [
        {'text': 'Invoice # 12345', ...},
        {'text': 'Date: 2024-01-15', ...},
        {'text': 'Total: $1,234.56', ...}
    ]
}

# Extract using template
template = get_template_by_name("template-generic-invoice")
extractor = ProfileExtractor()
results = extractor.extract_all_fields(template, ocr_result)

# Verify results
assert results['fields']['invoice_number']['value'] == '12345'
assert results['statistics']['extracted'] >= 3
```

### API Tests

See `test_template_api.py` for complete API integration tests.

---

## Future Templates

Planned templates for future releases:

- **Passport** - International passport data page
- **Bank Statement** - Monthly bank statements
- **Utility Bill** - Electric, gas, water bills
- **Medical Claim** - Insurance claim forms
- **Purchase Order** - Standard PO format
- **Packing Slip** - Shipping packing slips
- **Credit Card Statement** - Monthly statements
- **Pay Stub** - Payroll check stubs

To request a new template, open an issue with:
1. Document type and use case
2. Sample document (redacted/anonymized)
3. Fields to extract
4. Validation requirements

---

## Related Documentation

- [Profiles Documentation](TASK-002-Profile-Schema-Management-System.md) - Complete profile system guide
- [Field Extractors](../extractors.py) - Extraction strategy implementations
- [Field Utilities](../field_utils.py) - Transformers and validators
- [API Documentation](http://localhost:8000/docs) - Swagger API docs
