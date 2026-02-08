"""Tests for src.filters.bam_accuracy module (pure logic functions)."""

from unittest.mock import MagicMock

import pytest

from src.filters.bam_accuracy import (
    _get_ins_del_from_cigar,
    _get_matches_mismatches_from_md,
)


class TestGetInsDelFromCigar:
    def test_no_cigar(self):
        read = MagicMock()
        read.cigartuples = None
        assert _get_ins_del_from_cigar(read) is None

    def test_no_indels(self):
        read = MagicMock()
        # op 0 = MATCH, length 100
        read.cigartuples = [(0, 100)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 0
        assert dels == 0

    def test_insertions_only(self):
        read = MagicMock()
        # op 0 = MATCH (90), op 1 = INS (5), op 0 = MATCH (5)
        read.cigartuples = [(0, 90), (1, 5), (0, 5)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 5
        assert dels == 0

    def test_deletions_only(self):
        read = MagicMock()
        # op 0 = MATCH (90), op 2 = DEL (3), op 0 = MATCH (7)
        read.cigartuples = [(0, 90), (2, 3), (0, 7)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 0
        assert dels == 3

    def test_mixed_indels(self):
        read = MagicMock()
        read.cigartuples = [(0, 80), (1, 3), (0, 10), (2, 2), (0, 5)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 3
        assert dels == 2

    def test_multiple_insertions(self):
        read = MagicMock()
        read.cigartuples = [(0, 50), (1, 2), (0, 30), (1, 4), (0, 14)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 6
        assert dels == 0

    def test_ignores_other_operations(self):
        read = MagicMock()
        # op 4 = SOFT_CLIP, op 5 = HARD_CLIP
        read.cigartuples = [(4, 10), (0, 80), (1, 2), (4, 8)]
        ins, dels = _get_ins_del_from_cigar(read)
        assert ins == 2
        assert dels == 0


class TestGetMatchesMismatchesFromMd:
    def test_no_md_tag(self):
        read = MagicMock()
        read.get_tag.side_effect = KeyError("MD")
        assert _get_matches_mismatches_from_md(read) is None

    def test_all_matches(self):
        read = MagicMock()
        read.get_tag.return_value = "100"  # 100 matches, 0 mismatches
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 100
        assert mismatches == 0

    def test_single_mismatch(self):
        read = MagicMock()
        # 50 matches, 1 mismatch (A), 49 matches
        read.get_tag.return_value = "50A49"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 99
        assert mismatches == 1

    def test_multiple_mismatches(self):
        read = MagicMock()
        # 10 matches, T mismatch, 20 matches, G mismatch, 30 matches
        read.get_tag.return_value = "10T20G30"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 60
        assert mismatches == 2

    def test_deletion_in_md(self):
        read = MagicMock()
        # 50 matches, deletion of ACG, 47 matches
        read.get_tag.return_value = "50^ACG47"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 97
        assert mismatches == 0  # Deletions don't count as mismatches

    def test_complex_md_string(self):
        read = MagicMock()
        # 30 matches, A mismatch, 10 matches, ^TT deletion, 5 matches, C mismatch, 50 matches
        read.get_tag.return_value = "30A10^TT5C50"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 95  # 30 + 10 + 5 + 50
        assert mismatches == 2  # A and C

    def test_zero_length_md(self):
        read = MagicMock()
        read.get_tag.return_value = "0"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 0
        assert mismatches == 0

    def test_consecutive_mismatches(self):
        read = MagicMock()
        # 10 matches, A mismatch, T mismatch (0 in between), 10 matches
        read.get_tag.return_value = "10A0T10"
        matches, mismatches = _get_matches_mismatches_from_md(read)
        assert matches == 20
        assert mismatches == 2
