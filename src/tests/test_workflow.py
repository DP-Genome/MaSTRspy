"""Tests for src.core.workflow module."""

from src.core.file_detector import FileType
from src.core.workflow import WorkflowManager, WorkflowStage


class TestWorkflowStage:
    def test_enum_values(self):
        assert WorkflowStage.BASECALLING.value == "basecalling"
        assert WorkflowStage.DEMULTIPLEXING.value == "demultiplexing"
        assert WorkflowStage.PREPPING.value == "prepping"
        assert WorkflowStage.ANALYSIS.value == "analysis"


class TestWorkflowManager:
    def test_pod5_has_all_stages(self):
        wm = WorkflowManager(FileType.POD5)
        assert len(wm.stages) == 4
        assert WorkflowStage.BASECALLING in wm.stages
        assert WorkflowStage.DEMULTIPLEXING in wm.stages
        assert WorkflowStage.PREPPING in wm.stages
        assert WorkflowStage.ANALYSIS in wm.stages

    def test_fastq_has_prepping_and_analysis(self):
        wm = WorkflowManager(FileType.FASTQ)
        assert wm.stages == [WorkflowStage.PREPPING, WorkflowStage.ANALYSIS]

    def test_bam_unaligned_has_prepping_and_analysis(self):
        wm = WorkflowManager(FileType.BAM_UNALIGNED)
        assert wm.stages == [WorkflowStage.PREPPING, WorkflowStage.ANALYSIS]

    def test_bam_aligned_has_only_analysis(self):
        wm = WorkflowManager(FileType.BAM_ALIGNED)
        assert wm.stages == [WorkflowStage.ANALYSIS]

    def test_unknown_has_no_stages(self):
        wm = WorkflowManager(FileType.UNKNOWN)
        assert wm.stages == []

    def test_needs_basecalling_pod5(self):
        wm = WorkflowManager(FileType.POD5)
        assert wm.needs_basecalling() is True

    def test_needs_basecalling_fastq(self):
        wm = WorkflowManager(FileType.FASTQ)
        assert wm.needs_basecalling() is False

    def test_needs_prepping_fastq(self):
        wm = WorkflowManager(FileType.FASTQ)
        assert wm.needs_prepping() is True

    def test_needs_prepping_bam_aligned(self):
        wm = WorkflowManager(FileType.BAM_ALIGNED)
        assert wm.needs_prepping() is False

    def test_needs_prepping_bam_unaligned(self):
        wm = WorkflowManager(FileType.BAM_UNALIGNED)
        assert wm.needs_prepping() is True

    def test_pod5_stage_order(self):
        wm = WorkflowManager(FileType.POD5)
        assert wm.stages[0] == WorkflowStage.BASECALLING
        assert wm.stages[1] == WorkflowStage.DEMULTIPLEXING
        assert wm.stages[2] == WorkflowStage.PREPPING
        assert wm.stages[3] == WorkflowStage.ANALYSIS

    def test_file_type_stored(self):
        wm = WorkflowManager(FileType.FASTQ)
        assert wm.file_type == FileType.FASTQ
