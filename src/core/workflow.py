"""Workflow stage management for MaSTRspy."""

from enum import Enum
from typing import List

from src.core.file_detector import FileType


class WorkflowStage(Enum):
    BASECALLING = "basecalling"
    DEMULTIPLEXING = "demultiplexing"
    PREPPING = "prepping"
    ANALYSIS = "analysis"


class WorkflowManager:
    def __init__(self, file_type: FileType):
        self.file_type = file_type
        self.stages = self._build_stages()

    def _build_stages(self) -> List[WorkflowStage]:
        if self.file_type == FileType.POD5:
            return [
                WorkflowStage.BASECALLING,
                WorkflowStage.DEMULTIPLEXING,
                WorkflowStage.PREPPING,
                WorkflowStage.ANALYSIS,
            ]
        elif self.file_type in [FileType.FASTQ, FileType.BAM_UNALIGNED]:
            return [WorkflowStage.PREPPING, WorkflowStage.ANALYSIS]
        elif self.file_type == FileType.BAM_ALIGNED:
            return [WorkflowStage.ANALYSIS]
        return []

    def needs_basecalling(self) -> bool:
        return WorkflowStage.BASECALLING in self.stages

    def needs_prepping(self) -> bool:
        return WorkflowStage.PREPPING in self.stages
