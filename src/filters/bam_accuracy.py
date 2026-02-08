"""BAM alignment accuracy filter using CIGAR + MD tag."""

from typing import Callable, Dict, Optional, Tuple

import pysam


def _get_ins_del_from_cigar(read) -> Optional[Tuple[int, int]]:
    """Extract insertion and deletion counts from CIGAR tuples."""
    ins = 0
    dels = 0
    if read.cigartuples is None:
        return None
    for op, length in read.cigartuples:
        if op == 1:  # insertion
            ins += length
        elif op == 2:  # deletion
            dels += length
    return ins, dels


def _get_matches_mismatches_from_md(read) -> Optional[Tuple[int, int]]:
    """Parse MD tag to count matches and mismatches."""
    try:
        md = read.get_tag("MD")
    except KeyError:
        return None

    matches = 0
    mismatches = 0
    i = 0
    num = ""

    while i < len(md):
        c = md[i]
        if c.isdigit():
            num += c
            i += 1
            continue
        if num:
            matches += int(num)
            num = ""
        if c == "^":
            i += 1
            while i < len(md) and md[i].isalpha():
                i += 1
            continue
        if c.isalpha():
            mismatches += 1
            i += 1
            continue
        i += 1

    if num:
        matches += int(num)
    return matches, mismatches


def filter_bam_by_accuracy(
    in_bam: str,
    out_bam: str,
    min_acc: float,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Filter aligned BAM reads by alignment accuracy.

    Accuracy = matches / (matches + mismatches + insertions + deletions).
    Unmapped reads and reads missing MD/CIGAR are skipped.
    Returns dict with keys: passed, filtered, skipped.
    """
    passed = 0
    filtered = 0
    skipped = 0

    inp = pysam.AlignmentFile(in_bam, "rb")
    out = pysam.AlignmentFile(out_bam, "wb", template=inp)

    for r in inp.fetch(until_eof=True):
        if r.is_unmapped:
            skipped += 1
            continue
        md = _get_matches_mismatches_from_md(r)
        cd = _get_ins_del_from_cigar(r)
        if md is None or cd is None:
            skipped += 1
            continue
        matches, mismatches = md
        ins, dels = cd
        denom = matches + mismatches + ins + dels
        if denom == 0:
            skipped += 1
            continue
        acc = matches / denom
        if acc >= min_acc:
            out.write(r)
            passed += 1
        else:
            filtered += 1

    inp.close()
    out.close()

    log(
        f"[bam_accuracy_filter] Passed: {passed}, "
        f"Filtered: {filtered}, Skipped: {skipped}"
    )
    return {"passed": passed, "filtered": filtered, "skipped": skipped}
