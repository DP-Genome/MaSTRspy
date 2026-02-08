"""Python-native STR profile plotting (#26).

Replaces R script dependency with matplotlib for plot generation.
"""

import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def _parse_summary_tsv(filepath: str) -> Dict[str, List[Tuple[str, float]]]:
    """Parse a barcode summary TSV into {locus: [(ce_number, normalized_count), ...]}."""
    loci = {}
    with open(filepath, "r") as f:
        header = f.readline()  # skip header
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 6:
                continue
            locus = parts[1]
            ce_num = parts[2]
            try:
                norm_count = float(parts[5])
            except ValueError:
                continue
            if locus not in loci:
                loci[locus] = []
            loci[locus].append((ce_num, norm_count))
    return loci


def _parse_profile_tsv(filepath: str) -> Dict[str, List[dict]]:
    """Parse a barcode profile TSV into {locus: [{ce_num, norm, status, zygosity}, ...]}."""
    loci = {}
    with open(filepath, "r") as f:
        header = f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue
            locus = parts[1]
            entry = {
                "rank": parts[2],
                "ce_number": parts[3],
                "motif": parts[4],
                "raw_counts": parts[5],
                "normalized": parts[6],
                "status": parts[7],
            }
            # Check for optional zygosity column
            if len(parts) >= 9:
                entry["zygosity"] = parts[8]
            if locus not in loci:
                loci[locus] = []
            loci[locus].append(entry)
    return loci


def generate_profile_plot(
    summary_path: str,
    output_path: str,
    barcode_name: str = "",
    norm_cutoff: float = 0.1,
    logo_path: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> bool:
    """Generate a STR profile bar plot from a summary TSV.

    Args:
        summary_path: path to barcode_XX_summary.tsv
        output_path: path for the output PNG
        barcode_name: display name for the title
        norm_cutoff: normalization cutoff line
        logo_path: optional path to logo image (watermark)

    Returns:
        True if plot was generated, False otherwise.
    """
    if not HAS_MATPLOTLIB:
        log("[WARNING] matplotlib not installed. Skipping Python plot generation.")
        return False

    loci_data = _parse_summary_tsv(summary_path)
    if not loci_data:
        return False

    # Sort loci alphabetically
    sorted_loci = sorted(loci_data.keys())
    num_loci = len(sorted_loci)

    if num_loci == 0:
        return False

    # Create a figure with subplots — one per locus
    cols = min(6, num_loci)
    rows = (num_loci + cols - 1) // cols
    fig_width = max(16, cols * 3)
    fig_height = max(4, rows * 3.5)

    fig, axes = plt.subplots(rows, cols, figsize=(fig_width, fig_height))
    if rows == 1 and cols == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [axes]
    elif cols == 1:
        axes = [[ax] for ax in axes]

    fig.suptitle(
        f"STR Profile: {barcode_name}" if barcode_name else "STR Profile",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    for idx, locus in enumerate(sorted_loci):
        row = idx // cols
        col = idx % cols
        ax = axes[row][col]

        alleles = loci_data[locus]
        # Take top 10 alleles for display
        alleles = alleles[:10]

        ce_numbers = [a[0] for a in alleles]
        norm_counts = [a[1] for a in alleles]

        colors = ["#2196F3" if n >= norm_cutoff else "#BDBDBD" for n in norm_counts]

        bars = ax.bar(range(len(ce_numbers)), norm_counts, color=colors, width=0.7)
        ax.set_title(locus, fontsize=9, fontweight="bold")
        ax.set_xticks(range(len(ce_numbers)))
        ax.set_xticklabels(ce_numbers, fontsize=7, rotation=45, ha="right")
        ax.set_ylim(0, 1.1)
        ax.set_ylabel("Norm. Count", fontsize=7)
        ax.tick_params(axis="y", labelsize=7)

        # Draw cutoff line
        ax.axhline(y=norm_cutoff, color="red", linestyle="--", linewidth=0.8, alpha=0.7)

    # Hide empty subplots
    for idx in range(num_loci, rows * cols):
        row = idx // cols
        col = idx % cols
        axes[row][col].set_visible(False)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def run_python_plots(
    summaries_dir: str,
    norm_cutoff: float = 0.1,
    logo_path: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> None:
    """Generate Python-native plots for all barcode summaries.

    Args:
        summaries_dir: directory containing barcode*_summary.tsv files
        norm_cutoff: normalization cutoff for highlighting
        logo_path: optional path to logo image
    """
    if not HAS_MATPLOTLIB:
        log("[WARNING] matplotlib not available. Install with: pip install matplotlib")
        return

    log("--- Generating Python plots ---")

    plots_dir = os.path.join(summaries_dir, "Plots")
    os.makedirs(plots_dir, exist_ok=True)

    summary_files = sorted(Path(summaries_dir).glob("barcode*_summary.tsv"))

    for summary_file in summary_files:
        if summary_file.stat().st_size == 0:
            continue

        barcode_name = summary_file.name.replace("_summary.tsv", "")
        output_plot = os.path.join(plots_dir, f"{barcode_name}_plot.png")

        log(f"  Generating plot for {barcode_name}...")
        success = generate_profile_plot(
            str(summary_file),
            output_plot,
            barcode_name=barcode_name,
            norm_cutoff=norm_cutoff,
            logo_path=logo_path,
            log=log,
        )
        if not success:
            log(f"  [WARNING] Could not generate plot for {barcode_name}")

    log("--- Python plot generation complete ---")
