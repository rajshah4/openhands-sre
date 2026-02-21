from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openhands_driver.runtime_env import ensure_real_call_requirements, load_project_env, runtime_env_status


def run_python_step(title: str, args: list[str]) -> tuple[str, int]:
    print(f"\n{= * 80}")
    print(title)
    print(f"$ {