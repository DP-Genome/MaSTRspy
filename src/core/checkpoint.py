"""Checkpoint and resume support for long-running pipelines (#15)."""

import json
import os
from typing import Dict, List, Set


class CheckpointManager:
    """Tracks completed loci/stages so the pipeline can resume on failure.

    Checkpoint file format (JSON):
    {
        "version": 1,
        "completed_loci": ["sample.bam::locus.bed", ...],
        "completed_stages": ["mapping_stats", "genome_mapping", ...],
        "metadata": {...}
    }
    """

    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = checkpoint_path
        self._completed_loci: Set[str] = set()
        self._completed_stages: Set[str] = set()
        self._metadata: Dict = {}
        self._load()

    def _load(self):
        """Load checkpoint from disk if it exists."""
        if not os.path.isfile(self.checkpoint_path):
            return
        try:
            with open(self.checkpoint_path, "r") as f:
                data = json.load(f)
            self._completed_loci = set(data.get("completed_loci", []))
            self._completed_stages = set(data.get("completed_stages", []))
            self._metadata = data.get("metadata", {})
        except (json.JSONDecodeError, OSError):
            # Corrupt checkpoint — start fresh
            self._completed_loci = set()
            self._completed_stages = set()
            self._metadata = {}

    def _save(self):
        """Persist checkpoint to disk."""
        data = {
            "version": 1,
            "completed_loci": sorted(self._completed_loci),
            "completed_stages": sorted(self._completed_stages),
            "metadata": self._metadata,
        }
        os.makedirs(os.path.dirname(self.checkpoint_path) or ".", exist_ok=True)
        tmp_path = self.checkpoint_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.checkpoint_path)

    @staticmethod
    def locus_key(bam_path: str, bed_path: str) -> str:
        """Create a unique key for a bam+bed combination."""
        return f"{os.path.basename(bam_path)}::{os.path.basename(bed_path)}"

    def is_locus_complete(self, bam_path: str, bed_path: str) -> bool:
        """Check if a locus has already been processed."""
        return self.locus_key(bam_path, bed_path) in self._completed_loci

    def mark_locus_complete(self, bam_path: str, bed_path: str):
        """Mark a locus as completed and save checkpoint."""
        self._completed_loci.add(self.locus_key(bam_path, bed_path))
        self._save()

    def is_stage_complete(self, stage_name: str) -> bool:
        """Check if a pipeline stage has been completed."""
        return stage_name in self._completed_stages

    def mark_stage_complete(self, stage_name: str):
        """Mark a pipeline stage as completed and save checkpoint."""
        self._completed_stages.add(stage_name)
        self._save()

    def set_metadata(self, key: str, value):
        """Store arbitrary metadata in the checkpoint."""
        self._metadata[key] = value
        self._save()

    def get_metadata(self, key: str, default=None):
        """Retrieve metadata from the checkpoint."""
        return self._metadata.get(key, default)

    def get_remaining_loci(self, all_jobs: List[tuple]) -> List[tuple]:
        """Filter job list to only include incomplete loci.

        Args:
            all_jobs: list of (bam_path, bed_path, ...) tuples
        Returns:
            list of jobs not yet completed.
        """
        return [job for job in all_jobs if not self.is_locus_complete(job[0], job[1])]

    @property
    def completed_loci_count(self) -> int:
        return len(self._completed_loci)

    def clear(self):
        """Remove checkpoint file and reset state."""
        self._completed_loci = set()
        self._completed_stages = set()
        self._metadata = {}
        if os.path.isfile(self.checkpoint_path):
            os.remove(self.checkpoint_path)
