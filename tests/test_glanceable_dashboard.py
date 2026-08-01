"""Run Qt UI checks in isolation from the native audio/Vosk test process."""

import os
import subprocess
import sys
from pathlib import Path


def test_glanceable_dashboard_behaviors_in_offscreen_qt_process():
    project_root = Path(__file__).resolve().parents[1]
    check_script = Path(__file__).with_name("verify_glanceable_dashboard.py")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(project_root), environment.get("PYTHONPATH", "")])
    )

    result = subprocess.run(
        [sys.executable, str(check_script)],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, (
        f"Qt dashboard checks failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
