"""
File validation for uploaded documents.
Catches corrupted, empty, and mismatched files before they enter the pipeline.
"""

from pathlib import Path

# Magic bytes for common file types
MAGIC_BYTES = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "tiff": [b"II\x2a\x00", b"MM\x00\x2a"],  # Little-endian, Big-endian
    "tif": [b"II\x2a\x00", b"MM\x00\x2a"],
    "bmp": [b"BM"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],
    "xlsx": [b"PK\x03\x04"],  # ZIP-based
    "docx": [b"PK\x03\x04"],  # ZIP-based
    "csv": None,  # No magic bytes for CSV
}

MIN_FILE_SIZE = 100  # bytes


class ValidationError:
    def __init__(self, message: str, error_type: str = "invalid_file"):
        self.message = message
        self.error_type = error_type


def validate_file(file_bytes: bytes, file_type: str) -> ValidationError | None:
    """
    Validate uploaded file. Returns None if valid, ValidationError if not.
    """
    # Check empty
    if not file_bytes:
        return ValidationError("File is empty.", "empty_file")

    if len(file_bytes) < MIN_FILE_SIZE:
        return ValidationError(
            f"File too small ({len(file_bytes)} bytes). Minimum is {MIN_FILE_SIZE} bytes.",
            "file_too_small"
        )

    # Check magic bytes
    expected = MAGIC_BYTES.get(file_type.lower())
    if expected is not None:
        matches = any(file_bytes[:len(magic)] == magic for magic in expected)
        if not matches:
            return ValidationError(
                f"File content does not match expected {file_type.upper()} format. "
                f"The file may be corrupted or incorrectly named.",
                "magic_mismatch"
            )

    # Validate images can be decoded
    if file_type.lower() in ("png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif", "webp"):
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(file_bytes))
            img.verify()
        except Exception:
            return ValidationError(
                f"Image file cannot be decoded. The file may be corrupted or truncated.",
                "image_corrupt"
            )

    # Validate PDFs have at least 1 page
    if file_type.lower() == "pdf":
        try:
            import pdfplumber
            from io import BytesIO
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return ValidationError("PDF has no pages.", "empty_pdf")
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ["encrypt", "password", "protected", "crypt"]):
                return ValidationError(
                    "PDF is password-protected. Please provide an unencrypted version.",
                    "encrypted_pdf"
                )
            return ValidationError(
                f"PDF cannot be opened. The file may be corrupted: {str(e)[:100]}",
                "pdf_corrupt"
            )

    return None
