"""Tests for src.pipeline.file_organizer module."""

import os

import pytest

from src.pipeline.file_organizer import organize_by_barcode


class TestOrganizeByBarcode:
    def test_creates_barcode_directories(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        os.makedirs(counting_dir)

        organize_by_barcode(counting_dir, num_barcodes=4)

        for i in range(1, 5):
            assert os.path.isdir(os.path.join(counting_dir, f"barcode{i:02d}"))
        assert os.path.isdir(os.path.join(counting_dir, "unclassified"))

    def test_removes_toptwo_files(self, counting_dir_with_files):
        organize_by_barcode(counting_dir_with_files)
        remaining = os.listdir(counting_dir_with_files)
        toptwo = [f for f in remaining if f.endswith("Toptwo.txt")]
        assert len(toptwo) == 0

    def test_moves_barcode_files(self, counting_dir_with_files):
        organize_by_barcode(counting_dir_with_files, num_barcodes=4)

        barcode01_dir = os.path.join(counting_dir_with_files, "barcode01")
        files_in_dir = os.listdir(barcode01_dir)
        assert len(files_in_dir) == 2  # Two allele_freqs files

    def test_moves_unclassified_files(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        os.makedirs(counting_dir)

        # Create an unclassified file
        with open(os.path.join(counting_dir, "unclassified_freqs.txt"), "w") as f:
            f.write("test\n")

        organize_by_barcode(counting_dir, num_barcodes=2)

        unclassified_dir = os.path.join(counting_dir, "unclassified")
        assert os.path.isfile(
            os.path.join(unclassified_dir, "unclassified_freqs.txt")
        )

    def test_nonexistent_directory(self, tmp_dir):
        messages = []
        organize_by_barcode(
            os.path.join(tmp_dir, "nonexistent"),
            log=messages.append,
        )
        assert any("Error" in m or "not found" in m for m in messages)

    def test_custom_num_barcodes(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        os.makedirs(counting_dir)
        organize_by_barcode(counting_dir, num_barcodes=96)
        assert os.path.isdir(os.path.join(counting_dir, "barcode96"))
        assert not os.path.isdir(os.path.join(counting_dir, "barcode97"))

    def test_files_not_matching_barcode_stay(self, tmp_dir):
        counting_dir = os.path.join(tmp_dir, "Countings")
        os.makedirs(counting_dir)

        # Create a file that doesn't match any barcode pattern
        with open(os.path.join(counting_dir, "random_file.txt"), "w") as f:
            f.write("test\n")

        organize_by_barcode(counting_dir, num_barcodes=2)

        # File should still be in counting_dir (not moved)
        assert os.path.isfile(os.path.join(counting_dir, "random_file.txt"))
