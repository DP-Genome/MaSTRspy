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

    fastq_files = [f for f in files if f.suffix.lower() in [".fastq", ".fq"]]
    if fastq_files:
        return FileType.FASTQ, [str(f) for f in fastq_files]

    bam_files = [f for f in files if f.suffix.lower() == ".bam"]
    if bam_files:
        try:
            result = subprocess.run(
                ["samtools", "view", "-c", "-F", "4", str(bam_files[0])],
                capture_output=True,
                text=True,
                timeout=10,
            )
            is_aligned = int(result.stdout.strip()) > 0
            return (
                FileType.BAM_ALIGNED if is_aligned else FileType.BAM_UNALIGNED,
                [str(f) for f in bam_files],
            )
        except Exception:
            return FileType.BAM_UNALIGNED, [str(f) for f in bam_files]

    return FileType.UNKNOWN, []
