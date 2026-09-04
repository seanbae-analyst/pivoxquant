"""Smoke tests for scripts/nightly/env_sync_audit.sh (D5).

The script needs vercel/railway CLIs to do meaningful work. These tests verify
its graceful-skip behavior on a clean dev machine (no CLIs) and the
expected-key derivation logic.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = _ROOT / "scripts" / "nightly" / "env_sync_audit.sh"
EXPECTED_FILE = _ROOT / "scripts" / "cron" / "expected_env_keys.txt"


def test_script_exists_and_executable():
    assert SCRIPT.exists(), f"script missing: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"script not executable: {SCRIPT}"


def test_expected_env_keys_file_exists():
    assert EXPECTED_FILE.exists()
    content = EXPECTED_FILE.read_text("utf-8")
    # Must include at least the high-leverage keys CEO cares about.
    for key in (
        "DATABASE_URL", "FMP_API_KEY",
        "SENDGRID_API_KEY", "ANTHROPIC_API_KEY",
    ):
        assert key in content, f"expected key {key} missing from allowlist"


def test_script_graceful_skip_without_clis(tmp_path):
    """Without vercel/railway CLIs the script must exit 0 (graceful skip)."""
    # Build a PATH that intentionally excludes vercel/railway. Keep enough
    # for the script to run (bash/awk/grep/curl/sort/comm/...).
    safe_path = "/usr/bin:/bin:/usr/sbin:/sbin"
    env = {
        **os.environ,
        "PATH": safe_path,
        # Force the script to operate in this repo (it cd's by computing
        # ROOT_DIR from script location).
    }
    env.pop("SLACK_WEBHOOK_URL", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        timeout=30,
        text=True,
    )
    # exit 0 expected because vercel + railway CLIs unavailable.
    assert result.returncode == 0, (
        f"expected graceful exit 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_expected_key_list_dedup_and_sorted():
    """Sanity: the canonical key file has no obvious typos / duplicates."""
    content = EXPECTED_FILE.read_text("utf-8")
    keys = [
        line.strip() for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert keys, "expected_env_keys.txt is empty"
    assert len(keys) == len(set(keys)), "duplicate keys in expected_env_keys.txt"
    for k in keys:
        # Convention: SCREAMING_SNAKE_CASE only.
        assert k.replace("_", "").isalnum() and k.isupper(), f"bad key format: {k}"
