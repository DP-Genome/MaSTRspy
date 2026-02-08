"""Tests for src.plotting.runner module."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.plotting.runner import run_r_plots


class TestRunRPlots:
    def test_creates_plots_directory(self, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()

        run_r_plots(summaries_dir, r_script, "/fake/logo.jpg")
        assert os.path.isdir(os.path.join(summaries_dir, "Plots"))

    def test_skips_missing_r_script(self, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        messages = []
        run_r_plots(
            summaries_dir,
            "/nonexistent/script.R",
            "/fake/logo.jpg",
            log=messages.append,
        )
        assert any("not found" in m for m in messages)

    def test_skips_empty_summary_files(self, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()

        # Create empty summary file
        open(os.path.join(summaries_dir, "barcode01_summary.tsv"), "w").close()

        with patch("src.plotting.runner.subprocess.run") as mock_run:
            run_r_plots(summaries_dir, r_script, "/fake/logo.jpg")
            mock_run.assert_not_called()

    @patch("src.plotting.runner.subprocess.run")
    def test_calls_rscript_for_each_summary(self, mock_run, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()

        # Create non-empty summary files
        for bc in ["barcode01", "barcode02"]:
            path = os.path.join(summaries_dir, f"{bc}_summary.tsv")
            with open(path, "w") as f:
                f.write("header\ndata\n")

        run_r_plots(summaries_dir, r_script, "/fake/logo.jpg")
        assert mock_run.call_count == 2

    @patch("src.plotting.runner.subprocess.run")
    def test_includes_logo_if_exists(self, mock_run, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()
        logo = os.path.join(tmp_dir, "logo.jpg")
        open(logo, "w").close()

        with open(os.path.join(summaries_dir, "barcode01_summary.tsv"), "w") as f:
            f.write("data\n")

        run_r_plots(summaries_dir, r_script, logo)
        call_args = mock_run.call_args[0][0]
        assert logo in call_args

    @patch("src.plotting.runner.subprocess.run")
    def test_handles_rscript_failure(self, mock_run, tmp_dir):
        from subprocess import CalledProcessError

        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()

        with open(os.path.join(summaries_dir, "barcode01_summary.tsv"), "w") as f:
            f.write("data\n")

        mock_run.side_effect = CalledProcessError(1, "Rscript", stderr="error")
        messages = []
        run_r_plots(summaries_dir, r_script, "/fake/logo.jpg", log=messages.append)
        assert any("WARNING" in m for m in messages)

    @patch("src.plotting.runner.subprocess.run")
    def test_handles_rscript_not_found(self, mock_run, tmp_dir):
        summaries_dir = os.path.join(tmp_dir, "Summaries")
        os.makedirs(summaries_dir)
        r_script = os.path.join(tmp_dir, "plot.R")
        open(r_script, "w").close()

        with open(os.path.join(summaries_dir, "barcode01_summary.tsv"), "w") as f:
            f.write("data\n")

        mock_run.side_effect = FileNotFoundError()
        messages = []
        run_r_plots(summaries_dir, r_script, "/fake/logo.jpg", log=messages.append)
        assert any("Rscript not found" in m for m in messages)
