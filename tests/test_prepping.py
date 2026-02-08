"""Tests for src.pipeline.prepping module (barcode extraction logic)."""

import pytest

from src.pipeline.prepping import _extract_barcode_name


class TestExtractBarcodeName:
    def _log(self, msg):
        """Capture log messages."""
        self._messages.append(msg)

    def setup_method(self):
        self._messages = []

    def test_barcode_standard(self):
        assert _extract_barcode_name("barcode12", self._log) == "barcode12"

    def test_barcode_with_underscore(self):
        assert _extract_barcode_name("barcode_05", self._log) == "barcode05"

    def test_barcode_leading_zero(self):
        assert _extract_barcode_name("barcode1", self._log) == "barcode01"

    def test_barcode_uppercase(self):
        assert _extract_barcode_name("Barcode12", self._log) == "barcode12"

    def test_bc_pattern(self):
        assert _extract_barcode_name("BC12", self._log) == "barcode12"

    def test_bc_with_underscore(self):
        assert _extract_barcode_name("bc_05", self._log) == "barcode05"

    def test_trailing_number(self):
        assert _extract_barcode_name("sample_12", self._log) == "barcode12"

    def test_trailing_number_out_of_range(self):
        # Number > 96 should not match trailing pattern
        result = _extract_barcode_name("sample_99", self._log)
        assert result == "sample_99"  # Falls back to original

    def test_unclassified(self):
        assert _extract_barcode_name("unclassified", self._log) == "unclassified"

    def test_unclassified_case_insensitive(self):
        assert _extract_barcode_name("Unclassified", self._log) == "unclassified"

    def test_unknown_pattern_returns_original(self):
        result = _extract_barcode_name("mystery_file", self._log)
        assert result == "mystery_file"
        assert len(self._messages) == 1
        assert "WARNING" in self._messages[0]

    def test_barcode_in_complex_name(self):
        assert _extract_barcode_name("run1_barcode03_filtered", self._log) == "barcode03"

    def test_double_digit_formatting(self):
        # Single digit barcodes should be zero-padded
        assert _extract_barcode_name("barcode1", self._log) == "barcode01"
        assert _extract_barcode_name("barcode9", self._log) == "barcode09"

    def test_valid_trailing_range(self):
        # Numbers 1-96 are valid barcodes
        assert _extract_barcode_name("sample_1", self._log) == "barcode01"
        assert _extract_barcode_name("sample_96", self._log) == "barcode96"

    def test_zero_trailing_not_valid(self):
        # 0 is not a valid barcode number (range is 1-96)
        result = _extract_barcode_name("sample_0", self._log)
        assert result == "sample_0"
