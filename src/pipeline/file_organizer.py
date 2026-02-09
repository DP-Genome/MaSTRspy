"""Organize counting output files into barcode-specific subdirectories.

Replaces the file organization section of MaSTRspy_Analysis_P1.0.sh.
"""

import os
import re
import shutil
from typing import Callable


def organize_by_barcode(
    counting_dir: str,
    num_barcodes: int = 24,
    log: Callable[[str], None] = print,
) -> None:
    """Sort counting output files into barcode directories.

    1. Remove *Toptwo.txt files
    2. Create barcode01..barcodeNN + unclassified directories
    3. Move files matching barcodeXX pattern into corresponding dirs
    4. Move unclassified files into unclassified/
    """
    log(f"--- Starting File Organization in '{counting_dir}' ---")

    if not os.path.isdir(counting_dir):
        log(f"Error: Directory '{counting_dir}' not found.")
        return

    # 1. Remove legacy Toptwo.txt files (#12: no longer generated, but clean up old ones)
    toptwo_files = [
        f
        for f in os.listdir(counting_dir)
        if f.endswith("Toptwo.txt") and os.path.isfile(os.path.join(counting_dir, f))
    ]
    if toptwo_files:
        log(f"Removing {len(toptwo_files)} legacy Toptwo.txt files...")
        for f in toptwo_files:
            os.remove(os.path.join(counting_dir, f))
        log("Cleanup complete.")
    else:
        log("No legacy Toptwo.txt files to clean up.")

    # 2. Create barcode directories
    log(f"Creating directories from barcode01 to barcode{num_barcodes:02d}...")
    for i in range(1, num_barcodes + 1):
        os.makedirs(os.path.join(counting_dir, f"barcode{i:02d}"), exist_ok=True)
    os.makedirs(os.path.join(counting_dir, "unclassified"), exist_ok=True)
    log("Directories are ready.")

    # 3. Sort files into barcode directories
    log("Sorting files into corresponding barcode directories...")
    barcode_pattern = re.compile(r"(barcode\d+)")

    for fname in os.listdir(counting_dir):
        fpath = os.path.join(counting_dir, fname)
        if os.path.isdir(fpath):
            continue

        match = barcode_pattern.search(fname)
        if match:
            dest_dir = os.path.join(counting_dir, match.group(1))
            if os.path.isdir(dest_dir):
                log(f"Moving '{fname}' -> '{match.group(1)}/'")
                shutil.move(fpath, os.path.join(dest_dir, fname))

    # 4. Move unclassified files
    log("Moving unclassified text files...")
    for fname in os.listdir(counting_dir):
        fpath = os.path.join(counting_dir, fname)
        if os.path.isdir(fpath):
            continue
        if "unclassified" in fname and fname.endswith(".txt"):
            log(f"Moving '{fname}' -> 'unclassified/'")
            shutil.move(fpath, os.path.join(counting_dir, "unclassified", fname))
    log("Unclassified files sorted.")
    log("--- All files have been sorted. ---")
