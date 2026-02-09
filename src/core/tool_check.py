"""Pre-flight checks for external tool availability (#5)."""

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

REQUIRED_TOOLS = {
    "samtools": {"flag": "--version", "description": "SAM/BAM file manipulation"},
    "bedtools": {"flag": "--version", "description": "BED file operations"},
    "minimap2": {"flag": "--version", "description": "Read alignment"},
}

OPTIONAL_TOOLS = {
    "xatlas": {"flag": "--help", "description": "SNV calling (optional)"},
    "dorado": {"flag": "--version", "description": "Basecalling (POD5 input)"},
    "Rscript": {"flag": "--version", "description": "Plot generation (optional)"},
}


@dataclass
class ToolCheckResult:
    """Result of a pre-flight tool availability check."""

    available: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    optional_missing: List[str] = field(default_factory=list)

    @property
    def all_required_available(self) -> bool:
        return len(self.missing) == 0


def check_tool(name: str, version_flag: str = "--version") -> Optional[str]:
    """Check if a tool is available and return its version string."""
    path = shutil.which(name)
    if path is None:
        return None
    try:
        result = subprocess.run(
            [name, version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip() or result.stderr.strip()
        # Return first line of version output
        return output.split("\n")[0] if output else f"found at {path}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return f"found at {path}"


def check_tools_config(tools_config: Dict[str, str]) -> ToolCheckResult:
    """Check availability of tools specified in the tools config.

    Uses paths from config if provided, falls back to PATH lookup.
    """
    result = ToolCheckResult()

    for tool_key, info in REQUIRED_TOOLS.items():
        config_key = tool_key.upper()
        if config_key == "MINIMAP2":
            config_key = "MINIMAP"
        tool_path = tools_config.get(config_key, tool_key)
        version = check_tool(tool_path, info["flag"])
        if version:
            result.available[tool_key] = version
        else:
            result.missing.append(tool_key)

    for tool_key, info in OPTIONAL_TOOLS.items():
        version = check_tool(tool_key, info["flag"])
        if version:
            result.available[tool_key] = version
        else:
            result.optional_missing.append(tool_key)

    return result


def run_preflight_check(
    tools_config: Dict[str, str],
    log: Callable[[str], None] = print,
) -> ToolCheckResult:
    """Run pre-flight checks and log results.

    Raises RuntimeError if required tools are missing.
    """
    log("--- Pre-flight Tool Check ---")

    result = check_tools_config(tools_config)

    for tool, version in result.available.items():
        log(f"  [OK] {tool}: {version}")

    for tool in result.optional_missing:
        log(f"  [SKIP] {tool}: not found (optional)")

    for tool in result.missing:
        log(f"  [MISSING] {tool}: NOT FOUND")

    if not result.all_required_available:
        missing_str = ", ".join(result.missing)
        log(f"\n[ERROR] Required tools missing: {missing_str}")
        log("Please install missing tools and ensure they are on your PATH.")
        raise RuntimeError(f"Required tools missing: {missing_str}")

    log("--- All required tools available ---")
    return result
