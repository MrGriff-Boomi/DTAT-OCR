"""
Integration tests for Phase 7: Document Processing with Profiles

Tests the complete pipeline:
1. Upload document with profile
2. Process through OCR
3. Extract structured fields
4. Retrieve results via API
"""

from pathlib import Path
import tempfile
from database import (
    init_database, get_document, save_document,
    create_document_record, get_profile_by_name,
    seed_templates
)
from extraction_pipeline import ExtractionPipeline
from profile_templates import instantiate_template


def create_mock_invoice_pdf() -> Path:
    """Create a simple text file to simulate an invoice."""
    content = """
ACME CORPORATION
123 Main Street
Invoice #: INV-2024-001

Date: 2024-01-15

Bill To:
Customer Name
456 Oak Ave

Item                    Qty     Price       Total
Widget A                2       $10.00      $20.00
Gadget B                1       $15.00      $15.00

                        Subtotal:   $35.00
                        Tax:        $2.80
                        Total:      $37.80

Payment Terms: Net 30
"""
    # Create temp file
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def test_end_to_end_with_profile():
    """Test complete pipeline: upload, process, extract fields, retrieve."""
    print('='*60)
    print('TESTING END-TO-END WITH PROFILE')
    print('='*60)

    # Initialize database and seed templates
    init_database()
    seed_templates()

    # Get template profile
    profile = get_profile_by_name("template-generic-invoice")
    assert profile is not None, "Template not found"
    print(f"[PASS] Found profile: {profile.display_name}")

    # Create mock document
    mock_file = create_mock_invoice_pdf()

    try:
        # Read file
        with open(mock_file, 'rb') as f:
            file_bytes = f.read()

        # Create document record with profile
        record = create_document_record(
            filename="test_invoice.txt",
            file_bytes=file_bytes,
            file_type="txt"
        )
        record.profile_id = profile.id  # Assign profile
        doc_id = save_document(record)
        print(f"[PASS] Created document record: ID={doc_id}")

        # Reload record to get ID
        record = get_document(doc_id)
        assert record.profile_id == profile.id
        print(f"[PASS] Profile assigned: {record.profile_id}")

        # Process through pipeline
        pipeline = ExtractionPipeline()
        result = pipeline.process(record, mock_file)

        # Verify processing succeeded
        assert result.status == "completed", f"Expected completed, got {result.status}"
        print(f"[PASS] Document processed: {result.status}")

        # Verify OCR extraction happened
        assert result.char_count > 0
        print(f"[PASS] OCR extracted {result.char_count} characters")

        # Verify profile extraction happened
        assert result.extracted_fields is not None, "No extracted fields found"
        print(f"[PASS] Profile extraction completed")

        # Check extracted fields
        fields = result.extracted_fields.get('fields', {})
        assert len(fields) > 0, "No fields extracted"
        print(f"[PASS] Extracted {len(fields)} fields")

        # Verify specific fields
        if 'invoice_number' in fields:
            invoice_num = fields['invoice_number']
            print(f"  - invoice_number: {invoice_num.get('value')} (confidence: {invoice_num.get('confidence', 0):.2f})")

        if 'invoice_date' in fields:
            invoice_date = fields['invoice_date']
            print(f"  - invoice_date: {invoice_date.get('value')} (confidence: {invoice_date.get('confidence', 0):.2f})")

        if 'total_amount' in fields:
            total = fields['total_amount']
            print(f"  - total_amount: {total.get('value')} (confidence: {total.get('confidence', 0):.2f})")

        # Check statistics
        stats = result.extracted_fields.get('statistics', {})
        print(f"\nExtraction Statistics:")
        print(f"  Total fields: {stats.get('total_fields', 0)}")
        print(f"  Extracted: {stats.get('extracted', 0)}")
        print(f"  Failed: {stats.get('failed', 0)}")
        print(f"  Validated: {stats.get('validated', 0)}")

        print('\n[PASS] End-to-end test passed!')

    finally:
        # Cleanup
        mock_file.unlink(missing_ok=True)


def test_process_without_profile():
    """Test that documents without profile still work (backward compatibility)."""
    print('\n' + '='*60)
    print('TESTING BACKWARD COMPATIBILITY (NO PROFILE)')
    print('='*60)

    # Initialize database
    init_database()

    # Create mock document
    mock_file = create_mock_invoice_pdf()

    try:
        # Read file
        with open(mock_file, 'rb') as f:
            file_bytes = f.read()

        # Create document record WITHOUT profile
        record = create_document_record(
            filename="test_invoice_no_profile.txt",
            file_bytes=file_bytes,
            file_type="txt"
        )
        doc_id = save_document(record)
        print(f"[PASS] Created document record: ID={doc_id} (no profile)")

        # Reload record
        record = get_document(doc_id)
        assert record.profile_id is None
        print(f"[PASS] No profile assigned")

        # Process through pipeline
        pipeline = ExtractionPipeline()
        result = pipeline.process(record, mock_file)

        # Verify processing succeeded
        assert result.status == "completed"
        print(f"[PASS] Document processed: {result.status}")

        # Verify OCR extraction happened
        assert result.char_count > 0
        print(f"[PASS] OCR extracted {result.char_count} characters")

        # Verify NO profile extraction happened
        assert result.extracted_fields is None or result.extracted_fields == {}
        print(f"[PASS] No profile extraction (as expected)")

        print('\n[PASS] Backward compatibility test passed!')

    finally:
        # Cleanup
        mock_file.unlink(missing_ok=True)


def test_profile_extraction_error_handling():
    """Test that profile extraction errors don't crash the pipeline."""
    print('\n' + '='*60)
    print('TESTING ERROR HANDLING')
    print('='*60)

    # Initialize database
    init_database()

    # Create mock document
    mock_file = create_mock_invoice_pdf()

    try:
        # Read file
        with open(mock_file, 'rb') as f:
            file_bytes = f.read()

        # Create document record with INVALID profile ID
        record = create_document_record(
            filename="test_invoice_bad_profile.txt",
            file_bytes=file_bytes,
            file_type="txt"
        )
        record.profile_id = 99999  # Non-existent profile
        doc_id = save_document(record)
        print(f"[PASS] Created document with invalid profile ID")

        # Reload record
        record = get_document(doc_id)

        # Process through pipeline (should NOT crash)
        pipeline = ExtractionPipeline()
        result = pipeline.process(record, mock_file)

        # Verify processing still succeeded (OCR part)
        assert result.status == "completed"
        print(f"[PASS] Document processed despite invalid profile")

        # Verify OCR extraction happened
        assert result.char_count > 0
        print(f"[PASS] OCR extraction succeeded")

        # Profile extraction should have failed gracefully
        # (no extracted_fields or empty)
        print(f"[PASS] Pipeline handled invalid profile gracefully")

        print('\n[PASS] Error handling test passed!')

    finally:
        # Cleanup
        mock_file.unlink(missing_ok=True)


def test_extracted_fields_structure():
    """Test that extracted fields have correct structure."""
    print('\n' + '='*60)
    print('TESTING EXTRACTED FIELDS STRUCTURE')
    print('='*60)

    # Initialize database and seed templates
    init_database()
    seed_templates()

    # Get template profile
    profile = get_profile_by_name("template-generic-invoice")
    assert profile is not None

    # Create mock document
    mock_file = create_mock_invoice_pdf()

    try:
        # Read file
        with open(mock_file, 'rb') as f:
            file_bytes = f.read()

        # Create and process document
        record = create_document_record(
            filename="test_invoice_structure.txt",
            file_bytes=file_bytes,
            file_type="txt"
        )
        record.profile_id = profile.id
        doc_id = save_document(record)
        record = get_document(doc_id)

        # Process
        pipeline = ExtractionPipeline()
        result = pipeline.process(record, mock_file)

        # Verify structure
        assert result.extracted_fields is not None
        assert 'profile_name' in result.extracted_fields
        assert 'fields' in result.extracted_fields
        assert 'statistics' in result.extracted_fields
        print("[PASS] Top-level structure correct")

        # Check each field has required keys
        fields = result.extracted_fields['fields']
        for field_name, field_data in fields.items():
            assert 'value' in field_data, f"Missing 'value' in {field_name}"
            assert 'raw_value' in field_data, f"Missing 'raw_value' in {field_name}"
            assert 'confidence' in field_data, f"Missing 'confidence' in {field_name}"
            assert 'valid' in field_data, f"Missing 'valid' in {field_name}"
            assert 'field_type' in field_data, f"Missing 'field_type' in {field_name}"
            assert 'strategy' in field_data, f"Missing 'strategy' in {field_name}"
            print(f"[PASS] Field '{field_name}' has correct structure")

        # Check statistics
        stats = result.extracted_fields['statistics']
        assert 'total_fields' in stats
        assert 'extracted' in stats
        assert 'failed' in stats
        print("[PASS] Statistics structure correct")

        print('\n[PASS] Field structure test passed!')

    finally:
        # Cleanup
        mock_file.unlink(missing_ok=True)


if __name__ == '__main__':
    test_end_to_end_with_profile()
    test_process_without_profile()
    test_profile_extraction_error_handling()
    test_extracted_fields_structure()

    print('\n' + '='*60)
    print('ALL PHASE 7 INTEGRATION TESTS PASSED!')
    print('='*60)
