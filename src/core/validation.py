"""Input validation utilities (#13)."""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class ValidationResult:
    """Collects validation errors and warnings."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def validate_input_path(path: str) -> ValidationResult:
    """Validate that the input path exists and is readable."""
    result = ValidationResult()
    if not path:
        result.add_error("Input path is empty.")
        return result
    if not os.path.exists(path):
        result.add_error(f"Input path does not exist: {path}")
        return result
    if not os.access(path, os.R_OK):
        result.add_error(f"Input path is not readable: {path}")
    return result


def validate_output_path(path: str) -> ValidationResult:
    """Validate that the output directory can be created and written to."""
    result = ValidationResult()
    if not path:
        result.add_error("Output path is empty.")
        return result

    parent = os.path.dirname(path) or "."
    if not os.path.exists(parent):
        result.add_error(f"Parent directory does not exist: {parent}")
        return result
    if not os.access(parent, os.W_OK):
        result.add_error(f"Output directory is not writable: {parent}")
    return result


def validate_reference_genome(path: str) -> ValidationResult:
    """Validate that a reference genome file exists."""
    result = ValidationResult()
    if not path:
        result.add_error("Reference genome path is empty.")
        return result
    if not os.path.isfile(path):
        result.add_error(f"Reference genome not found: {path}")
        return result
    if not os.access(path, os.R_OK):
        result.add_error(f"Reference genome is not readable: {path}")
    return result


def estimate_disk_space(input_path: str) -> Optional[int]:
    """Estimate required disk space (bytes) based on input size.

    Rough heuristic: 3x input size for intermediate files.
    Returns None if input size cannot be determined.
    """
    try:
        if os.path.isfile(input_path):
            return os.path.getsize(input_path) * 3
        elif os.path.isdir(input_path):
            total = sum(
                f.stat().st_size for f in Path(input_path).rglob("*") if f.is_file()
            )
            return total * 3
    except OSError:
        return None
    return None


def check_disk_space(output_dir: str, required_bytes: int) -> ValidationResult:
    """Check if there's enough disk space at the output location."""
    result = ValidationResult()
    try:
        check_dir = (
            output_dir
            if os.path.exists(output_dir)
            else os.path.dirname(output_dir) or "."
        )
        usage = shutil.disk_usage(check_dir)
        if usage.free < required_bytes:
            free_gb = usage.free / (1024**3)
            req_gb = required_bytes / (1024**3)
            result.add_warning(
                f"Low disk space: {free_gb:.1f} GB free, "
                f"~{req_gb:.1f} GB estimated needed."
            )
    except OSError:
        result.add_warning("Could not check disk space.")
    return result


def validate_pipeline_inputs(
    params: Dict,
    log: Callable[[str], None] = print,
) -> ValidationResult:
    """Run all input validations for the pipeline.

    Returns a combined ValidationResult.
    """
    combined = ValidationResult()

    log("--- Validating pipeline inputs ---")

    # Input path
    v = validate_input_path(params.get("input_dir", "") or params.get("input_path", ""))
    combined.errors.extend(v.errors)
    combined.warnings.extend(v.warnings)

    # Output path
    v = validate_output_path(params.get("output_dir", ""))
    combined.errors.extend(v.errors)
    combined.warnings.extend(v.warnings)

    # Reference genome (if prepping is needed)
    ref_genome = params.get("ref_genome", "")
    if ref_genome and params.get("needs_prepping", True):
        v = validate_reference_genome(ref_genome)
        combined.errors.extend(v.errors)
        combined.warnings.extend(v.warnings)

    # Disk space estimate
    input_path = params.get("input_dir", "") or params.get("input_path", "")
    if input_path and os.path.exists(input_path):
        estimated = estimate_disk_space(input_path)
        if estimated:
            output_dir = params.get("output_dir", "")
            v = check_disk_space(output_dir, estimated)
            combined.warnings.extend(v.warnings)

    # Log results
    for err in combined.errors:
        log(f"  [ERROR] {err}")
    for warn in combined.warnings:
        log(f"  [WARNING] {warn}")

    if combined.is_valid:
        log("--- Input validation passed ---")
    else:
        log("--- Input validation FAILED ---")

    return combined
