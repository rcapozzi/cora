"""Tests for UUID v7 utilities."""

import pytest
from cora.utils.ids import generate_uuid7, is_valid_uuid7


class TestUUID7Generation:
    def test_generate_uuid7_returns_string(self):
        result = generate_uuid7()
        assert isinstance(result, str)

    def test_generate_uuid7_format(self):
        result = generate_uuid7()
        # UUID v7 format: xxxxxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx (36 chars)
        assert len(result) == 36
        assert result.count('-') == 4
        parts = result.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_generate_uuid7_version_bits(self):
        result = generate_uuid7()
        # Version is in the 13th character (index 14 with dashes)
        # UUID v7 has version = 7
        assert result[14] == '7'

    def test_generate_uuid7_uniqueness(self):
        ids = {generate_uuid7() for _ in range(100)}
        assert len(ids) == 100  # All unique

    def test_is_valid_uuid7_valid(self):
        uuid_str = generate_uuid7()
        assert is_valid_uuid7(uuid_str) is True

    def test_is_valid_uuid7_invalid_format(self):
        assert is_valid_uuid7("not-a-uuid") is False
        assert is_valid_uuid7("") is False
        assert is_valid_uuid7("018f1e8e-7b32-7c00-8000-000000000000") is True  # Valid v7

    def test_is_valid_uuid7_wrong_version(self):
        # UUID v4 (random) should fail v7 validation
        import uuid
        v4_str = str(uuid.uuid4())
        # v4 has version 4 at position 14
        assert is_valid_uuid7(v4_str) is False