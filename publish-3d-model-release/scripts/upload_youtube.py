#!/usr/bin/env python3
"""Compatibility entrypoint for the separate uv-managed publish-youtube skill."""

import subprocess
import sys
from pathlib import Path

from publisher_support import child_environment

if __name__ == "__main__":
    skill = Path(__file__).resolve().parents[2] / "publish-youtube"
    raise SystemExit(
        subprocess.call(
            [
                "uv",
                "run",
                "--locked",
                "--project",
                str(skill),
                str(skill / "scripts" / "upload_youtube.py"),
                *sys.argv[1:],
            ],
            env=child_environment(),
        )
    )
