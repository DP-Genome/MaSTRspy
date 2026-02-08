"""Tests for src.core.tool_check module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.core.tool_check import (
    OPTIONAL_TOOLS,
    REQUIRED_TOOLS,
    ToolCheckResult,
    check_tool,
    check_tools_config,
    run_preflight_check,
)


class TestToolCheckResult:
    def test_all_required_available_when_no_missing(self):
        result = ToolCheckResult(
            available={"samtools": "1.18", "bedtools": "2.31"},
            missing=[],
            optional_missing=[],
        )
        assert result.all_required_available is True

    def test_all_required_available_when_missing(self):
        result = ToolCheckResult(
            available={"samtools": "1.18"},
            missing=["bedtools"],
            optional_missing=[],
        )
        assert result.all_required_available is False

    def test_all_required_available_with_only_optional_missing(self):
        result = ToolCheckResult(
            available={"samtools": "1.18"},
            missing=[],
            optional_missing=["dorado"],
        )
        assert result.all_required_available is True

    def test_default_factory_empty_lists(self):
        result = ToolCheckResult()
        assert result.available == {}
        assert result.missing == []
        assert result.optional_missing == []
        assert result.all_required_available is True

    def test_multiple_missing_tools(self):
        result = ToolCheckResult(
            available={},
            missing=["samtools", "bedtools", "minimap2", "xatlas"],
            optional_missing=["dorado", "Rscript"],
        )
        assert result.all_required_available is False
        assert len(result.missing) == 4
        assert len(result.optional_missing) == 2


class TestCheckTool:
    @patch("src.core.tool_check.shutil.which")
    def test_tool_not_found_returns_none(self, mock_which):
        mock_which.return_value = None
        assert check_tool("samtools") is None
        mock_which.assert_called_once_with("samtools")

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_found_returns_version_from_stdout(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/samtools"
        mock_run.return_value = MagicMock(
            stdout="samtools 1.18\nUsing htslib 1.18",
            stderr="",
        )
        result = check_tool("samtools", "--version")
        assert result == "samtools 1.18"
        mock_run.assert_called_once_with(
            ["samtools", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_found_returns_version_from_stderr(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/xatlas"
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="xatlas version 0.3\nUsage: xatlas [options]",
        )
        result = check_tool("xatlas", "--help")
        assert result == "xatlas version 0.3"

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_found_empty_output_returns_path(self, mock_which, mock_run):
        mock_which.return_value = "/usr/local/bin/mytool"
        mock_run.return_value = MagicMock(stdout="", stderr="")
        result = check_tool("mytool")
        assert result == "found at /usr/local/bin/mytool"

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_timeout_returns_found_at_path(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/slowtool"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="slowtool", timeout=5)
        result = check_tool("slowtool")
        assert result == "found at /usr/bin/slowtool"

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_file_not_found_error(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/broken"
        mock_run.side_effect = FileNotFoundError()
        result = check_tool("broken")
        assert result == "found at /usr/bin/broken"

    @patch("src.core.tool_check.subprocess.run")
    @patch("src.core.tool_check.shutil.which")
    def test_tool_os_error(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/bad"
        mock_run.side_effect = OSError("Permission denied")
        result = check_tool("bad")
        assert result == "found at /usr/bin/bad"

    @patch("src.core.tool_check.shutil.which")
    def test_custom_version_flag(self, mock_which):
        mock_which.return_value = None
        check_tool("xatlas", version_flag="--help")
        mock_which.assert_called_once_with("xatlas")


class TestCheckToolsConfig:
    @patch("src.core.tool_check.check_tool")
    def test_all_tools_available(self, mock_check):
        mock_check.return_value = "v1.0"
        tools_config = {}
        result = check_tools_config(tools_config)
        assert result.all_required_available is True
        assert len(result.missing) == 0
        assert len(result.available) == len(REQUIRED_TOOLS) + len(OPTIONAL_TOOLS)

    @patch("src.core.tool_check.check_tool")
    def test_required_tool_missing(self, mock_check):
        def side_effect(name, flag=None):
            if name == "samtools":
                return None
            return "v1.0"

        mock_check.side_effect = side_effect
        result = check_tools_config({})
        assert "samtools" in result.missing
        assert result.all_required_available is False

    @patch("src.core.tool_check.check_tool")
    def test_optional_tool_missing(self, mock_check):
        def side_effect(name, flag=None):
            if name in ("dorado", "Rscript"):
                return None
            return "v1.0"

        mock_check.side_effect = side_effect
        result = check_tools_config({})
        assert "dorado" in result.optional_missing
        assert "Rscript" in result.optional_missing
        assert result.all_required_available is True

    @patch("src.core.tool_check.check_tool")
    def test_config_path_override_for_samtools(self, mock_check):
        mock_check.return_value = "v1.0"
        tools_config = {"SAMTOOLS": "/custom/path/samtools"}
        check_tools_config(tools_config)
        # Verify the custom path was used for samtools
        calls = [str(c) for c in mock_check.call_args_list]
        found = any("/custom/path/samtools" in c for c in calls)
        assert found, f"Expected custom path in calls: {calls}"

    @patch("src.core.tool_check.check_tool")
    def test_config_path_override_for_minimap(self, mock_check):
        """minimap2 uses MINIMAP as its config key, not MINIMAP2."""
        mock_check.return_value = "v1.0"
        tools_config = {"MINIMAP": "/custom/minimap2"}
        check_tools_config(tools_config)
        calls = [str(c) for c in mock_check.call_args_list]
        found = any("/custom/minimap2" in c for c in calls)
        assert found, f"Expected custom minimap path in calls: {calls}"

    @patch("src.core.tool_check.check_tool")
    def test_all_required_missing(self, mock_check):
        mock_check.return_value = None
        result = check_tools_config({})
        assert len(result.missing) == len(REQUIRED_TOOLS)
        assert len(result.optional_missing) == len(OPTIONAL_TOOLS)
        assert result.all_required_available is False

    @patch("src.core.tool_check.check_tool")
    def test_empty_config_uses_tool_name_as_path(self, mock_check):
        mock_check.return_value = "v1.0"
        check_tools_config({})
        # With empty config, required tools should be looked up by their own name
        call_args = [c[0][0] for c in mock_check.call_args_list]
        assert "samtools" in call_args
        assert "bedtools" in call_args
        assert "minimap2" in call_args
        assert "xatlas" in call_args


class TestRunPreflightCheck:
    @patch("src.core.tool_check.check_tools_config")
    def test_raises_when_required_missing(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"bedtools": "v2.31"},
            missing=["samtools", "minimap2"],
            optional_missing=[],
        )
        with pytest.raises(RuntimeError, match="Required tools missing"):
            run_preflight_check({})

    @patch("src.core.tool_check.check_tools_config")
    def test_raises_with_missing_tool_names_in_message(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={},
            missing=["xatlas"],
            optional_missing=[],
        )
        with pytest.raises(RuntimeError, match="xatlas"):
            run_preflight_check({})

    @patch("src.core.tool_check.check_tools_config")
    def test_passes_when_all_available(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"samtools": "1.18", "bedtools": "2.31",
                       "minimap2": "2.26", "xatlas": "0.3"},
            missing=[],
            optional_missing=[],
        )
        result = run_preflight_check({})
        assert result.all_required_available is True

    @patch("src.core.tool_check.check_tools_config")
    def test_logs_available_tools(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"samtools": "1.18"},
            missing=[],
            optional_missing=[],
        )
        log_messages = []
        run_preflight_check({}, log=log_messages.append)
        log_text = "\n".join(log_messages)
        assert "[OK] samtools: 1.18" in log_text

    @patch("src.core.tool_check.check_tools_config")
    def test_logs_optional_missing(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"samtools": "1.18", "bedtools": "2.31",
                       "minimap2": "2.26", "xatlas": "0.3"},
            missing=[],
            optional_missing=["dorado"],
        )
        log_messages = []
        run_preflight_check({}, log=log_messages.append)
        log_text = "\n".join(log_messages)
        assert "[SKIP] dorado" in log_text

    @patch("src.core.tool_check.check_tools_config")
    def test_logs_required_missing_before_raising(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={},
            missing=["samtools"],
            optional_missing=[],
        )
        log_messages = []
        with pytest.raises(RuntimeError):
            run_preflight_check({}, log=log_messages.append)
        log_text = "\n".join(log_messages)
        assert "[MISSING] samtools" in log_text
        assert "[ERROR]" in log_text

    @patch("src.core.tool_check.check_tools_config")
    def test_logs_success_banner(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"samtools": "1.18"},
            missing=[],
            optional_missing=[],
        )
        log_messages = []
        run_preflight_check({}, log=log_messages.append)
        log_text = "\n".join(log_messages)
        assert "All required tools available" in log_text

    @patch("src.core.tool_check.check_tools_config")
    def test_passes_tools_config_through(self, mock_check):
        mock_check.return_value = ToolCheckResult(
            available={"samtools": "1.18"},
            missing=[],
            optional_missing=[],
        )
        custom_config = {"SAMTOOLS": "/opt/samtools"}
        run_preflight_check(custom_config)
        mock_check.assert_called_once_with(custom_config)

    @patch("src.core.tool_check.check_tools_config")
    def test_returns_result_on_success(self, mock_check):
        expected = ToolCheckResult(
            available={"samtools": "1.18", "bedtools": "2.31",
                       "minimap2": "2.26", "xatlas": "0.3"},
            missing=[],
            optional_missing=["dorado"],
        )
        mock_check.return_value = expected
        result = run_preflight_check({})
        assert result is expected
