"""Tests of the runner (run_bl.py): its refusals and its one-launch path in fresh processes, on a temporary copy of
the experiment with a small roster made of development names; the pilot's rule on hand-made rows.
No operation outside the development names is searched. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

import bl_frozen
import presets_bl as P
import run_bl as R

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = [sys.executable, "-s", "-B"]
ENV = dict(os.environ, PYTHONHASHSEED="0")
# The small roster of the rehearsal is given by a wrapper in the COPY (never in the experiment's folder): it replaces
# the roster and the list of names labelled "development", optionally makes the address-space reading come out near
# the ceiling from its n-th call on, and then calls run_bl.main unchanged.
WRAPPER = '''import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guards_bl, presets_bl, run_bl
CONFIG = json.load(open(os.path.join(HERE, "rehearsal_config.json")))
ROSTER = CONFIG["roster"]
assert all(t in presets_bl.DEV_ROSTER for t in ROSTER), "the rehearsal uses development names only"
presets_bl.DEV_ROSTER = tuple(CONFIG["development"])       # the names still labelled development in the rehearsal
run_bl.roster_of = lambda name: list(ROSTER)
if CONFIG.get("near_ceiling_from_reading"):
    real, calls = guards_bl.address_space_peak_kb, [0]
    def reading():
        calls[0] += 1
        if calls[0] >= CONFIG["near_ceiling_from_reading"]:
            return (presets_bl.MEMORY_CEILING_BYTES - presets_bl.ADDRESS_SPACE_MARGIN_BYTES) // 1024 + 1
        return real()
    guards_bl.address_space_peak_kb = reading
sys.exit(run_bl.main(sys.argv[1:]))
'''


def copy_exp(tmp_path, protocol=True, size_c=4, name="expcopy"):
    """A copy of what a freeze covers: the modules, the delta files, the census, README.md and the tests. The copy's
    presets get SIZE_C = size_c whatever the experiment's own presets say (None: not set, as before the pilot)."""
    d = tmp_path / name
    (d / "tests").mkdir(parents=True)
    for n in R.OWN_FILES + ("README.md",):
        shutil.copy(os.path.join(HERE, n), d / n)
    for n in sorted(os.listdir(os.path.join(HERE, "tests"))):
        if n.endswith(".py"):
            shutil.copy(os.path.join(HERE, "tests", n), d / "tests" / n)
    if protocol:
        (d / "PROTOCOL.md").write_text("test protocol\n")
    src = (d / "presets_bl.py").read_text()
    line = [x for x in src.splitlines() if x.startswith("SIZE_C = ")]
    assert len(line) == 1
    (d / "presets_bl.py").write_text(src.replace(line[0], "SIZE_C = %s" % size_c))
    (d / "rehearsal_main.py").write_text(WRAPPER)
    return d


def configure(exp, roster, development, near=None):
    (exp / "rehearsal_config.json").write_text(json.dumps(dict(roster=roster, development=development, near_ceiling_from_reading=near)))


def run(args, base=None, script="run_bl.py", env=None, timeout=900):
    return subprocess.run(PY + [os.path.join(str(base or HERE), script)] + args, env=env or ENV, capture_output=True, text=True,
                          cwd=tempfile.gettempdir(), timeout=timeout)


def text(r):
    return r.stderr + r.stdout


def code_hashes_of(exp):
    h = {os.path.relpath(str(exp / n), bl_frozen.ROOT): R.sha256_file(str(exp / n)) for n in R.OWN_FILES}
    h[os.path.relpath(bl_frozen.STAGE_A_FREEZE, bl_frozen.ROOT)] = R.sha256_file(bl_frozen.STAGE_A_FREEZE)
    return h


def decided(status="eligible"):
    return dict(decision=dict(status=status, reason_kind=None if status == "eligible" else "generator"), counts=dict())


# ---------------------------------------------------------------- in-process pieces
def test_receipt_exclusive_one_launch_only(tmp_path):
    p1 = R.ensure_receipt(str(tmp_path), "/tmp/out_a", "f" * 64, "e" * 64)
    assert os.path.exists(p1) and os.stat(p1).st_mode & 0o222 == 0
    body = json.load(open(p1))
    assert body["freeze_sha256"] == "f" * 64 and body["setup_record_sha256"] == "e" * 64 and body["outdir"].endswith("out_a")
    for other in ("/tmp/out_a", "/tmp/out_b"):                      # the same folder too: an interrupted run is never resumed
        with pytest.raises(SystemExit):
            R.ensure_receipt(str(tmp_path), other, "f" * 64)
    with pytest.raises(SystemExit):
        R.refuse_if_launched(str(tmp_path))
    R.refuse_if_launched(str(tmp_path / "nowhere"))


def test_the_freeze_list_names_every_module_and_no_environment_variable_moves_the_receipt():
    assert set(R.OWN_FILES) == {"bl_frozen.py", "guards_bl.py", "presets_bl.py", "blocks_c.py", "build_bl.py", "search_bl.py", "gen_bl.py",
                                "episode_bl.py", "summarize_bl.py", "run_bl.py", "search_bl.delta", "gen_bl.delta", "census_source.json",
                                "derive_n.py", "N_RECORD.json", "ticks_measure.json"}
    modules = sorted(n for n in os.listdir(HERE) if n.endswith("_bl.py") or n in ("blocks_c.py", "bl_frozen.py"))
    after = set(R.AFTER_RUN_FILES)                         # the checks after the run and the rehearsal: frozen, never imported by the run
    assert after == {"after_run_bl.py", "earlier_result_check.py", "rehearse_run_once_path_bl.py"} and not after & set(R.OWN_FILES)
    assert set(modules) - after <= set(R.OWN_FILES) and set(R.POLICY_FILES) <= set(R.OWN_FILES)
    covered = {os.path.basename(k) for k in R.file_hashes()}
    assert set(R.OWN_FILES) <= covered and after <= covered and "README.md" in covered and "FREEZE.json" in covered
    assert {n for n in os.listdir(os.path.join(HERE, "tests")) if n.endswith(".py")} <= covered
    src = open(os.path.join(HERE, "run_bl.py")).read()
    assert "environ.get(" not in src.replace('os.environ.get("PYTHONHASHSEED")', "") and "getenv" not in src
    pol = R.policy()
    assert pol["ARITY_RULE"] is True and pol["MAX_FN"] == 16000 and pol["ALLOWANCE"] == 60.0 and pol["MAX_BANK"] == 1500000
    assert pol["MAX_COMBINATIONS"] == 1_900_000 and pol["cpu_budget_s"] == 600.0                           # the budget counted in combinations is on
    assert set(pol["sha256"]) == {"presets_bl.py", "build_bl.py", "blocks_c.py", "search_bl.py", "gen_bl.py"}
    assert all(pol["sha256"][n] == R.sha256_file(os.path.join(HERE, n)) for n in pol["sha256"])


def row(stop_class, fit=False):
    return dict(stop_class=stop_class, fit=fit, incomplete=stop_class in ("hard_stop", "memory_failure", "address_space_near_ceiling", "infrastructure_failure"))


def rule(by_size, eligible=True):
    return R.pilot_rule({s: [row(*r) if isinstance(r, tuple) else row(r) for r in rows] for s, rows in by_size.items()}, eligible)


def test_the_numeric_rule_for_the_size_limit_of_c():
    done, cap, allowance, bank = "size_limit_completed", "size_limit_completed_function_cap", "allowance_used_up", "bank_cap_reached"
    found = ("found", True)
    assert rule({4: [done] * 5, 5: [done] * 5, 6: [done] * 5})["s"] == 6
    assert rule({4: [done] * 5, 5: [done] * 4 + [allowance], 6: [done] * 3 + [allowance] * 2})["s"] == 5          # 80 per cent exactly qualifies
    assert rule({4: [done] * 4, 5: [done] * 3 + [allowance], 6: [allowance] * 4})["s"] == 4                       # 75 per cent does not
    assert rule({4: [done] * 5, 5: [cap] * 4 + [bank], 6: [allowance] * 5})["s"] == 5                             # completed with the cap reached counts
    assert rule({4: [allowance] * 5, 5: [allowance] * 5, 6: [bank] * 5})["s"] == 4                                # none qualifies
    assert rule({4: [allowance] * 5, 5: [allowance] * 5, 6: [done] * 5})["s"] == 6                                # the largest that qualifies
    assert rule({4: [found] * 3, 5: [found] * 3, 6: [found] * 3})["s"] == 6                                       # no fruitless search: qualifies
    assert rule({4: [done] * 2, 5: [found, found, allowance], 6: [found] * 3})["s"] == 6
    assert rule({4: [done] * 5, 5: [done] * 4 + ["hard_stop"] * 2, 6: ["memory_failure"] * 6})["s"] == 4          # an infrastructure stop did not complete
    assert rule({4: [done] * 5, 5: [done] * 5, 6: [done] * 5}, eligible=False)["s"] == 4                          # no development name is eligible
    assert rule({})["s"] == 4 and rule({4: [], 5: [], 6: []})["s"] == 4
    r = rule({4: [done] * 5, 5: [done] * 4 + [allowance], 6: [found, done, allowance, allowance]})
    assert r["by_size"]["5"] == dict(searches=5, fits=0, fruitless=5, fruitless_that_completed_the_level=4, share=0.8, qualifies=True)
    assert r["by_size"]["6"]["share"] == pytest.approx(1 / 3) and r["by_size"]["6"]["fits"] == 1 and r["threshold"] == 0.8
    assert "not exhaustive" in r["note"] and P.PILOT_COMPLETION_SHARE == 0.8
    assert P.SIZE_C == 4                                             # set on 14 November from pilot_s.json by this rule


def test_the_pilots_table_keeps_the_two_kinds_of_completed_level_apart():
    rows = []
    for label, _, _ in R.PILOT_SEARCHES:
        for cls, fit in (("size_limit_completed", False), ("size_limit_completed_function_cap", False), ("allowance_used_up", False), ("found", True)):
            rows.append(dict(row(cls, fit), pilot_search=label, cpu_s=10.0 if cls != "found" else 1.0, bank=1000, function_valued_entries=4078,
                             function_cap_reached=cls.endswith("cap"), address_space_peak_kb=500000, resident_peak_kb=400000))
    table = R.pilot_table(rows)
    assert list(table) == ["C-36@4", "C-36@5", "C-36@6", "L4-36", "L5-36", "LC4-36"]
    for t in table.values():
        assert (t["searches"], t["fits"], t["level_completed_without_the_function_cap"], t["level_completed_with_the_function_cap_reached_not_exhaustive"],
                t["budget_used_up"], t["bank_cap_reached"], t["infrastructure_stop"]) == (4, 1, 1, 1, 1, 0, 0)
        assert t["cpu_s_median"] == 10.0 and t["cpu_s_largest"] == 10.0 and t["function_cap_reached"] == 1 and t["address_space_peak_kb_largest"] == 500000
    lines = R.table_lines(table)
    assert len(lines) == 8 and "done+cap" in lines[0] and "NOT an exhaustive search" in lines[-1]
    assert R.pilot_table([])["C-36@4"]["searches"] == 0


def test_the_calibration_set_of_a_freeze(tmp_path):
    controls = list(P.CONTROL_NAMES)
    sr = dict(targets={c: decided() for c in controls[:25]})
    sr["targets"].update({c: decided("excluded") for c in controls[25:]})
    manifest = {c: dict(tree=["L", "c_len", ["P", "x0"]], nodes=2 + (i % 4)) for i, c in enumerate(controls)}
    cs = R.calibration_set(sr, manifest, 4)
    assert cs["K"] == len(cs["names"]) == sum(1 for i in range(25) if 2 + (i % 4) <= 4) and cs["size_c"] == 4
    none = R.calibration_set(sr, None, 4)
    assert none["available"] is False and none["K"] is None and none["names"] is None and none["eligible_controls"] == controls[:25]
    import summarize_bl as SM
    assert SM.calibration_set(sr, manifest, 4) == cs


# ---------------------------------------------------------------- refusals, in fresh processes
def test_refusals_in_fresh_processes(tmp_path):
    exp = copy_exp(tmp_path, protocol=False, size_c=None)
    out = str(tmp_path / "out")
    sr = tmp_path / "setup.json"
    sr.write_text(json.dumps(dict(roster="all", targets={"color": decided()}, hashes=code_hashes_of(exp))))
    fz = tmp_path / "fz.json"
    r = run([out, "--roster", "all"], base=exp)
    assert r.returncode != 0 and "freeze" in text(r) and not os.path.exists(out)
    r = run([out, "--roster", "all", "--freeze", str(fz)], base=exp)
    assert r.returncode != 0 and "setup" in text(r) and not os.path.exists(out)                    # no setup record
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "SIZE_C is not set" in text(r) and not os.path.exists(out)        # the size limit of C is not fixed
    r = run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "SIZE_C is not set" in text(r) and not fz.exists()
    r = run([out, "--roster", "dev", "--targets", "rapply"], base=exp)
    assert r.returncode != 0 and "--dev-size-c" in text(r) and not os.path.exists(out)             # a development run needs it too
    r = run([out, "--roster", "dev", "--targets", "rapply", "--dev-size-c", "7"], base=exp)
    assert r.returncode != 0 and "must be one of" in text(r) and not os.path.exists(out)
    # ---- the size limit set in the copy's presets (as the author will do after the pilot)
    exp = copy_exp(tmp_path, protocol=False, size_c=4, name="expcopy4")
    sr.write_text(json.dumps(dict(roster="all", targets={"color": decided()}, hashes=code_hashes_of(exp))))
    r = run([out, "--roster", "dev", "--targets", "rapply", "--dev-size-c", "5"], base=exp)
    assert r.returncode != 0 and "cannot change it" in text(r) and not os.path.exists(out)
    r = run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp)                       # no PROTOCOL.md
    assert r.returncode != 0 and "PROTOCOL.md" in text(r) and not fz.exists()
    (exp / "PROTOCOL.md").write_text("test protocol\n")
    r = run(["--make-freeze", str(fz)], base=exp)                                                  # no setup record given
    assert r.returncode != 0 and "setup record" in text(r) and not fz.exists()
    r = run(["--make-freeze", str(fz), "--setup-record", str(tmp_path / "nope.json")], base=exp)
    assert r.returncode != 0 and not fz.exists()
    stale = tmp_path / "stale.json"                                                                # made by other code
    hashes = code_hashes_of(exp)
    stale.write_text(json.dumps(dict(roster="all", targets={"color": decided()}, hashes=dict(hashes, **{sorted(hashes)[0]: "0" * 64}))))
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "other code" in text(r) and not fz.exists()
    stale.write_text(json.dumps(dict(roster="all", targets={"color": decided()})))                 # no record of its code at all
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "other code" in text(r) and not fz.exists()
    stale.write_text(json.dumps(dict(roster="dev", targets={"color": decided()}, hashes=hashes)))  # not a pass over the full roster
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "full roster" in text(r) and not fz.exists()
    stale.write_text(json.dumps(dict(roster="all", targets={"color": decided(), "rot180": dict(decision=dict(status="incomplete"))}, hashes=hashes)))
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "neither eligible nor excluded" in text(r) and not fz.exists()
    stale.write_text("not json")
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "unreadable" in text(r) and not fz.exists()
    assert run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp).returncode == 0
    first = open(fz).read()
    r = run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp)                       # a freeze is written once
    assert r.returncode != 0 and "exists" in text(r) and open(fz).read() == first
    body = json.load(open(fz))
    names = [k.split("/")[-1] for k in body["files"]]
    for need in ("PROTOCOL.md", "README.md", "FREEZE.json", "conftest.py", "test_blocks_c.py", "test_build_bl.py", "test_copies.py",
                 "test_episode_bl.py", "test_summarize_bl.py", "test_run_bl.py") + R.OWN_FILES:
        assert need in names, need
    assert any(k.endswith("visible_failure_20261113/episode.py") for k in body["stage_a_files"]) and body["setup_record"]["name"] == "setup.json"
    assert any(k.endswith("core_operations_20261113/search.py") for k in body["stage_a_files"]) and any(k.endswith("arc-dsl/dsl.py") for k in body["stage_a_files"])
    assert body["witness_manifest_present"] is False and body["calibration"]["available"] is False and body["policy"]["SIZE_C"] == 4
    assert body["policy"]["ARITY_RULE"] is True and body["policy"]["MAX_FN"] == 16000
    # ---- a hash in the freeze that is wrong
    bad = tmp_path / "bad.json"
    for table in ("files", "stage_a_files"):
        b2 = json.loads(json.dumps(body))
        b2[table][sorted(b2[table])[0]] = "0" * 64
        bad.write_text(json.dumps(b2))
        r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
        assert r.returncode != 0 and "differs from the freeze" in text(r) and not os.path.exists(out)
    for tail in ("README.md", "PROTOCOL.md", "test_run_bl.py", "search_bl.delta", "census_source.json", "blocks_c.py", "FREEZE.json"):
        b2 = json.loads(json.dumps(body))
        b2["files"].pop([k for k in b2["files"] if k.endswith(tail)][0])
        bad.write_text(json.dumps(b2))
        r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
        assert r.returncode != 0 and "does not cover" in text(r), tail
    b2 = json.loads(json.dumps(body))
    b2["stage_a_files"].pop(sorted(b2["stage_a_files"])[0])
    bad.write_text(json.dumps(b2))
    r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "does not cover stage A's files" in text(r)
    bad.write_text("{}")
    r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "unreadable" in text(r)
    # ---- a changed setup record
    sr2 = tmp_path / "setup2.json"
    sr2.write_text(json.dumps(dict(roster="all", targets={"rot180": decided()}, hashes=hashes)))
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr2)], base=exp)
    assert r.returncode != 0 and "setup record differs" in text(r) and not os.path.exists(out)
    # ---- options of the development roster with the full roster
    for extra in (["--dev-size-c", "4"], ["--targets", "color"]):
        r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)] + extra, base=exp)
        assert r.returncode != 0 and "development roster only" in text(r)
    # ---- a changed file after the freeze; a witness manifest that appears after the freeze
    readme = (exp / "README.md").read_text()
    (exp / "README.md").write_text("changed after the freeze\n")
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in text(r) and not os.path.exists(out)
    (exp / "README.md").write_text(readme)
    (exp / P.WITNESS_MANIFEST).write_text("{}")
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "does not cover" in text(r) and P.WITNESS_MANIFEST in text(r)
    fz3 = tmp_path / "fz3.json"
    assert run(["--make-freeze", str(fz3), "--setup-record", str(sr)], base=exp).returncode == 0   # a freeze made with the manifest covers it
    b3 = json.load(open(fz3))
    assert b3["witness_manifest_present"] is True and any(k.endswith(P.WITNESS_MANIFEST) for k in b3["files"]) and b3["calibration"]["K"] == 0
    (exp / P.WITNESS_MANIFEST).write_text('{"size": {}}')
    r = run([out, "--roster", "all", "--freeze", str(fz3), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in text(r)
    os.remove(exp / P.WITNESS_MANIFEST)
    # ---- a valid freeze, but the output folder is not new or empty: refused before any receipt is written
    os.makedirs(out)
    open(os.path.join(out, "left_over"), "w").write("x")
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "new or empty" in text(r) and not (exp / "RECEIPT_ALL_ROSTER.json").exists()
    shutil.rmtree(out)
    # ---- a valid freeze, but a receipt of an all-roster run exists: refused for another output folder AND for the same one
    for earlier in (str(tmp_path / "first_out"), out):
        (exp / "RECEIPT_ALL_ROSTER.json").write_text(json.dumps(dict(outdir=earlier)))
        r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
        assert r.returncode != 0 and "receipt" in text(r) and "never resumed" in text(r) and not os.path.exists(out)
    os.makedirs(out)                                                 # the launched run's own folder, with files in it: the same refusal
    open(os.path.join(out, "left_over"), "w").write("x")
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "never resumed" in text(r) and os.listdir(out) == ["left_over"]
    shutil.rmtree(out)
    # ---- no hash seed; targets outside the roster; a setup record that does not exist; outputs that exist
    r = run([out, "--roster", "dev"], base=exp, env={k: v for k, v in ENV.items() if k != "PYTHONHASHSEED"})
    assert r.returncode != 0 and "PYTHONHASHSEED" in text(r)
    r = run([out, "--roster", "dev", "--targets", "hline"], base=exp)
    assert r.returncode != 0 and "outside" in text(r) and not os.path.exists(os.path.join(out, "targets"))
    r = run([out + "_2", "--roster", "dev", "--targets", "rapply", "--setup-record", str(tmp_path / "nope.json")], base=exp)
    assert r.returncode != 0 and "does not exist" in text(r) and not os.path.exists(out + "_2")
    exists = tmp_path / "exists.json"
    exists.write_text("{}")
    for args in (["--setup-only", str(exists), "--roster", "dev"], ["--pilot-s", str(exists)]):
        r = run(args, base=exp)
        assert r.returncode != 0 and "exists" in text(r) and exists.read_text() == "{}"
    r = run(["--pilot-s", str(tmp_path / "p.json"), "--targets", "hline"], base=exp)
    assert r.returncode != 0 and "development names only" in text(r) and not (tmp_path / "p.json").exists()
    r = run(["--pilot-s", str(tmp_path / "p.json"), "--roster", "all"], base=exp)
    assert r.returncode != 0 and "development names only" in text(r)
    r = run(["--setup-only", str(tmp_path / "s.json")], base=exp)
    assert r.returncode != 0 and "--roster" in text(r)
    r = run(["--summarize", str(tmp_path / "nowhere")], base=exp)
    assert r.returncode != 0 and "not an output folder" in text(r)


# ---------------------------------------------------------------- the memory ceiling, read back in a fresh process for each mode
def test_the_memory_ceiling_is_set_in_a_fresh_process_for_every_mode(tmp_path):
    exp = copy_exp(tmp_path)
    configure(exp, ["rapply"], ["rapply"])                           # one development name that the setup step excludes: no search is run
    probe = "import os, sys, json, resource; sys.path.insert(0, %r); import run_bl; before = resource.getrlimit(resource.RLIMIT_AS)[0]; " \
            "c = run_bl.set_memory_ceiling(); print(json.dumps([before == resource.RLIM_INFINITY or before, c, resource.getrlimit(resource.RLIMIT_AS)[0]]))" % str(exp)
    r = subprocess.run(PY + ["-c", probe], env=ENV, capture_output=True, text=True, timeout=120)
    before, c, after = json.loads(r.stdout.strip().splitlines()[-1])
    assert after == c["soft_limit_bytes"] == P.MEMORY_CEILING_BYTES == 32 * 2 ** 30 and c["requested_bytes"] == after and c["margin_bytes"] == 2 ** 30
    want = dict(soft_limit_bytes=P.MEMORY_CEILING_BYTES, requested_bytes=P.MEMORY_CEILING_BYTES)
    # setup-only
    s = tmp_path / "setup.json"
    r = run(["--setup-only", str(s), "--roster", "dev"], base=exp, script="rehearsal_main.py")
    assert r.returncode == 0, text(r)
    rec = json.load(open(s))
    assert {k: rec["memory_ceiling"][k] for k in want} == want and rec["pools_setup_cpu_s"] > 0 and rec["counts"]["excluded"] == 1
    assert rec["targets"]["rapply"]["decision"]["reason_kind"] == "unsupported_values" and rec["development_only"] is True
    # the pilot
    p = tmp_path / "pilot.json"
    r = run(["--pilot-s", str(p), "--targets", "rapply"], base=exp, script="rehearsal_main.py")
    assert r.returncode == 0, text(r)
    pilot = json.load(open(p))
    assert {k: pilot["memory_ceiling"][k] for k in want} == want and pilot["eligible"] == [] and pilot["s_by_the_rule"] == 4
    assert pilot["rule"]["any_development_name_eligible"] is False and pilot["presets_SIZE_C_is_not_set_by_the_pilot"] == 4
    assert set(pilot["policy"]["sha256"]) == set(R.POLICY_FILES) and pilot["policy"]["MAX_FN"] == 16000 and pilot["policy"]["ARITY_RULE"] is True
    # a development run
    out = tmp_path / "dev"
    r = run([str(out), "--roster", "dev"], base=exp, script="rehearsal_main.py")
    assert r.returncode == 0, text(r)
    manifest = json.load(open(out / "MANIFEST.json"))
    assert {k: manifest["memory_ceiling"][k] for k in want} == want and manifest["size_c"] == 4 and manifest["development_only"] is True
    costs = json.load(open(out / "RUN_COSTS.json"))
    assert costs["pools_setup_cpu_s"] > 0 and costs["memory_ceiling"]["soft_limit_bytes"] == P.MEMORY_CEILING_BYTES
    assert json.load(open(out / "targets" / "rapply.json"))["status"] == "excluded" and (out / "SUMMARY.json").exists()
    # (the all-roster mode is read back in the one-launch test below)


# ---------------------------------------------------------------- the one-launch path, end to end
def seals_of(out, name):
    return [json.loads(x)["name"] for x in open(os.path.join(out, "journal", name + ".jsonl")) if '"event": "seal"' in x]


def test_the_one_launch_path_end_to_end_on_a_small_roster_of_development_names(tmp_path):
    exp = copy_exp(tmp_path)
    configure(exp, ["color", "rapply"], ["rapply"])                  # color counts as outside the development names in this rehearsal
    S, F, OUT = str(exp / "SETUP_RECORD_ALL.json"), str(exp / "FREEZE.json"), str(tmp_path / "full_out")
    main = "rehearsal_main.py"
    r = run([OUT, "--roster", "all"], base=exp, script=main)
    assert r.returncode != 0 and "freeze" in text(r)
    assert run(["--setup-only", S, "--roster", "all"], base=exp, script=main).returncode == 0
    r = run(["--setup-only", S, "--roster", "all"], base=exp, script=main)
    assert r.returncode != 0 and "exists" in text(r)
    sr = json.load(open(S))
    assert sr["roster"] == "all" and sr["targets"]["color"]["decision"]["status"] == "eligible" and sr["targets"]["color"]["opened_roles"] == ["pool_source"]
    assert sr["targets"]["rapply"]["decision"]["status"] == "excluded" and sr["counts"]["eligible"] == 1 and "final_panel" not in json.dumps(sr)
    assert sr["hashes"] == code_hashes_and_extras(exp)
    assert run(["--make-freeze", F, "--setup-record", S], base=exp, script=main).returncode == 0
    assert run(["--make-freeze", F, "--setup-record", S], base=exp, script=main).returncode != 0
    os.makedirs(OUT)
    open(os.path.join(OUT, "left_over"), "w").write("x")
    r = run([OUT, "--roster", "all", "--freeze", F, "--setup-record", S], base=exp, script=main)
    assert r.returncode != 0 and "new or empty" in text(r) and not (exp / "RECEIPT_ALL_ROSTER.json").exists()
    shutil.rmtree(OUT)
    r = run([OUT, "--roster", "all", "--freeze", F, "--setup-record", S], base=exp, script=main)        # THE LAUNCH
    assert r.returncode == 0 and "summary:" in text(r), text(r)
    rc = exp / "RECEIPT_ALL_ROSTER.json"
    assert rc.exists() and os.stat(rc).st_mode & 0o222 == 0 and json.load(open(rc))["freeze_sha256"] == R.sha256_file(F)
    assert json.load(open(rc))["setup_record_sha256"] == R.sha256_file(S)
    fz = json.load(open(F))
    assert not [k for table in ("files", "stage_a_files") for k, v in fz[table].items() if R.sha256_file(os.path.join(bl_frozen.ROOT, k)) != v]
    assert R.sha256_file(S) == fz["setup_record"]["sha256"]
    recs = {t: json.load(open(os.path.join(OUT, "targets", t + ".json"))) for t in ("color", "rapply")}
    assert recs["color"]["status"] == "done" and recs["rapply"]["status"] == "excluded" and recs["color"]["dev"] is False
    assert seals_of(OUT, "color") == ["setup_record", "first_fits_9", "first_fits_36", "selections", "final_set"]
    manifest = json.load(open(os.path.join(OUT, "MANIFEST.json")))
    assert manifest["roster"] == "all" and manifest["freeze_sha256"] == R.sha256_file(F) and manifest["size_c"] == 4 and manifest["size_c_from"] == "presets"
    assert manifest["memory_ceiling"]["soft_limit_bytes"] == P.MEMORY_CEILING_BYTES and manifest["development_only"] is False
    s = json.load(open(os.path.join(OUT, "SUMMARY.json")))
    prim, rcn = s["PRIMARY"], s["reconciliation_with_the_committed_setup_record"]
    assert prim["cohort_complete"] is True and prim["status"] == "not_interpretable" and prim["provisional"] is False      # no manifest of witnesses
    assert prim["not_interpretable_reasons"] and s["calibration"]["state"] == "unavailable"
    assert rcn["available"] and rcn["n_decisions_differ"] == 0 and rcn["n_counts_differ"] == 0 and rcn["n_compared"] == 2
    assert s["secondary_outside_the_development_names"]["short_stratum"]["paired_on_the_committed_cohort"]["N"] == 1
    assert s["costs_of_the_whole_job"]["setup_of_the_pools_cpu_s"] > 0
    before = {f: R.sha256_file(os.path.join(OUT, "targets", f)) for f in sorted(os.listdir(os.path.join(OUT, "targets")))}
    for folder in (OUT, OUT + "_2"):                                 # a second launch, into the same folder or another one
        r = run([folder, "--roster", "all", "--freeze", F, "--setup-record", S], base=exp, script=main)
        assert r.returncode != 0 and "never resumed" in text(r)
    assert before == {f: R.sha256_file(os.path.join(OUT, "targets", f)) for f in sorted(os.listdir(os.path.join(OUT, "targets")))}
    assert not os.path.exists(OUT + "_2")
    os.chmod(rc, 0o644)


def code_hashes_and_extras(exp):
    """What a setup record names as the code that made it: file_hashes() of the copy (modules, documents, tests, stage A's freeze)."""
    out = code_hashes_of(exp)
    for n in ["PROTOCOL.md", "README.md"] + ["tests/" + f for f in sorted(os.listdir(exp / "tests")) if f.endswith(".py")]:
        out[os.path.relpath(str(exp / n), bl_frozen.ROOT)] = R.sha256_file(str(exp / n))
    return out


def test_an_address_space_near_the_ceiling_ends_the_whole_process_and_the_summary_is_provisional(tmp_path):
    """One process runs the whole roster. When the address space comes near the ceiling in target k: there are
    records for targets 1 to k, no summary, and the exit status of presets EXIT_NEAR_CEILING; a later --summarize
    lists the committed targets without a record and the primary is provisional."""
    exp = copy_exp(tmp_path)
    roster = ["rapply", "color", "rot180"]                           # rot180: a longer source body, labelled outside development here
    configure(exp, roster, ["rapply"])
    S, F, OUT = str(exp / "SETUP_RECORD_ALL.json"), str(exp / "FREEZE.json"), str(tmp_path / "full_out")
    main = "rehearsal_main.py"
    assert run(["--setup-only", S, "--roster", "all"], base=exp, script=main).returncode == 0
    assert json.load(open(S))["targets"]["rot180"]["decision"]["status"] == "eligible"
    assert run(["--make-freeze", F, "--setup-record", S], base=exp, script=main).returncode == 0
    configure(exp, roster, ["rapply"], near=3)                       # rapply reads twice (and is excluded); the third reading is color's first
    r = run([OUT, "--roster", "all", "--freeze", F, "--setup-record", S], base=exp, script=main)
    assert r.returncode == P.EXIT_NEAR_CEILING == 86 and "near the ceiling" in text(r) and "runs nothing more" in text(r)
    assert sorted(os.listdir(os.path.join(OUT, "targets"))) == ["color.json", "rapply.json"]          # targets 1 to k, and nothing after
    color = json.load(open(os.path.join(OUT, "targets", "color.json")))
    assert color["status"] == "incomplete" and color["stop_class"] == "address_space_near_ceiling" and "searches" not in color
    assert json.load(open(os.path.join(OUT, "targets", "rapply.json")))["status"] == "excluded"
    assert not os.path.exists(os.path.join(OUT, "SUMMARY.json")) and not os.path.exists(os.path.join(OUT, "RUN_COSTS.json"))
    assert (exp / "RECEIPT_ALL_ROSTER.json").exists()                # the one launch happened: it is not started again
    r = run([OUT, "--roster", "all", "--freeze", F, "--setup-record", S], base=exp, script=main)
    assert r.returncode != 0 and "never resumed" in text(r)
    # the setup-only pass stops the same way and writes no record
    S2 = str(tmp_path / "setup_again.json")
    r = run(["--setup-only", S2, "--roster", "all"], base=exp, script=main)
    assert r.returncode == P.EXIT_NEAR_CEILING and not os.path.exists(S2) and "no setup record was written" in text(r)
    configure(exp, roster, ["rapply"])
    r = run(["--summarize", OUT, "--setup-record", S], base=exp, script=main)
    assert r.returncode == 0 and "provisional" in text(r), text(r)
    s = json.load(open(os.path.join(OUT, "SUMMARY.json")))
    prim = s["PRIMARY"]
    assert prim["status"] == "provisional" and prim["committed_eligible_targets_without_a_record"] == ["rot180"] and prim["N"] == 0
    assert any("have no record" in x for x in prim["provisional_reasons"]) and s["counts"]["incomplete"] == 1 and s["counts"]["not_yet_run"] == 1
    # color is of the short stratum: never in the primary's table, and a committed eligible target without a complete record all the same
    assert prim["other_committed_eligible_targets_without_a_complete_record"] == ["color"] and prim["other_committed_eligible_targets_without_a_record"] == []
    short = s["secondary_outside_the_development_names"]["short_stratum"]
    assert short["incomplete_infrastructure"] == {"color": color["reason"]} and short["paired_on_the_committed_cohort"]["without_a_complete_record"] == ["color"]
    os.chmod(exp / "RECEIPT_ALL_ROSTER.json", 0o644)


def test_a_malformed_combination_budget_refuses_before_anything_runs(tmp_path):
    exp = copy_exp(tmp_path)
    src = (exp / "presets_bl.py").read_text()
    assert src.count("\nMAX_COMBINATIONS = 1_900_000 ") == 1
    (exp / "presets_bl.py").write_text(src.replace("\nMAX_COMBINATIONS = 1_900_000 ", "\nMAX_COMBINATIONS = 0         "))
    setup, out = tmp_path / "setup.json", tmp_path / "o"
    for args in (["--setup-only", str(setup), "--roster", "dev"], [str(out), "--roster", "dev", "--targets", "rapply"],
                 ["--pilot-s", str(tmp_path / "p.json"), "--targets", "rapply"]):
        r = run(args, base=exp)
        assert r.returncode != 0 and "MAX_COMBINATIONS" in text(r) and "refusing" in text(r), text(r)
    assert not setup.exists() and not out.exists() and not (tmp_path / "p.json").exists()


def test_setup_only_in_a_fresh_process_refuses_an_existing_file(tmp_path):
    f = tmp_path / "exists.json"
    f.write_text("{}")
    r = run(["--setup-only", str(f), "--roster", "dev"])
    assert r.returncode != 0 and "exists" in text(r) and f.read_text() == "{}"


# ---------------------------------------------------------------- a memory-hungry search under a low ceiling, end to end
HUNGRY = '''import json, sys
sys.path.insert(0, %r)
import presets_bl as P
P.MEMORY_CEILING_BYTES = 3 * 2 ** 29                       # this test's low ceiling: 1.5 GiB (the margin stays 1 GiB)
import run_bl
ceiling = run_bl.set_memory_ceiling()
import dslx
import build_bl as BB
import episode_bl as E
import guards_bl as G


HELD = []


def blow(x):                                               # an invented operation that eats memory: 64 MiB more at every call
    HELD.append(bytearray(64 * 2 ** 20))
    return x


real = BB.build


def build_with_a_hungry_operation(block_set, hidden, examples, **kw):
    ops, leaves, Y, op_ns, leaf_ns, consts = real(block_set, hidden, examples, **kw)
    return [("blow", BB.operation_wrapper(blow, "blow", kw.get("counts")), (dslx.ACC["Integer"],), False)] + ops, leaves, Y, op_ns, leaf_ns, consts


BB.build = build_with_a_hungry_operation
ep = E.Episode.__new__(E.Episode)                          # an episode with invented examples: no library operation is the target
ep.X, ep.hidden, ep.n_params, ep.j = "invented", [], 1, None
ep.sealed, ep.done, ep.fit, ep.incomplete, ep.res = {"setup_record": "invented"}, set(), {}, [], dict(memory=[])
# the target's outputs are larger than any value a search keeps, so no expression can ever fit
ep.rec = E.Records([((i + 1,), tuple(range(4000 + i))) for i in range(66)], ep.sealed)
ep.rec.open("fit9")
stop = None
try:
    a = ep.run_search("hungry", "C", "fit9", 4)
except G.NearCeiling as e:
    stop = str(e)
    a = ep.res["searches"]["hungry"]
print(json.dumps(dict(ceiling=ceiling, stop=stop, calls_of_the_hungry_operation=len(HELD),
                      record={k: a.get(k) for k in ("stop", "stop_class", "incomplete", "fit", "expr", "coverage", "error", "cpu_s",
                                                    "stop_before_the_address_space_check", "address_space_peak_kb", "level_completed", "bank")})))
'''


def test_a_memory_hungry_search_under_a_low_ceiling_ends_as_an_infrastructure_stop(tmp_path):
    """End to end in a fresh process with a ceiling of 1.5 GiB on its address space: an invented search whose
    values eat memory. It must end as an infrastructure stop (a memory failure translated on its way, or an
    address space flagged near the ceiling) and never as a search that found something or found nothing."""
    script = tmp_path / "hungry.py"
    script.write_text(HUNGRY % HERE)
    r = subprocess.run(PY + [str(script)], env=ENV, capture_output=True, text=True, cwd=str(tmp_path), timeout=900)
    assert r.returncode == 0, text(r)[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ceiling"]["soft_limit_bytes"] == 3 * 2 ** 29 and out["ceiling"]["requested_bytes"] == 3 * 2 ** 29
    rec = out["record"]
    assert rec["stop_class"] in ("memory_failure", "address_space_near_ceiling") and rec["incomplete"] is True
    assert rec["fit"] is False and rec["expr"] is None and rec["coverage"] is None          # neither "found" nor a fruitless search that ended on its own
    assert rec["stop_class"] not in ("found", "size_limit_completed", "size_limit_completed_function_cap", "allowance_used_up", "bank_cap_reached")
    # the operation ran out of memory inside the enumerator: translated on its way (never skipped as a failed candidate), and
    # the address space, read after the search, is within the margin of the ceiling: the process must end
    assert 10 <= out["calls_of_the_hungry_operation"] <= 24 and rec["cpu_s"] < 30
    assert rec["stop_before_the_address_space_check"] == "memory_failure" and "memory failure in operation blow" in rec["error"]
    assert rec["stop_class"] == "address_space_near_ceiling" and out["stop"] is not None and "near the ceiling" in out["stop"]
    assert rec["address_space_peak_kb"] * 1024 >= 3 * 2 ** 29 - P.ADDRESS_SPACE_MARGIN_BYTES
