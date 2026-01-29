"""
Field Extraction Strategies

Implements various strategies for extracting structured fields from OCR results
based on user-defined extraction profiles.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
from profiles import (
    FieldDefinition,
    ExtractionStrategy,
    CoordinateBox,
    KeywordRule
)


class FieldExtractor:
    """Base class for field extraction strategies"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Any, float, Optional[Dict]]:
        """
        Extract field value from OCR result.

        Args:
            field_def: Field definition with extraction rules
            ocr_result: Normalized OCR result (DTAT format)
            page: Page number to extract from (1-indexed)

        Returns:
            Tuple of (value, confidence, location_dict)
            - value: Extracted text or None if not found
            - confidence: 0.0-1.0 confidence score
            - location_dict: Bounding box coordinates or None
        """
        raise NotImplementedError("Subclasses must implement extract()")


class CoordinateExtractor(FieldExtractor):
    """Extract text from specific bounding box coordinates"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Extract text from specific coordinates on page.

        Uses normalized coordinates (0.0-1.0) for position and size.
        Finds all text blocks that overlap with the specified bounding box.
        """
        box = field_def.coordinate_box
        if not box:
            return None, 0.0, None

        # Get blocks from OCR result
        blocks = ocr_result.get('blocks', [])
        if not blocks:
            return None, 0.0, None

        # Find blocks within bounding box
        matching_blocks = []
        for block in blocks:
            # Skip blocks on different pages
            if block.get('page', 1) != box.page:
                continue

            # Get block geometry
            geometry = block.get('geometry', {})
            block_box = geometry.get('boundingBox', {})

            if not block_box:
                continue

            # Check if boxes overlap
            if self._boxes_overlap(box, block_box):
                matching_blocks.append(block)

        if not matching_blocks:
            return None, 0.0, None

        # Concatenate text from all matching blocks
        text = ' '.join(b.get('text', '') for b in matching_blocks)

        # Calculate average confidence
        confidences = [b.get('confidence', 0.0) for b in matching_blocks]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Return location as dict
        location = {
            'page': box.page,
            'x': box.x,
            'y': box.y,
            'width': box.width,
            'height': box.height
        }

        return text.strip(), avg_confidence, location

    def _boxes_overlap(self, box1: CoordinateBox, box2: Dict[str, float]) -> bool:
        """
        Check if two bounding boxes overlap.

        Args:
            box1: CoordinateBox with normalized coordinates
            box2: Dict with 'left', 'top', 'width', 'height' keys (normalized)

        Returns:
            True if boxes overlap, False otherwise
        """
        # box1 uses x, y, width, height
        # box2 uses left, top, width, height
        # Both are normalized (0.0-1.0)

        box1_right = box1.x + box1.width
        box1_bottom = box1.y + box1.height
        box2_right = box2.get('left', 0) + box2.get('width', 0)
        box2_bottom = box2.get('top', 0) + box2.get('height', 0)

        # No overlap if:
        # - box1 is completely to the left of box2
        # - box2 is completely to the left of box1
        # - box1 is completely above box2
        # - box2 is completely above box1
        # Use <= for edge-touching boxes (they should NOT overlap)
        no_overlap = (
            box1_right <= box2.get('left', 0) or
            box2_right <= box1.x or
            box1_bottom <= box2.get('top', 0) or
            box2_bottom <= box1.y
        )

        return not no_overlap


class KeywordProximityExtractor(FieldExtractor):
    """Extract value near a keyword"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Extract text adjacent to a keyword.

        Finds the keyword block, then searches for adjacent blocks in the
        specified direction (right, left, above, below) within max_distance.
        """
        rule = field_def.keyword_rule
        if not rule:
            return None, 0.0, None

        # Get blocks from OCR result
        blocks = ocr_result.get('blocks', [])
        if not blocks:
            return None, 0.0, None

        # Filter blocks by page
        page_blocks = [b for b in blocks if b.get('page', 1) == page]

        # Find keyword block
        keyword_block = None
        for block in page_blocks:
            text = block.get('text', '')
            if rule.keyword.lower() in text.lower():
                keyword_block = block
                break

        if not keyword_block:
            return None, 0.0, None

        # Find adjacent block in specified direction
        target_block = self._find_adjacent_block(
            keyword_block,
            page_blocks,
            direction=rule.direction,
            max_distance=rule.max_distance,
            ocr_result=ocr_result,
            page=page
        )

        if not target_block:
            return None, 0.0, None

        text = target_block.get('text', '')

        # Apply regex pattern if specified
        if rule.pattern:
            match = re.search(rule.pattern, text)
            if match:
                # Use first capture group if available, otherwise full match
                text = match.group(1) if match.groups() else match.group(0)
            else:
                # Pattern didn't match
                return None, 0.0, None

        confidence = target_block.get('confidence', 0.0)
        geometry = target_block.get('geometry', {})
        location = geometry.get('boundingBox')

        return text.strip(), confidence, location

    def _find_adjacent_block(
        self,
        anchor: Dict[str, Any],
        blocks: List[Dict[str, Any]],
        direction: str,
        max_distance: int,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Find block adjacent to anchor in specified direction.

        Args:
            anchor: Reference block containing the keyword
            blocks: List of all blocks to search
            direction: 'right', 'left', 'above', or 'below'
            max_distance: Maximum distance in pixels (will be normalized)
            ocr_result: Full OCR result (for page dimensions)
            page: Page number (for page dimensions lookup)

        Returns:
            Closest matching block or None
        """
        # Get anchor position
        anchor_geom = anchor.get('geometry', {})
        anchor_box = anchor_geom.get('boundingBox', {})
        ax = anchor_box.get('left', 0)
        ay = anchor_box.get('top', 0)
        aw = anchor_box.get('width', 0)
        ah = anchor_box.get('height', 0)

        # Calculate anchor center and right edge
        anchor_center_x = ax + aw / 2
        anchor_center_y = ay + ah / 2
        anchor_right = ax + aw
        anchor_bottom = ay + ah

        # Convert max_distance to normalized units
        # max_distance is in pixels, normalize to 0.0-1.0 scale
        # Get actual page dimensions if available, otherwise use reasonable default
        page_info = ocr_result.get('page_dimensions', {}).get(page, {})
        page_width = page_info.get('width', 1000)  # Default to 1000px if not available
        max_dist_normalized = max_distance / page_width

        candidates = []
        for block in blocks:
            if block == anchor:
                continue

            # Get block position
            block_geom = block.get('geometry', {})
            block_box = block_geom.get('boundingBox', {})
            bx = block_box.get('left', 0)
            by = block_box.get('top', 0)
            bw = block_box.get('width', 0)
            bh = block_box.get('height', 0)

            block_center_x = bx + bw / 2
            block_center_y = by + bh / 2

            # Calculate distance
            distance = abs(block_center_x - anchor_center_x) + abs(block_center_y - anchor_center_y)

            if distance > max_dist_normalized:
                continue

            # Check direction with tolerance
            # Use adaptive tolerance based on anchor box height for more realistic matching
            # This handles multi-line values and varying font sizes better than fixed percentage
            tolerance = max(ah * 1.5, 0.02)  # At least 2%, or 1.5x anchor height

            if direction == 'right':
                # Block should be to the right and roughly same vertical position
                # Use >= to avoid gaps with edge-touching or overlapping blocks
                if bx >= anchor_right and abs(block_center_y - anchor_center_y) < tolerance:
                    candidates.append((distance, block))

            elif direction == 'left':
                # Block should be to the left and roughly same vertical position
                # Use <= to avoid gaps with edge-touching or overlapping blocks
                if bx + bw <= ax and abs(block_center_y - anchor_center_y) < tolerance:
                    candidates.append((distance, block))

            elif direction == 'below':
                # Block should be below and roughly same horizontal position
                # Use >= to avoid gaps with edge-touching or overlapping blocks
                if by >= anchor_bottom and abs(block_center_x - anchor_center_x) < tolerance:
                    candidates.append((distance, block))

            elif direction == 'above':
                # Block should be above and roughly same horizontal position
                # Use <= to avoid gaps with edge-touching or overlapping blocks
                if by + bh <= ay and abs(block_center_x - anchor_center_x) < tolerance:
                    candidates.append((distance, block))

        if not candidates:
            return None

        # Return closest candidate
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]  # Return block from (distance, block) tuple


class TableColumnExtractor(FieldExtractor):
    """Extract data from specific table column"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Extract text from specific table column.

        Supports both column name (header-based) and column index lookup.
        Can filter rows based on conditions in other columns.
        """
        from profiles import TableColumnRule

        rule = field_def.table_column_rule
        if not rule:
            return None, 0.0, None

        # Get tables from OCR result
        tables = ocr_result.get('tables', [])
        if not tables:
            return None, 0.0, None

        # Get specific table by index
        if rule.table_index >= len(tables):
            return None, 0.0, None

        table = tables[rule.table_index]

        # Determine column index
        col_idx = rule.column_index
        if col_idx is None and rule.column_name:
            # Find column by header name
            headers = table.get('headers', [])
            for i, header in enumerate(headers):
                if rule.column_name.lower() in header.lower():
                    col_idx = i
                    break

        if col_idx is None:
            return None, 0.0, None

        # Extract values from column
        rows = table.get('rows', [])
        values = []
        confidences = []

        for row in rows:
            # Check row filter if specified
            if rule.row_filter:
                matches_filter = True
                for filter_col, filter_val in rule.row_filter.items():
                    # Find the filter column index
                    filter_col_idx = None
                    if isinstance(filter_col, str):
                        headers = table.get('headers', [])
                        for i, header in enumerate(headers):
                            if filter_col.lower() in header.lower():
                                filter_col_idx = i
                                break
                    else:
                        filter_col_idx = filter_col

                    if filter_col_idx is None or filter_col_idx >= len(row):
                        matches_filter = False
                        break

                    cell_value = row[filter_col_idx].get('text', '')
                    if filter_val.lower() not in cell_value.lower():
                        matches_filter = False
                        break

                if not matches_filter:
                    continue

            # Extract value from target column
            if col_idx < len(row):
                cell = row[col_idx]
                cell_text = cell.get('text', '')
                cell_conf = cell.get('confidence', 0.0)

                if cell_text:
                    values.append(cell_text)
                    confidences.append(cell_conf)

        if not values:
            return None, 0.0, None

        # Return concatenated values or first value
        result_text = ' | '.join(values) if len(values) > 1 else values[0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Location is the table reference
        location = {
            'table_index': rule.table_index,
            'column_index': col_idx,
            'column_name': rule.column_name,
            'row_count': len(values)
        }

        return result_text, avg_confidence, location


class RegexExtractor(FieldExtractor):
    """Extract text using regex pattern matching"""

    def extract(
        self,
        field_def: FieldDefinition,
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Extract text using regex pattern.

        Searches all text blocks for pattern match, returns first match.
        """
        pattern = field_def.regex_pattern
        if not pattern:
            return None, 0.0, None

        # Get blocks from OCR result
        blocks = ocr_result.get('blocks', [])
        if not blocks:
            return None, 0.0, None

        # Filter by page if specified
        page_blocks = [b for b in blocks if b.get('page', 1) == page]

        # Search through blocks for pattern match
        for block in page_blocks:
            text = block.get('text', '')
            if not text:
                continue

            try:
                match = re.search(pattern, text)
                if match:
                    # Extract matched text (first capture group or full match)
                    extracted = match.group(1) if match.groups() else match.group(0)
                    confidence = block.get('confidence', 0.0)

                    # Get location
                    geometry = block.get('geometry', {})
                    location = geometry.get('boundingBox')

                    return extracted, confidence, location

            except re.error:
                # Invalid regex pattern - skip this block
                continue

        # No match found
        return None, 0.0, None


# Factory function for getting the right extractor
def get_extractor(strategy: ExtractionStrategy) -> FieldExtractor:
    """
    Get the appropriate extractor for a given strategy.

    Args:
        strategy: ExtractionStrategy enum value

    Returns:
        FieldExtractor instance

    Raises:
        ValueError: If strategy is not yet implemented
    """
    extractors = {
        ExtractionStrategy.COORDINATE: CoordinateExtractor(),
        ExtractionStrategy.KEYWORD_PROXIMITY: KeywordProximityExtractor(),
        ExtractionStrategy.TABLE_COLUMN: TableColumnExtractor(),
        ExtractionStrategy.REGEX_PATTERN: RegexExtractor(),
    }

    extractor = extractors.get(strategy)
    if not extractor:
        raise ValueError(
            f"Extractor for strategy '{strategy.value}' not yet implemented. "
            f"Available strategies: {list(extractors.keys())}"
        )

    return extractor


# Profile Extraction Orchestrator
class ProfileExtractor:
    """
    Orchestrates extraction of all fields in a profile.

    Combines extraction strategies, transformations, and validations
    into a complete extraction pipeline.
    """

    def __init__(self, llm_client=None):
        """
        Initialize profile extractor.

        Args:
            llm_client: Optional LLM client for semantic extraction (AWS Bedrock, etc.)
        """
        self.llm_client = llm_client

        # Import utilities
        from field_utils import FieldTransformers, FieldValidators
        self.transformers = FieldTransformers()
        self.validators = FieldValidators()

    def extract_all_fields(
        self,
        profile: 'ExtractionProfile',
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Extract all fields defined in profile from OCR result.

        Args:
            profile: ExtractionProfile with field definitions
            ocr_result: Normalized OCR result (DTAT format)
            page: Page number to extract from (default: 1)

        Returns:
            Dictionary with extraction results:
            {
                'profile_id': int,
                'profile_name': str,
                'fields': {
                    'field_name': {
                        'value': Any,  # Transformed value
                        'raw_value': str,  # Original extracted text
                        'confidence': float,  # 0.0-1.0
                        'location': dict,  # Bounding box or location info
                        'valid': bool,  # Passed validation
                        'validation_error': str | None,  # Error message if invalid
                        'field_type': str,  # Field type
                        'strategy': str  # Extraction strategy used
                    },
                    ...
                },
                'statistics': {
                    'total_fields': int,
                    'extracted': int,  # Successfully extracted
                    'failed': int,  # Failed to extract
                    'validated': int,  # Passed validation
                    'validation_failed': int,  # Failed validation
                    'avg_confidence': float  # Average confidence across all fields
                }
            }
        """
        from profiles import ExtractionProfile, FieldType

        results = {
            'profile_id': profile.id,
            'profile_name': profile.name,
            'fields': {},
            'statistics': {
                'total_fields': len(profile.fields),
                'extracted': 0,
                'failed': 0,
                'validated': 0,
                'validation_failed': 0,
                'avg_confidence': 0.0
            }
        }

        confidences = []

        # Process each field
        for field_def in profile.fields:
            field_result = self._extract_field(field_def, ocr_result, page)
            results['fields'][field_def.name] = field_result

            # Update statistics
            if field_result['value'] is not None:
                results['statistics']['extracted'] += 1
                confidences.append(field_result['confidence'])
            else:
                results['statistics']['failed'] += 1

            if field_result['valid']:
                results['statistics']['validated'] += 1
            else:
                results['statistics']['validation_failed'] += 1

        # Calculate average confidence
        if confidences:
            results['statistics']['avg_confidence'] = sum(confidences) / len(confidences)

        return results

    def _extract_field(
        self,
        field_def: 'FieldDefinition',
        ocr_result: Dict[str, Any],
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Extract a single field with transformation and validation.

        Args:
            field_def: Field definition with extraction rules
            ocr_result: OCR result data
            page: Page number

        Returns:
            Dictionary with field extraction result
        """
        from profiles import FieldType

        # Initialize result structure
        field_result = {
            'value': None,
            'raw_value': None,
            'confidence': 0.0,
            'location': None,
            'valid': True,
            'validation_error': None,
            'field_type': field_def.field_type.value,
            'strategy': field_def.strategy.value
        }

        try:
            # Step 1: Extract raw value using appropriate strategy
            extractor = get_extractor(field_def.strategy)
            raw_value, confidence, location = extractor.extract(field_def, ocr_result, page)

            # Store raw extraction results
            field_result['raw_value'] = raw_value
            field_result['confidence'] = confidence
            field_result['location'] = location

            # If extraction failed, use default value if available
            if raw_value is None:
                if field_def.default_value is not None:
                    field_result['value'] = field_def.default_value
                    field_result['valid'] = True
                    return field_result
                else:
                    # No default value, validate as missing
                    is_valid, error = self.validators.validate_field(None, field_def)
                    field_result['valid'] = is_valid
                    field_result['validation_error'] = error
                    return field_result

            # Step 2: Transform value based on field type
            transformed_value = self._transform_value(raw_value, field_def)
            field_result['value'] = transformed_value

            # Step 3: Apply format string if specified
            if field_def.format_string and transformed_value is not None:
                formatted = self.transformers.apply_format_string(
                    transformed_value,
                    field_def.format_string
                )
                if formatted is not None:
                    field_result['value'] = formatted

            # Step 4: Use default value if transformation failed
            if field_result['value'] is None and field_def.default_value is not None:
                field_result['value'] = field_def.default_value

            # Step 5: Validate the final value
            is_valid, error = self.validators.validate_field(
                field_result['value'],
                field_def
            )
            field_result['valid'] = is_valid
            field_result['validation_error'] = error

        except Exception as e:
            # Handle extraction errors gracefully
            field_result['valid'] = False
            field_result['validation_error'] = f"Extraction error: {str(e)}"

        return field_result

    def _transform_value(
        self,
        raw_value: str,
        field_def: 'FieldDefinition'
    ) -> Any:
        """
        Transform raw extracted text to typed value based on field type.

        Args:
            raw_value: Raw text extracted from document
            field_def: Field definition with type info

        Returns:
            Transformed value or None if transformation fails
        """
        from profiles import FieldType

        if raw_value is None:
            return None

        # Apply transformation based on field type
        try:
            if field_def.field_type == FieldType.NUMBER:
                return self.transformers.to_number(raw_value)

            elif field_def.field_type == FieldType.CURRENCY:
                return self.transformers.to_currency(raw_value)

            elif field_def.field_type == FieldType.DATE:
                return self.transformers.to_date(raw_value)

            elif field_def.field_type == FieldType.PHONE:
                return self.transformers.normalize_phone(raw_value)

            elif field_def.field_type == FieldType.BOOLEAN:
                return self.transformers.to_boolean(raw_value)

            elif field_def.field_type == FieldType.EMAIL:
                # Email is just text, return as-is (could add validation)
                return raw_value.strip()

            elif field_def.field_type == FieldType.ADDRESS:
                # Address is just text, return as-is
                return raw_value.strip()

            elif field_def.field_type == FieldType.TEXT:
                # Plain text, return as-is
                return raw_value.strip()

            else:
                # Unknown type, return raw value
                return raw_value

        except Exception:
            # Transformation failed, return None
            return None

    def extract_with_retry(
        self,
        profile: 'ExtractionProfile',
        ocr_result: Dict[str, Any],
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Extract fields with retry logic for failed extractions.

        Useful for handling transient failures or trying different strategies.

        Args:
            profile: ExtractionProfile
            ocr_result: OCR result
            max_retries: Maximum retry attempts per field

        Returns:
            Extraction results with retry statistics
        """
        results = self.extract_all_fields(profile, ocr_result)

        # Track retry attempts
        results['retry_info'] = {
            'attempted': 0,
            'succeeded': 0,
            'failed': 0
        }

        # Retry failed required fields
        if results['statistics']['failed'] > 0:
            for field_name, field_result in results['fields'].items():
                if field_result['value'] is None:
                    # Find field definition
                    field_def = next(
                        (f for f in profile.fields if f.name == field_name),
                        None
                    )

                    if field_def and field_def.required:
                        # Retry extraction
                        for attempt in range(max_retries):
                            results['retry_info']['attempted'] += 1
                            retry_result = self._extract_field(
                                field_def,
                                ocr_result
                            )

                            if retry_result['value'] is not None:
                                results['fields'][field_name] = retry_result
                                results['statistics']['failed'] -= 1
                                results['statistics']['extracted'] += 1
                                results['retry_info']['succeeded'] += 1
                                break
                        else:
                            results['retry_info']['failed'] += 1

        return results
