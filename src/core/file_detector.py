"""File type detection for MaSTRspy input directories."""

import subprocess
from enum import Enum
from pathlib import Path
from typing import List, Tuple


class FileType(Enum):
    POD5 = "pod5"
    BAM_ALIGNED = "bam_aligned"
    BAM_UNALIGNED = "bam_unaligned"
    FASTQ = "fastq"
    UNKNOWN = "unknown"


def detect_file_type(path: str) -> Tuple[FileType, List[str]]:
    """Detect the file type present in the given path.

    Returns a tuple of (FileType, list of matching file paths).
    """
    path_obj = Path(path)
    if not path_obj.exists():
        return FileType.UNKNOWN, []

    files = list(path_obj.iterdir()) if path_obj.is_dir() else [path_obj]

    pod5_files = [f for f in files if f.suffix.lower() == ".pod5"]
    if pod5_files:
        return FileType.POD5, [str(f) for f in pod5_files]

    fastq_files = [
        f for f in files
        if f.suffix.lower() in [".fastq", ".fq"]
        or f.name.lower().endswith((".fastq.gz", ".fq.gz"))
    ]
    if fastq_files:
        return FileType.FASTQ, [str(f) for f in fastq_files]

    bam_files = [f for f in files if f.suffix.lower() == ".bam"]
    if bam_files:
        # Sample up to 3 BAMs to determine alignment status
        sample_bams = bam_files[:3]
        aligned_count = 0
        for bam in sample_bams:
            try:
                result = subprocess.run(
                    ["samtools", "view", "-c", "-F", "4", str(bam)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if int(result.stdout.strip()) > 0:
                    aligned_count += 1
            except Exception:
                pass
        is_aligned = aligned_count > 0
        return (
            FileType.BAM_ALIGNED if is_aligned else FileType.BAM_UNALIGNED,
            [str(f) for f in bam_files],
        )

    return FileType.UNKNOWN, []
