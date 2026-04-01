"""
Simple tests for field transformers and validators
"""

from field_utils import FieldTransformers, FieldValidators
from datetime import datetime
from decimal import Decimal


def test_transformers():
    """Test field transformers"""
    print('='*60)
    print('TESTING FIELD TRANSFORMERS')
    print('='*60)

    # Test to_number
    assert FieldTransformers.to_number("1,234.56") == 1234.56
    assert FieldTransformers.to_number("$1,234") == 1234.0
    assert FieldTransformers.to_number("1.234,56") == 1234.56  # European
    assert FieldTransformers.to_number("1 234") == 1234.0
    print('[PASS] to_number()')

    # Test to_currency
    result = FieldTransformers.to_currency("$1,234.56")
    assert result == Decimal("1234.56")
    print('[PASS] to_currency()')

    # Test to_date
    date1 = FieldTransformers.to_date("2024-01-15")
    assert date1 == datetime(2024, 1, 15)
    date2 = FieldTransformers.to_date("01/15/2024")
    assert date2 == datetime(2024, 1, 15)
    date3 = FieldTransformers.to_date("Jan 15, 2024")
    assert date3 == datetime(2024, 1, 15)
    print('[PASS] to_date()')

    # Test normalize_phone
    phone1 = FieldTransformers.normalize_phone("(555) 123-4567")
    assert phone1 == "+1-555-123-4567"
    phone2 = FieldTransformers.normalize_phone("555.123.4567")
    assert phone2 == "+1-555-123-4567"
    print('[PASS] normalize_phone()')

    # Test to_boolean
    assert FieldTransformers.to_boolean("yes") == True
    assert FieldTransformers.to_boolean("no") == False
    assert FieldTransformers.to_boolean("1") == True
    assert FieldTransformers.to_boolean("0") == False
    assert FieldTransformers.to_boolean("true") == True
    assert FieldTransformers.to_boolean("false") == False
    print('[PASS] to_boolean()')

    # Test apply_format_string
    formatted = FieldTransformers.apply_format_string(1234.5, "{:.2f}")
    assert formatted == "1234.50"
    date_formatted = FieldTransformers.apply_format_string(datetime(2024, 1, 15), "%Y-%m-%d")
    assert date_formatted == "2024-01-15"
    print('[PASS] apply_format_string()')


def test_validators():
    """Test field validators"""
    print('\n' + '='*60)
    print('TESTING FIELD VALIDATORS')
    print('='*60)

    # Test validate_pattern
    assert FieldValidators.validate_pattern("123-45-6789", r"\d{3}-\d{2}-\d{4}") == True
    assert FieldValidators.validate_pattern("123456789", r"\d{3}-\d{2}-\d{4}") == False
    print('[PASS] validate_pattern()')

    # Test validate_range
    assert FieldValidators.validate_range(50, min_value=0, max_value=100) == True
    assert FieldValidators.validate_range(150, min_value=0, max_value=100) == False
    assert FieldValidators.validate_range(-10, min_value=0, max_value=100) == False
    assert FieldValidators.validate_range("75", min_value=0, max_value=100) == True
    print('[PASS] validate_range()')

    # Test validate_allowed_values
    assert FieldValidators.validate_allowed_values("red", ["red", "green", "blue"]) == True
    assert FieldValidators.validate_allowed_values("Red", ["red", "green", "blue"]) == True  # Case insensitive
    assert FieldValidators.validate_allowed_values("yellow", ["red", "green", "blue"]) == False
    print('[PASS] validate_allowed_values()')

    # Test validate_required
    assert FieldValidators.validate_required("value", required=True) == True
    assert FieldValidators.validate_required(None, required=True) == False
    assert FieldValidators.validate_required("", required=True) == False
    assert FieldValidators.validate_required(None, required=False) == True
    print('[PASS] validate_required()')


def test_extractors():
    """Test new extractors"""
    print('\n' + '='*60)
    print('TESTING NEW EXTRACTORS')
    print('='*60)

    from extractors import TableColumnExtractor, RegexExtractor, get_extractor
    from profiles import FieldDefinition, FieldType, ExtractionStrategy, TableColumnRule

    # Test TableColumnExtractor
    extractor = TableColumnExtractor()
    field_def = FieldDefinition(
        name="total",
        label="Total",
        field_type=FieldType.CURRENCY,
        strategy=ExtractionStrategy.TABLE_COLUMN,
        table_column_rule=TableColumnRule(
            table_index=0,
            column_index=1
        )
    )

    ocr_result = {
        'tables': [
            {
                'headers': ['Item', 'Amount', 'Quantity'],
                'rows': [
                    [
                        {'text': 'Widget', 'confidence': 0.95},
                        {'text': '$10.00', 'confidence': 0.93},
                        {'text': '5', 'confidence': 0.98}
                    ],
                    [
                        {'text': 'Gadget', 'confidence': 0.94},
                        {'text': '$20.00', 'confidence': 0.92},
                        {'text': '3', 'confidence': 0.97}
                    ]
                ]
            }
        ]
    }

    value, confidence, location = extractor.extract(field_def, ocr_result)
    assert '$10.00' in value or '$20.00' in value
    assert confidence > 0.9
    print('[PASS] TableColumnExtractor')

    # Test RegexExtractor
    regex_extractor = RegexExtractor()
    field_def2 = FieldDefinition(
        name="invoice_num",
        label="Invoice Number",
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.REGEX_PATTERN,
        regex_pattern=r'INV-\d{5}'
    )

    ocr_result2 = {
        'blocks': [
            {
                'text': 'Invoice Number: INV-12345',
                'confidence': 0.95,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.1,
                        'top': 0.1,
                        'width': 0.3,
                        'height': 0.03
                    }
                }
            }
        ]
    }

    value2, confidence2, location2 = regex_extractor.extract(field_def2, ocr_result2)
    assert value2 == 'INV-12345'
    assert confidence2 > 0.9
    print('[PASS] RegexExtractor')

    # Test factory includes new extractors
    table_ext = get_extractor(ExtractionStrategy.TABLE_COLUMN)
    assert isinstance(table_ext, TableColumnExtractor)
    print('[PASS] Factory returns TableColumnExtractor')

    regex_ext = get_extractor(ExtractionStrategy.REGEX_PATTERN)
    assert isinstance(regex_ext, RegexExtractor)
    print('[PASS] Factory returns RegexExtractor')


if __name__ == '__main__':
    test_transformers()
    test_validators()
    test_extractors()

    print('\n' + '='*60)
    print('ALL TESTS PASSED!')
    print('='*60)
