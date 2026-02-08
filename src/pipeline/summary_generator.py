"""Generate barcode summary and profile TSV files.

Replaces the summary generation sections of MaSTRspy_Analysis_P1.0.sh.
"""

import os
import re
from typing import Callable, Dict


def generate_summaries(
    counting_dir: str,
    norm_cutoff: float,
    overrides: Dict[str, float],
    log: Callable[[str], None] = print,
) -> None:
    """Generate summary and profile TSV files for each barcode directory.

    Args:
        counting_dir: path to the Countings directory with barcode subdirs
        norm_cutoff: global normalization cutoff
        overrides: dict of locus -> cutoff overrides
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

    for barcode_name in barcode_dirs:
        barcode_path = os.path.join(counting_dir, barcode_name)
        _generate_barcode_summary(barcode_path, barcode_name, summaries_dir, log)
        _generate_barcode_profile(
            barcode_path, barcode_name, summaries_dir, norm_cutoff, overrides, log
        )

    log("--- Summaries created in the 'Summaries' directory. ---")
    log("--- Barcode Profiles created in the 'Summaries' directory. ---")


def _generate_barcode_summary(
    barcode_path: str,
    barcode_name: str,
    summaries_dir: str,
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
            locus_name = fname.split("_")[0]
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

                # Extract CE number
                ce_match = re.search(r"CE(\d+(?:\.\d+)?)", str_field)
                ce_num = ce_match.group(1) if ce_match else ""

                # Extract motif (everything from first '[' onwards)
                motif_match = re.search(r"\[.*", str_field)
                motif = motif_match.group(0) if motif_match else ""

                out.write(
                    f"{barcode_name}\t{locus_name}\t{ce_num}\t"
                    f"{motif}\t{raw_counts}\t{normalized}\n"
                )


def _generate_barcode_profile(
    barcode_path: str,
    barcode_name: str,
    summaries_dir: str,
    norm_cutoff: float,
    overrides: Dict[str, float],
    log: Callable[[str], None],
) -> None:
    """Generate a profile TSV (top 2 alleles per locus) for one barcode."""
    profile_file = os.path.join(summaries_dir, f"{barcode_name}_Profile.tsv")

    with open(profile_file, "w") as out:
        out.write(
            "Barcode\tLocus\tAllele_Rank\tCE_Number\tMotif\t"
            "RawCounts\tNormalizedCounts\tStatus\n"
        )

        allele_files = sorted(
            f for f in os.listdir(barcode_path) if f.endswith("_Allele_freqs.txt")
        )

        for fname in allele_files:
            locus_name = fname.split("_")[0]
            effective_cutoff = overrides.get(locus_name, norm_cutoff)
            fpath = os.path.join(barcode_path, fname)

            with open(fpath, "r") as fin:
                lines = fin.readlines()

            rank = 0
            for line in lines[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue

                rank += 1
                if rank > 2:
                    break

                parts = line.split("\t")
                if len(parts) < 3:
                    continue

                str_field = parts[0]
                raw_counts = parts[1]
                normalized_str = parts[2]

                # Extract CE number
                ce_match = re.search(r"CE(\d+(?:\.\d+)?)", str_field)
                ce_num = ce_match.group(1) if ce_match else ""

                # Extract motif
                motif_match = re.search(r"\[.*", str_field)
                motif = motif_match.group(0) if motif_match else ""

                # Determine status
                try:
                    norm_val = float(normalized_str)
                except ValueError:
                    norm_val = 0.0

                if norm_val >= effective_cutoff:
                    status = "PASS"
                else:
                    status = f"FLAGGED (Below {effective_cutoff})"

                out.write(
                    f"{barcode_name}\t{locus_name}\t{rank}\t{ce_num}\t"
                    f"{motif}\t{raw_counts}\t{normalized_str}\t{status}\n"
                )

    log(f"  Generated profile for {barcode_name}")
