"""Tests for src.pipeline.workflow_plan module."""

import os

from src.core.file_detector import FileType
from src.pipeline.workflow_plan import WorkflowPlan, WorkflowStep, build_workflow_plan


class TestWorkflowStep:
    def test_basic_creation(self):
        step = WorkflowStep(name="test", description="A test step")
        assert step.name == "test"
        assert step.description == "A test step"
        assert step.params == {}

    def test_creation_with_params(self):
        step = WorkflowStep(
            name="analysis",
            description="Run analysis",
            params={"threads": 8, "ref": "/path/to/ref"},
        )
        assert step.params["threads"] == 8
        assert step.params["ref"] == "/path/to/ref"


class TestWorkflowPlan:
    def test_add_step(self):
        plan = WorkflowPlan()
        plan.add_step("basecalling", "Run basecaller", model="fast")
        assert len(plan.steps) == 1
        assert plan.steps[0].name == "basecalling"
        assert plan.steps[0].description == "Run basecaller"
        assert plan.steps[0].params == {"model": "fast"}

    def test_add_multiple_steps(self):
        plan = WorkflowPlan()
        plan.add_step("step1", "First step")
        plan.add_step("step2", "Second step")
        plan.add_step("step3", "Third step")
        assert len(plan.steps) == 3

    def test_step_names_property(self):
        plan = WorkflowPlan()
        plan.add_step("basecalling", "Run basecaller")
        plan.add_step("demultiplexing", "Demux reads")
        plan.add_step("analysis", "Run analysis")
        assert plan.step_names == ["basecalling", "demultiplexing", "analysis"]

    def test_step_names_empty(self):
        plan = WorkflowPlan()
        assert plan.step_names == []

    def test_len(self):
        plan = WorkflowPlan()
        assert len(plan) == 0
        plan.add_step("step1", "desc1")
        assert len(plan) == 1
        plan.add_step("step2", "desc2")
        assert len(plan) == 2

    def test_default_fields(self):
        plan = WorkflowPlan()
        assert plan.steps == []
        assert plan.exp_output_dir == ""
        assert plan.input_for_analysis == ""

    def test_add_step_preserves_order(self):
        plan = WorkflowPlan()
        names = ["alpha", "beta", "gamma", "delta"]
        for n in names:
            plan.add_step(n, f"Description of {n}")
        assert plan.step_names == names

    def test_add_step_with_no_extra_params(self):
        plan = WorkflowPlan()
        plan.add_step("simple", "A simple step")
        assert plan.steps[0].params == {}

    def test_add_step_with_many_params(self):
        plan = WorkflowPlan()
        plan.add_step(
            "complex",
            "A step with many params",
            input_dir="/data/in",
            output_dir="/data/out",
            threads=16,
            ref_genome="/ref/hg38.fa",
            min_len=100,
        )
        step = plan.steps[0]
        assert step.params["input_dir"] == "/data/in"
        assert step.params["threads"] == 16
        assert step.params["min_len"] == 100


class TestBuildWorkflowPlan:
    def _base_params(self, **overrides):
        """Create a base parameter dict with sensible defaults."""
        params = {
            "output_dir": "/data/output",
            "exp_name": "experiment1",
            "input_path": "/data/input/reads",
            "file_type": FileType.POD5,
            "needs_prepping": True,
            "model_path": "/models/fast",
            "demux_kit": "SQK-NBD114-24",
            "ref_genome": "/ref/hg38.fa",
            "input_type": "bam",
            "min_dorado_q": 10,
            "min_mean_q": 7,
            "min_len": 50,
            "min_acc": 0.8,
            "num_threads": 16,
        }
        params.update(overrides)
        return params

    def test_pod5_has_four_steps(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 4
        assert plan.step_names == [
            "basecalling",
            "demultiplexing",
            "prepping",
            "analysis",
        ]

    def test_pod5_basecalling_step_params(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        bc_step = plan.steps[0]
        assert bc_step.name == "basecalling"
        assert bc_step.params["model_path"] == "/models/fast"
        assert bc_step.params["input_path"] == "/data/input/reads"

    def test_pod5_demux_step_params(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        demux_step = plan.steps[1]
        assert demux_step.name == "demultiplexing"
        assert demux_step.params["demux_kit"] == "SQK-NBD114-24"

    def test_pod5_prepping_step_receives_demux_output(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        demux_step = plan.steps[1]
        prep_step = plan.steps[2]
        assert prep_step.params["input_dir"] == demux_step.params["output_dir"]

    def test_pod5_analysis_step_receives_prepped_output(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        prep_step = plan.steps[2]
        analysis_step = plan.steps[3]
        assert analysis_step.params["input_dir"] == prep_step.params["output_dir"]

    def test_bam_with_prepping_has_two_steps(self):
        params = self._base_params(
            file_type=FileType.BAM_UNALIGNED,
            needs_prepping=True,
        )
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 2
        assert plan.step_names == ["prepping", "analysis"]

    def test_bam_without_prepping_has_one_step(self):
        params = self._base_params(
            file_type=FileType.BAM_ALIGNED,
            needs_prepping=False,
        )
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 1
        assert plan.step_names == ["analysis"]

    def test_bam_without_prepping_analysis_uses_input_path(self):
        params = self._base_params(
            file_type=FileType.BAM_ALIGNED,
            needs_prepping=False,
            input_path="/data/aligned_bams",
        )
        plan = build_workflow_plan(params, "/project")
        analysis_step = plan.steps[0]
        assert analysis_step.params["input_dir"] == "/data/aligned_bams"

    def test_fastq_with_prepping(self):
        params = self._base_params(
            file_type=FileType.FASTQ,
            needs_prepping=True,
        )
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 2
        assert plan.step_names == ["prepping", "analysis"]

    def test_fastq_without_prepping(self):
        params = self._base_params(
            file_type=FileType.FASTQ,
            needs_prepping=False,
        )
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 1
        assert plan.step_names == ["analysis"]

    def test_exp_output_dir_set_correctly(self):
        params = self._base_params(
            output_dir="/data/output",
            exp_name="myexp",
        )
        plan = build_workflow_plan(params, "/project")
        expected = os.path.join("/data/output", "myexp")
        assert plan.exp_output_dir == expected

    def test_input_for_analysis_with_prepping(self):
        params = self._base_params(
            file_type=FileType.BAM_UNALIGNED,
            needs_prepping=True,
        )
        plan = build_workflow_plan(params, "/project")
        # input_for_analysis should point to prepped directory
        assert "3_prepped" in plan.input_for_analysis

    def test_input_for_analysis_without_prepping(self):
        params = self._base_params(
            file_type=FileType.BAM_ALIGNED,
            needs_prepping=False,
            input_path="/data/aligned",
        )
        plan = build_workflow_plan(params, "/project")
        assert plan.input_for_analysis == "/data/aligned"

    def test_input_for_analysis_pod5(self):
        params = self._base_params(file_type=FileType.POD5)
        plan = build_workflow_plan(params, "/project")
        assert "3_prepped" in plan.input_for_analysis

    def test_analysis_step_always_present(self):
        for ft in [
            FileType.POD5,
            FileType.BAM_ALIGNED,
            FileType.BAM_UNALIGNED,
            FileType.FASTQ,
            FileType.UNKNOWN,
        ]:
            params = self._base_params(file_type=ft, needs_prepping=False)
            plan = build_workflow_plan(params, "/project")
            assert "analysis" in plan.step_names

    def test_analysis_receives_project_dir(self):
        params = self._base_params(
            file_type=FileType.BAM_ALIGNED,
            needs_prepping=False,
        )
        plan = build_workflow_plan(params, "/my/project")
        analysis_step = [s for s in plan.steps if s.name == "analysis"][0]
        assert analysis_step.params["project_dir"] == "/my/project"

    def test_analysis_receives_config_params(self):
        params = self._base_params(
            file_type=FileType.BAM_ALIGNED,
            needs_prepping=False,
        )
        plan = build_workflow_plan(params, "/project")
        analysis_step = [s for s in plan.steps if s.name == "analysis"][0]
        assert analysis_step.params["config_params"] is params

    def test_prepping_step_params(self):
        params = self._base_params(
            file_type=FileType.FASTQ,
            needs_prepping=True,
            ref_genome="/ref/hg38.fa",
            min_len=100,
            num_threads=8,
        )
        plan = build_workflow_plan(params, "/project")
        prep_step = plan.steps[0]
        assert prep_step.params["ref_genome"] == "/ref/hg38.fa"
        assert prep_step.params["min_len"] == 100
        assert prep_step.params["num_threads"] == 8

    def test_unknown_file_type_with_prepping(self):
        params = self._base_params(
            file_type=FileType.UNKNOWN,
            needs_prepping=True,
        )
        plan = build_workflow_plan(params, "/project")
        assert len(plan) == 2
        assert plan.step_names == ["prepping", "analysis"]

    def test_output_directories_are_nested_under_exp_dir(self):
        params = self._base_params(
            file_type=FileType.POD5,
            output_dir="/out",
            exp_name="run1",
        )
        plan = build_workflow_plan(params, "/project")
        exp_dir = os.path.join("/out", "run1")
        for step in plan.steps:
            for key, val in step.params.items():
                if key.endswith("_dir") and key.startswith("output"):
                    assert val.startswith(
                        exp_dir
                    ), f"Step '{step.name}' output dir {val} not under {exp_dir}"
