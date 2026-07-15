"""Hatchling build hook (ADR-015): bundles the canvas frontend's prebuilt
static assets into the wheel, so `pip install agent-draft` alone gives a
working `agentdraft canvas` UI with no separate Node.js install for the end
user - only whoever builds/publishes the wheel needs Node, the same tradeoff
tools like Streamlit/Jupyter Lab/MLflow/Arize Phoenix make.

Runs `npm ci && npm run build` in canvas/ only if canvas/dist doesn't
already exist (a contributor who already built it once, or a CI cache
restore, skips the rebuild) and only if npm is actually on PATH - a
Python-only contributor without Node installed still gets a working
package, just without a bundled canvas UI (server.py degrades gracefully).
Set AGENTDRAFT_SKIP_CANVAS_BUILD=1 to skip unconditionally, e.g. in CI jobs
that only need the Python package installed, not a real canvas build.
"""

import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CanvasBuildHook(BuildHookInterface):  # type: ignore[misc]
    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        if os.environ.get("AGENTDRAFT_SKIP_CANVAS_BUILD"):
            return

        root = Path(self.root)
        canvas_dir = root / "canvas"
        dist_dir = canvas_dir / "dist"
        target_dir = root / "src" / "agentdraft" / "canvas_static"

        if not dist_dir.is_dir():
            npm = shutil.which("npm")
            if npm is None:
                return  # no Node available - agentdraft canvas degrades gracefully
            subprocess.run([npm, "ci"], cwd=canvas_dir, check=True)
            subprocess.run([npm, "run", "build"], cwd=canvas_dir, check=True)

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(dist_dir, target_dir)
