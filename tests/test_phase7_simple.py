"""
Simple integration tests for Phase 7 (no OCR required)

Tests profile extraction integration without needing full OCR pipeline.
"""

from database import (
    init_database, get_document, save_document,
    create_document_record, get_profile_by_name,
    seed_templates, DocumentRecord, ProcessingStatus
)
from extraction_pipeline import ExtractionPipeline


def test_extract_with_profile_method():
    """Test _extract_with_profile method directly."""
    print('='*60)
    print('TESTING _extract_with_profile METHOD')
    print('='*60)

    # Initialize database and seed templates
    init_database()
    seed_templates()

    # Get template profile
    profile = get_profile_by_name("template-generic-invoice")
    assert profile is not None
    print(f"[PASS] Found profile: {profile.display_name}")

    # Create a mock OCR result
    mock_ocr_result = {
        'blocks': [
            {
                'id': 'block_0',
                'block_type': 'LINE',
                'text': 'Invoice # INV-2024-001',
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
            },
            {
                'id': 'block_1',
                'block_type': 'LINE',
                'text': 'Date: 2024-01-15',
                'confidence': 0.93,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.1,
                        'top': 0.15,
                        'width': 0.2,
                        'height': 0.03
                    }
                }
            },
            {
                'id': 'block_2',
                'block_type': 'LINE',
                'text': 'Total: $1,234.56',
                'confidence': 0.94,
                'page': 1,
                'geometry': {
                    'boundingBox': {
                        'left': 0.1,
                        'top': 0.5,
                        'width': 0.2,
                        'height': 0.03
                    }
                }
            }
        ],
        'page_count': 1
    }

    # Create document record with profile
    record = DocumentRecord()
    record.id = 1
    record.profile_id = profile.id
    record.status = ProcessingStatus.COMPLETED.value
    record.page_count = 1

    # Test _extract_with_profile
    pipeline = ExtractionPipeline()
    pipeline._extract_with_profile(record, mock_ocr_result)

    # Verify extracted_fields was set
    assert record.extracted_fields is not None
    print("[PASS] Profile extraction completed")

    # Check structure
    assert 'fields' in record.extracted_fields
    assert 'statistics' in record.extracted_fields
    print("[PASS] Extracted fields has correct structure")

    # Check fields
    fields = record.extracted_fields['fields']
    print(f"[PASS] Extracted {len(fields)} fields")

    # Check statistics
    stats = record.extracted_fields['statistics']
    print(f"\nExtraction Statistics:")
    print(f"  Total fields: {stats.get('total_fields', 0)}")
    print(f"  Extracted: {stats.get('extracted', 0)}")
    print(f"  Failed: {stats.get('failed', 0)}")

    # Show extracted fields
    if fields:
        print(f"\nExtracted Fields:")
        for field_name, field_data in fields.items():
            value = field_data.get('value')
            confidence = field_data.get('confidence', 0)
            valid = field_data.get('valid', False)
            status_icon = "OK" if valid else "FAIL"
            print(f"  [{status_icon}] {field_name}: {value} (conf: {confidence:.2f})")

    print('\n[PASS] _extract_with_profile test passed!')


def test_profile_assignment():
    """Test that profile can be assigned to document."""
    print('\n' + '='*60)
    print('TESTING PROFILE ASSIGNMENT')
    print('='*60)

    init_database()
    seed_templates()

    # Get profile
    profile = get_profile_by_name("template-generic-invoice")
    assert profile is not None

    # Create document with profile
    record = create_document_record(
        filename="test.txt",
        file_bytes=b"test content",
        file_type="txt"
    )
    record.profile_id = profile.id

    # Save
    doc_id = save_document(record)
    print(f"[PASS] Document created with profile: ID={doc_id}")

    # Reload and verify
    record = get_document(doc_id)
    assert record.profile_id == profile.id
    print(f"[PASS] Profile assignment persisted")

    print('\n[PASS] Profile assignment test passed!')


def test_extracted_fields_storage():
    """Test that extracted_fields can be stored and retrieved."""
    print('\n' + '='*60)
    print('TESTING EXTRACTED FIELDS STORAGE')
    print('='*60)

    init_database()

    # Create document
    record = create_document_record(
        filename="test.txt",
        file_bytes=b"test content",
        file_type="txt"
    )
    doc_id = save_document(record)

    # Reload
    record = get_document(doc_id)

    # Set extracted fields
    test_fields = {
        'profile_name': 'test-profile',
        'fields': {
            'field1': {'value': 'test', 'confidence': 0.95},
            'field2': {'value': 123, 'confidence': 0.88}
        },
        'statistics': {
            'total_fields': 2,
            'extracted': 2,
            'failed': 0
        }
    }

    record.extracted_fields = test_fields
    save_document(record)
    print("[PASS] Extracted fields saved")

    # Reload and verify
    record = get_document(doc_id)
    assert record.extracted_fields is not None
    assert record.extracted_fields['profile_name'] == 'test-profile'
    assert len(record.extracted_fields['fields']) == 2
    print("[PASS] Extracted fields retrieved correctly")

    print('\n[PASS] Extracted fields storage test passed!')


if __name__ == '__main__':
    test_extract_with_profile_method()
    test_profile_assignment()
    test_extracted_fields_storage()

    print('\n' + '='*60)
    print('ALL PHASE 7 SIMPLE TESTS PASSED!')
    print('='*60)
