"""Tests for src.filters.fastq_quality module."""

import os

from src.filters.fastq_quality import _mean_q, filter_fastq


class TestMeanQ:
    def test_empty_string(self):
        assert _mean_q("") == 0.0

    def test_single_char(self):
        # '!' is ASCII 33, Phred 0
        assert _mean_q("!") == 0.0

    def test_known_quality_string(self):
        # '?' is ASCII 63, Phred 30
        assert _mean_q("??") == 30.0

    def test_mixed_qualities(self):
        # '!' = Q0, '?' = Q30 => mean = 15.0
        assert _mean_q("!?") == 15.0

    def test_high_quality(self):
        # 'I' is ASCII 73, Phred 40
        assert _mean_q("III") == 40.0


class TestFilterFastq:
    def test_no_filtering(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        result = filter_fastq(sample_fastq, out, min_mean_q=0, min_len=0)
        assert result["passed"] == 3
        assert result["filtered"] == 0

    def test_length_filter(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        # min_len=8 should keep reads with length >= 8 (read1=10, read3=10)
        result = filter_fastq(sample_fastq, out, min_mean_q=0, min_len=8)
        assert result["passed"] == 2
        assert result["filtered"] == 1

    def test_quality_filter(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        # min_mean_q=20 should keep Q30 reads (read1, read2) but not Q5 (read3)
        result = filter_fastq(sample_fastq, out, min_mean_q=20, min_len=0)
        assert result["passed"] == 2
        assert result["filtered"] == 1

    def test_combined_filter(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        # min_mean_q=20 AND min_len=8: only read1 (len=10, Q30) passes
        result = filter_fastq(sample_fastq, out, min_mean_q=20, min_len=8)
        assert result["passed"] == 1
        assert result["filtered"] == 2

    def test_output_is_valid_fastq(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        filter_fastq(sample_fastq, out, min_mean_q=20, min_len=0)

        # Verify output is valid FASTQ (4 lines per record)
        with open(out) as f:
            lines = f.readlines()
        assert len(lines) % 4 == 0
        # 2 reads passed, so 8 lines
        assert len(lines) == 8
        assert lines[0].startswith("@")
        assert lines[2].startswith("+")

    def test_all_filtered(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        result = filter_fastq(sample_fastq, out, min_mean_q=50, min_len=100)
        assert result["passed"] == 0
        assert result["filtered"] == 3

    def test_empty_input(self, tmp_dir):
        inp = os.path.join(tmp_dir, "empty.fastq")
        out = os.path.join(tmp_dir, "out.fastq")
        open(inp, "w").close()
        result = filter_fastq(inp, out, min_mean_q=0, min_len=0)
        assert result["passed"] == 0
        assert result["filtered"] == 0

    def test_custom_log_callback(self, sample_fastq, tmp_dir):
        out = os.path.join(tmp_dir, "out.fastq")
        messages = []
        filter_fastq(sample_fastq, out, min_mean_q=0, min_len=0, log=messages.append)
        assert len(messages) == 1
        assert "fastq_filter" in messages[0]
