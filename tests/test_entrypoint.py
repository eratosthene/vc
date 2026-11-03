"""The Docker entrypoint's checks, run with a stand-in for `flask`."""

import os
import subprocess
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parent.parent / "docker" / "docker-entrypoint.sh"


def run_entrypoint(tmp_path, config_exists):
    config = tmp_path / "config.py"
    if config_exists:
        config.write_text("")
    # A fake `flask` that records what it was asked, so no database is needed.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    flask = bin_dir / "flask"
    flask.write_text(f'#!/bin/sh\necho "flask $*" >> "{tmp_path}/calls"\n')
    flask.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "VC_CONFIG_FILE": str(config),
    }
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "echo", "started"],
        env=env,
        capture_output=True,
        text=True,
    )
    calls = tmp_path / "calls"
    return result, calls.read_text() if calls.exists() else ""


def test_fails_without_a_mounted_config(tmp_path):
    result, calls = run_entrypoint(tmp_path, config_exists=False)
    assert result.returncode == 1
    assert "mount one" in result.stderr
    assert calls == ""  # it never got as far as the database


def test_sets_up_the_database_then_runs_the_command(tmp_path):
    result, calls = run_entrypoint(tmp_path, config_exists=True)
    assert result.returncode == 0
    assert calls == "flask setup-db\n"
    assert result.stdout == "started\n"
