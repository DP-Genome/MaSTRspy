"""Regression tests for two results-affecting bugs found in the Sep 2026 audit.

1. bedtools bamtofastq (v2.31) writes every BAM record twice, doubling all read
   counts. locus_processor must extract reads with `samtools fastq` instead.
2. Per-locus cutoff overrides were looked up by the file-derived locus name
   (VWA, PENTAD, PENTAE) while overrides.tsv used vWA/PentaD/PentaE, so those
   loci silently fell back to the global cutoff.
"""

import subprocess
from unittest import mock

from src.core.config import load_overrides, normalize_locus_name
from src.pipeline import locus_processor
from src.pipeline.summary_generator import _extract_locus_from_filename


def test_read_extraction_uses_samtools_fastq_not_bedtools_bamtofastq(tmp_path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        # make the sorted BAM "exist" so later steps do not blow up
        for arg in cmd:
            if str(arg).endswith(".sorted.bam"):
                open(arg, "w").close()
        m = mock.Mock(returncode=0, stderr="", stdout="")
        return m

    def fake_popen(cmd, **kw):
        m = mock.Mock()
        m.stdout = iter([])
        m.wait = lambda: 0
        return m

    bed = tmp_path / "TPOX.bed"
    bed.write_text("chr2\t1\t2\tTPOX\n")
    with (
        mock.patch.object(subprocess, "run", side_effect=fake_run),
        mock.patch.object(subprocess, "Popen", side_effect=fake_popen),
    ):
        locus_processor.process_locus(
            str(tmp_path / "barcode10_prepped.bam"),
            str(bed),
            {
                "output_dir": str(tmp_path / "out"),
                "str_fasta": str(tmp_path),
                "bedtools": "bedtools",
                "samtools": "samtools",
                "minimap": "minimap2",
            },
            temp_dir=str(tmp_path / "tmp"),
            log=lambda *_: None,
        )
    flat = [" ".join(c) for c in calls]
    assert not any("bamtofastq" in c for c in flat), flat
    assert any(c.startswith("samtools fastq") and "-F 2308" in c for c in flat), flat


def test_override_keys_match_file_derived_locus_names(tmp_path):
    tsv = tmp_path / "overrides.tsv"
    tsv.write_text("vWA\t0.4\nPentaD\t0.4\nPentaE\t0.4\nDYS481\t0.5\nDYS385a\t0.4\n")
    ov = load_overrides(str(tsv))
    for fname in [
        "VWA_barcode10_prepped.bam_Allele_freqs.txt",
        "PENTAD_barcode10_prepped.bam_Allele_freqs.txt",
        "PENTAE_barcode10_prepped.bam_Allele_freqs.txt",
    ]:
        locus = _extract_locus_from_filename(fname)
        assert ov.get(normalize_locus_name(locus)) == 0.4, (fname, locus, ov)
    assert (
        ov[
            normalize_locus_name(
                _extract_locus_from_filename(
                    "DYS481_barcode10_prepped.bam_Allele_freqs.txt"
                )
            )
        ]
        == 0.5
    )
