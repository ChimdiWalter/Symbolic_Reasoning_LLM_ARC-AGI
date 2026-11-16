"""Tests for render_results_tables.py.

The test file and the script live together in a results_tables/ subfolder of
the experiment folder.  BL_EXP overrides the experiment folder (needed when
running from the scratchpad).

Author: Chimdi Walter Ndubuisi
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EXP = os.environ.get("BL_EXP", os.path.dirname(_THIS_DIR))
OUTDIR = os.path.join(EXP, "full_out")
CHECK = os.path.join(EXP, "AFTER_RUN_CHECK.json")
EARLIER = os.path.join(EXP, "EARLIER_RESULT_CHECK.json")
TIME = os.path.join(EXP, "detached_job_record", "time.txt")
SCRIPT = os.path.join(_THIS_DIR, "render_results_tables.py")

# fail early if the experiment folder is wrong
if not os.path.isfile(os.path.join(OUTDIR, "SUMMARY.json")):
    raise RuntimeError(
        "experiment folder has no full_out/SUMMARY.json: %s"
        " (set BL_EXP to the experiment folder)" % EXP)

SECTION_TITLES = [
    "### Names used in these tables",
    "### Run",
    "### Primary comparison",
    "### Calibration",
    "### Secondary comparisons (descriptive, uncorrected)",
    "### The six searches",
    "### Stages and candidate sets",
    "### Order of sets",
    "### Sizes of found expressions",
    "### Costs",
    "### Every selected expression",
    "### Selected and wrong",
    "### Nine examples against 36",
    "### Comparison with the earlier study",
]


def run_script(out_path, outdir=OUTDIR, check=CHECK,
               earlier=EARLIER, time=TIME):
    return subprocess.run(
        [sys.executable, "-I", SCRIPT, outdir,
         "--check", check, "--earlier", earlier,
         "--time", time, "--out", str(out_path)],
        capture_output=True, text=True)


def test_runs_and_is_deterministic(tmp_path):
    """The script exits 0 on the real inputs, produces byte-identical
    output on a second run, and refuses to write to the same path."""
    out1 = tmp_path / "t1.md"
    r1 = run_script(out1)
    assert r1.returncode == 0, r1.stderr

    out2 = tmp_path / "t2.md"
    r2 = run_script(out2)
    assert r2.returncode == 0, r2.stderr
    assert out1.read_bytes() == out2.read_bytes(), (
        "output is not byte-identical across runs")

    r3 = run_script(out1)
    assert r3.returncode == 1
    assert "already exists" in r3.stderr


def test_all_section_titles(tmp_path):
    """The output contains every required section heading."""
    out = tmp_path / "t.md"
    r = run_script(out)
    assert r.returncode == 0, r.stderr
    text = out.read_text()
    for title in SECTION_TITLES:
        assert title in text, "missing section: %s" % title


def test_cross_check_on_reduced_copy(tmp_path):
    """A reduced copy with a changed count fails on cross-check,
    names the field, and writes nothing."""
    fake_out = tmp_path / "full_out"
    fake_targets = fake_out / "targets"
    fake_targets.mkdir(parents=True)

    with open(os.path.join(OUTDIR, "SUMMARY.json")) as f:
        summ = json.load(f)
    summ["counts"]["records"] = 3
    summ["counts"]["listed"] = 3
    summ["counts"]["excluded"] = 0
    summ["counts"]["incomplete"] = 0
    summ["counts"]["done"] = 999
    with open(str(fake_out / "SUMMARY.json"), "w") as f:
        json.dump(summ, f)

    shutil.copy2(os.path.join(OUTDIR, "RUN_COSTS.json"),
                 str(fake_out / "RUN_COSTS.json"))

    copied = 0
    src = os.path.join(OUTDIR, "targets")
    for fn in sorted(os.listdir(src)):
        if copied >= 3:
            break
        path = os.path.join(src, fn)
        with open(path) as f:
            rec = json.load(f)
        if rec.get("status") == "done":
            shutil.copy2(path, str(fake_targets / fn))
            copied += 1

    out = tmp_path / "result.md"
    r = run_script(out, outdir=str(fake_out))
    assert r.returncode == 1, (
        "expected exit 1 but got %d" % r.returncode)
    assert "counts.done" in r.stderr, (
        "expected 'counts.done' in stderr, got: %s" % r.stderr)
    assert not out.exists(), "output file should not have been created"


def test_time_file_missing_field(tmp_path):
    """A time file with a missing field makes the script exit 1
    with a message and write nothing."""
    bad_time = tmp_path / "bad_time.txt"
    bad_time.write_text(
        "\tUser time (seconds): 100.0\n"
        "\tSystem time (seconds): 10.0\n"
        "\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01:50\n"
        "\tMaximum resident set size (kbytes): 12345\n"
    )
    out = tmp_path / "result.md"
    r = run_script(out, time=str(bad_time))
    assert r.returncode == 1, (
        "expected exit 1 but got %d" % r.returncode)
    assert "exit" in r.stderr.lower(), (
        "expected 'exit' in stderr, got: %s" % r.stderr)
    assert not out.exists(), "output file should not have been created"
