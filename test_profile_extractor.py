"""
Integration tests for ProfileExtractor
"""

from extractors import ProfileExtractor
from profiles import (
    ExtractionProfile,
    FieldDefinition,
    FieldType,
    ExtractionStrategy,
    CoordinateBox,
    KeywordRule
)


def test_profile_extraction_complete_workflow():
    """Test complete extraction workflow with multiple fields"""
    print('='*60)
    print('TESTING PROFILE EXTRACTOR - COMPLETE WORKFLOW')
    print('='*60)

    # Create a profile with multiple field types
    profile = ExtractionProfile(
        name="test_invoice",
        display_name="Test Invoice",
        document_type="invoice",
        fields=[
            # Coordinate extraction - Invoice number
            FieldDefinition(
                name="invoice_number",
                label="Invoice Number",
                field_type=FieldType.TEXT,
                required=True,
                strategy=ExtractionStrategy.COORDINATE,
                coordinate_box=CoordinateBox(
                    page=1,
                    x=0.1,
                    y=0.1,
                    width=0.2,
                    height=0.05
                )
            ),
            # Keyword extraction - Total amount
            FieldDefinition(
                name="total",
                label="Total Amount",
                field_type=FieldType.CURRENCY,
                required=True,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Total:",
                    direction="right",
                    max_distance=200
                )
            ),
            # Keyword extraction - Date
            FieldDefinition(
                name="invoice_date",
                label="Invoice Date",
                field_type=FieldType.DATE,
                required=True,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Date:",
                    direction="right",
                    max_distance=200
                )
            ),
            # Optional field with default
            FieldDefinition(
                name="payment_terms",
                label="Payment Terms",
                field_type=FieldType.TEXT,
                required=False,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Terms:",
                    direction="right",
                    max_distance=200
                ),
                default_value="Net 30"
            )
        ]
    )

    # Mock OCR result with invoice data
    ocr_result = {
        'blocks': [
            # Invoice number (coordinate-based)
            {
                'text': 'INV-2024-001',
                'confidence': 0.95,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.12,
                        'top': 0.11,
                        'width': 0.15,
                        'height': 0.03
                    }
                }
            },
            # Total label and amount
            {
                'text': 'Total:',
                'confidence': 0.96,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.1,
                        'top': 0.5,
                        'width': 0.08,
                        'height': 0.03
                    }
                }
            },
            {
                'text': '$1,234.56',
                'confidence': 0.94,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.25,
                        'top': 0.502,
                        'width': 0.12,
                        'height': 0.03
                    }
                }
            },
            # Date label and value
            {
                'text': 'Date:',
                'confidence': 0.97,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.1,
                        'top': 0.2,
                        'width': 0.06,
                        'height': 0.03
                    }
                }
            },
            {
                'text': '2024-01-15',
                'confidence': 0.93,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.22,
                        'top': 0.202,
                        'width': 0.15,
                        'height': 0.03
                    }
                }
            }
            # Note: payment_terms keyword "Terms:" is missing - should use default value
        ]
    }

    # Create extractor and extract all fields
    extractor = ProfileExtractor()
    results = extractor.extract_all_fields(profile, ocr_result)

    # Verify results structure
    assert 'profile_name' in results
    assert results['profile_name'] == 'test_invoice'
    print('[PASS] Results structure correct')

    # Verify statistics
    stats = results['statistics']
    assert stats['total_fields'] == 4
    # All 4 fields have values (3 extracted, 1 default) so extracted=4, failed=0
    assert stats['extracted'] == 4
    assert stats['failed'] == 0
    print(f'[PASS] Statistics: {stats}')

    # Verify invoice_number field
    invoice_num = results['fields']['invoice_number']
    assert invoice_num['value'] == 'INV-2024-001'
    assert invoice_num['raw_value'] == 'INV-2024-001'
    assert invoice_num['confidence'] > 0.9
    assert invoice_num['valid'] == True
    assert invoice_num['field_type'] == 'text'
    assert invoice_num['strategy'] == 'coordinate'
    print('[PASS] Invoice number extracted and validated')

    # Verify total field (with currency transformation)
    total = results['fields']['total']
    assert total['raw_value'] == '$1,234.56'
    # Value should be transformed to Decimal
    from decimal import Decimal
    assert total['value'] == Decimal('1234.56')
    assert total['confidence'] > 0.9
    assert total['valid'] == True
    assert total['field_type'] == 'currency'
    print('[PASS] Total amount extracted and transformed')

    # Verify date field (with date transformation)
    date = results['fields']['invoice_date']
    assert date['raw_value'] == '2024-01-15'
    # Value should be transformed to datetime
    from datetime import datetime
    assert date['value'] == datetime(2024, 1, 15)
    assert date['confidence'] > 0.9
    assert date['valid'] == True
    assert total['field_type'] == 'currency'
    print('[PASS] Date extracted and transformed')

    # Verify optional field with default value
    terms = results['fields']['payment_terms']
    assert terms['value'] == 'Net 30'  # Default value used
    assert terms['raw_value'] is None  # Not extracted
    assert terms['confidence'] == 0.0
    assert terms['valid'] == True  # Valid because not required
    print('[PASS] Default value applied for missing optional field')

    print('\n[PASS] Complete workflow test passed!')


def test_validation_failures():
    """Test validation catches invalid values"""
    print('\n' + '='*60)
    print('TESTING PROFILE EXTRACTOR - VALIDATION')
    print('='*60)

    # Create profile with validation rules
    profile = ExtractionProfile(
        name="test_validation",
        display_name="Test Validation",
        document_type="test",
        fields=[
            FieldDefinition(
                name="amount",
                label="Amount",
                field_type=FieldType.CURRENCY,
                required=True,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Amount:",
                    direction="right",
                    max_distance=200
                ),
                min_value=0.0,
                max_value=1000.0  # Amount should be <= 1000
            )
        ]
    )

    # OCR result with amount that exceeds max_value
    ocr_result = {
        'blocks': [
            {'text': 'Amount:', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.1, 'top': 0.5, 'width': 0.1, 'height': 0.03}}},
            {'text': '$5,000.00', 'confidence': 0.93, 'page': 1,  # Exceeds max
             'geometry': {'boundingBox': {'left': 0.25, 'top': 0.502, 'width': 0.12, 'height': 0.03}}}
        ]
    }

    extractor = ProfileExtractor()
    results = extractor.extract_all_fields(profile, ocr_result)

    # Verify validation caught the error
    amount = results['fields']['amount']
    assert amount['value'] is not None  # Value was extracted and transformed
    assert amount['valid'] == False  # But validation failed
    assert 'out of range' in amount['validation_error'].lower()
    print('[PASS] Validation correctly flagged out-of-range value')

    # Verify statistics reflect validation failure
    assert results['statistics']['extracted'] == 1
    assert results['statistics']['validated'] == 0
    assert results['statistics']['validation_failed'] == 1
    print('[PASS] Statistics reflect validation failure')


def test_required_field_missing():
    """Test handling of missing required fields"""
    print('\n' + '='*60)
    print('TESTING PROFILE EXTRACTOR - REQUIRED FIELDS')
    print('='*60)

    profile = ExtractionProfile(
        name="test_required",
        display_name="Test Required",
        document_type="test",
        fields=[
            FieldDefinition(
                name="reference_number",
                label="Reference Number",
                field_type=FieldType.TEXT,
                required=True,  # Required but not in document
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Ref:",
                    direction="right",
                    max_distance=200
                )
            )
        ]
    )

    # Empty OCR result - field not found
    ocr_result = {'blocks': []}

    extractor = ProfileExtractor()
    results = extractor.extract_all_fields(profile, ocr_result)

    # Verify required field validation failed
    ref = results['fields']['reference_number']
    assert ref['value'] is None
    assert ref['valid'] == False
    assert 'required' in ref['validation_error'].lower()
    print('[PASS] Missing required field flagged as invalid')


def test_extraction_with_retry():
    """Test retry logic for failed extractions"""
    print('\n' + '='*60)
    print('TESTING PROFILE EXTRACTOR - RETRY LOGIC')
    print('='*60)

    profile = ExtractionProfile(
        name="test_retry",
        display_name="Test Retry",
        document_type="test",
        fields=[
            FieldDefinition(
                name="code",
                label="Code",
                field_type=FieldType.TEXT,
                required=True,
                strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
                keyword_rule=KeywordRule(
                    keyword="Code:",
                    direction="right",
                    max_distance=200
                )
            )
        ]
    )

    # OCR result missing the field
    ocr_result = {'blocks': []}

    extractor = ProfileExtractor()
    results = extractor.extract_with_retry(profile, ocr_result, max_retries=2)

    # Verify retry info is present
    assert 'retry_info' in results
    assert results['retry_info']['attempted'] == 2  # Tried 2 times
    assert results['retry_info']['succeeded'] == 0  # Still failed
    assert results['retry_info']['failed'] == 1
    print('[PASS] Retry logic executed for failed required field')


if __name__ == '__main__':
    test_profile_extraction_complete_workflow()
    test_validation_failures()
    test_required_field_missing()
    test_extraction_with_retry()

    print('\n' + '='*60)
    print('ALL PROFILE EXTRACTOR TESTS PASSED!')
    print('='*60)
