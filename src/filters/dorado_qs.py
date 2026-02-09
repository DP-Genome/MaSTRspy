"""Dorado basecaller quality score (qs tag) filters for BAM and FASTQ."""

import re
from typing import Callable, Dict

import pysam


def filter_bam_by_qs(
    in_bam: str,
    out_bam: str,
    min_qs: float,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Filter BAM reads by the Dorado 'qs' tag.

    Reads without the tag are passed through with a warning.
    Returns dict with keys: passed, filtered, no_tag_count.
    """
    passed = 0
    filtered = 0
    no_tag_count = 0
    tag_found = False

    inp = pysam.AlignmentFile(in_bam, "rb", check_sq=False)
    out = pysam.AlignmentFile(out_bam, "wb", template=inp)

    for r in inp.fetch(until_eof=True):
        try:
            qs_value = r.get_tag("qs")
            tag_found = True
            if qs_value >= min_qs:
                out.write(r)
                passed += 1
            else:
                filtered += 1
        except KeyError:
            no_tag_count += 1
            out.write(r)
            passed += 1

    inp.close()
    out.close()

    if not tag_found and no_tag_count > 0:
        log("[WARNING] Dorado 'qs' tag not found in any reads. " "Filter not applied.")
        log(f"[dorado_qs_filter] All {passed} reads passed " "(no qs tag available)")
    elif no_tag_count > 0:
        log(f"[WARNING] {no_tag_count} reads missing 'qs' tag " "(passed through)")
        log(f"[dorado_qs_filter] Passed: {passed}, Filtered: {filtered}")
    else:
        log(f"[dorado_qs_filter] Passed: {passed}, Filtered: {filtered}")

    return {"passed": passed, "filtered": filtered, "no_tag_count": no_tag_count}


# (#7) Improved regex: handles qs:f:12.5, qs:i:12, qs=12.5, qs=f:12.5
# Also handles scientific notation (e.g., qs:f:1.2e1) and negative values
_QS_PATTERN = re.compile(r"qs[:=](?:[fi]:)?(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


def filter_fastq_by_qs(
    input_path: str,
    output_path: str,
    min_qs: float,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Filter FASTQ reads by the Dorado 'qs' tag in the header.

    (#7) Improved regex handles: qs:f:12.5, qs:i:12, qs=12.5,
    qs=f:12.5, and scientific notation.
    Reads without the tag are passed through.
    Returns dict with keys: passed, filtered, no_tag_count.
    """
    passed = 0
    filtered = 0
    no_tag_count = 0
    tag_found = False

    with open(input_path, "r") as fin, open(output_path, "w") as fout:
        while True:
            header = fin.readline()
            if not header:
                break
            seq = fin.readline().rstrip("\n")
            plus = fin.readline()
            qual = fin.readline().rstrip("\n")

            if not qual:
                break

            match = _QS_PATTERN.search(header)

            if match:
                tag_found = True
                qs_value = float(match.group(1))
                if qs_value >= min_qs:
                    fout.write(header)
                    fout.write(seq + "\n")
                    fout.write(plus)
                    fout.write(qual + "\n")
                    passed += 1
                else:
                    filtered += 1
            else:
                no_tag_count += 1
                fout.write(header)
                fout.write(seq + "\n")
                fout.write(plus)
                fout.write(qual + "\n")
                passed += 1

    if not tag_found and no_tag_count > 0:
        log(
            "[WARNING] Dorado 'qs' tag not found in FASTQ headers. "
            "Filter not applied."
        )
        log(
            f"[dorado_qs_filter_fastq] All {passed} reads passed "
            "(no qs tag available)"
        )
    elif no_tag_count > 0:
        log(
            f"[WARNING] {no_tag_count} reads missing 'qs' tag in header "
            "(passed through)"
        )
        log(f"[dorado_qs_filter_fastq] Passed: {passed}, " f"Filtered: {filtered}")
    else:
        log(f"[dorado_qs_filter_fastq] Passed: {passed}, " f"Filtered: {filtered}")

    return {"passed": passed, "filtered": filtered, "no_tag_count": no_tag_count}
