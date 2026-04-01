"""
Configuration for Document Processing Pipeline
"""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class ProcessingConfig:
    """Pipeline configuration - easily toggle features."""

    # Extraction levels (enable/disable)
    enable_native_extraction: bool = True    # Level 1: Free parsing
    enable_local_ocr: bool = False           # Level 2: LightOnOCR (disabled - too slow on CPU)
    enable_textract: bool = True             # Level 3: AWS Textract (~1-3s per page)

    # Retry settings
    max_retries_per_level: int = 2
    retry_delay_seconds: int = 5

    # Quality thresholds (0-100)
    min_confidence_score: int = 60           # Below this, escalate to next level
    min_chars_per_page: int = 100            # Below this, likely failed extraction
    max_gibberish_ratio: float = 0.15        # Above this, likely garbage output

    # OCR Model settings
    ocr_model_name: str = "lightonai/LightOnOCR-1B-1025"
    ocr_max_new_tokens: int = 2048
    ocr_image_max_dim: int = 1540
    ocr_offline_mode: bool = True  # Don't call HF Hub if model is cached

    # AWS settings (for Textract)
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    textract_features: list = field(default_factory=lambda: ["TABLES", "FORMS"])
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    s3_prefix: str = field(default_factory=lambda: os.getenv("S3_PREFIX", "dtat-ocr/temp/"))

    # Database settings
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "sqlite:///documents.db"
    ))

    # Storage settings
    store_original_file: bool = True         # Store original doc as base64 too
    max_file_size_mb: int = 50               # Reject files larger than this

    # Edge case handling
    enable_dedup: bool = True                # Skip re-processing identical documents
    enable_handwriting: bool = True          # Add HANDWRITING to Textract FeatureTypes for images
    blank_page_threshold: int = 10           # Pages with fewer chars flagged as blank
    default_language: str = field(default_factory=lambda: os.getenv("OCR_LANGUAGE", "en"))  # Language hint

    # Processing settings
    batch_size: int = 10                     # Process N docs before committing
    worker_timeout_seconds: int = 300        # 5 min max per document


# Default config - can be overridden
config = ProcessingConfig()


def enable_textract():
    """Enable Textract fallback (for production use)."""
    config.enable_textract = True
    print("Textract fallback ENABLED")


def disable_textract():
    """Disable Textract fallback (for cost savings)."""
    config.enable_textract = False
    print("Textract fallback DISABLED")
