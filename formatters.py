"""
Output Formatters for Multi-Format OCR Support

Converts internal normalized format to industry-standard formats:
- Textract: AWS Textract-compatible
- Google: Google Cloud Vision-compatible (future)
- Azure: Azure Computer Vision-compatible (future)
- DTAT: Native format (backward compatibility)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from extraction_pipeline import NormalizedResult, NormalizedBlock


class OutputFormatter(ABC):
    """Base class for output formatters"""

    @abstractmethod
    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        """
        Convert normalized result to specific format.

        Args:
            result: Internal normalized extraction result

        Returns:
            Formatted output as dictionary (ready for JSON serialization)
        """
        pass


class TextractFormatter(OutputFormatter):
    """
    AWS Textract-compatible format.

    Implements DetectDocumentText API response structure:
    https://docs.aws.amazon.com/textract/latest/dg/API_DetectDocumentText.html
    """

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        """Convert to Textract format"""
        blocks = []

        # Convert each normalized block to Textract block
        for block in result.blocks:
            textract_block = self._convert_block(block)
            blocks.append(textract_block)

        return {
            "Blocks": blocks,
            "DocumentMetadata": {
                "Pages": result.page_count
            },
            "DetectDocumentTextModelVersion": "1.0",
            "ResponseMetadata": {
                "RequestId": "dtat-ocr",
                "HTTPStatusCode": 200
            }
        }

    def _convert_block(self, block: NormalizedBlock) -> Dict[str, Any]:
        """Convert NormalizedBlock to Textract block format"""
        textract_block = {
            "BlockType": block.block_type.upper(),
            "Id": block.id,
            "Confidence": block.confidence,
            "Geometry": {
                "BoundingBox": {
                    "Left": block.geometry.bounding_box.left,
                    "Top": block.geometry.bounding_box.top,
                    "Width": block.geometry.bounding_box.width,
                    "Height": block.geometry.bounding_box.height
                },
                "Polygon": [
                    {"X": p.x, "Y": p.y} for p in block.geometry.polygon
                ]
            },
            "Page": block.page
        }

        # Add text if present
        if block.text:
            textract_block["Text"] = block.text

        # Add relationships if present
        if block.relationships:
            textract_block["Relationships"] = [
                {
                    "Type": rel.type.upper(),
                    "Ids": rel.ids
                }
                for rel in block.relationships
            ]

        return textract_block


class GoogleVisionFormatter(OutputFormatter):
    """
    Google Cloud Vision-compatible format.

    Implements Text Detection API response structure:
    https://cloud.google.com/vision/docs/ocr

    Note: Google uses absolute pixel coordinates, so we convert from normalized.
    """

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        """Convert to Google Vision format"""
        # Google uses absolute coordinates - assume standard page size
        # In production, we'd get actual image dimensions from document metadata
        page_width = 1000
        page_height = 1000

        text_annotations = []

        # First annotation is full text
        full_text = self._extract_full_text(result.blocks)
        if full_text:
            text_annotations.append({
                "description": full_text,
                "boundingPoly": self._get_document_bounds(result.blocks, page_width, page_height)
            })

        # Subsequent annotations are individual text blocks
        for block in result.blocks:
            if block.text and block.block_type in ["WORD", "LINE"]:
                text_annotations.append({
                    "description": block.text,
                    "boundingPoly": self._convert_polygon(
                        block.geometry.polygon,
                        page_width,
                        page_height
                    )
                })

        return {
            "textAnnotations": text_annotations,
            "fullTextAnnotation": {
                "text": full_text,
                "pages": self._build_pages(result, page_width, page_height)
            }
        }

    def _extract_full_text(self, blocks: List[NormalizedBlock]) -> str:
        """Extract all text from LINE blocks"""
        lines = [b.text for b in blocks if b.block_type == "LINE" and b.text]
        return "\n".join(lines)

    def _get_document_bounds(self, blocks: List[NormalizedBlock], width: int, height: int) -> Dict:
        """Get bounding box for entire document"""
        # Simplified - use full page bounds
        return {
            "vertices": [
                {"x": 0, "y": 0},
                {"x": width, "y": 0},
                {"x": width, "y": height},
                {"x": 0, "y": height}
            ]
        }

    def _convert_polygon(self, polygon: List, width: int, height: int) -> Dict:
        """Convert normalized polygon to absolute pixel coordinates"""
        return {
            "vertices": [
                {
                    "x": int(p.x * width),
                    "y": int(p.y * height)
                }
                for p in polygon
            ]
        }

    def _build_pages(self, result: NormalizedResult, width: int, height: int) -> List[Dict]:
        """Build page structure for fullTextAnnotation"""
        pages = []
        for page_num in range(1, result.page_count + 1):
            page_blocks = [b for b in result.blocks if b.page == page_num]

            pages.append({
                "width": width,
                "height": height,
                "blocks": [
                    {
                        "boundingBox": self._convert_polygon(b.geometry.polygon, width, height),
                        "paragraphs": [{
                            "boundingBox": self._convert_polygon(b.geometry.polygon, width, height),
                            "words": [{
                                "boundingBox": self._convert_polygon(b.geometry.polygon, width, height),
                                "symbols": []
                            }]
                        }]
                    }
                    for b in page_blocks if b.block_type == "LINE"
                ]
            })

        return pages


class AzureOCRFormatter(OutputFormatter):
    """
    Azure Computer Vision Read API-compatible format.

    Implements Read API response structure:
    https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/call-read-api
    """

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        """Convert to Azure OCR format"""
        # Azure uses absolute coordinates
        page_width = 1000
        page_height = 1000

        return {
            "status": "succeeded",
            "createdDateTime": "2024-01-01T00:00:00Z",
            "lastUpdatedDateTime": "2024-01-01T00:00:00Z",
            "analyzeResult": {
                "version": "3.2",
                "modelVersion": "2022-04-30",
                "readResults": self._build_read_results(result, page_width, page_height)
            }
        }

    def _build_read_results(self, result: NormalizedResult, width: int, height: int) -> List[Dict]:
        """Build readResults array (one entry per page)"""
        read_results = []

        for page_num in range(1, result.page_count + 1):
            page_blocks = [b for b in result.blocks if b.page == page_num and b.block_type == "LINE"]

            read_results.append({
                "page": page_num,
                "angle": 0,
                "width": width,
                "height": height,
                "unit": "pixel",
                "lines": [
                    {
                        "text": block.text,
                        "boundingBox": self._convert_to_8point(
                            block.geometry.polygon,
                            width,
                            height
                        ),
                        "words": self._split_into_words(block.text, block.geometry, width, height)
                    }
                    for block in page_blocks if block.text
                ]
            })

        return read_results

    def _convert_to_8point(self, polygon: List, width: int, height: int) -> List[int]:
        """
        Convert polygon to 8-point array [x1,y1,x2,y2,x3,y3,x4,y4].
        Azure uses this format for bounding boxes.
        """
        coords = []
        for point in polygon[:4]:  # Take first 4 points (corners)
            coords.extend([
                int(point.x * width),
                int(point.y * height)
            ])

        # If fewer than 4 points, duplicate the last point
        while len(coords) < 8:
            coords.extend(coords[-2:])

        return coords

    def _split_into_words(self, text: str, geometry, width: int, height: int) -> List[Dict]:
        """
        Split line text into words.
        Note: Without word-level geometry, we approximate word positions.
        """
        if not text:
            return []

        words = text.split()
        word_boxes = []

        # Approximate word positions (equal distribution across line width)
        bbox = geometry.bounding_box
        word_width = bbox.width / len(words) if words else bbox.width

        for i, word in enumerate(words):
            word_left = bbox.left + (i * word_width)
            word_boxes.append({
                "text": word,
                "boundingBox": [
                    int(word_left * width),
                    int(bbox.top * height),
                    int((word_left + word_width) * width),
                    int(bbox.top * height),
                    int((word_left + word_width) * width),
                    int((bbox.top + bbox.height) * height),
                    int(word_left * width),
                    int((bbox.top + bbox.height) * height)
                ],
                "confidence": 0.99  # Placeholder
            })

        return word_boxes


class DTATFormatter(OutputFormatter):
    """
    DTAT native format (backward compatibility).

    Returns the simple format that DTAT originally used.
    """

    def format(self, result: NormalizedResult) -> Dict[str, Any]:
        """Convert to DTAT native format"""
        # Extract text from LINE blocks
        text_lines = [
            block.text for block in result.blocks
            if block.block_type == "LINE" and block.text
        ]

        # Extract tables from TABLE blocks (simplified for now)
        tables = self._extract_tables(result.blocks)

        return {
            "status": "completed",
            "extracted_text": "\n".join(text_lines),
            "extracted_tables": tables,
            "confidence_score": result.confidence_score,
            "page_count": result.page_count,
            "char_count": sum(len(line) for line in text_lines),
            "metadata": {
                "extraction_method": result.document_metadata.extraction_method,
                "processing_time_ms": result.document_metadata.processing_time_ms,
                "block_count": len(result.blocks)
            }
        }

    def _extract_tables(self, blocks: List[NormalizedBlock]) -> List[Dict]:
        """Extract tables from TABLE blocks"""
        tables = []

        # Group TABLE blocks
        table_blocks = [b for b in blocks if b.block_type == "TABLE"]

        for table_block in table_blocks:
            # For now, return basic table info
            # Full table extraction would require CELL blocks and relationships
            tables.append({
                "table_id": table_block.id,
                "page": table_block.page,
                "confidence": table_block.confidence
            })

        return tables


# Formatter registry
FORMATTERS = {
    "textract": TextractFormatter(),
    "google": GoogleVisionFormatter(),
    "azure": AzureOCRFormatter(),
    "dtat": DTATFormatter()
}


def get_formatter(format_name: str) -> OutputFormatter:
    """
    Get formatter by name.

    Args:
        format_name: "textract", "google", "azure", or "dtat"

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format name is not recognized
    """
    formatter = FORMATTERS.get(format_name.lower())
    if not formatter:
        raise ValueError(
            f"Unknown format: {format_name}. "
            f"Supported formats: {', '.join(FORMATTERS.keys())}"
        )
    return formatter
