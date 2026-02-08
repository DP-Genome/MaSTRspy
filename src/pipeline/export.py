"""Multi-sample report export functionality (#25)."""

import csv
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional


def export_combined_report(
    summaries_dir: str,
    output_path: str,
    log: Callable[[str], None] = print,
) -> None:
    """Export a combined multi-barcode summary report.

    Merges all barcode summary TSVs into a single file with
    an additional overview sheet.

    Args:
        summaries_dir: directory containing barcode*_summary.tsv files
        output_path: path for the combined output TSV
    """
    log("--- Generating combined report ---")

    summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))
    profile_files = sorted(Path(summaries_dir).glob("barcode*_Profile.tsv"))

    if not summary_files:
        log("[WARNING] No summary files found. Skipping export.")
        return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Combined summary
    _write_combined_summaries(summary_files, output_path, log)

    # Combined profiles
    profile_output = output_path.replace("_combined_summary", "_combined_profile")
    if profile_output == output_path:
        profile_output = output_path.replace(".tsv", "_profiles.tsv")
    _write_combined_profiles(profile_files, profile_output, log)

    # Overview stats
    overview_output = output_path.replace("_combined_summary", "_overview")
    if overview_output == output_path:
        overview_output = output_path.replace(".tsv", "_overview.tsv")
    _write_overview(summary_files, profile_files, overview_output, log)

    log(f"  Combined summary: {output_path}")
    log(f"  Combined profiles: {profile_output}")
    log(f"  Overview: {overview_output}")
    log("--- Combined report generation complete ---")


def _write_combined_summaries(
    summary_files: List[Path],
    output_path: str,
    log: Callable[[str], None],
) -> None:
    """Merge all barcode summary TSVs into one file."""
    with open(output_path, "w") as out:
        header_written = False
        for sf in summary_files:
            with open(sf, "r") as f:
                lines = f.readlines()
            if not header_written and lines:
                out.write(lines[0])
                header_written = True
            for line in lines[1:]:
                if line.strip():
                    out.write(line)


def _write_combined_profiles(
    profile_files: List[Path],
    output_path: str,
    log: Callable[[str], None],
) -> None:
    """Merge all barcode profile TSVs into one file."""
    with open(output_path, "w") as out:
        header_written = False
        for pf in profile_files:
            with open(pf, "r") as f:
                lines = f.readlines()
            if not header_written and lines:
                out.write(lines[0])
                header_written = True
            for line in lines[1:]:
                if line.strip():
                    out.write(line)


def _write_overview(
    summary_files: List[Path],
    profile_files: List[Path],
    output_path: str,
    log: Callable[[str], None],
) -> None:
    """Write an overview TSV with per-barcode statistics."""
    with open(output_path, "w") as out:
        out.write(
            "Barcode\tTotal_Loci\tLoci_With_Calls\t"
            "Homozygous\tHeterozygous\tNo_Call\t"
            "Overall_Quality\n"
        )

        for pf in profile_files:
            barcode = pf.name.replace("_Profile.tsv", "")
            loci_data: Dict[str, List[dict]] = {}

            with open(pf, "r") as f:
                header = f.readline()
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) < 8:
                        continue
                    locus = parts[1]
                    if locus not in loci_data:
                        loci_data[locus] = []
                    entry = {"status": parts[7]}
                    if len(parts) >= 9:
                        entry["zygosity"] = parts[8]
                    loci_data[locus].append(entry)

            total_loci = len(loci_data)
            loci_with_calls = sum(
                1 for alleles in loci_data.values()
                if any(a["status"] == "PASS" for a in alleles)
            )

            # Count zygosity
            homo = hetero = no_call = 0
            for alleles in loci_data.values():
                zygosity = alleles[0].get("zygosity", "") if alleles else ""
                if zygosity == "Homozygous":
                    homo += 1
                elif zygosity == "Heterozygous":
                    hetero += 1
                else:
                    passing = [a for a in alleles if a["status"] == "PASS"]
                    if len(passing) == 0:
                        no_call += 1
                    elif len(passing) == 1:
                        homo += 1
                    else:
                        hetero += 1

            quality_pct = (loci_with_calls / total_loci * 100) if total_loci > 0 else 0

            out.write(
                f"{barcode}\t{total_loci}\t{loci_with_calls}\t"
                f"{homo}\t{hetero}\t{no_call}\t"
                f"{quality_pct:.1f}%\n"
            )
