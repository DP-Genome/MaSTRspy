"""Tests for src.pipeline.analysis module (helper and config logic)."""

from unittest.mock import patch

import pytest

from src.pipeline.analysis import _process_locus_wrapper


class TestProcessLocusWrapper:
    @patch("src.pipeline.analysis.process_locus")
    def test_unpacks_args_correctly(self, mock_process):
        args = ("sample.bam", "locus.bed", {"key": "val"}, None)
        _process_locus_wrapper(args)
        mock_process.assert_called_once_with(
            "sample.bam", "locus.bed", {"key": "val"}, None
        )

    @patch("src.pipeline.analysis.process_locus")
    def test_propagates_exception(self, mock_process):
        mock_process.side_effect = RuntimeError("fail")
        with pytest.raises(RuntimeError, match="fail"):
            _process_locus_wrapper(("a", "b", {}, None))
