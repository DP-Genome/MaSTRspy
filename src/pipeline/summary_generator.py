"""Generate barcode summary and profile TSV files.

Replaces the summary generation sections of MaSTRspy_Analysis_P1.0.sh.
"""

import os
import re
from typing import Callable, Dict, List, Tuple

from src.pipeline.allele_parser import (
    ParsedAllele,
    call_zygosity,
    detect_stutter,
    parse_allele_name,
)

# Regex to split locus name from the rest of the allele freq filename.
# Filenames are {locus}_{barcode}_{...}_Allele_freqs.txt
_LOCUS_FROM_FNAME = re.compile(r"^(.+?)_(?:barcode\d+|unclassified|[A-Za-z]+\d*_prepped)")


def _extract_locus_from_filename(fname: str) -> str:
    """Extract locus name from an allele frequency filename.

    Handles loci with underscores (e.g., CSF1_PO) by matching up to
    the barcode/sample portion of the filename.
    """
    m = _LOCUS_FROM_FNAME.match(fname)
    if m:
        return m.group(1)
    # Fallback: first segment before underscore
    return fname.split("_")[0]


def generate_summaries(
    counting_dir: str,
    norm_cutoff: float,
    overrides: Dict[str, float],
    log: Callable[[str], None] = print,
    normalization_method: str = "max",
    stutter_filter: bool = True,
    stutter_ratio: float = 0.15,
) -> Dict[str, dict]:
    """Generate summary and profile TSV files for each barcode directory.

    (#17) Supports multiple normalization methods: "max", "total", "noise_floor"
    (#18) Optional stutter filtering.
    (#19) Zygosity calling in profile output.
    (#20) Returns per-sample quality metrics.

    Args:
        counting_dir: path to the Countings directory with barcode subdirs
        norm_cutoff: global normalization cutoff
        overrides: dict of locus -> cutoff overrides
        normalization_method: "max" (default), "total", or "noise_floor"
        stutter_filter: whether to apply stutter filtering
        stutter_ratio: max ratio for stutter detection

    Returns:
        Dict mapping barcode name to quality metrics (#20).
    """
    log("--- Starting Summary Generation ---")

    summaries_dir = os.path.join(counting_dir, "Summaries")
    os.makedirs(summaries_dir, exist_ok=True)

    # Process each barcode directory
    barcode_dirs = sorted(
        d
        for d in os.listdir(counting_dir)
        if os.path.isdir(os.path.join(counting_dir, d)) and d.startswith("barcode")
    )

    quality_metrics: Dict[str, dict] = {}

    for barcode_name in barcode_dirs:
        barcode_path = os.path.join(counting_dir, barcode_name)
        _generate_barcode_summary(
            barcode_path, barcode_name, summaries_dir, normalization_method, log
        )
        metrics = _generate_barcode_profile(
            barcode_path, barcode_name, summaries_dir,
            norm_cutoff, overrides, normalization_method,
            stutter_filter, stutter_ratio, log,
        )
        quality_metrics[barcode_name] = metrics

    # (#20) Write quality metrics summary
    _write_quality_report(quality_metrics, summaries_dir, log)

    log("--- Summaries created in the 'Summaries' directory. ---")
    log("--- Barcode Profiles created in the 'Summaries' directory. ---")

    return quality_metrics


def _normalize_counts(
    raw_counts: List[Tuple[str, int]],
    method: str = "max",
) -> List[Tuple[str, int, float]]:
    """Normalize allele counts using the specified method (#17).

    Methods:
        "max": divide by maximum count (default, original behavior)
        "total": divide by total count across all alleles
        "noise_floor": divide by max, then subtract noise floor (2nd percentile)

    Returns list of (allele_name, raw_count, normalized_count).
    """
    if not raw_counts:
        return []

    counts = [c for _, c in raw_counts]

    if method == "total":
        total = sum(counts)
        denominator = total if total > 0 else 1
    elif method == "noise_floor":
        max_count = max(counts)
        denominator = max_count if max_count > 0 else 1
    else:  # "max" (default)
        max_count = max(counts)
        denominator = max_count if max_count > 0 else 1

    # Pre-compute noise floor once (if needed) instead of inside the loop
    noise_floor_value = 0.0
    if method == "noise_floor" and len(counts) >= 10:
        sorted_counts = sorted(counts)
        noise_idx = max(0, len(sorted_counts) // 50)  # 2nd percentile
        noise_floor_value = sorted_counts[noise_idx] / denominator

    result = []
    for name, count in raw_counts:
        normalized = count / denominator
        if method == "noise_floor" and len(counts) >= 10:
            normalized = max(0, normalized - noise_floor_value)
        result.append((name, count, normalized))

    return result


def _generate_barcode_summary(
    barcode_path: str,
    barcode_name: str,
    summaries_dir: str,
    normalization_method: str,
    log: Callable[[str], None],
) -> None:
    """Generate a summary TSV for one barcode directory."""
    output_summary = os.path.join(summaries_dir, f"{barcode_name}_summary.tsv")

    with open(output_summary, "w") as out:
        out.write("Barcode\tLocus\tCE_Number\tMotif\tRawCounts\tNormalizedCounts\n")

        allele_files = sorted(
            f for f in os.listdir(barcode_path) if f.endswith("_Allele_freqs.txt")
        )

        for fname in allele_files:
            locus_name = _extract_locus_from_filename(fname)
            fpath = os.path.join(barcode_path, fname)

            with open(fpath, "r") as fin:
                lines = fin.readlines()

            for line in lines[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue

                str_field = parts[0]
                raw_counts = parts[1]
                normalized = parts[2]

                # (#3) Use allele_parser for extraction
                parsed = parse_allele_name(str_field)

                out.write(
                    f"{barcode_name}\t{locus_name}\t{parsed.ce_number}\t"
                    f"{parsed.motif}\t{raw_counts}\t{normalized}\n"
                )


def _generate_barcode_profile(
    barcode_path: str,
    barcode_name: str,
    summaries_dir: str,
    norm_cutoff: float,
    overrides: Dict[str, float],
    normalization_method: str,
    stutter_filter: bool,
    stutter_ratio: float,
    log: Callable[[str], None],
) -> dict:
    """Generate a profile TSV (top 2 alleles per locus) for one barcode.

    (#18) Applies stutter filtering before allele selection.
    (#19) Adds zygosity calling column.
    (#20) Returns quality metrics for this barcode.

    Returns dict with quality metrics.
    """
    profile_file = os.path.join(summaries_dir, f"{barcode_name}_Profile.tsv")

    total_loci = 0
    loci_with_calls = 0
    homozygous_count = 0
    heterozygous_count = 0
    no_call_count = 0

    with open(profile_file, "w") as out:
        out.write(
            "Barcode\tLocus\tAllele_Rank\tCE_Number\tMotif\t"
            "RawCounts\tNormalizedCounts\tStatus\tZygosity\n"
        )

        allele_files = sorted(
            f for f in os.listdir(barcode_path) if f.endswith("_Allele_freqs.txt")
        )

        for fname in allele_files:
            locus_name = _extract_locus_from_filename(fname)
            effective_cutoff = overrides.get(locus_name, norm_cutoff)
            fpath = os.path.join(barcode_path, fname)
            total_loci += 1

            with open(fpath, "r") as fin:
                lines = fin.readlines()

            # Parse all alleles for this locus
            raw_alleles: List[Tuple[str, int]] = []
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                try:
                    raw_alleles.append((parts[0], int(parts[1])))
                except ValueError:
                    continue

            # Apply normalization
            normalized_alleles = _normalize_counts(raw_alleles, normalization_method)

            # Build ParsedAllele objects
            max_count = max((c for _, c, _ in normalized_alleles), default=1)
            parsed_alleles = []
            for name, raw_count, norm_count in normalized_alleles:
                pa = parse_allele_name(name)
                pa.raw_count = raw_count
                pa.normalized_count = norm_count
                parsed_alleles.append(pa)

            # (#18) Apply stutter filter
            if stutter_filter and parsed_alleles:
                parsed_alleles = detect_stutter(parsed_alleles, stutter_ratio)

            # Select top 2 alleles
            top_alleles = parsed_alleles[:2]

            # (#19) Call zygosity
            zygosity = call_zygosity(parsed_alleles, effective_cutoff)

            if zygosity == "No Call":
                no_call_count += 1
            else:
                loci_with_calls += 1
                if zygosity == "Homozygous":
                    homozygous_count += 1
                else:
                    heterozygous_count += 1

            # Write profile entries
            for rank, pa in enumerate(top_alleles, start=1):
                if pa.normalized_count >= effective_cutoff:
                    status = "PASS"
                else:
                    status = f"FLAGGED (Below {effective_cutoff})"

                out.write(
                    f"{barcode_name}\t{locus_name}\t{rank}\t{pa.ce_number}\t"
                    f"{pa.motif}\t{pa.raw_count}\t{pa.normalized_count}\t"
                    f"{status}\t{zygosity}\n"
                )

    log(f"  Generated profile for {barcode_name}")

    # (#20) Quality metrics
    quality_pct = (loci_with_calls / total_loci * 100) if total_loci > 0 else 0
    metrics = {
        "total_loci": total_loci,
        "loci_with_calls": loci_with_calls,
        "homozygous": homozygous_count,
        "heterozygous": heterozygous_count,
        "no_call": no_call_count,
        "quality_pct": quality_pct,
    }
    log(
        f"    Quality: {loci_with_calls}/{total_loci} loci called "
        f"({quality_pct:.1f}%), {homozygous_count} homo, "
        f"{heterozygous_count} hetero, {no_call_count} no-call"
    )
    return metrics


def _write_quality_report(
    quality_metrics: Dict[str, dict],
    summaries_dir: str,
    log: Callable[[str], None],
) -> None:
    """Write a per-sample quality report TSV (#20)."""
    report_path = os.path.join(summaries_dir, "sample_quality_report.tsv")
    with open(report_path, "w") as f:
        f.write(
            "Barcode\tTotal_Loci\tLoci_With_Calls\t"
            "Homozygous\tHeterozygous\tNo_Call\tQuality_Pct\n"
        )
        for barcode, metrics in sorted(quality_metrics.items()):
            f.write(
                f"{barcode}\t{metrics['total_loci']}\t"
                f"{metrics['loci_with_calls']}\t{metrics['homozygous']}\t"
                f"{metrics['heterozygous']}\t{metrics['no_call']}\t"
                f"{metrics['quality_pct']:.1f}%\n"
            )
    log(f"  Quality report: {report_path}")
