"""Tests for src.filters.filter_report module."""

import os

import pytest

from src.filters.filter_report import (
    FilterReport,
    FilterStageResult,
    write_qc_report,
)


class TestFilterStageResult:
    def test_total_input(self):
        stage = FilterStageResult(
            stage_name="quality",
            passed=80,
            filtered=15,
            skipped=5,
        )
        assert stage.total_input == 100

    def test_total_input_all_passed(self):
        stage = FilterStageResult(
            stage_name="quality",
            passed=100,
            filtered=0,
            skipped=0,
        )
        assert stage.total_input == 100

    def test_pass_rate(self):
        stage = FilterStageResult(
            stage_name="quality",
            passed=80,
            filtered=15,
            skipped=5,
        )
        assert stage.pass_rate == pytest.approx(80.0)

    def test_pass_rate_all_passed(self):
        stage = FilterStageResult(
            stage_name="quality",
            passed=100,
            filtered=0,
            skipped=0,
        )
        assert stage.pass_rate == pytest.approx(100.0)

    def test_pass_rate_none_passed(self):
        stage = FilterStageResult(
            stage_name="quality",
            passed=0,
            filtered=90,
            skipped=10,
        )
        assert stage.pass_rate == pytest.approx(0.0)

    def test_zero_total_input_pass_rate(self):
        stage = FilterStageResult(
            stage_name="empty",
            passed=0,
            filtered=0,
            skipped=0,
        )
        assert stage.total_input == 0
        assert stage.pass_rate == 0.0

    def test_no_tag_count_default(self):
        stage = FilterStageResult(stage_name="test")
        assert stage.no_tag_count == 0

    def test_no_tag_count_set(self):
        stage = FilterStageResult(
            stage_name="test",
            passed=50,
            filtered=30,
            skipped=10,
            no_tag_count=5,
        )
        assert stage.no_tag_count == 5


class TestFilterReport:
    def test_add_stage(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        assert len(report.stages) == 1
        assert report.stages[0].stage_name == "quality"
        assert report.stages[0].passed == 80

    def test_add_multiple_stages(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})
        assert len(report.stages) == 2

    def test_add_stage_missing_keys_default_to_zero(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {})
        assert report.stages[0].passed == 0
        assert report.stages[0].filtered == 0
        assert report.stages[0].skipped == 0

    def test_add_stage_with_no_tag_count(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 50, "no_tag_count": 3})
        assert report.stages[0].no_tag_count == 3

    def test_total_input_from_first_stage(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})
        assert report.total_input == 100  # From first stage

    def test_total_input_no_stages(self):
        report = FilterReport(sample_name="sample1")
        assert report.total_input == 0

    def test_final_passed_from_last_stage(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})
        assert report.final_passed == 70  # From last stage

    def test_final_passed_no_stages(self):
        report = FilterReport(sample_name="sample1")
        assert report.final_passed == 0

    def test_overall_pass_rate(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 50, "filtered": 30, "skipped": 0})
        # 50 final passed / 100 total input = 50%
        assert report.overall_pass_rate == pytest.approx(50.0)

    def test_overall_pass_rate_no_stages(self):
        report = FilterReport(sample_name="sample1")
        assert report.overall_pass_rate == 0.0

    def test_overall_pass_rate_zero_input(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 0, "filtered": 0, "skipped": 0})
        assert report.overall_pass_rate == 0.0

    def test_to_tsv_rows(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})
        rows = report.to_tsv_rows()
        assert len(rows) == 2
        # Check first row content
        fields = rows[0].split("\t")
        assert fields[0] == "sample1"
        assert fields[1] == "quality"
        assert fields[2] == "100"  # total_input
        assert fields[3] == "80"  # passed
        assert fields[4] == "15"  # filtered
        assert fields[5] == "5"  # skipped
        assert fields[6] == "80.0%"

    def test_to_tsv_rows_empty(self):
        report = FilterReport(sample_name="sample1")
        rows = report.to_tsv_rows()
        assert rows == []

    def test_summary_line(self):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})
        summary = report.summary_line()
        assert "[QC] sample1:" in summary
        assert "100 reads in" in summary
        assert "70 out" in summary
        assert "quality" in summary
        assert "length" in summary

    def test_summary_line_single_stage(self):
        report = FilterReport(sample_name="mysample")
        report.add_stage("accuracy", {"passed": 90, "filtered": 10, "skipped": 0})
        summary = report.summary_line()
        assert "mysample" in summary
        assert "90 out" in summary
        assert "accuracy" in summary

    def test_summary_line_pass_rate_format(self):
        report = FilterReport(sample_name="s1")
        report.add_stage("q", {"passed": 75, "filtered": 25, "skipped": 0})
        summary = report.summary_line()
        assert "75.0% pass" in summary


class TestWriteQcReport:
    def test_creates_file_with_correct_format(self, tmp_dir):
        report = FilterReport(sample_name="sample1")
        report.add_stage("quality", {"passed": 80, "filtered": 15, "skipped": 5})
        report.add_stage("length", {"passed": 70, "filtered": 10, "skipped": 0})

        output_path = os.path.join(tmp_dir, "qc_report.tsv")
        messages = []
        write_qc_report([report], output_path, log=messages.append)
        assert os.path.isfile(output_path)

        with open(output_path, "r") as f:
            lines = f.readlines()

        # Header line
        assert (
            lines[0].strip()
            == "Sample\tStage\tInputReads\tPassed\tFiltered\tSkipped\tPassRate"
        )
        # Two data rows
        assert len(lines) == 3  # header + 2 stages
        assert lines[1].startswith("sample1\tquality\t")
        assert lines[2].startswith("sample1\tlength\t")

    def test_creates_parent_directory(self, tmp_dir):
        report = FilterReport(sample_name="s1")
        report.add_stage("q", {"passed": 10, "filtered": 0, "skipped": 0})
        output_path = os.path.join(tmp_dir, "subdir", "qc_report.tsv")
        write_qc_report([report], output_path)
        assert os.path.isfile(output_path)

    def test_multiple_reports(self, tmp_dir):
        report1 = FilterReport(sample_name="sample1")
        report1.add_stage("quality", {"passed": 80, "filtered": 20, "skipped": 0})

        report2 = FilterReport(sample_name="sample2")
        report2.add_stage("quality", {"passed": 60, "filtered": 30, "skipped": 10})

        output_path = os.path.join(tmp_dir, "qc_report.tsv")
        write_qc_report([report1, report2], output_path)

        with open(output_path, "r") as f:
            lines = f.readlines()

        # header + 1 stage per sample = 3 lines
        assert len(lines) == 3
        assert "sample1" in lines[1]
        assert "sample2" in lines[2]

    def test_empty_reports_list(self, tmp_dir):
        output_path = os.path.join(tmp_dir, "qc_report.tsv")
        write_qc_report([], output_path)
        assert os.path.isfile(output_path)
        with open(output_path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1  # Header only

    def test_logs_output_path(self, tmp_dir):
        report = FilterReport(sample_name="s1")
        report.add_stage("q", {"passed": 10, "filtered": 0, "skipped": 0})
        output_path = os.path.join(tmp_dir, "qc_report.tsv")
        messages = []
        write_qc_report([report], output_path, log=messages.append)
        assert len(messages) == 1
        assert output_path in messages[0]
        assert "[INFO]" in messages[0]
