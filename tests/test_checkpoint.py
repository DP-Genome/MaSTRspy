"""Tests for src.core.checkpoint module."""

import json
import os

import pytest

from src.core.checkpoint import CheckpointManager


class TestCheckpointManagerInit:
    def test_creates_fresh_when_no_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert mgr.completed_loci_count == 0
        assert not mgr.is_stage_complete("any_stage")

    def test_stores_checkpoint_path(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert mgr.checkpoint_path == path


class TestLocusRoundTrip:
    def test_mark_and_check_locus(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/sample.bam", "/ref/locus.bed")
        assert mgr.is_locus_complete("/data/sample.bam", "/ref/locus.bed")

    def test_incomplete_locus_returns_false(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert not mgr.is_locus_complete("/data/sample.bam", "/ref/locus.bed")

    def test_different_bam_not_complete(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/sample.bam", "/ref/locus.bed")
        assert not mgr.is_locus_complete("/data/other.bam", "/ref/locus.bed")

    def test_saves_to_disk_on_mark(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/l.bed")
        assert os.path.isfile(path)


class TestStageRoundTrip:
    def test_mark_and_check_stage(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_stage_complete("mapping_stats")
        assert mgr.is_stage_complete("mapping_stats")

    def test_incomplete_stage_returns_false(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert not mgr.is_stage_complete("mapping_stats")

    def test_multiple_stages(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_stage_complete("mapping_stats")
        mgr.mark_stage_complete("genome_mapping")
        assert mgr.is_stage_complete("mapping_stats")
        assert mgr.is_stage_complete("genome_mapping")
        assert not mgr.is_stage_complete("counting")


class TestGetRemainingLoci:
    def test_filters_completed_jobs(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        jobs = [
            ("/data/s.bam", "/ref/A.bed", "extra_a"),
            ("/data/s.bam", "/ref/B.bed", "extra_b"),
            ("/data/s.bam", "/ref/C.bed", "extra_c"),
        ]
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        remaining = mgr.get_remaining_loci(jobs)
        assert len(remaining) == 2
        assert remaining[0][1] == "/ref/B.bed"
        assert remaining[1][1] == "/ref/C.bed"

    def test_all_complete_returns_empty(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        jobs = [
            ("/data/s.bam", "/ref/A.bed"),
            ("/data/s.bam", "/ref/B.bed"),
        ]
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr.mark_locus_complete("/data/s.bam", "/ref/B.bed")
        remaining = mgr.get_remaining_loci(jobs)
        assert remaining == []

    def test_none_complete_returns_all(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        jobs = [
            ("/data/s.bam", "/ref/A.bed"),
            ("/data/s.bam", "/ref/B.bed"),
        ]
        remaining = mgr.get_remaining_loci(jobs)
        assert len(remaining) == 2


class TestCompletedLociCount:
    def test_zero_initially(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert mgr.completed_loci_count == 0

    def test_correct_count_after_marking(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr.mark_locus_complete("/data/s.bam", "/ref/B.bed")
        assert mgr.completed_loci_count == 2

    def test_no_duplicates(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        assert mgr.completed_loci_count == 1


class TestClear:
    def test_removes_file_and_resets_state(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr.mark_stage_complete("stage1")
        mgr.set_metadata("key", "value")
        mgr.clear()
        assert not os.path.isfile(path)
        assert mgr.completed_loci_count == 0
        assert not mgr.is_stage_complete("stage1")
        assert mgr.get_metadata("key") is None

    def test_clear_when_no_file_exists(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.clear()  # Should not raise
        assert mgr.completed_loci_count == 0


class TestLocusKey:
    def test_static_method_format(self):
        key = CheckpointManager.locus_key("/data/path/sample.bam", "/ref/path/locus.bed")
        assert key == "sample.bam::locus.bed"

    def test_uses_basename_only(self):
        key = CheckpointManager.locus_key("/a/b/c/d.bam", "/x/y/z.bed")
        assert key == "d.bam::z.bed"

    def test_no_path_components(self):
        key = CheckpointManager.locus_key("sample.bam", "locus.bed")
        assert key == "sample.bam::locus.bed"


class TestPersistence:
    def test_state_persists_across_instances(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr1 = CheckpointManager(path)
        mgr1.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr1.mark_stage_complete("genome_mapping")
        mgr1.set_metadata("run_id", "abc123")

        mgr2 = CheckpointManager(path)
        assert mgr2.is_locus_complete("/data/s.bam", "/ref/A.bed")
        assert mgr2.is_stage_complete("genome_mapping")
        assert mgr2.get_metadata("run_id") == "abc123"
        assert mgr2.completed_loci_count == 1

    def test_file_contains_valid_json(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        with open(path, "r") as f:
            data = json.load(f)
        assert "version" in data
        assert data["version"] == 1
        assert "completed_loci" in data
        assert "completed_stages" in data
        assert "metadata" in data

    def test_completed_loci_sorted_in_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/C.bed")
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        mgr.mark_locus_complete("/data/s.bam", "/ref/B.bed")
        with open(path, "r") as f:
            data = json.load(f)
        loci = data["completed_loci"]
        assert loci == sorted(loci)


class TestCorruptCheckpoint:
    def test_corrupt_json_starts_fresh(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        with open(path, "w") as f:
            f.write("{{{invalid json!!!")
        mgr = CheckpointManager(path)
        assert mgr.completed_loci_count == 0
        assert not mgr.is_stage_complete("any")

    def test_empty_file_starts_fresh(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        with open(path, "w") as f:
            pass
        mgr = CheckpointManager(path)
        assert mgr.completed_loci_count == 0

    def test_partial_json_starts_fresh(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        with open(path, "w") as f:
            f.write('{"version": 1, "completed_loci":')
        mgr = CheckpointManager(path)
        assert mgr.completed_loci_count == 0

    def test_can_write_after_corrupt_load(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        with open(path, "w") as f:
            f.write("not json")
        mgr = CheckpointManager(path)
        mgr.mark_locus_complete("/data/s.bam", "/ref/A.bed")
        assert mgr.completed_loci_count == 1
        # Verify file is now valid JSON
        with open(path, "r") as f:
            data = json.load(f)
        assert len(data["completed_loci"]) == 1


class TestMetadata:
    def test_set_and_get_metadata(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.set_metadata("run_id", "abc123")
        assert mgr.get_metadata("run_id") == "abc123"

    def test_get_missing_key_returns_default(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        assert mgr.get_metadata("missing") is None
        assert mgr.get_metadata("missing", "fallback") == "fallback"

    def test_overwrite_metadata(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.set_metadata("key", "value1")
        mgr.set_metadata("key", "value2")
        assert mgr.get_metadata("key") == "value2"

    def test_metadata_supports_various_types(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr = CheckpointManager(path)
        mgr.set_metadata("string", "hello")
        mgr.set_metadata("number", 42)
        mgr.set_metadata("float", 3.14)
        mgr.set_metadata("list", [1, 2, 3])
        mgr.set_metadata("nested", {"a": 1})
        assert mgr.get_metadata("string") == "hello"
        assert mgr.get_metadata("number") == 42
        assert mgr.get_metadata("float") == 3.14
        assert mgr.get_metadata("list") == [1, 2, 3]
        assert mgr.get_metadata("nested") == {"a": 1}

    def test_metadata_persists(self, tmp_dir):
        path = os.path.join(tmp_dir, "ckpt.json")
        mgr1 = CheckpointManager(path)
        mgr1.set_metadata("persistent", True)
        mgr2 = CheckpointManager(path)
        assert mgr2.get_metadata("persistent") is True
