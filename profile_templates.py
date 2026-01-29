"""
Built-in Profile Templates for Common Document Types

Provides pre-configured extraction profiles for:
- Generic invoices
- Retail receipts
- W-2 tax forms
- Driver's licenses

Users can instantiate these templates and customize them for their needs.
"""

from typing import Dict, List, Optional
from profiles import (
    ExtractionProfile,
    FieldDefinition,
    FieldType,
    ExtractionStrategy,
    CoordinateBox,
    KeywordRule,
    TableColumnRule
)


# ==================== Template Definitions ====================

TEMPLATE_GENERIC_INVOICE = ExtractionProfile(
    name="template-generic-invoice",
    display_name="Generic Invoice Template",
    description="Standard invoice fields (works with most vendors)",
    document_type="invoice",
    is_template=True,
    fields=[
        FieldDefinition(
            name="invoice_number",
            label="Invoice Number",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Invoice #",
                direction="right",
                max_distance=150
            )
        ),
        FieldDefinition(
            name="invoice_date",
            label="Invoice Date",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Date:",
                direction="right",
                max_distance=150
            )
        ),
        FieldDefinition(
            name="vendor_name",
            label="Vendor Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.0, y=0.0, width=0.5, height=0.15, page=1)
        ),
        FieldDefinition(
            name="total_amount",
            label="Total Amount",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Total",
                direction="right",
                max_distance=200,
                pattern=r"\$?([0-9,]+\.\d{2})"
            ),
            min_value=0.0
        ),
        FieldDefinition(
            name="line_items",
            label="Line Items",
            field_type=FieldType.TEXT,
            required=False,
            strategy=ExtractionStrategy.TABLE_COLUMN,
            table_column_rule=TableColumnRule(
                table_index=0
            )
        )
    ]
)


TEMPLATE_RETAIL_RECEIPT = ExtractionProfile(
    name="template-retail-receipt",
    display_name="Retail Receipt Template",
    description="Point-of-sale receipts (restaurants, retail)",
    document_type="receipt",
    is_template=True,
    fields=[
        FieldDefinition(
            name="merchant_name",
            label="Merchant Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.2, y=0.0, width=0.6, height=0.1, page=1)
        ),
        FieldDefinition(
            name="transaction_date",
            label="Date",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.REGEX_PATTERN,
            regex_pattern=r"(\d{1,2}/\d{1,2}/\d{4})"
        ),
        FieldDefinition(
            name="subtotal",
            label="Subtotal",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Subtotal", direction="right", max_distance=100)
        ),
        FieldDefinition(
            name="tax",
            label="Tax",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Tax", direction="right", max_distance=100)
        ),
        FieldDefinition(
            name="total",
            label="Total",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(keyword="Total", direction="right", max_distance=100),
            min_value=0.0
        )
    ]
)


TEMPLATE_W2_TAX_FORM = ExtractionProfile(
    name="template-w2-tax-form",
    display_name="W-2 Wage and Tax Statement",
    description="IRS Form W-2 (standardized layout)",
    document_type="tax_form",
    is_template=True,
    fields=[
        FieldDefinition(
            name="employee_ssn",
            label="Employee SSN",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.15, width=0.3, height=0.05, page=1),
            validation_pattern=r"\d{3}-\d{2}-\d{4}"
        ),
        FieldDefinition(
            name="employer_ein",
            label="Employer EIN",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.22, width=0.3, height=0.05, page=1),
            validation_pattern=r"\d{2}-\d{7}"
        ),
        FieldDefinition(
            name="employee_name",
            label="Employee Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.0, y=0.15, width=0.4, height=0.1, page=1)
        ),
        FieldDefinition(
            name="employer_name",
            label="Employer Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.0, y=0.0, width=0.5, height=0.12, page=1)
        ),
        FieldDefinition(
            name="wages_box1",
            label="Wages, tips, other compensation (Box 1)",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.35, width=0.2, height=0.05, page=1),
            min_value=0.0
        ),
        FieldDefinition(
            name="federal_tax_withheld_box2",
            label="Federal income tax withheld (Box 2)",
            field_type=FieldType.CURRENCY,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.8, y=0.35, width=0.2, height=0.05, page=1),
            min_value=0.0
        ),
        FieldDefinition(
            name="social_security_wages_box3",
            label="Social security wages (Box 3)",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.42, width=0.2, height=0.05, page=1),
            min_value=0.0
        ),
        FieldDefinition(
            name="medicare_wages_box5",
            label="Medicare wages and tips (Box 5)",
            field_type=FieldType.CURRENCY,
            required=False,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.5, y=0.52, width=0.2, height=0.05, page=1),
            min_value=0.0
        )
    ]
)


TEMPLATE_DRIVERS_LICENSE = ExtractionProfile(
    name="template-drivers-license",
    display_name="Driver's License Template",
    description="US driver's license (standard fields)",
    document_type="identification",
    is_template=True,
    fields=[
        FieldDefinition(
            name="license_number",
            label="License Number",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="DL",
                direction="right",
                max_distance=100
            )
        ),
        FieldDefinition(
            name="full_name",
            label="Full Name",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.3, y=0.15, width=0.5, height=0.1, page=1)
        ),
        FieldDefinition(
            name="date_of_birth",
            label="Date of Birth",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="DOB",
                direction="right",
                max_distance=100
            )
        ),
        FieldDefinition(
            name="expiration_date",
            label="Expiration Date",
            field_type=FieldType.DATE,
            required=True,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="EXP",
                direction="right",
                max_distance=100
            )
        ),
        FieldDefinition(
            name="address",
            label="Address",
            field_type=FieldType.ADDRESS,
            required=False,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.3, y=0.35, width=0.6, height=0.15, page=1)
        ),
        FieldDefinition(
            name="sex",
            label="Sex",
            field_type=FieldType.TEXT,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="SEX",
                direction="right",
                max_distance=50
            ),
            allowed_values=["M", "F", "X"]
        ),
        FieldDefinition(
            name="height",
            label="Height",
            field_type=FieldType.TEXT,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="HGT",
                direction="right",
                max_distance=50
            )
        ),
        FieldDefinition(
            name="eyes",
            label="Eye Color",
            field_type=FieldType.TEXT,
            required=False,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="EYES",
                direction="right",
                max_distance=50
            ),
            allowed_values=["BLK", "BLU", "BRO", "GRY", "GRN", "HAZ", "MAR", "PNK"]
        ),
        FieldDefinition(
            name="state",
            label="Issuing State",
            field_type=FieldType.TEXT,
            required=True,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(x=0.0, y=0.0, width=0.3, height=0.1, page=1)
        )
    ]
)


# ==================== Template Registry ====================

BUILT_IN_TEMPLATES: Dict[str, ExtractionProfile] = {
    "template-generic-invoice": TEMPLATE_GENERIC_INVOICE,
    "template-retail-receipt": TEMPLATE_RETAIL_RECEIPT,
    "template-w2-tax-form": TEMPLATE_W2_TAX_FORM,
    "template-drivers-license": TEMPLATE_DRIVERS_LICENSE,
}


def get_all_templates() -> List[ExtractionProfile]:
    """
    Get all built-in templates.

    Returns:
        List of ExtractionProfile objects (templates)
    """
    return list(BUILT_IN_TEMPLATES.values())


def get_template_by_name(name: str) -> Optional[ExtractionProfile]:
    """
    Get a template by name.

    Args:
        name: Template name (e.g., "template-generic-invoice")

    Returns:
        ExtractionProfile if found, None otherwise
    """
    return BUILT_IN_TEMPLATES.get(name)


def instantiate_template(
    template_name: str,
    new_name: str,
    customizations: Optional[Dict] = None
) -> ExtractionProfile:
    """
    Create a new profile from a template with customizations.

    Args:
        template_name: Name of the template to instantiate
        new_name: Name for the new profile (must be unique)
        customizations: Optional dict of fields to override

    Returns:
        New ExtractionProfile instance (not a template)

    Raises:
        ValueError: If template not found or new_name conflicts with template

    Example:
        profile = instantiate_template(
            template_name="template-generic-invoice",
            new_name="acme-invoice",
            customizations={
                "display_name": "Acme Corp Invoice",
                "organization_id": "org-123"
            }
        )
    """
    # Get template
    template = get_template_by_name(template_name)
    if not template:
        raise ValueError(f"Template '{template_name}' not found")

    # Validate new name doesn't conflict with templates
    if new_name.startswith("template-"):
        raise ValueError("Custom profile names cannot start with 'template-'")

    # Clone template using model_copy()
    new_profile = template.model_copy(deep=True)

    # Reset template-specific fields
    new_profile.name = new_name
    new_profile.is_template = False
    new_profile.version = 1
    new_profile.created_at = None  # Will be set by database
    new_profile.updated_at = None

    # Apply customizations
    if customizations:
        for key, value in customizations.items():
            # Don't allow overriding critical fields
            if key in ['is_template', 'version']:
                continue
            if hasattr(new_profile, key):
                setattr(new_profile, key, value)

    return new_profile


def get_templates_by_document_type(doc_type: str) -> List[ExtractionProfile]:
    """
    Get templates filtered by document type.

    Args:
        doc_type: Document type (invoice, receipt, tax_form, identification)

    Returns:
        List of matching templates
    """
    return [
        template for template in BUILT_IN_TEMPLATES.values()
        if template.document_type == doc_type
    ]
