"""STR allele name parsing utilities (#3).

Extracts structured allele information from raw allele name strings
produced by the STR motif alignment step. Replaces fragile string
splitting with robust regex-based parsing.

Expected allele name formats:
    LOCUS_CEXX_[MOTIF]N          e.g., D3S1358_CE15_[TCTA]15
    LOCUS_CEXX.X_[MOTIF]N        e.g., D3S1358_CE15.3_[TCTA]15[TCT]1
    LOCUS_[MOTIF]N_CEXX           alternate ordering
"""

import re
from dataclasses import dataclass
from typing import List, Optional

# Pattern to extract CE number: CE followed by digits (optionally with decimal)
_CE_PATTERN = re.compile(r"CE(\d+(?:\.\d+)?)")

# Pattern to extract motif: everything from first '[' to end
_MOTIF_PATTERN = re.compile(r"(\[.*)")

# Pattern to extract locus name: the first segment before _CE or _[
_LOCUS_PATTERN = re.compile(r"^([A-Za-z0-9]+(?:S\d+)?)")


@dataclass
class ParsedAllele:
    """Structured representation of a parsed STR allele."""

    raw_name: str
    locus: str
    ce_number: str
    motif: str
    raw_count: int = 0
    normalized_count: float = 0.0

    @property
    def ce_float(self) -> Optional[float]:
        """CE number as a float, or None if not parseable."""
        try:
            return float(self.ce_number)
        except (ValueError, TypeError):
            return None

    @property
    def repeat_count(self) -> Optional[int]:
        """Extract the integer repeat count from the CE number."""
        if self.ce_number:
            try:
                return int(self.ce_number.split(".")[0])
            except (ValueError, IndexError):
                return None
        return None


def parse_allele_name(allele_name: str) -> ParsedAllele:
    """Parse a raw allele name string into structured components.

    Args:
        allele_name: raw allele string, e.g. "D3S1358_CE15_[TCTA]15"

    Returns:
        ParsedAllele with locus, ce_number, and motif extracted.
    """
    # Extract CE number
    ce_match = _CE_PATTERN.search(allele_name)
    ce_number = ce_match.group(1) if ce_match else ""

    # Extract motif
    motif_match = _MOTIF_PATTERN.search(allele_name)
    motif = motif_match.group(1) if motif_match else ""

    # Extract locus name
    locus_match = _LOCUS_PATTERN.search(allele_name)
    locus = locus_match.group(1) if locus_match else allele_name.split("_")[0]

    return ParsedAllele(
        raw_name=allele_name,
        locus=locus,
        ce_number=ce_number,
        motif=motif,
    )


def parse_allele_with_counts(
    allele_name: str, raw_count: int, max_count: int
) -> ParsedAllele:
    """Parse allele name and attach count information.

    Args:
        allele_name: raw allele string
        raw_count: raw read count for this allele
        max_count: maximum count across all alleles (for normalization)
    """
    parsed = parse_allele_name(allele_name)
    parsed.raw_count = raw_count
    parsed.normalized_count = raw_count / max_count if max_count > 0 else 0.0
    return parsed


def detect_stutter(
    alleles: List[ParsedAllele],
    stutter_ratio: float = 0.15,
) -> List[ParsedAllele]:
    """Flag potential stutter artifacts (#18).

    Stutter peaks are typically at n-1 (or n+1) repeats of the major allele
    and below a threshold ratio relative to the major allele.

    Args:
        alleles: sorted list of ParsedAllele (highest count first)
        stutter_ratio: maximum normalized count to be considered stutter

    Returns:
        list of alleles with stutter candidates removed.
    """
    if len(alleles) < 2:
        return alleles

    major = alleles[0]
    major_repeat = major.repeat_count

    if major_repeat is None:
        return alleles

    filtered = [major]
    for allele in alleles[1:]:
        repeat = allele.repeat_count
        if repeat is None:
            filtered.append(allele)
            continue

        # Check if this allele is n-1 or n+1 of the major allele
        is_stutter_position = abs(repeat - major_repeat) == 1
        is_below_threshold = allele.normalized_count <= stutter_ratio

        if is_stutter_position and is_below_threshold:
            # This is likely a stutter artifact — skip it
            continue

        filtered.append(allele)

    return filtered


def call_zygosity(
    alleles: List[ParsedAllele],
    norm_cutoff: float,
) -> str:
    """Determine zygosity from the top alleles (#19).

    Args:
        alleles: sorted list of ParsedAllele (highest count first)
        norm_cutoff: minimum normalized count to consider a real allele

    Returns:
        "Homozygous", "Heterozygous", or "No Call"
    """
    passing = [a for a in alleles if a.normalized_count >= norm_cutoff]

    if len(passing) == 0:
        return "No Call"
    elif len(passing) == 1:
        return "Homozygous"
    else:
        return "Heterozygous"
