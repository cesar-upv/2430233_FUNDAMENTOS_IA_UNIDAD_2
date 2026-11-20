import os
import subprocess
import sys
from pathlib import Path


def test_installed_mvp_runs_replays_and_captures_real_gui(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    screenshot = tmp_path / "mvp.png"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/smoke_gui.py",
            "--simulate",
            "--minimum",
            "--theme",
            "dark",
            "--screenshot",
            str(screenshot),
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "deterministic rerun, replay and inspection OK" in result.stdout
    assert not any(
        error in result.stderr
        for error in ("QThread: Destroyed", "QObject::", "Traceback")
    )
    for path in (
        screenshot,
        tmp_path / "mvp-analysis.png",
        tmp_path / "mvp-parameters.png",
    ):
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert path.stat().st_size > 10_000
