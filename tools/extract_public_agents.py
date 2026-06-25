#!/usr/bin/env python3
"""Extract runnable public-kernel agents into baselines/.

The notebooks are kept as source artifacts, but the benchmark harness needs
plain Python files. This script makes that extraction reproducible.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

WRITEFILE_AGENTS = {
    "public_lb1224.py": ROOT / "public_kernels/lb1224/orbit-wars-lb-1224-fork.ipynb",
    "public_shuming_exp30.py": ROOT / "public_kernels/shuming_exp30/orbit-wars-exp30.ipynb",
    "public_ajay12.py": ROOT / "public_kernels/ajay12/oribt-war-12.ipynb",
    "public_evogen1093.py": ROOT / "public_kernels/evogen1093/evogen-v5-1093.ipynb",
}

RAHUL_AGENT = (
    "public_rahul1608.py",
    ROOT / "public_kernels/rahul1608/orbit-wars-advanced-agent-target-1608-6.ipynb",
)

LB1039_AGENT = (
    "public_lb1039.py",
    ROOT / "public_kernels/lb1039/orbit-wars-1039-2-lb-launch-safety-heuristic.ipynb",
)


def notebook_sources(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def strip_writefile(source: str) -> str:
    lines = source.splitlines()
    if lines and lines[0].lstrip().startswith("%%writefile"):
        lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


def extract_writefile(path: Path) -> str:
    for source in notebook_sources(path):
        if "%%writefile" in source and "def agent" in source:
            return strip_writefile(source)
    raise ValueError(f"No writefile agent cell found in {path}")


def extract_rahul(path: Path) -> str:
    for source in notebook_sources(path):
        if "submission_code" not in source:
            continue
        match = re.search(r'submission_code\s*=\s*"""(.*?)"""', source, re.S)
        if match and "def agent" in match.group(1):
            return match.group(1).strip() + "\n"
    raise ValueError(f"No submission_code agent string found in {path}")


def extract_lb1039(path: Path) -> str:
    sources = notebook_sources(path)
    code_cells = []
    for source in sources:
        if "sample_obs" in source:
            continue
        if "def agent" in source or code_cells:
            code_cells.append(source)
        elif any(marker in source for marker in ("import math", "def is_orbiting", "def fleet_speed", "class InterceptSolution", "NEUTRAL_OWNER")):
            code_cells.append(source)
    code = "\n\n".join(cell.strip() for cell in code_cells if cell.strip()) + "\n"
    if "def agent" not in code:
        raise ValueError(f"No lb1039 agent code found in {path}")
    return code


def with_header(filename: str, source_path: Path, code: str) -> str:
    rel_source = source_path.relative_to(ROOT)
    return (
        "# Auto-extracted by tools/extract_public_agents.py.\n"
        f"# Source notebook: {rel_source}\n\n"
        f"{code}"
    )


def main() -> None:
    out_dir = ROOT / "baselines"
    out_dir.mkdir(exist_ok=True)

    written: list[Path] = []
    for filename, source_path in WRITEFILE_AGENTS.items():
        code = extract_writefile(source_path)
        out_path = out_dir / filename
        out_path.write_text(with_header(filename, source_path, code))
        written.append(out_path)

    rahul_filename, rahul_path = RAHUL_AGENT
    rahul_code = extract_rahul(rahul_path)
    rahul_out = out_dir / rahul_filename
    rahul_out.write_text(with_header(rahul_filename, rahul_path, rahul_code))
    written.append(rahul_out)

    lb1039_filename, lb1039_path = LB1039_AGENT
    lb1039_code = extract_lb1039(lb1039_path)
    lb1039_out = out_dir / lb1039_filename
    lb1039_out.write_text(with_header(lb1039_filename, lb1039_path, lb1039_code))
    written.append(lb1039_out)

    for path in written:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
