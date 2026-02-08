"""Tests for src.pipeline.allele_parser module."""

import pytest

from src.pipeline.allele_parser import (
    ParsedAllele,
    call_zygosity,
    detect_stutter,
    parse_allele_name,
    parse_allele_with_counts,
)


class TestParsedAlleleCeFloat:
    def test_integer_ce_returns_float(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="15", motif="")
        assert allele.ce_float == 15.0

    def test_decimal_ce_returns_float(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="15.3", motif="")
        assert allele.ce_float == 15.3

    def test_empty_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="", motif="")
        assert allele.ce_float is None

    def test_non_numeric_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="abc", motif="")
        assert allele.ce_float is None

    def test_none_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number=None, motif="")
        assert allele.ce_float is None


class TestParsedAlleleRepeatCount:
    def test_integer_ce_returns_int(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="15", motif="")
        assert allele.repeat_count == 15

    def test_decimal_ce_returns_integer_part(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="15.3", motif="")
        assert allele.repeat_count == 15

    def test_empty_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="", motif="")
        assert allele.repeat_count is None

    def test_non_numeric_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="abc", motif="")
        assert allele.repeat_count is None

    def test_none_ce_returns_none(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number=None, motif="")
        assert allele.repeat_count is None


class TestParsedAlleleDefaults:
    def test_raw_count_defaults_to_zero(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="10", motif="")
        assert allele.raw_count == 0

    def test_normalized_count_defaults_to_zero(self):
        allele = ParsedAllele(raw_name="x", locus="L", ce_number="10", motif="")
        assert allele.normalized_count == 0.0


class TestParseAlleleName:
    def test_standard_format(self):
        result = parse_allele_name("D3S1358_CE15_[TCTA]15")
        assert result.locus == "D3S1358"
        assert result.ce_number == "15"
        assert result.motif == "[TCTA]15"
        assert result.raw_name == "D3S1358_CE15_[TCTA]15"

    def test_decimal_ce(self):
        result = parse_allele_name("D3S1358_CE15.3_[TCTA]15[TCT]1")
        assert result.locus == "D3S1358"
        assert result.ce_number == "15.3"
        assert result.motif == "[TCTA]15[TCT]1"

    def test_decimal_ce_float_property(self):
        result = parse_allele_name("D3S1358_CE15.3_[TCTA]15[TCT]1")
        assert result.ce_float == 15.3

    def test_decimal_ce_repeat_count(self):
        result = parse_allele_name("D3S1358_CE15.3_[TCTA]15[TCT]1")
        assert result.repeat_count == 15

    def test_unknown_format_no_ce(self):
        result = parse_allele_name("SOME_RANDOM_STRING")
        assert result.raw_name == "SOME_RANDOM_STRING"
        assert result.ce_number == ""
        assert result.motif == ""
        assert result.locus == "SOME"

    def test_unknown_format_with_brackets_only(self):
        result = parse_allele_name("LOCUS_[MOTIF]5")
        assert result.motif == "[MOTIF]5"
        assert result.ce_number == ""
        assert result.locus == "LOCUS"

    def test_vwa_locus(self):
        result = parse_allele_name("vWA_CE17_[TCTA]17")
        assert result.locus == "vWA"
        assert result.ce_number == "17"

    def test_complex_motif_multiple_brackets(self):
        result = parse_allele_name("D3S1358_CE16_[TCTA]10[TCTG]3[TCTA]3")
        assert result.motif == "[TCTA]10[TCTG]3[TCTA]3"
        assert result.ce_number == "16"

    def test_counts_default_to_zero(self):
        result = parse_allele_name("D3S1358_CE15_[TCTA]15")
        assert result.raw_count == 0
        assert result.normalized_count == 0.0


class TestParseAlleleWithCounts:
    def test_normalization_calculation(self):
        result = parse_allele_with_counts("D3S1358_CE15_[TCTA]15", 80, 100)
        assert result.raw_count == 80
        assert result.normalized_count == pytest.approx(0.8)

    def test_max_count_gives_normalized_one(self):
        result = parse_allele_with_counts("D3S1358_CE15_[TCTA]15", 100, 100)
        assert result.normalized_count == pytest.approx(1.0)

    def test_zero_max_count_gives_normalized_zero(self):
        result = parse_allele_with_counts("D3S1358_CE15_[TCTA]15", 50, 0)
        assert result.normalized_count == 0.0

    def test_preserves_parsed_fields(self):
        result = parse_allele_with_counts("D3S1358_CE15_[TCTA]15", 50, 100)
        assert result.locus == "D3S1358"
        assert result.ce_number == "15"
        assert result.motif == "[TCTA]15"

    def test_small_count(self):
        result = parse_allele_with_counts("D3S1358_CE15_[TCTA]15", 1, 1000)
        assert result.normalized_count == pytest.approx(0.001)


class TestDetectStutter:
    def test_removes_n_minus_1_stutter_below_threshold(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        stutter = ParsedAllele(
            raw_name="b", locus="L", ce_number="14", motif="m",
            raw_count=10, normalized_count=0.10,
        )
        result = detect_stutter([major, stutter], stutter_ratio=0.15)
        assert len(result) == 1
        assert result[0].ce_number == "15"

    def test_removes_n_plus_1_stutter_below_threshold(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        stutter = ParsedAllele(
            raw_name="b", locus="L", ce_number="16", motif="m",
            raw_count=5, normalized_count=0.05,
        )
        result = detect_stutter([major, stutter], stutter_ratio=0.15)
        assert len(result) == 1

    def test_keeps_real_allele_above_threshold(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        real = ParsedAllele(
            raw_name="b", locus="L", ce_number="14", motif="m",
            raw_count=80, normalized_count=0.80,
        )
        result = detect_stutter([major, real], stutter_ratio=0.15)
        assert len(result) == 2

    def test_keeps_allele_not_at_stutter_position(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        distant = ParsedAllele(
            raw_name="b", locus="L", ce_number="12", motif="m",
            raw_count=10, normalized_count=0.10,
        )
        result = detect_stutter([major, distant], stutter_ratio=0.15)
        assert len(result) == 2

    def test_handles_empty_list(self):
        result = detect_stutter([])
        assert result == []

    def test_handles_single_allele(self):
        allele = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        result = detect_stutter([allele])
        assert len(result) == 1

    def test_handles_alleles_without_repeat_count_major(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        minor = ParsedAllele(
            raw_name="b", locus="L", ce_number="14", motif="m",
            raw_count=5, normalized_count=0.05,
        )
        result = detect_stutter([major, minor])
        assert len(result) == 2  # Can't detect stutter without major repeat

    def test_handles_alleles_without_repeat_count_minor(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        minor = ParsedAllele(
            raw_name="b", locus="L", ce_number="", motif="m",
            raw_count=5, normalized_count=0.05,
        )
        result = detect_stutter([major, minor])
        assert len(result) == 2  # Minor without CE is kept

    def test_stutter_exactly_at_threshold_is_removed(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        borderline = ParsedAllele(
            raw_name="b", locus="L", ce_number="14", motif="m",
            raw_count=15, normalized_count=0.15,
        )
        result = detect_stutter([major, borderline], stutter_ratio=0.15)
        assert len(result) == 1  # 0.15 <= 0.15, so it IS removed

    def test_multiple_alleles_mixed(self):
        major = ParsedAllele(
            raw_name="a", locus="L", ce_number="15", motif="m",
            raw_count=100, normalized_count=1.0,
        )
        real = ParsedAllele(
            raw_name="b", locus="L", ce_number="16", motif="m",
            raw_count=80, normalized_count=0.80,
        )
        stutter = ParsedAllele(
            raw_name="c", locus="L", ce_number="14", motif="m",
            raw_count=10, normalized_count=0.10,
        )
        result = detect_stutter([major, real, stutter], stutter_ratio=0.15)
        assert len(result) == 2
        ce_numbers = [a.ce_number for a in result]
        assert "15" in ce_numbers
        assert "16" in ce_numbers
        assert "14" not in ce_numbers


class TestCallZygosity:
    def test_heterozygous_with_two_passing(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=100, normalized_count=1.0,
            ),
            ParsedAllele(
                raw_name="b", locus="L", ce_number="16", motif="m",
                raw_count=80, normalized_count=0.80,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.3) == "Heterozygous"

    def test_heterozygous_with_three_passing(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=100, normalized_count=1.0,
            ),
            ParsedAllele(
                raw_name="b", locus="L", ce_number="16", motif="m",
                raw_count=80, normalized_count=0.80,
            ),
            ParsedAllele(
                raw_name="c", locus="L", ce_number="17", motif="m",
                raw_count=50, normalized_count=0.50,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.3) == "Heterozygous"

    def test_homozygous_with_one_passing(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=100, normalized_count=1.0,
            ),
            ParsedAllele(
                raw_name="b", locus="L", ce_number="14", motif="m",
                raw_count=5, normalized_count=0.05,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.3) == "Homozygous"

    def test_no_call_with_zero_passing(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=5, normalized_count=0.05,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.3) == "No Call"

    def test_no_call_with_empty_list(self):
        assert call_zygosity([], norm_cutoff=0.3) == "No Call"

    def test_cutoff_boundary_exact_match_passes(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=100, normalized_count=0.30,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.30) == "Homozygous"

    def test_cutoff_boundary_just_below_fails(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=100, normalized_count=0.29,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.30) == "No Call"

    def test_zero_cutoff_everything_passes(self):
        alleles = [
            ParsedAllele(
                raw_name="a", locus="L", ce_number="15", motif="m",
                raw_count=1, normalized_count=0.0,
            ),
        ]
        assert call_zygosity(alleles, norm_cutoff=0.0) == "Homozygous"
