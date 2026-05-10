"""Tests for src.core.file_detector module."""

import os
from unittest.mock import patch

from src.core.file_detector import FileType, detect_file_type


class TestFileType:
    def test_enum_values(self):
        assert FileType.POD5.value == "pod5"
        assert FileType.BAM_ALIGNED.value == "bam_aligned"
        assert FileType.BAM_UNALIGNED.value == "bam_unaligned"
        assert FileType.FASTQ.value == "fastq"
        assert FileType.UNKNOWN.value == "unknown"

    def test_enum_members_count(self):
        assert len(FileType) == 5


class TestDetectFileType:
    def test_nonexistent_path(self):
        ft, files = detect_file_type("/nonexistent/path")
        assert ft == FileType.UNKNOWN
        assert files == []

    def test_detect_pod5_files(self, tmp_dir):
        # Create .pod5 files
        for name in ["run1.pod5", "run2.pod5"]:
            open(os.path.join(tmp_dir, name), "w").close()
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.POD5
        assert len(files) == 2

    def test_detect_fastq_files(self, tmp_dir):
        for name in ["sample1.fastq", "sample2.fq"]:
            open(os.path.join(tmp_dir, name), "w").close()
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.FASTQ
        assert len(files) == 2

    def test_pod5_takes_priority_over_fastq(self, tmp_dir):
        open(os.path.join(tmp_dir, "run.pod5"), "w").close()
        open(os.path.join(tmp_dir, "sample.fastq"), "w").close()
        ft, _ = detect_file_type(tmp_dir)
        assert ft == FileType.POD5

    def test_empty_directory(self, tmp_dir):
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.UNKNOWN
        assert files == []

    def test_single_file_path(self, tmp_dir):
        fq = os.path.join(tmp_dir, "test.fastq")
        open(fq, "w").close()
        ft, files = detect_file_type(fq)
        assert ft == FileType.FASTQ
        assert len(files) == 1

    @patch("src.core.file_detector.subprocess.run")
    def test_detect_aligned_bam(self, mock_run, tmp_dir):
        bam = os.path.join(tmp_dir, "sample.bam")
        open(bam, "w").close()
        mock_run.return_value.stdout = "100\n"
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.BAM_ALIGNED
        assert len(files) == 1

    @patch("src.core.file_detector.subprocess.run")
    def test_detect_unaligned_bam(self, mock_run, tmp_dir):
        bam = os.path.join(tmp_dir, "sample.bam")
        open(bam, "w").close()
        mock_run.return_value.stdout = "0\n"
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.BAM_UNALIGNED
        assert len(files) == 1

    @patch("src.core.file_detector.subprocess.run")
    def test_bam_detection_falls_back_on_exception(self, mock_run, tmp_dir):
        bam = os.path.join(tmp_dir, "sample.bam")
        open(bam, "w").close()
        mock_run.side_effect = Exception("samtools not found")
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.BAM_UNALIGNED
        assert len(files) == 1

    def test_ignores_unrecognized_extensions(self, tmp_dir):
        open(os.path.join(tmp_dir, "readme.txt"), "w").close()
        open(os.path.join(tmp_dir, "data.csv"), "w").close()
        ft, files = detect_file_type(tmp_dir)
        assert ft == FileType.UNKNOWN
        assert files == []
