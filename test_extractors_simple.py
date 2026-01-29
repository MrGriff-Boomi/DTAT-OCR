"""
Simple extractor tests (without pytest dependency)
"""

from extractors import CoordinateExtractor, KeywordProximityExtractor, get_extractor
from profiles import FieldDefinition, FieldType, ExtractionStrategy, CoordinateBox, KeywordRule

def test_coordinate_extractor():
    """Test CoordinateExtractor"""
    print('='*60)
    print('TESTING COORDINATE EXTRACTOR')
    print('='*60)

    extractor = CoordinateExtractor()

    # Test 1: Extract from coordinates
    field_def = FieldDefinition(
        name='invoice_number',
        label='Invoice Number',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.COORDINATE,
        coordinate_box=CoordinateBox(page=1, x=0.5, y=0.1, width=0.2, height=0.05)
    )

    ocr_result = {
        'blocks': [
            {'text': 'INV-12345', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.52, 'top': 0.11, 'width': 0.15, 'height': 0.03}}}
        ]
    }

    value, confidence, location = extractor.extract(field_def, ocr_result)
    assert value == 'INV-12345', f'Expected INV-12345, got {value}'
    assert confidence > 0.9, f'Expected confidence > 0.9, got {confidence}'
    print('[PASS] Extract text from coordinates')

    # Test 2: Multiple blocks
    field_def2 = FieldDefinition(
        name='address',
        label='Address',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.COORDINATE,
        coordinate_box=CoordinateBox(page=1, x=0.1, y=0.2, width=0.4, height=0.1)
    )

    ocr_result2 = {
        'blocks': [
            {'text': '123 Main St', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.11, 'top': 0.21, 'width': 0.15, 'height': 0.03}}},
            {'text': 'Suite 100', 'confidence': 0.92, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.11, 'top': 0.25, 'width': 0.12, 'height': 0.03}}}
        ]
    }

    value, confidence, _ = extractor.extract(field_def2, ocr_result2)
    assert '123 Main St' in value, f'Expected 123 Main St in {value}'
    assert 'Suite 100' in value, f'Expected Suite 100 in {value}'
    print('[PASS] Concatenate multiple blocks')

    # Test 3: No match
    field_def3 = FieldDefinition(
        name='test',
        label='Test',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.COORDINATE,
        coordinate_box=CoordinateBox(page=1, x=0.8, y=0.8, width=0.1, height=0.1)
    )

    value, confidence, location = extractor.extract(field_def3, ocr_result)
    assert value is None, f'Expected None, got {value}'
    assert confidence == 0.0, f'Expected 0.0, got {confidence}'
    print('[PASS] Return None when no blocks overlap')


def test_keyword_extractor():
    """Test KeywordProximityExtractor"""
    print('\n' + '='*60)
    print('TESTING KEYWORD PROXIMITY EXTRACTOR')
    print('='*60)

    extractor = KeywordProximityExtractor()

    # Test 1: Value to right of keyword
    field_def = FieldDefinition(
        name='total',
        label='Total',
        field_type=FieldType.CURRENCY,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(keyword='Total:', direction='right', max_distance=200)
    )

    ocr_result = {
        'blocks': [
            {'text': 'Total:', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.1, 'top': 0.5, 'width': 0.1, 'height': 0.03}}},
            {'text': '1234.56', 'confidence': 0.92, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.25, 'top': 0.502, 'width': 0.12, 'height': 0.03}}}
        ]
    }

    value, confidence, _ = extractor.extract(field_def, ocr_result)
    assert value == '1234.56', f'Expected 1234.56, got {value}'
    assert confidence > 0.9, f'Expected > 0.9, got {confidence}'
    print('[PASS] Extract value to right of keyword')

    # Test 2: Value below keyword
    field_def2 = FieldDefinition(
        name='date',
        label='Date',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(keyword='Date:', direction='below', max_distance=100)
    )

    ocr_result2 = {
        'blocks': [
            {'text': 'Date:', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.1, 'top': 0.2, 'width': 0.08, 'height': 0.03}}},
            {'text': '2024-01-15', 'confidence': 0.93, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.105, 'top': 0.24, 'width': 0.15, 'height': 0.03}}}
        ]
    }

    value, confidence, _ = extractor.extract(field_def2, ocr_result2)
    assert value == '2024-01-15', f'Expected 2024-01-15, got {value}'
    print('[PASS] Extract value below keyword')

    # Test 3: With regex pattern
    field_def3 = FieldDefinition(
        name='amount',
        label='Amount',
        field_type=FieldType.CURRENCY,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(
            keyword='Amount:',
            direction='right',
            max_distance=200,
            pattern=r'([0-9,]+\.[0-9]{2})'  # Extract just numbers
        )
    )

    ocr_result3 = {
        'blocks': [
            {'text': 'Amount:', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.1, 'top': 0.3, 'width': 0.12, 'height': 0.03}}},
            {'text': 'USD 523.45 paid', 'confidence': 0.90, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.25, 'top': 0.302, 'width': 0.2, 'height': 0.03}}}
        ]
    }

    value, confidence, _ = extractor.extract(field_def3, ocr_result3)
    assert value == '523.45', f'Expected 523.45, got {value}'
    print('[PASS] Extract with regex pattern')

    # Test 4: Keyword not found
    field_def4 = FieldDefinition(
        name='test',
        label='Test',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(keyword='NotFound:', direction='right', max_distance=200)
    )

    value, confidence, location = extractor.extract(field_def4, ocr_result)
    assert value is None, f'Expected None, got {value}'
    assert confidence == 0.0, f'Expected 0.0, got {confidence}'
    print('[PASS] Return None when keyword not found')

    # Test 5: No adjacent block
    field_def5 = FieldDefinition(
        name='test',
        label='Test',
        field_type=FieldType.TEXT,
        strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
        keyword_rule=KeywordRule(keyword='Label:', direction='right', max_distance=10)
    )

    ocr_result4 = {
        'blocks': [
            {'text': 'Label:', 'confidence': 0.95, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.1, 'top': 0.5, 'width': 0.1, 'height': 0.03}}},
            {'text': 'Far', 'confidence': 0.90, 'page': 1,
             'geometry': {'boundingBox': {'left': 0.8, 'top': 0.5, 'width': 0.1, 'height': 0.03}}}
        ]
    }

    value, _, _ = extractor.extract(field_def5, ocr_result4)
    assert value is None, f'Expected None, got {value}'
    print('[PASS] Return None when no adjacent block')


def test_factory():
    """Test extractor factory"""
    print('\n' + '='*60)
    print('TESTING EXTRACTOR FACTORY')
    print('='*60)

    ext1 = get_extractor(ExtractionStrategy.COORDINATE)
    assert isinstance(ext1, CoordinateExtractor)
    print('[PASS] Get CoordinateExtractor')

    ext2 = get_extractor(ExtractionStrategy.KEYWORD_PROXIMITY)
    assert isinstance(ext2, KeywordProximityExtractor)
    print('[PASS] Get KeywordProximityExtractor')

    try:
        get_extractor(ExtractionStrategy.TABLE_COLUMN)
        assert False, 'Should have raised ValueError'
    except ValueError:
        print('[PASS] Raise ValueError for unimplemented extractor')


if __name__ == '__main__':
    test_coordinate_extractor()
    test_keyword_extractor()
    test_factory()

    print('\n' + '='*60)
    print('ALL TESTS PASSED!')
    print('='*60)
