"""
Tests for profile templates
"""

from profile_templates import (
    get_all_templates,
    get_template_by_name,
    instantiate_template,
    get_templates_by_document_type,
    TEMPLATE_GENERIC_INVOICE,
    TEMPLATE_RETAIL_RECEIPT,
    TEMPLATE_W2_TAX_FORM,
    TEMPLATE_DRIVERS_LICENSE
)
from profiles import FieldType, ExtractionStrategy


def test_all_templates_exist():
    """Test that all 4 templates are available."""
    print('='*60)
    print('TESTING ALL TEMPLATES EXIST')
    print('='*60)

    templates = get_all_templates()
    assert len(templates) == 4, f"Expected 4 templates, got {len(templates)}"

    template_names = [t.name for t in templates]
    assert "template-generic-invoice" in template_names
    assert "template-retail-receipt" in template_names
    assert "template-w2-tax-form" in template_names
    assert "template-drivers-license" in template_names

    print(f"[PASS] All 4 templates found: {template_names}")


def test_get_template_by_name():
    """Test retrieving templates by name."""
    print('\n' + '='*60)
    print('TESTING GET TEMPLATE BY NAME')
    print('='*60)

    # Test valid template
    invoice = get_template_by_name("template-generic-invoice")
    assert invoice is not None
    assert invoice.name == "template-generic-invoice"
    assert invoice.is_template == True
    assert invoice.document_type == "invoice"
    print(f"[PASS] Retrieved invoice template: {invoice.display_name}")

    # Test invalid template
    invalid = get_template_by_name("non-existent-template")
    assert invalid is None
    print("[PASS] Returns None for non-existent template")


def test_invoice_template_fields():
    """Test invoice template has correct fields."""
    print('\n' + '='*60)
    print('TESTING INVOICE TEMPLATE FIELDS')
    print('='*60)

    template = TEMPLATE_GENERIC_INVOICE
    assert len(template.fields) == 5

    field_names = [f.name for f in template.fields]
    assert "invoice_number" in field_names
    assert "invoice_date" in field_names
    assert "vendor_name" in field_names
    assert "total_amount" in field_names
    assert "line_items" in field_names

    # Check specific field configurations
    invoice_num = next(f for f in template.fields if f.name == "invoice_number")
    assert invoice_num.required == True
    assert invoice_num.field_type == FieldType.TEXT
    assert invoice_num.strategy == ExtractionStrategy.KEYWORD_PROXIMITY

    total = next(f for f in template.fields if f.name == "total_amount")
    assert total.field_type == FieldType.CURRENCY
    assert total.min_value == 0.0

    print(f"[PASS] Invoice template has 5 fields with correct configuration")


def test_receipt_template_fields():
    """Test receipt template has correct fields."""
    print('\n' + '='*60)
    print('TESTING RECEIPT TEMPLATE FIELDS')
    print('='*60)

    template = TEMPLATE_RETAIL_RECEIPT
    assert len(template.fields) == 5

    field_names = [f.name for f in template.fields]
    assert "merchant_name" in field_names
    assert "transaction_date" in field_names
    assert "subtotal" in field_names
    assert "tax" in field_names
    assert "total" in field_names

    # Check date field uses regex
    date_field = next(f for f in template.fields if f.name == "transaction_date")
    assert date_field.strategy == ExtractionStrategy.REGEX_PATTERN
    assert date_field.regex_pattern is not None

    print(f"[PASS] Receipt template has 5 fields with correct configuration")


def test_w2_template_fields():
    """Test W-2 template has correct fields."""
    print('\n' + '='*60)
    print('TESTING W-2 TEMPLATE FIELDS')
    print('='*60)

    template = TEMPLATE_W2_TAX_FORM
    assert len(template.fields) >= 6  # At least 6 fields

    field_names = [f.name for f in template.fields]
    assert "employee_ssn" in field_names
    assert "employer_ein" in field_names
    assert "wages_box1" in field_names
    assert "federal_tax_withheld_box2" in field_names

    # Check SSN validation pattern
    ssn_field = next(f for f in template.fields if f.name == "employee_ssn")
    assert ssn_field.validation_pattern is not None
    assert "\\d{3}-\\d{2}-\\d{4}" in ssn_field.validation_pattern

    print(f"[PASS] W-2 template has {len(template.fields)} fields with validation patterns")


def test_drivers_license_template_fields():
    """Test driver's license template has correct fields."""
    print('\n' + '='*60)
    print('TESTING DRIVERS LICENSE TEMPLATE FIELDS')
    print('='*60)

    template = TEMPLATE_DRIVERS_LICENSE
    assert len(template.fields) >= 5

    field_names = [f.name for f in template.fields]
    assert "license_number" in field_names
    assert "full_name" in field_names
    assert "date_of_birth" in field_names
    assert "expiration_date" in field_names

    # Check sex field has allowed values
    if "sex" in field_names:
        sex_field = next(f for f in template.fields if f.name == "sex")
        assert sex_field.allowed_values is not None
        assert "M" in sex_field.allowed_values
        assert "F" in sex_field.allowed_values

    print(f"[PASS] Driver's license template has {len(template.fields)} fields")


def test_instantiate_template():
    """Test creating a profile from a template."""
    print('\n' + '='*60)
    print('TESTING TEMPLATE INSTANTIATION')
    print('='*60)

    # Create custom profile from template
    custom_profile = instantiate_template(
        template_name="template-generic-invoice",
        new_name="acme-invoice",
        customizations={
            "display_name": "Acme Corp Invoice",
            "organization_id": "org-123",
            "description": "Custom invoice format for Acme Corp"
        }
    )

    # Verify customizations applied
    assert custom_profile.name == "acme-invoice"
    assert custom_profile.display_name == "Acme Corp Invoice"
    assert custom_profile.organization_id == "org-123"
    assert custom_profile.description == "Custom invoice format for Acme Corp"

    # Verify template fields preserved
    assert custom_profile.is_template == False
    assert custom_profile.version == 1
    assert len(custom_profile.fields) == 5  # Same as template

    print(f"[PASS] Created custom profile: {custom_profile.name}")
    print(f"  Display name: {custom_profile.display_name}")
    print(f"  Organization: {custom_profile.organization_id}")
    print(f"  Fields: {len(custom_profile.fields)}")


def test_instantiate_template_validation():
    """Test template instantiation validation."""
    print('\n' + '='*60)
    print('TESTING TEMPLATE INSTANTIATION VALIDATION')
    print('='*60)

    # Test non-existent template
    try:
        instantiate_template(
            template_name="non-existent",
            new_name="test"
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not found" in str(e)
        print("[PASS] Raises error for non-existent template")

    # Test invalid name (starts with template-)
    try:
        instantiate_template(
            template_name="template-generic-invoice",
            new_name="template-custom"
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "cannot start with" in str(e)
        print("[PASS] Raises error for invalid profile name")


def test_get_templates_by_document_type():
    """Test filtering templates by document type."""
    print('\n' + '='*60)
    print('TESTING FILTER BY DOCUMENT TYPE')
    print('='*60)

    # Test invoice type
    invoices = get_templates_by_document_type("invoice")
    assert len(invoices) == 1
    assert invoices[0].name == "template-generic-invoice"
    print(f"[PASS] Found {len(invoices)} invoice template")

    # Test receipt type
    receipts = get_templates_by_document_type("receipt")
    assert len(receipts) == 1
    assert receipts[0].name == "template-retail-receipt"
    print(f"[PASS] Found {len(receipts)} receipt template")

    # Test tax_form type
    tax_forms = get_templates_by_document_type("tax_form")
    assert len(tax_forms) == 1
    assert tax_forms[0].name == "template-w2-tax-form"
    print(f"[PASS] Found {len(tax_forms)} tax form template")

    # Test identification type
    ids = get_templates_by_document_type("identification")
    assert len(ids) == 1
    assert ids[0].name == "template-drivers-license"
    print(f"[PASS] Found {len(ids)} identification template")

    # Test non-existent type
    other = get_templates_by_document_type("passport")
    assert len(other) == 0
    print(f"[PASS] Returns empty list for non-existent document type")


def test_template_immutability():
    """Test that instantiating a template doesn't modify the original."""
    print('\n' + '='*60)
    print('TESTING TEMPLATE IMMUTABILITY')
    print('='*60)

    # Get original template
    original = get_template_by_name("template-generic-invoice")
    original_field_count = len(original.fields)
    original_display_name = original.display_name

    # Create instance and modify it
    instance = instantiate_template(
        template_name="template-generic-invoice",
        new_name="modified-invoice",
        customizations={
            "display_name": "Modified Invoice"
        }
    )

    # Verify original unchanged
    original_after = get_template_by_name("template-generic-invoice")
    assert len(original_after.fields) == original_field_count
    assert original_after.display_name == original_display_name
    assert original_after.is_template == True

    print("[PASS] Original template unchanged after instantiation")


if __name__ == '__main__':
    test_all_templates_exist()
    test_get_template_by_name()
    test_invoice_template_fields()
    test_receipt_template_fields()
    test_w2_template_fields()
    test_drivers_license_template_fields()
    test_instantiate_template()
    test_instantiate_template_validation()
    test_get_templates_by_document_type()
    test_template_immutability()

    print('\n' + '='*60)
    print('ALL TEMPLATE TESTS PASSED!')
    print('='*60)
