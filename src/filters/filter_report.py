"""Consolidated filter QC report (#8)."""

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class FilterStageResult:
    """Result of a single filtering stage."""

    stage_name: str
    passed: int = 0
    filtered: int = 0
    skipped: int = 0
    no_tag_count: int = 0

    @property
    def total_input(self) -> int:
        return self.passed + self.filtered + self.skipped

    @property
    def pass_rate(self) -> float:
        total = self.total_input
        return (self.passed / total * 100) if total > 0 else 0.0


@dataclass
class FilterReport:
    """Aggregated QC report across all filtering stages for a sample."""

    sample_name: str
    stages: List[FilterStageResult] = field(default_factory=list)

    def add_stage(self, stage_name: str, stats: Dict[str, int]):
        """Add a filter stage result from a filter function's return dict."""
        stage = FilterStageResult(
            stage_name=stage_name,
            passed=stats.get("passed", 0),
            filtered=stats.get("filtered", 0),
            skipped=stats.get("skipped", 0),
            no_tag_count=stats.get("no_tag_count", 0),
        )
        self.stages.append(stage)

    @property
    def total_input(self) -> int:
        """Total reads at the start of filtering (from first stage)."""
        if self.stages:
            return self.stages[0].total_input
        return 0

    @property
    def final_passed(self) -> int:
        """Reads that passed all stages (from last stage)."""
        if self.stages:
            return self.stages[-1].passed
        return 0

    @property
    def overall_pass_rate(self) -> float:
        total = self.total_input
        return (self.final_passed / total * 100) if total > 0 else 0.0

    def to_tsv_rows(self) -> List[str]:
        """Generate TSV-formatted rows for the report."""
        rows = []
        for stage in self.stages:
            rows.append(
                f"{self.sample_name}\t{stage.stage_name}\t"
                f"{stage.total_input}\t{stage.passed}\t"
                f"{stage.filtered}\t{stage.skipped}\t"
                f"{stage.pass_rate:.1f}%"
            )
        return rows

    def summary_line(self) -> str:
        """Return a one-line summary of the filtering."""
        stages_str = " -> ".join(
            f"{s.stage_name}({s.pass_rate:.0f}%)" for s in self.stages
        )
        return (
            f"[QC] {self.sample_name}: {self.total_input} reads in, "
            f"{self.final_passed} out ({self.overall_pass_rate:.1f}% pass) | "
            f"{stages_str}"
        )


def write_qc_report(
    reports: List[FilterReport],
    output_path: str,
    log: Callable[[str], None] = print,
) -> None:
    """Write a consolidated QC report TSV for all samples.

    Args:
        reports: list of FilterReport objects (one per sample)
        output_path: path to write the QC TSV file
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w") as f:
        f.write("Sample\tStage\tInputReads\tPassed\tFiltered\tSkipped\tPassRate\n")
        for report in reports:
            for row in report.to_tsv_rows():
                f.write(row + "\n")

    log(f"[INFO] QC report written to: {output_path}")
