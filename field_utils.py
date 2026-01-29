"""
Field Transformation and Validation Utilities

Provides utilities for transforming extracted text into typed values
and validating those values against field definitions.
"""

import re
from datetime import datetime
from typing import Any, Optional, List
from decimal import Decimal, InvalidOperation


class FieldTransformers:
    """Transform extracted text into typed values"""

    @staticmethod
    def to_number(text: str) -> Optional[float]:
        """
        Convert text to number, handling commas and common formats.

        Examples:
            "1,234.56" -> 1234.56
            "1.234,56" -> 1234.56 (European format)
            "$1,234" -> 1234.0
            "1 234" -> 1234.0 (space separator)
        """
        if not text:
            return None

        # Remove common currency symbols and whitespace
        cleaned = text.strip()
        cleaned = re.sub(r'[$€£¥₹]', '', cleaned)
        cleaned = cleaned.replace(' ', '')

        # Detect format: check if comma is decimal separator
        # European format: 1.234,56 (period for thousands, comma for decimal)
        # US format: 1,234.56 (comma for thousands, period for decimal)
        if ',' in cleaned and '.' in cleaned:
            # Both present - determine which is decimal separator
            last_comma = cleaned.rfind(',')
            last_period = cleaned.rfind('.')
            if last_comma > last_period:
                # European: 1.234,56
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # US: 1,234.56
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Only comma - could be thousands or decimal
            # If comma is in last 3 positions, it's likely decimal separator
            comma_pos = cleaned.rfind(',')
            if len(cleaned) - comma_pos <= 3:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        # If only period, keep as is

        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def to_currency(text: str) -> Optional[Decimal]:
        """
        Convert text to currency (Decimal for precision).

        Examples:
            "$1,234.56" -> Decimal("1234.56")
            "USD 1234.56" -> Decimal("1234.56")
            "€1.234,56" -> Decimal("1234.56")
        """
        if not text:
            return None

        # First convert to float using to_number
        num = FieldTransformers.to_number(text)
        if num is None:
            return None

        try:
            # Convert to Decimal for currency precision
            return Decimal(str(num))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def to_date(text: str, formats: Optional[List[str]] = None) -> Optional[datetime]:
        """
        Parse date from text, trying multiple formats.

        Args:
            text: Date string to parse
            formats: List of strftime formats to try (optional)

        Returns:
            datetime object or None

        Default formats:
            - ISO: 2024-01-15, 2024/01/15
            - US: 01/15/2024, 1/15/24
            - European: 15.01.2024, 15/01/2024
            - Written: Jan 15, 2024, January 15, 2024
        """
        if not text:
            return None

        text = text.strip()

        # Default format attempts
        if formats is None:
            formats = [
                '%Y-%m-%d',          # 2024-01-15
                '%Y/%m/%d',          # 2024/01/15
                '%d/%m/%Y',          # 15/01/2024
                '%m/%d/%Y',          # 01/15/2024
                '%d.%m.%Y',          # 15.01.2024
                '%m/%d/%y',          # 01/15/24
                '%d/%m/%y',          # 15/01/24
                '%b %d, %Y',         # Jan 15, 2024
                '%B %d, %Y',         # January 15, 2024
                '%d %b %Y',          # 15 Jan 2024
                '%d %B %Y',          # 15 January 2024
            ]

        # Try each format
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def normalize_phone(text: str, country_code: str = 'US') -> Optional[str]:
        """
        Normalize phone number to standard format.

        Args:
            text: Raw phone number text
            country_code: Country code for formatting (default US)

        Returns:
            Normalized phone number string

        Examples:
            "(555) 123-4567" -> "+1-555-123-4567" (US)
            "555.123.4567" -> "+1-555-123-4567" (US)
            "+1 555 123 4567" -> "+1-555-123-4567" (US)
        """
        if not text:
            return None

        # Extract digits only
        digits = re.sub(r'\D', '', text)

        if not digits:
            return None

        # US phone number formatting
        if country_code == 'US':
            # Check length
            if len(digits) == 10:
                # Add country code
                return f"+1-{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
            elif len(digits) == 11 and digits[0] == '1':
                # Already has country code
                return f"+1-{digits[1:4]}-{digits[4:7]}-{digits[7:11]}"
            elif len(digits) == 7:
                # Local number without area code
                return f"{digits[0:3]}-{digits[3:7]}"

        # International format (E.164)
        # Just return with + and digits for now
        return f"+{digits}"

    @staticmethod
    def to_boolean(text: str) -> Optional[bool]:
        """
        Convert text to boolean.

        True values: "true", "yes", "y", "1", "on", "checked", "✓", "x"
        False values: "false", "no", "n", "0", "off", "unchecked", ""

        Case-insensitive.
        """
        if not text:
            return False

        text = text.strip().lower()

        true_values = {'true', 'yes', 'y', '1', 'on', 'checked', '✓', 'x', 't'}
        false_values = {'false', 'no', 'n', '0', 'off', 'unchecked', '', 'f'}

        if text in true_values:
            return True
        elif text in false_values:
            return False

        return None

    @staticmethod
    def apply_format_string(value: Any, format_string: str) -> Optional[str]:
        """
        Apply format string to value.

        Examples:
            (1234.5, "{:.2f}") -> "1234.50"
            (datetime(2024,1,15), "%Y-%m-%d") -> "2024-01-15"
        """
        if value is None or format_string is None:
            return None

        try:
            # For datetime objects, use strftime
            if isinstance(value, datetime):
                return value.strftime(format_string)
            # For numbers, use format string
            elif isinstance(value, (int, float, Decimal)):
                return format_string.format(value)
            # For strings, pass through
            else:
                return str(value)
        except (ValueError, TypeError):
            return None


class FieldValidators:
    """Validate extracted field values against rules"""

    @staticmethod
    def validate_pattern(value: str, pattern: str) -> bool:
        """
        Validate value matches regex pattern.

        Args:
            value: Text to validate
            pattern: Regex pattern

        Returns:
            True if matches, False otherwise
        """
        if not value or not pattern:
            return True

        try:
            return bool(re.match(pattern, value))
        except re.error:
            # Invalid pattern - consider it passed
            return True

    @staticmethod
    def validate_range(
        value: Any,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> bool:
        """
        Validate numeric value is within range.

        Args:
            value: Value to validate (will be converted to float)
            min_value: Minimum allowed value (inclusive)
            max_value: Maximum allowed value (inclusive)

        Returns:
            True if in range, False otherwise
        """
        if value is None:
            return False

        try:
            # Convert to float for comparison
            if isinstance(value, str):
                num_val = FieldTransformers.to_number(value)
            elif isinstance(value, Decimal):
                num_val = float(value)
            else:
                num_val = float(value)

            if num_val is None:
                return False

            # Check range
            if min_value is not None and num_val < min_value:
                return False
            if max_value is not None and num_val > max_value:
                return False

            return True

        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_allowed_values(value: Any, allowed_values: List[str]) -> bool:
        """
        Validate value is in whitelist.

        Args:
            value: Value to check
            allowed_values: List of allowed values

        Returns:
            True if value in list, False otherwise
        """
        if not allowed_values:
            return True

        if value is None:
            return False

        # Case-insensitive comparison
        value_str = str(value).strip().lower()
        allowed_lower = [str(v).strip().lower() for v in allowed_values]

        return value_str in allowed_lower

    @staticmethod
    def validate_required(value: Any, required: bool) -> bool:
        """
        Validate required field is present.

        Args:
            value: Value to check
            required: Whether field is required

        Returns:
            True if valid, False if required but missing
        """
        if not required:
            return True

        # Check if value is present and non-empty
        if value is None:
            return False

        if isinstance(value, str) and not value.strip():
            return False

        return True

    @staticmethod
    def validate_field(
        value: Any,
        field_def: Any,
        raise_on_error: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Validate value against all field definition rules.

        Args:
            value: Extracted value to validate
            field_def: FieldDefinition with validation rules
            raise_on_error: If True, raise exception on validation failure

        Returns:
            Tuple of (is_valid, error_message)
        """
        from profiles import FieldDefinition

        if not isinstance(field_def, FieldDefinition):
            return True, None

        # Check required
        if not FieldValidators.validate_required(value, field_def.required):
            error = f"Field '{field_def.name}' is required but missing"
            if raise_on_error:
                raise ValueError(error)
            return False, error

        # If value is None/empty and not required, it's valid
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, None

        # Check pattern
        if field_def.validation_pattern:
            if not FieldValidators.validate_pattern(str(value), field_def.validation_pattern):
                error = f"Field '{field_def.name}' does not match pattern '{field_def.validation_pattern}'"
                if raise_on_error:
                    raise ValueError(error)
                return False, error

        # Check range (for numeric fields)
        if field_def.min_value is not None or field_def.max_value is not None:
            if not FieldValidators.validate_range(value, field_def.min_value, field_def.max_value):
                error = f"Field '{field_def.name}' is out of range [{field_def.min_value}, {field_def.max_value}]"
                if raise_on_error:
                    raise ValueError(error)
                return False, error

        # Check allowed values
        if field_def.allowed_values:
            if not FieldValidators.validate_allowed_values(value, field_def.allowed_values):
                error = f"Field '{field_def.name}' must be one of: {field_def.allowed_values}"
                if raise_on_error:
                    raise ValueError(error)
                return False, error

        return True, None
