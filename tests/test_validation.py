"""Tests for src.core.validation module."""

import os

import pytest

from src.core.validation import (
    ValidationResult,
    check_disk_space,
    estimate_disk_space,
    validate_input_path,
    validate_output_path,
    validate_pipeline_inputs,
    validate_reference_genome,
)


class TestValidationResult:
    def test_is_valid_when_no_errors(self):
        result = ValidationResult()
        assert result.is_valid is True

    def test_is_invalid_when_errors_present(self):
        result = ValidationResult()
        result.add_error("something went wrong")
        assert result.is_valid is False

    def test_warnings_do_not_affect_validity(self):
        result = ValidationResult()
        result.add_warning("low disk space")
        assert result.is_valid is True

    def test_errors_and_warnings_accumulate(self):
        result = ValidationResult()
        result.add_error("err1")
        result.add_error("err2")
        result.add_warning("warn1")
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestValidateInputPath:
    def test_empty_path(self):
        result = validate_input_path("")
        assert not result.is_valid
        assert any("empty" in e.lower() for e in result.errors)

    def test_nonexistent_path(self):
        result = validate_input_path("/nonexistent/path/to/nowhere")
        assert not result.is_valid
        assert any("does not exist" in e for e in result.errors)

    def test_valid_file_path(self, tmp_dir):
        file_path = os.path.join(tmp_dir, "input.bam")
        with open(file_path, "w") as f:
            f.write("data")
        result = validate_input_path(file_path)
        assert result.is_valid

    def test_valid_directory_path(self, tmp_dir):
        result = validate_input_path(tmp_dir)
        assert result.is_valid

    def test_none_treated_as_falsy(self):
        result = validate_input_path(None)
        assert not result.is_valid

    def test_error_message_includes_path(self):
        bad_path = "/this/does/not/exist"
        result = validate_input_path(bad_path)
        assert any(bad_path in e for e in result.errors)


class TestValidateOutputPath:
    def test_empty_path(self):
        result = validate_output_path("")
        assert not result.is_valid
        assert any("empty" in e.lower() for e in result.errors)

    def test_valid_parent_dir(self, tmp_dir):
        output_path = os.path.join(tmp_dir, "results", "output.tsv")
        # Parent of "results/output.tsv" relative to tmp_dir is tmp_dir/results
        # But the direct parent dirname would be tmp_dir/results which doesn't exist
        # So use a path whose parent exists
        output_path = os.path.join(tmp_dir, "output.tsv")
        result = validate_output_path(output_path)
        assert result.is_valid

    def test_nonexistent_parent_dir(self):
        result = validate_output_path("/nonexistent/parent/dir/output.tsv")
        assert not result.is_valid
        assert any("does not exist" in e for e in result.errors)

    def test_none_treated_as_falsy(self):
        result = validate_output_path(None)
        assert not result.is_valid


class TestValidateReferenceGenome:
    def test_empty_path(self):
        result = validate_reference_genome("")
        assert not result.is_valid
        assert any("empty" in e.lower() for e in result.errors)

    def test_nonexistent_file(self):
        result = validate_reference_genome("/nonexistent/genome.fa")
        assert not result.is_valid
        assert any("not found" in e for e in result.errors)

    def test_valid_file(self, tmp_dir):
        ref_path = os.path.join(tmp_dir, "genome.fa")
        with open(ref_path, "w") as f:
            f.write(">chr1\nACGT\n")
        result = validate_reference_genome(ref_path)
        assert result.is_valid

    def test_directory_not_accepted(self, tmp_dir):
        # A directory is not a file, so validate_reference_genome should reject it
        result = validate_reference_genome(tmp_dir)
        assert not result.is_valid

    def test_none_treated_as_falsy(self):
        result = validate_reference_genome(None)
        assert not result.is_valid


class TestEstimateDiskSpace:
    def test_with_file(self, tmp_dir):
        file_path = os.path.join(tmp_dir, "data.bin")
        with open(file_path, "wb") as f:
            f.write(b"x" * 1000)
        estimate = estimate_disk_space(file_path)
        assert estimate == 3000  # 1000 * 3

    def test_with_directory(self, tmp_dir):
        subdir = os.path.join(tmp_dir, "subdir")
        os.makedirs(subdir)
        for name in ["a.txt", "b.txt"]:
            with open(os.path.join(subdir, name), "wb") as f:
                f.write(b"x" * 500)
        estimate = estimate_disk_space(subdir)
        # 2 files * 500 bytes * 3 = 3000
        assert estimate == 3000

    def test_with_nested_directory(self, tmp_dir):
        subdir = os.path.join(tmp_dir, "level1", "level2")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "deep.txt"), "wb") as f:
            f.write(b"x" * 200)
        # rglob finds files recursively
        estimate = estimate_disk_space(os.path.join(tmp_dir, "level1"))
        assert estimate == 600  # 200 * 3

    def test_nonexistent_path(self):
        estimate = estimate_disk_space("/nonexistent/path")
        assert estimate is None

    def test_empty_file(self, tmp_dir):
        file_path = os.path.join(tmp_dir, "empty.bin")
        with open(file_path, "w") as f:
            pass
        estimate = estimate_disk_space(file_path)
        assert estimate == 0

    def test_empty_directory(self, tmp_dir):
        empty_dir = os.path.join(tmp_dir, "empty_dir")
        os.makedirs(empty_dir)
        estimate = estimate_disk_space(empty_dir)
        assert estimate == 0


class TestCheckDiskSpace:
    def test_valid_dir_returns_result(self, tmp_dir):
        result = check_disk_space(tmp_dir, 1)
        # Should be valid since we only need 1 byte
        assert result.is_valid

    def test_massive_requirement_warns(self, tmp_dir):
        # Request a petabyte -- should trigger a warning
        result = check_disk_space(tmp_dir, 10**15)
        assert len(result.warnings) > 0

    def test_zero_bytes_no_warning(self, tmp_dir):
        result = check_disk_space(tmp_dir, 0)
        assert result.is_valid
        assert len(result.warnings) == 0

    def test_nonexistent_dir_uses_parent(self, tmp_dir):
        nonexistent = os.path.join(tmp_dir, "doesnotexist")
        result = check_disk_space(nonexistent, 1)
        # Should still work by falling back to parent directory
        assert isinstance(result, ValidationResult)


class TestValidatePipelineInputs:
    def test_valid_params(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        ref_path = os.path.join(tmp_dir, "genome.fa")
        with open(ref_path, "w") as f:
            f.write(">chr1\nACGT\n")

        messages = []
        result = validate_pipeline_inputs(
            {
                "input_dir": input_dir,
                "output_dir": os.path.join(output_dir, "results"),
                "ref_genome": ref_path,
                "needs_prepping": True,
            },
            log=messages.append,
        )
        assert result.is_valid

    def test_invalid_input_dir(self, tmp_dir):
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(output_dir)
        messages = []
        result = validate_pipeline_inputs(
            {
                "input_dir": "/nonexistent/input",
                "output_dir": os.path.join(output_dir, "results"),
            },
            log=messages.append,
        )
        assert not result.is_valid

    def test_invalid_output_dir(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        os.makedirs(input_dir)
        messages = []
        result = validate_pipeline_inputs(
            {
                "input_dir": input_dir,
                "output_dir": "/nonexistent/parent/output",
            },
            log=messages.append,
        )
        assert not result.is_valid

    def test_empty_params(self):
        messages = []
        result = validate_pipeline_inputs({}, log=messages.append)
        assert not result.is_valid

    def test_ref_genome_validation_when_prepping(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        messages = []
        result = validate_pipeline_inputs(
            {
                "input_dir": input_dir,
                "output_dir": os.path.join(output_dir, "results"),
                "ref_genome": "/nonexistent/genome.fa",
                "needs_prepping": True,
            },
            log=messages.append,
        )
        assert not result.is_valid
        assert any("genome" in e.lower() or "not found" in e.lower() for e in result.errors)

    def test_ref_genome_skipped_when_not_prepping(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        messages = []
        result = validate_pipeline_inputs(
            {
                "input_dir": input_dir,
                "output_dir": os.path.join(output_dir, "results"),
                "ref_genome": "/nonexistent/genome.fa",
                "needs_prepping": False,
            },
            log=messages.append,
        )
        # Should pass since needs_prepping is False, so ref_genome is not validated
        assert result.is_valid

    def test_logs_errors_and_warnings(self, tmp_dir):
        messages = []
        validate_pipeline_inputs(
            {
                "input_dir": "/nonexistent/input",
                "output_dir": "/nonexistent/output/file",
            },
            log=messages.append,
        )
        # Should have at least the "Validating" message plus error messages
        assert any("Validating" in m for m in messages)
        assert any("[ERROR]" in m for m in messages)

    def test_logs_passed_when_valid(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        messages = []
        validate_pipeline_inputs(
            {
                "input_dir": input_dir,
                "output_dir": os.path.join(output_dir, "results"),
            },
            log=messages.append,
        )
        assert any("passed" in m.lower() for m in messages)

    def test_logs_failed_when_invalid(self):
        messages = []
        validate_pipeline_inputs({}, log=messages.append)
        assert any("FAILED" in m for m in messages)

    def test_uses_input_path_key_as_fallback(self, tmp_dir):
        input_dir = os.path.join(tmp_dir, "input")
        output_dir = os.path.join(tmp_dir, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        messages = []
        result = validate_pipeline_inputs(
            {
                "input_path": input_dir,
                "output_dir": os.path.join(output_dir, "results"),
            },
            log=messages.append,
        )
        assert result.is_valid
