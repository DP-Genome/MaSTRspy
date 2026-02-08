"""Pure-function workflow orchestration (#10).

Separates the workflow planning logic from execution so it can be
tested without a GUI or actual file I/O.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.file_detector import FileType


@dataclass
class WorkflowStep:
    """A single step in the workflow plan."""

    name: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPlan:
    """Complete workflow plan that can be inspected before execution."""

    steps: List[WorkflowStep] = field(default_factory=list)
    exp_output_dir: str = ""
    input_for_analysis: str = ""

    def add_step(self, name: str, description: str, **params):
        self.steps.append(WorkflowStep(name=name, description=description, params=params))

    @property
    def step_names(self) -> List[str]:
        return [s.name for s in self.steps]

    def __len__(self):
        return len(self.steps)


def build_workflow_plan(params: Dict[str, Any], project_dir: str) -> WorkflowPlan:
    """Build a workflow plan from the given parameters.

    This is a pure function that computes what steps need to run
    without executing anything. Makes the workflow testable.

    Args:
        params: user-configured parameters from the GUI
        project_dir: root project directory

    Returns:
        WorkflowPlan describing all steps to execute.
    """
    plan = WorkflowPlan()
    plan.exp_output_dir = os.path.join(params["output_dir"], params["exp_name"])

    file_type = params.get("file_type", FileType.UNKNOWN)
    input_path = params.get("input_path", "")

    # Track where input comes from as steps build
    current_input = input_path

    # Step 1: Basecalling (POD5 only)
    if file_type == FileType.POD5:
        basecalled_bam = os.path.join(plan.exp_output_dir, "1_basecalled.bam")
        plan.add_step(
            "basecalling",
            "Run dorado basecaller on POD5 input",
            model_path=params.get("model_path", ""),
            input_path=input_path,
            output_bam=basecalled_bam,
        )

        # Step 2: Demultiplexing (POD5 only)
        demux_dir = os.path.join(plan.exp_output_dir, "2_demuxed")
        plan.add_step(
            "demultiplexing",
            "Demultiplex basecalled reads",
            demux_kit=params.get("demux_kit", "None"),
            input_bam=basecalled_bam,
            output_dir=demux_dir,
        )
        current_input = demux_dir

    # Step 3: Prepping (if needed)
    if params.get("needs_prepping", True):
        prepped_dir = os.path.join(plan.exp_output_dir, "3_prepped")
        plan.add_step(
            "prepping",
            "Align and filter reads",
            input_dir=current_input,
            output_dir=prepped_dir,
            ref_genome=params.get("ref_genome", ""),
            exp_name=params.get("exp_name", ""),
            input_type=params.get("input_type", "bam"),
            min_dorado_q=params.get("min_dorado_q", 0),
            min_mean_q=params.get("min_mean_q", 0),
            min_len=params.get("min_len", 0),
            min_acc=params.get("min_acc", 0),
            num_threads=params.get("num_threads", 16),
        )
        current_input = prepped_dir

    # Step 4: Analysis (always)
    analysis_dir = os.path.join(plan.exp_output_dir, "4_analysis")
    plan.add_step(
        "analysis",
        "Run STR analysis pipeline",
        input_dir=current_input,
        output_dir=analysis_dir,
        config_params=params,
        project_dir=project_dir,
    )

    plan.input_for_analysis = current_input
    return plan
