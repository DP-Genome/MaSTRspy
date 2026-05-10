"""Tests for src.filters.bam_accuracy module (pure logic functions)."""

from unittest.mock import MagicMock

import pytest

from src.filters.bam_accuracy import (
    _compute_accuracy_fast,
    _get_ins_del_from_cigar,
    _get_matches_mismatches_from_md,
)


class TestComputeAccuracyFast:
    def test_no_nm_tag(self):
        read = MagicMock()
        read.get_tag.side_effect = KeyError("NM")
        assert _compute_accuracy_fast(read) is None

    def test_no_cigar(self):
        read = MagicMock()
        read.get_tag.return_value = 5
        read.cigartuples = None
        assert _compute_accuracy_fast(read) is None

    def test_perfect_alignment(self):
        read = MagicMock()
        read.get_tag.return_value = 0  # NM = 0
        read.cigartuples = [(0, 100)]  # 100M
        assert _compute_accuracy_fast(read) == 1.0

    def test_with_mismatches(self):
        read = MagicMock()
        read.get_tag.return_value = 5  # NM = 5
        read.cigartuples = [(0, 100)]  # 100M
        assert _compute_accuracy_fast(read) == pytest.approx(0.95)

    def test_with_indels(self):
        read = MagicMock()
        # NM = 3 (1 mismatch + 2 insertions)
        read.get_tag.return_value = 3
        # 90M + 2I + 8M = denom 100
        read.cigartuples = [(0, 90), (1, 2), (0, 8)]
        assert _compute_accuracy_fast(read) == pytest.approx(0.97)

    def test_zero_denom(self):
        read = MagicMock()
        read.get_tag.return_value = 0
        # Only soft clips (op 4), no M/I/D
        read.cigartuples = [(4, 50)]
        assert _compute_accuracy_fast(read) is None

    def test_ignores_soft_hard_clips(self):
        read = MagicMock()
        read.get_tag.return_value = 2  # NM = 2
        # 10S + 80M + 5I + 5D + 10S → denom = 80+5+5 = 90
        read.cigartuples = [(4, 10), (0, 80), (1, 5), (2, 5), (4, 10)]
        assert _compute_accuracy_fast(read) == pytest.approx((90 - 2) / 90)


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
