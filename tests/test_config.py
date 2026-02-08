"""Tests for src.core.config module."""

import os

import pytest

from src.core.config import (
    DEMUX_KITS,
    FILTER_PRESETS,
    compute_thread_split,
    generate_input_config,
    load_input_config,
    load_overrides,
    load_tools_config,
)


class TestFilterPresets:
    def test_presets_contain_expected_keys(self):
        expected = {"None", "Lenient", "Moderate", "Stringent", "Custom"}
        assert set(FILTER_PRESETS.keys()) == expected

    def test_none_preset_has_zero_values(self):
        p = FILTER_PRESETS["None"]
        assert p["min_dorado_q"] == 0.0
        assert p["min_mean_q"] == 0.0
        assert p["min_len"] == 0
        assert p["min_acc"] == 0.0

    def test_stringent_stricter_than_moderate(self):
        mod = FILTER_PRESETS["Moderate"]
        stg = FILTER_PRESETS["Stringent"]
        assert stg["min_dorado_q"] > mod["min_dorado_q"]
        assert stg["min_mean_q"] > mod["min_mean_q"]
        assert stg["min_len"] > mod["min_len"]
        assert stg["min_acc"] > mod["min_acc"]

    def test_custom_preset_is_empty(self):
        assert FILTER_PRESETS["Custom"] == {}


class TestDemuxKits:
    def test_kits_list_not_empty(self):
        assert len(DEMUX_KITS) > 0

    def test_none_is_first_option(self):
        assert DEMUX_KITS[0] == "None"

    def test_all_kits_are_strings(self):
        for kit in DEMUX_KITS:
            assert isinstance(kit, str)


class TestLoadInputConfig:
    def test_loads_key_value_pairs(self, sample_input_config):
        config = load_input_config(sample_input_config)
        assert config["INPUT_DIR"] == "/data/input"
        assert config["OUTPUT_DIR"] == "/data/output"
        assert config["INPUT_BAM"] == "yes"

    def test_strips_quotes(self, sample_input_config):
        config = load_input_config(sample_input_config)
        # Values should have quotes stripped
        assert '"' not in config["INPUT_DIR"]

    def test_ignores_comments(self, sample_input_config):
        config = load_input_config(sample_input_config)
        # Comment lines should not produce keys
        for key in config:
            assert not key.startswith("#")

    def test_ignores_blank_lines(self, sample_input_config):
        config = load_input_config(sample_input_config)
        assert "" not in config

    def test_handles_numeric_values(self, sample_input_config):
        config = load_input_config(sample_input_config)
        assert config["NORM_CUTOFF"] == "0.1"
        assert float(config["NORM_CUTOFF"]) == 0.1

    def test_empty_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.txt")
        with open(path, "w") as f:
            pass
        config = load_input_config(path)
        assert config == {}

    def test_lines_without_equals(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.txt")
        with open(path, "w") as f:
            f.write("no_equals_here\n")
            f.write("KEY=value\n")
        config = load_input_config(path)
        assert "no_equals_here" not in config
        assert config["KEY"] == "value"


class TestLoadToolsConfig:
    def test_delegates_to_load_input_config(self, tmp_dir):
        path = os.path.join(tmp_dir, "tools.txt")
        with open(path, "w") as f:
            f.write("BEDTOOLS=/usr/bin/bedtools\n")
            f.write("SAMTOOLS=/usr/bin/samtools\n")
        config = load_tools_config(path)
        assert config["BEDTOOLS"] == "/usr/bin/bedtools"
        assert config["SAMTOOLS"] == "/usr/bin/samtools"


class TestLoadOverrides:
    def test_loads_locus_cutoffs(self, sample_overrides_tsv):
        overrides = load_overrides(sample_overrides_tsv)
        assert overrides["D3S1358"] == 0.4
        assert overrides["vWA"] == 0.4
        assert overrides["DYS481"] == 0.5

    def test_returns_empty_dict_for_empty_path(self):
        overrides = load_overrides("")
        assert overrides == {}

    def test_returns_empty_dict_for_nonexistent_file(self):
        overrides = load_overrides("/nonexistent/path.tsv")
        assert overrides == {}

    def test_ignores_comments(self, sample_overrides_tsv):
        overrides = load_overrides(sample_overrides_tsv)
        assert len(overrides) == 3  # Only data lines, not comment

    def test_handles_invalid_float(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad_overrides.tsv")
        with open(path, "w") as f:
            f.write("LOCUS1\tnot_a_number\n")
            f.write("LOCUS2\t0.3\n")
        overrides = load_overrides(path)
        assert "LOCUS1" not in overrides
        assert overrides["LOCUS2"] == 0.3


class TestGenerateInputConfig:
    def test_generates_basic_config_without_master(self):
        result = generate_input_config(
            "/input", "/output", {"norm_cutoff": 0.15}
        )
        assert 'INPUT_DIR="/input"' in result
        assert 'OUTPUT_DIR="/output"' in result
        assert "NORM_CUTOFF=0.15" in result

    def test_includes_overrides_path(self):
        result = generate_input_config(
            "/input",
            "/output",
            {"norm_cutoff": 0.1, "norm_cutoff_overrides": "/path/to/overrides.tsv"},
        )
        assert 'NORM_CUTOFF_OVERRIDES="/path/to/overrides.tsv"' in result

    def test_empty_overrides_path(self):
        result = generate_input_config(
            "/input", "/output", {"norm_cutoff": 0.1, "norm_cutoff_overrides": ""}
        )
        assert "NORM_CUTOFF_OVERRIDES=\n" in result or "NORM_CUTOFF_OVERRIDES" not in result

    def test_uses_master_config_template(self, sample_input_config):
        result = generate_input_config(
            "/new/input",
            "/new/output",
            {"norm_cutoff": 0.2},
            master_config_path=sample_input_config,
        )
        assert 'INPUT_DIR="/new/input"' in result
        assert 'OUTPUT_DIR="/new/output"' in result
        assert "NORM_CUTOFF=0.2" in result

    def test_default_norm_cutoff(self):
        result = generate_input_config("/input", "/output", {})
        assert "NORM_CUTOFF=0.1" in result

    def test_writes_thread_settings_without_master(self):
        result = generate_input_config(
            "/input", "/output", {"num_threads": 128}
        )
        assert "NUM_PARALLEL_JOBS=8" in result
        assert "NUM_THREADS=16" in result

    def test_writes_thread_settings_with_master(self, sample_input_config):
        # Add thread lines to the sample config
        with open(sample_input_config, "a") as f:
            f.write("NUM_PARALLEL_JOBS=8\n")
            f.write("NUM_THREADS=16\n")
        result = generate_input_config(
            "/input", "/output", {"num_threads": 32},
            master_config_path=sample_input_config,
        )
        assert "NUM_PARALLEL_JOBS=2" in result
        assert "NUM_THREADS=16" in result

    def test_appends_thread_settings_when_missing_from_master(self, sample_input_config):
        result = generate_input_config(
            "/input", "/output", {"num_threads": 64},
            master_config_path=sample_input_config,
        )
        assert "NUM_PARALLEL_JOBS=8" in result
        assert "NUM_THREADS=8" in result

    def test_enable_snv_yes(self):
        result = generate_input_config(
            "/input", "/output", {"enable_snv": True}
        )
        assert "ENABLE_SNV=yes" in result

    def test_enable_snv_no_by_default(self):
        result = generate_input_config("/input", "/output", {})
        assert "ENABLE_SNV=no" in result

    def test_enable_snv_false(self):
        result = generate_input_config(
            "/input", "/output", {"enable_snv": False}
        )
        assert "ENABLE_SNV=no" in result


class TestComputeThreadSplit:
    def test_128_threads(self):
        assert compute_thread_split(128) == (8, 16)

    def test_64_threads(self):
        assert compute_thread_split(64) == (8, 8)

    def test_32_threads(self):
        assert compute_thread_split(32) == (2, 16)

    def test_16_threads(self):
        assert compute_thread_split(16) == (2, 8)

    def test_2_threads(self):
        assert compute_thread_split(2) == (2, 1)

    def test_1_thread_clamps_to_min(self):
        jobs, tpj = compute_thread_split(1)
        assert jobs == 2
        assert tpj == 1  # max(1, 1 // 2) = max(1, 0) = 1
