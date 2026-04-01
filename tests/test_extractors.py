"""
Unit tests for field extractors
"""

import pytest
from extractors import (
    FieldExtractor,
    CoordinateExtractor,
    KeywordProximityExtractor,
    get_extractor
)
from profiles import (
    FieldDefinition,
    FieldType,
    ExtractionStrategy,
    CoordinateBox,
    KeywordRule
)


class TestCoordinateExtractor:
    """Tests for CoordinateExtractor"""

    def test_extract_from_coordinates(self):
        """Test extracting text from specific coordinates"""
        extractor = CoordinateExtractor()

        # Create field definition with coordinate box
        field_def = FieldDefinition(
            name="invoice_number",
            label="Invoice Number",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(
                page=1,
                x=0.5,      # 50% from left
                y=0.1,      # 10% from top
                width=0.2,  # 20% wide
                height=0.05 # 5% tall
            )
        )

        # Mock OCR result with blocks
        ocr_result = {
            'blocks': [
                {
                    'text': 'INV-12345',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.52,
                            'top': 0.11,
                            'width': 0.15,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': 'Other text',
                    'confidence': 0.90,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.2,
                            'width': 0.2,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        # Extract
        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        # Verify
        assert value == 'INV-12345'
        assert confidence > 0.9
        assert location['page'] == 1
        assert location['x'] == 0.5

    def test_extract_multiple_overlapping_blocks(self):
        """Test extracting text when multiple blocks overlap the coordinate box"""
        extractor = CoordinateExtractor()

        field_def = FieldDefinition(
            name="address",
            label="Address",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(
                page=1,
                x=0.1,
                y=0.2,
                width=0.4,
                height=0.1
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': '123 Main St',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.11,
                            'top': 0.21,
                            'width': 0.15,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': 'Suite 100',
                    'confidence': 0.92,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.11,
                            'top': 0.25,
                            'width': 0.12,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        # Should concatenate both blocks
        assert '123 Main St' in value
        assert 'Suite 100' in value
        assert confidence > 0.9

    def test_extract_no_match(self):
        """Test extraction when no blocks overlap the coordinate box"""
        extractor = CoordinateExtractor()

        field_def = FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(
                page=1,
                x=0.8,
                y=0.8,
                width=0.1,
                height=0.1
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Text at top',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.1,
                            'width': 0.2,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        # Should return None
        assert value is None
        assert confidence == 0.0
        assert location is None

    def test_extract_different_page(self):
        """Test extraction ignores blocks on different pages"""
        extractor = CoordinateExtractor()

        field_def = FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.COORDINATE,
            coordinate_box=CoordinateBox(
                page=2,  # Looking for page 2
                x=0.5,
                y=0.5,
                width=0.2,
                height=0.1
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Page 1 text',
                    'confidence': 0.95,
                    'page': 1,  # On page 1
                    'geometry': {
                        'boundingBox': {
                            'left': 0.5,
                            'top': 0.5,
                            'width': 0.2,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=2)

        # Should not match page 1 block
        assert value is None

    def test_boxes_overlap(self):
        """Test box overlap detection"""
        extractor = CoordinateExtractor()

        box1 = CoordinateBox(page=1, x=0.5, y=0.5, width=0.2, height=0.1)

        # Overlapping box
        box2_overlap = {'left': 0.55, 'top': 0.52, 'width': 0.1, 'height': 0.05}
        assert extractor._boxes_overlap(box1, box2_overlap)

        # Non-overlapping box (to the right)
        box2_right = {'left': 0.8, 'top': 0.5, 'width': 0.1, 'height': 0.1}
        assert not extractor._boxes_overlap(box1, box2_right)

        # Non-overlapping box (below)
        box2_below = {'left': 0.5, 'top': 0.7, 'width': 0.2, 'height': 0.1}
        assert not extractor._boxes_overlap(box1, box2_below)


class TestKeywordProximityExtractor:
    """Tests for KeywordProximityExtractor"""

    def test_extract_value_to_right_of_keyword(self):
        """Test extracting value to the right of a keyword"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="total",
            label="Total Amount",
            field_type=FieldType.CURRENCY,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Total:",
                direction="right",
                max_distance=200
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Total:',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': '$1,234.56',
                    'confidence': 0.92,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.25,  # To the right
                            'top': 0.502,   # Same vertical position
                            'width': 0.12,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        assert value == '$1,234.56'
        assert confidence > 0.9
        assert location is not None

    def test_extract_value_below_keyword(self):
        """Test extracting value below a keyword"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="date",
            label="Date",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Date:",
                direction="below",
                max_distance=100
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Date:',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.2,
                            'width': 0.08,
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
                            'left': 0.105,  # Same horizontal position
                            'top': 0.24,    # Below
                            'width': 0.15,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        assert value == '2024-01-15'
        assert confidence > 0.9

    def test_extract_with_regex_pattern(self):
        """Test extracting value with regex pattern matching"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="amount",
            label="Amount",
            field_type=FieldType.CURRENCY,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Amount:",
                direction="right",
                max_distance=200,
                pattern=r'\$?([0-9,]+\.\d{2})'  # Extract just the number
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Amount:',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.3,
                            'width': 0.12,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': 'USD $523.45 paid',
                    'confidence': 0.90,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.25,
                            'top': 0.302,
                            'width': 0.2,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        # Should extract just the currency amount
        assert value == '523.45'
        assert confidence > 0.85

    def test_extract_keyword_not_found(self):
        """Test extraction when keyword is not found"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="NotFound:",
                direction="right",
                max_distance=200
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Some text',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        assert value is None
        assert confidence == 0.0
        assert location is None

    def test_extract_no_adjacent_block(self):
        """Test extraction when no adjacent block is found"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Label:",
                direction="right",
                max_distance=50  # Very small distance
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Label:',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': 'Far away value',
                    'confidence': 0.90,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.8,  # Too far away
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        assert value is None

    def test_extract_pattern_no_match(self):
        """Test extraction when regex pattern doesn't match"""
        extractor = KeywordProximityExtractor()

        field_def = FieldDefinition(
            name="test",
            label="Test",
            field_type=FieldType.TEXT,
            strategy=ExtractionStrategy.KEYWORD_PROXIMITY,
            keyword_rule=KeywordRule(
                keyword="Code:",
                direction="right",
                max_distance=200,
                pattern=r'\d{5}'  # Requires 5 digits
            )
        )

        ocr_result = {
            'blocks': [
                {
                    'text': 'Code:',
                    'confidence': 0.95,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.1,
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                },
                {
                    'text': 'ABC',  # Not digits
                    'confidence': 0.90,
                    'page': 1,
                    'geometry': {
                        'boundingBox': {
                            'left': 0.25,
                            'top': 0.5,
                            'width': 0.1,
                            'height': 0.03
                        }
                    }
                }
            ]
        }

        value, confidence, location = extractor.extract(field_def, ocr_result, page=1)

        # Pattern didn't match, should return None
        assert value is None


class TestGetExtractor:
    """Tests for extractor factory function"""

    def test_get_coordinate_extractor(self):
        """Test getting coordinate extractor"""
        extractor = get_extractor(ExtractionStrategy.COORDINATE)
        assert isinstance(extractor, CoordinateExtractor)

    def test_get_keyword_extractor(self):
        """Test getting keyword proximity extractor"""
        extractor = get_extractor(ExtractionStrategy.KEYWORD_PROXIMITY)
        assert isinstance(extractor, KeywordProximityExtractor)

    def test_get_unimplemented_extractor(self):
        """Test getting unimplemented extractor raises error"""
        with pytest.raises(ValueError, match="not yet implemented"):
            get_extractor(ExtractionStrategy.TABLE_COLUMN)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
