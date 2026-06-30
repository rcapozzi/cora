"""UUID v7 generation utilities per RFC 9562."""

import uuid6


def generate_uuid7() -> str:
    """Generate a UUID v7 (time-ordered) as a canonical 36-character string.

    Returns:
        str: UUID v7 in standard format (e.g., '018f1e8e-7b32-7c00-8000-000000000000')
    """
    return str(uuid6.uuid7())


def is_valid_uuid7(value: str) -> bool:
    """Validate that a string is a valid UUID v7 format.

    Args:
        value: String to validate

    Returns:
        bool: True if valid UUID v7 format, False otherwise
    """
    try:
        uuid_obj = uuid6.UUID(value)
        # UUID v7 has version bits = 7 (bits 48-51 of the UUID)
        return uuid_obj.version == 7
    except (ValueError, AttributeError):
        return False