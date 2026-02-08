"""Configuration loading and constants for MaSTRspy."""

import os
import re
from typing import Dict, Optional

FILTER_PRESETS = {
    "None": {"min_dorado_q": 0.0, "min_mean_q": 0.0, "min_len": 0, "min_acc": 0.0},
    "Lenient": {
        "min_dorado_q": 8.0,
        "min_mean_q": 8.0,
        "min_len": 100,
        "min_acc": 0.80,
    },
    "Moderate": {
        "min_dorado_q": 10.0,
        "min_mean_q": 10.0,
        "min_len": 200,
        "min_acc": 0.85,
    },
    "Stringent": {
        "min_dorado_q": 12.0,
        "min_mean_q": 12.0,
        "min_len": 300,
        "min_acc": 0.90,
    },
    "Custom": {},
}

DEMUX_KITS = [
    "None",
    "SQK-RBK114-24",
    "SQK-NBD114-24",
    "SQK-RBK110-96",
    "SQK-NBD112-24",
]


def compute_thread_split(total_threads: int) -> tuple:
    """Split a total thread count into (parallel_jobs, threads_per_job).

    >= 64 threads: 8 parallel jobs
    <  64 threads: 2 parallel jobs
    """
    if total_threads >= 64:
        jobs = 8
    else:
        jobs = 2
    threads_per_job = max(1, total_threads // jobs)
    return jobs, threads_per_job


def load_input_config(path: str) -> Dict[str, str]:
    """Parse a KEY=value config file (shell-style), ignoring comments."""
    config = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            config[key] = value
    return config


def load_tools_config(path: str) -> Dict[str, str]:
    """Parse tools config file and return dict of tool name → path."""
    return load_input_config(path)


def load_overrides(path: str) -> Dict[str, float]:
    """Load per-locus normalization cutoff overrides from a TSV file.

    Returns dict mapping locus name to cutoff value.
    """
    overrides = {}
    if not path or not os.path.isfile(path):
        return overrides
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                locus = parts[0].strip()
                try:
                    cutoff = float(parts[1].strip())
                    overrides[locus] = cutoff
                except ValueError:
                    continue
    return overrides


def generate_input_config(
    input_dir: str,
    output_dir: str,
    params: Dict,
    master_config_path: Optional[str] = None,
) -> str:
    """Generate an InputConfig.txt content string with updated paths and params."""
    norm_cutoff = params.get("norm_cutoff", 0.10)
    norm_cutoff_overrides = params.get("norm_cutoff_overrides", "")
    total_threads = params.get("num_threads", 16)
    num_jobs, threads_per_job = compute_thread_split(total_threads)
    enable_snv = "yes" if params.get("enable_snv", False) else "no"

    if master_config_path and os.path.exists(master_config_path):
        with open(master_config_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        saw_norm_cutoff = False
        saw_norm_overrides = False
        saw_num_parallel_jobs = False
        saw_num_threads = False
        saw_enable_snv = False

        for line in lines:
            if re.match(r"^\s*INPUT_DIR=", line):
                new_lines.append(f'INPUT_DIR="{input_dir}"\n')
            elif re.match(r"^\s*OUTPUT_DIR=", line):
                new_lines.append(f'OUTPUT_DIR="{output_dir}"\n')
            elif re.match(r"^\s*INPUT_BAM=", line):
                new_lines.append('INPUT_BAM="yes"\n')
            elif re.match(r"^\s*NORM_CUTOFF=", line):
                saw_norm_cutoff = True
                new_lines.append(f"NORM_CUTOFF={norm_cutoff}\n")
            elif re.match(r"^\s*NORM_CUTOFF_OVERRIDES=", line):
                saw_norm_overrides = True
                if norm_cutoff_overrides:
                    new_lines.append(
                        f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n'
                    )
                else:
                    new_lines.append("NORM_CUTOFF_OVERRIDES=\n")
            elif re.match(r"^\s*NUM_PARALLEL_JOBS=", line):
                saw_num_parallel_jobs = True
                new_lines.append(f"NUM_PARALLEL_JOBS={num_jobs}\n")
            elif re.match(r"^\s*NUM_THREADS=", line):
                saw_num_threads = True
                new_lines.append(f"NUM_THREADS={threads_per_job}\n")
            elif re.match(r"^\s*ENABLE_SNV=", line):
                saw_enable_snv = True
                new_lines.append(f"ENABLE_SNV={enable_snv}\n")
            else:
                new_lines.append(line)

        if not saw_norm_cutoff:
            new_lines.append(f"NORM_CUTOFF={norm_cutoff}\n")
        if not saw_norm_overrides:
            if norm_cutoff_overrides:
                new_lines.append(f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n')
            else:
                new_lines.append("NORM_CUTOFF_OVERRIDES=\n")
        if not saw_num_parallel_jobs:
            new_lines.append(f"NUM_PARALLEL_JOBS={num_jobs}\n")
        if not saw_num_threads:
            new_lines.append(f"NUM_THREADS={threads_per_job}\n")
        if not saw_enable_snv:
            new_lines.append(f"ENABLE_SNV={enable_snv}\n")

        return "".join(new_lines)
    else:
        config_str = (
            f'INPUT_DIR="{input_dir}"\n'
            f'OUTPUT_DIR="{output_dir}"\n'
            f'INPUT_BAM="yes"\n'
            f"NORM_CUTOFF={norm_cutoff}\n"
            f"NUM_PARALLEL_JOBS={num_jobs}\n"
            f"NUM_THREADS={threads_per_job}\n"
            f"ENABLE_SNV={enable_snv}\n"
        )
        if norm_cutoff_overrides:
            config_str += f'NORM_CUTOFF_OVERRIDES="{norm_cutoff_overrides}"\n'
        return config_str
