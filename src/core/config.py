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
    Always caps jobs to total_threads so we never over-subscribe.
    """
    if total_threads >= 64:
        jobs = 8
    else:
        jobs = 2
    jobs = min(jobs, total_threads)
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
    """Generate an InputConfig.txt content string with updated paths and params.

    All GUI-provided params override master config values so that
    STR_FASTA, STR_BED, GENOME_FASTA, REGION_BED, and READ_TYPE
    are never stale developer paths.
    """
    norm_cutoff = params.get("norm_cutoff", 0.10)
    norm_cutoff_overrides = params.get("norm_cutoff_overrides", "")
    total_threads = params.get("num_threads", 16)
    num_jobs, threads_per_job = compute_thread_split(total_threads)
    enable_snv = "yes" if params.get("enable_snv", False) else "no"
    read_type = params.get("read_type", "ont")
    str_fasta = params.get("str_fasta", "")
    str_bed = params.get("str_bed", "")
    genome_fasta = params.get("genome_fasta", "")
    region_bed = params.get("region_bed", "")

    # Map of keys the GUI always overrides
    overrides_map = {
        "INPUT_DIR": f'"{input_dir}"',
        "OUTPUT_DIR": f'"{output_dir}"',
        "INPUT_BAM": '"yes"',
        "NORM_CUTOFF": str(norm_cutoff),
        "NUM_PARALLEL_JOBS": str(num_jobs),
        "NUM_THREADS": str(threads_per_job),
        "ENABLE_SNV": enable_snv,
        "READ_TYPE": read_type,
    }
    if norm_cutoff_overrides:
        overrides_map["NORM_CUTOFF_OVERRIDES"] = f'"{norm_cutoff_overrides}"'
    else:
        overrides_map["NORM_CUTOFF_OVERRIDES"] = ""
    if str_fasta:
        overrides_map["STR_FASTA"] = str_fasta
    if str_bed:
        overrides_map["STR_BED"] = str_bed
    if genome_fasta:
        overrides_map["GENOME_FASTA"] = genome_fasta
    if region_bed:
        overrides_map["REGION_BED"] = region_bed

    if master_config_path and os.path.exists(master_config_path):
        with open(master_config_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        seen_keys = set()

        for line in lines:
            matched = False
            for key, value in overrides_map.items():
                if re.match(rf"^\s*{key}=", line):
                    new_lines.append(f"{key}={value}\n")
                    seen_keys.add(key)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        # Append any keys not found in the master config
        for key, value in overrides_map.items():
            if key not in seen_keys:
                new_lines.append(f"{key}={value}\n")

        return "".join(new_lines)
    else:
        lines = [f"{key}={value}\n" for key, value in overrides_map.items()]
        return "".join(lines)
