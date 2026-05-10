"""FASTQ quality and length filter."""

from typing import Callable, Dict


def _mean_q(qual: str) -> float:
    """Compute mean Phred quality from an ASCII quality string."""
    if not qual:
        return 0.0
    return sum(qual.encode("ascii")) / len(qual) - 33


def filter_fastq(
    input_path: str,
    output_path: str,
    min_mean_q: float,
    min_len: int,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Filter FASTQ reads by minimum mean quality and minimum length.

    Returns dict with keys: passed, filtered.
    """
    passed = 0
    filtered = 0

    with open(input_path, "r") as fin, open(output_path, "w") as fout:
        while True:
            h = fin.readline()
            if not h:
                break
            s = fin.readline().rstrip("\n")
            p = fin.readline()
            q = fin.readline().rstrip("\n")
            if not q:
                break
            if len(s) < min_len:
                filtered += 1
                continue
            if _mean_q(q) < min_mean_q:
                filtered += 1
                continue
            fout.write(h)
            fout.write(s + "\n")
            fout.write(p)
            fout.write(q + "\n")
            passed += 1

    log(f"[fastq_filter] Passed: {passed}, Filtered: {filtered}")
    return {"passed": passed, "filtered": filtered}
