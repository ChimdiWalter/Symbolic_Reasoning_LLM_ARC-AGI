"""BL1 runner: deterministic, CPU only. Author: Chimdi Walter Ndubuisi

    env PYTHONHASHSEED=0 python -s -B run_bl.py --setup-only <out.json> --roster dev|all
    env PYTHONHASHSEED=0 python -s -B run_bl.py --pilot-s <out.json> [--targets a,b]
    env PYTHONHASHSEED=0 python -s -B run_bl.py <outdir> --roster dev [--targets a,b] [--dev-size-c N] [--setup-record J]
    env PYTHONHASHSEED=0 python -s -B run_bl.py --make-freeze <path> --setup-record <J>       (writes a hash manifest; runs nothing)
    env PYTHONHASHSEED=0 python -s -B run_bl.py <outdir> --roster all --freeze <FREEZE.json> --setup-record <J>
    env PYTHONHASHSEED=0 python -s -B run_bl.py --summarize <outdir> [--setup-record J]       (reads records; runs nothing)

Every mode first sets the ceiling on the memory of the process (the address space, presets MEMORY_CEILING_BYTES)
and records the limit it reads back. When the largest address space of the process comes within the margin of
that ceiling (guards_bl.NearCeiling), the unit of work is recorded as an infrastructure stop and the process ends
with exit status presets EXIT_NEAR_CEILING; nothing after it is run in that process.

--roster dev needs no freeze and every output is labelled development only; the size limit of C comes from presets
SIZE_C or, while that is not set, from --dev-size-c (development runs only); a development run that is started
again skips the targets whose record exists. The pooled inputs (the generator over every library operation) are
set up once, before the first target, and their cost is its own line. --roster all REFUSES unless presets
SIZE_C is set, a freeze and the committed setup record are given, every hash in the freeze matches (this
experiment's modules and delta files, PROTOCOL.md, README.md, every tests/*.py, census_source.json, the witness
manifest if there is one, the setup record, and, through stage A's freeze, every file of stage A and of the
operations study), the output folder is new or empty, and no receipt of an all-roster run exists; it writes an
exclusive read-only receipt before the first target. THE ALL-ROSTER RUN IS LAUNCHED ONCE: a receipt that exists
refuses every later launch, whatever its output folder, so an interrupted run is not resumed, reset or replayed.
No environment variable or flag moves the receipt folder.
--setup-only runs ONLY the setup step (no search; no fit role and no final role is opened). --make-freeze refuses
a setup record that was made by other code than the files being frozen, or in which a target is neither eligible
nor excluded. --pilot-s runs, on every eligible development name, C-36 at each candidate size and L4-36, L5-36 and
LC4-36, and applies the protocol's numeric rule for the size limit s of C; it does not set SIZE_C.
"""
import argparse
import glob
import hashlib
import json
import os
import platform
import resource
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_frozen                 # noqa: E402  (hash check of the imported frozen modules happens here)
import guards_bl as G            # noqa: E402
import presets_bl as P           # noqa: E402

OWN_FILES = ("bl_frozen.py", "guards_bl.py", "presets_bl.py", "blocks_c.py", "build_bl.py", "search_bl.py", "gen_bl.py",
             "episode_bl.py", "summarize_bl.py", "run_bl.py", "search_bl.delta", "gen_bl.delta", P.CENSUS_FILE,
             "derive_n.py", "N_RECORD.json", "ticks_measure.json")
POLICY_FILES = ("presets_bl.py", "build_bl.py", "blocks_c.py", "search_bl.py", "gen_bl.py")
AFTER_RUN_FILES = ("after_run_bl.py", "earlier_result_check.py", "rehearse_run_once_path_bl.py")   # covered by a freeze; no part in the run
ROOT = bl_frozen.ROOT
LABEL = P.LABEL
PILOT_SEARCHES = tuple(("C-36@%d" % s, "C", s) for s in P.SIZE_C_CANDIDATES) + (
    ("L4-36", "L", P.SIZE_L4), ("L5-36", "L", P.SIZE_L5), ("LC4-36", "LC", P.SIZE_L4))


def sha256_file(p):
    return bl_frozen.sha256_file(p)


def set_memory_ceiling():
    """Set the ceiling on the address space of this process (never above a hard limit already in force) and return
    what is read back."""
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    want = P.MEMORY_CEILING_BYTES if hard == resource.RLIM_INFINITY else min(P.MEMORY_CEILING_BYTES, hard)
    resource.setrlimit(resource.RLIMIT_AS, (want, hard))
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if soft != want:
        raise SystemExit("refusing: the memory ceiling could not be set (asked %d, read back %d)" % (want, soft))
    return dict(requested_bytes=P.MEMORY_CEILING_BYTES, soft_limit_bytes=soft, hard_limit_bytes=None if hard == resource.RLIM_INFINITY else hard,
                margin_bytes=P.ADDRESS_SPACE_MARGIN_BYTES, what="RLIMIT_AS, the address space of this process")


def extra_files(require_protocol=False):
    """Documents, tests, the checks made after the run and the witness manifest covered by a freeze."""
    names = ["PROTOCOL.md", "README.md"] + list(AFTER_RUN_FILES)
    tdir = os.path.join(HERE, "tests")
    names += ["tests/" + f for f in sorted(os.listdir(tdir)) if f.endswith(".py")] if os.path.isdir(tdir) else []
    names.append(P.WITNESS_MANIFEST)
    out = []
    for n in names:
        p = os.path.join(HERE, n)
        if os.path.exists(p):
            out.append(p)
        elif n == "PROTOCOL.md" and require_protocol:
            raise SystemExit("refusing: PROTOCOL.md does not exist (a freeze covers it)")
    return out


def rel(p, base=None):
    return os.path.relpath(p, base or ROOT)


def file_hashes(require_protocol=False):
    """{path relative to the repository root: sha256}: this experiment's files, documents, tests and stage A's freeze file."""
    out = {}
    for n in OWN_FILES:
        out[rel(os.path.join(HERE, n))] = sha256_file(os.path.join(HERE, n))
    for p in extra_files(require_protocol):
        out[rel(p)] = sha256_file(p)
    out[rel(bl_frozen.STAGE_A_FREEZE)] = sha256_file(bl_frozen.STAGE_A_FREEZE)
    return out


def code_hashes():
    """{path: sha256} of the files that decide a setup record: this experiment's modules and stage A's freeze file."""
    out = {rel(os.path.join(HERE, n)): sha256_file(os.path.join(HERE, n)) for n in OWN_FILES}
    out[rel(bl_frozen.STAGE_A_FREEZE)] = sha256_file(bl_frozen.STAGE_A_FREEZE)
    return out


def policy():
    """The policy in force for a search: the presets that shape it and the hashes of the files that implement it."""
    return dict(ARITY_RULE=P.ARITY_RULE, MAX_FN=P.MAX_FN, ALLOWANCE=P.ALLOWANCE, MAX_BANK=P.MAX_BANK, SIZE_C=P.SIZE_C,
                TIME_SAFETY_LIMIT_S=P.TIME_SAFETY_LIMIT_S, cpu_budget_s=P.cpu_budget(), system_allocation=P.system_allocation(),
                MAX_COMBINATIONS=P.MAX_COMBINATIONS,
                SIZE_C_CANDIDATES=list(P.SIZE_C_CANDIDATES), MAX_ELEMENTS=P.MAX_ELEMENTS, MAX_NESTING=P.MAX_NESTING, MAX_INT_BITS=P.MAX_INT_BITS,
                MEMORY_CEILING_BYTES=P.MEMORY_CEILING_BYTES, ADDRESS_SPACE_MARGIN_BYTES=P.ADDRESS_SPACE_MARGIN_BYTES,
                sha256={n: sha256_file(os.path.join(HERE, n)) for n in POLICY_FILES})


def read_setup_record(path):
    try:
        with open(path) as f:
            sr = json.load(f)
        assert isinstance(sr["targets"], dict) and sr["targets"]
    except (OSError, ValueError, KeyError, AssertionError, TypeError):
        raise SystemExit("refusing: the setup record is unreadable")
    return sr


def calibration_set(setup_record, manifest, size_c):
    """The K controls of the calibration (protocol section 9), as the summary computes them: pinned controls that
    are eligible in the committed setup record and have a witness of at most size_c nodes. No outcome is read."""
    import summarize_bl as SM
    return SM.calibration_set(setup_record, manifest, size_c)


def make_freeze(path, setup_record):
    if os.path.lexists(path):
        raise SystemExit("refusing: %s exists (a freeze is written once)" % path)
    if not setup_record or not os.path.exists(setup_record):
        raise SystemExit("refusing: the setup record does not exist (a freeze covers it)")
    sr = read_setup_record(setup_record)
    if sr.get("roster") != "all":
        raise SystemExit("refusing: the setup record is unreadable or is not a setup-only pass over the full roster")
    made_by = sr.get("hashes") or {}
    stale = sorted(k for k, v in code_hashes().items() if made_by.get(k) != v)
    if stale:
        raise SystemExit("refusing: the setup record was made by other code than the files being frozen (%s); make it again"
                         % [os.path.basename(k) for k in stale])
    undecided = sorted(t for t, v in sr["targets"].items() if (v.get("decision") or {}).get("status") not in ("eligible", "excluded"))
    if undecided:
        raise SystemExit("refusing: the setup record has targets that are neither eligible nor excluded (%s)" % undecided[:6])
    if P.SIZE_C not in P.SIZE_C_CANDIDATES:
        raise SystemExit("refusing: presets SIZE_C is not set (a freeze fixes the size limit of C and the calibration set)")
    files = file_hashes(True)
    manifest = None
    mp = os.path.join(HERE, P.WITNESS_MANIFEST)
    if os.path.exists(mp):
        with open(mp) as f:
            manifest = json.load(f)
    body = dict(author="Chimdi Walter Ndubuisi", what="hash manifest of BL1 (operations from blocks below the library)", files=files,
                stage_a_files=bl_frozen.stage_a_files(), setup_record=dict(name=os.path.basename(setup_record), sha256=sha256_file(setup_record)),
                witness_manifest_present=manifest is not None, policy=policy(), calibration=calibration_set(sr, manifest, P.SIZE_C),
                python=platform.python_version(), env="PYTHONHASHSEED=0, python3 -s -B")
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True)
        f.write("\n")


def check_freeze(path, setup_record, base=None):
    """Return the sha256 of the freeze file, or raise SystemExit when a hash differs, a file is not covered, a
    witness manifest appeared after the freeze, or the setup record is not the committed one."""
    base = base or ROOT
    try:
        with open(path, "rb") as f:
            raw = f.read()
        body = json.loads(raw)
        files, sfiles, srec = body["files"], body["stage_a_files"], body["setup_record"]
        assert isinstance(files, dict) and isinstance(sfiles, dict) and isinstance(srec, dict)
    except (OSError, ValueError, KeyError, AssertionError, TypeError) as e:
        raise SystemExit("refusing: freeze file unreadable (%s)" % type(e).__name__)
    need = {rel(os.path.join(HERE, n), base) for n in OWN_FILES}
    need |= {rel(p, base) for p in extra_files(True)}
    need.add(rel(bl_frozen.STAGE_A_FREEZE, base))
    missing = sorted(need - set(files))
    if missing:
        raise SystemExit("refusing: freeze does not cover %s" % missing)
    live_a = bl_frozen.stage_a_files()
    missing = sorted(set(live_a) - set(sfiles))
    if missing:
        raise SystemExit("refusing: freeze does not cover stage A's files %s" % missing)
    for table in (files, sfiles):
        for r, want in sorted(table.items()):
            p = os.path.join(base, r)
            if not os.path.exists(p) or sha256_file(p) != want:
                raise SystemExit("refusing: %s differs from the freeze" % r)
    for r, want in live_a.items():
        if sfiles.get(r) != want:
            raise SystemExit("refusing: stage A's freeze lists a different hash for %s" % r)
    if not setup_record or not os.path.exists(setup_record) or sha256_file(setup_record) != srec.get("sha256"):
        raise SystemExit("refusing: the setup record differs from the freeze (or does not exist)")
    return hashlib.sha256(raw).hexdigest()


def refuse_if_launched(folder):
    """A receipt that already exists refuses, whatever its output folder: an interrupted run is not resumed, reset or replayed."""
    existing = sorted(glob.glob(os.path.join(folder, "RECEIPT_ALL_ROSTER*.json")))
    if existing:
        raise SystemExit("refusing: an all-roster run already has a receipt (%s); it is launched once and never resumed" % existing[0])


def ensure_receipt(folder, outdir, freeze_sha, setup_sha=None):
    """Exclusive read-only receipt of THE all-roster run, written before its first target."""
    refuse_if_launched(folder)
    p = os.path.join(folder, "RECEIPT_ALL_ROSTER.json")
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        raise SystemExit("refusing: receipt exists")
    with os.fdopen(fd, "w") as f:
        json.dump(dict(outdir=os.path.realpath(outdir), freeze_sha256=freeze_sha, setup_record_sha256=setup_sha, pid=os.getpid(),
                       time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), f, indent=1)
    return p


def roster_of(name):
    import episode_bl as E
    return list(P.DEV_ROSTER) if name == "dev" else E.roster_all()


def set_up_pools():
    """Build the pooled inputs (the generator over every library operation) before the first target, so that their
    cost is its own line and is not folded into the first target. Returns the processor seconds it took."""
    import episode_bl as E
    t = time.process_time()
    E.pools()
    return round(time.process_time() - t, 2)


def end_near_ceiling(e, where):
    print("STOP: %s (%s). The unit of work is an infrastructure stop; this process ends with exit status %d and runs nothing more."
          % (e, where, P.EXIT_NEAR_CEILING), flush=True)
    return P.EXIT_NEAR_CEILING


# ---------------------------------------------------------------- the setup-only pass
def do_setup_only(path, roster_name, ceiling=None):
    import episode_bl as E
    if os.path.exists(path):
        raise SystemExit("refusing: %s exists" % path)
    made_by = file_hashes()                                    # taken BEFORE the pass; the record names the code that made it
    pools_cpu_s = set_up_pools()
    roster = roster_of(roster_name)
    views = {}
    t0 = time.process_time()
    for i, X in enumerate(roster):
        try:
            v = E.setup_only(X)
        except G.NearCeiling as e:
            return end_near_ceiling(e, "setup of %s; no setup record was written" % X)
        except G.ResourceStop as e:
            v = dict(decision=dict(status="incomplete", reason_kind="memory_failure"), counts=dict(reason=str(e)), cpu_s=None, opened_roles=None)
        except MemoryError:
            v = dict(decision=dict(status="incomplete", reason_kind="memory_failure"), counts=dict(reason="MemoryError"), cpu_s=None, opened_roles=None)
        except Exception as e:                                   # noqa: BLE001  (infrastructure: the target is not decided)
            v = dict(decision=dict(status="incomplete", reason_kind="infrastructure_failure"),
                     counts=dict(reason="%s: %s" % (type(e).__name__, str(e)[:300])), cpu_s=None, opened_roles=None)
        views[X] = {k: v.get(k) for k in ("decision", "counts", "cpu_s", "opened_roles", "memory")}
        print("[%d/%d] %s %s %s" % (i + 1, len(roster), X, v["decision"]["status"], v["decision"].get("reason_kind") or ""), flush=True)
    if file_hashes() != made_by:
        raise SystemExit("refusing: a file of this experiment changed during the setup-only pass; nothing written")
    dec = {X: v["decision"] for X, v in views.items()}

    def count(pred):
        return sum(1 for X, d in dec.items() if pred(X, d))
    outside = lambda X: X not in P.DEV_ROSTER                    # noqa: E731
    by = {}
    for stratum in ("short", "longer"):
        names = [X for X in dec if P.stratum_of(X) == stratum and outside(X)]
        kinds = sorted({dec[X].get("reason_kind") for X in names if dec[X]["status"] == "excluded"})
        by[stratum] = dict(n=len(names), eligible=sum(dec[X]["status"] == "eligible" for X in names),
                           excluded_by_kind={k: sum(dec[X].get("reason_kind") == k and dec[X]["status"] == "excluded" for X in names) for k in kinds})
    body = dict(label=LABEL, what="setup-only pass: eligibility record (no search; no fit role and no final role is opened)", roster=roster_name,
                development_only=roster_name == "dev", targets=views, hashes=made_by, seq_tag=P.SEQ_TAG, policy=policy(), memory_ceiling=ceiling,
                python=platform.python_version(),
                counts=dict(n=len(views), eligible=count(lambda X, d: d["status"] == "eligible"), excluded=count(lambda X, d: d["status"] == "excluded"),
                            incomplete=count(lambda X, d: d["status"] not in ("eligible", "excluded")),
                            development_names=count(lambda X, d: not outside(X)),
                            development_names_eligible=count(lambda X, d: not outside(X) and d["status"] == "eligible"),
                            outside_development_by_stratum=by,
                            controls_eligible=count(lambda X, d: X in P.CONTROL_NAMES and d["status"] == "eligible")),
                cpu_s=round(time.process_time() - t0, 1), pools_setup_cpu_s=pools_cpu_s)
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    print("setup-only record written:", path, json.dumps(body["counts"], sort_keys=True))
    return 0


# ---------------------------------------------------------------- the pilot for the size limit s of C
def pilot_rule(rows_by_size, any_eligible):
    """The protocol's numeric rule. rows_by_size: {size: [search record]} for C-36. s is the largest candidate size
    for which at least PILOT_COMPLETION_SHARE of the searches without a fit ended by completing the level (with or
    without the function cap reached); a size with no fruitless search qualifies; if none qualifies, or no
    development name is eligible, s = 4."""
    reading = {}
    for size in P.SIZE_C_CANDIDATES:
        rows = rows_by_size.get(size, [])
        fruitless = [r for r in rows if not r["fit"]]
        completed = [r for r in fruitless if r["stop_class"] in ("size_limit_completed", "size_limit_completed_function_cap")]
        share = (len(completed) / len(fruitless)) if fruitless else None
        reading[str(size)] = dict(searches=len(rows), fits=len(rows) - len(fruitless), fruitless=len(fruitless),
                                  fruitless_that_completed_the_level=len(completed), share=share,
                                  qualifies=bool(rows) and (share is None or share >= P.PILOT_COMPLETION_SHARE))
    qualifying = [s for s in P.SIZE_C_CANDIDATES if reading[str(s)]["qualifies"]]
    s = max(qualifying) if (qualifying and any_eligible) else min(P.SIZE_C_CANDIDATES)
    return dict(s=s, by_size=reading, threshold=P.PILOT_COMPLETION_SHARE, any_development_name_eligible=any_eligible,
                note="completing a level with the function cap reached counts as completing it for this rule; it is a bounded "
                     "tuning policy and such a search is not exhaustive")


def pilot_table(rows):
    """One line of counts per kind of search of the pilot."""
    table = {}
    for label, _, _ in PILOT_SEARCHES:
        rs = [r for r in rows if r["pilot_search"] == label]
        cpu = [r["cpu_s"] for r in rs]
        entries = [r.get("function_valued_entries") for r in rs if r.get("function_valued_entries") is not None]
        table[label] = dict(
            searches=len(rs), fits=sum(r["fit"] for r in rs),
            level_completed_without_the_function_cap=sum(r["stop_class"] == "size_limit_completed" for r in rs),
            level_completed_with_the_function_cap_reached_not_exhaustive=sum(r["stop_class"] == "size_limit_completed_function_cap" for r in rs),
            budget_used_up=sum(r["stop_class"] in ("allowance_used_up", "combination_budget_used_up") for r in rs),
            bank_cap_reached=sum(r["stop_class"] == "bank_cap_reached" for r in rs),
            infrastructure_stop=sum(r["incomplete"] for r in rs),
            cpu_s_median=round(statistics.median(cpu), 2) if cpu else None, cpu_s_largest=round(max(cpu), 2) if cpu else None,
            cpu_s_sum=round(sum(cpu), 1), bank_largest=max([r["bank"] or 0 for r in rs], default=None),
            function_valued_entries_largest=max(entries, default=None),
            function_cap_reached=sum(bool(r.get("function_cap_reached")) for r in rs),
            address_space_peak_kb_largest=max([r["address_space_peak_kb"] or 0 for r in rs], default=None),
            resident_peak_kb_largest=max([r["resident_peak_kb"] or 0 for r in rs], default=None))
    return table


def table_lines(table):
    head = "%-8s %4s %4s %9s %9s %9s %5s %6s %8s %8s %9s %8s %11s %11s" % (
        "search", "n", "fit", "done", "done+cap", "budget", "bank", "infra", "cpu med", "cpu max", "bank max", "fn max", "VmPeak kB", "RSS kB")
    lines = [head]
    for label, t in table.items():
        lines.append("%-8s %4d %4d %9d %9d %9d %5d %6d %8s %8s %9s %8s %11s %11s" % (
            label, t["searches"], t["fits"], t["level_completed_without_the_function_cap"],
            t["level_completed_with_the_function_cap_reached_not_exhaustive"], t["budget_used_up"], t["bank_cap_reached"],
            t["infrastructure_stop"], t["cpu_s_median"], t["cpu_s_largest"], t["bank_largest"], t["function_valued_entries_largest"],
            t["address_space_peak_kb_largest"], t["resident_peak_kb_largest"]))
    lines.append("done: the level of the size limit was completed with no cap reached (the only exhaustive ending). done+cap: completed with "
                 "the cap on function-valued entries reached; that is NOT an exhaustive search.")
    return lines


def do_pilot(path, targets=None, ceiling=None):
    import episode_bl as E
    if os.path.exists(path):
        raise SystemExit("refusing: %s exists" % path)
    names = list(P.DEV_ROSTER)
    if targets:
        bad = [t for t in targets if t not in names]
        if bad:
            raise SystemExit("refusing: the pilot uses development names only (%s)" % bad)
        names = list(targets)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pol = policy()
    rows, setups = [], {}
    w0 = time.time()
    pools_cpu_s = set_up_pools()
    t0 = time.process_time()
    stop = None
    for i, X in enumerate(names):
        ep = E.Episode(X)
        try:
            excluded = ep.setup()
            setups[X] = ep.setup_view()
            if excluded is not None:
                print("[%d/%d] %s excluded (%s)" % (i + 1, len(names), X, ep.res.get("reason_kind")), flush=True)
                continue
            # the nine-example searches are not part of the pilot: the seal that the 36-example role needs is written as such
            ep.seal("first_fits_9", dict(pilot_for_s="the nine-example searches are not run by the pilot"))
            ep.rec.open("fit36")
            for label, block_set, size in PILOT_SEARCHES:
                a = ep.run_search(label, block_set, "fit36", size)
                rows.append(dict(a, target=X, pilot_search=label))
                print("[%d/%d] %s %-8s %-34s level %s bank %s cpu %.1f fn %s peak %s kB" % (
                    i + 1, len(names), X, label, a["stop_class"], a["level_completed"], a["bank"], a["cpu_s"],
                    a.get("function_valued_entries"), a["address_space_peak_kb"]), flush=True)
        except G.NearCeiling as e:
            stop = e
            setups.setdefault(X, dict(decision=dict(status="incomplete", reason_kind="address_space_near_ceiling")))
            break
        except G.ResourceStop as e:
            setups[X] = dict(decision=dict(status="incomplete", reason_kind="memory_failure"), counts=dict(reason=str(e)))
        except MemoryError:
            setups[X] = dict(decision=dict(status="incomplete", reason_kind="memory_failure"), counts=dict(reason="MemoryError"))
        except Exception as e:                                   # noqa: BLE001  (infrastructure: the name is not decided)
            setups[X] = dict(decision=dict(status="incomplete", reason_kind="infrastructure_failure"),
                             counts=dict(reason="%s: %s" % (type(e).__name__, str(e)[:300])))
    eligible = [X for X, v in setups.items() if v["decision"]["status"] == "eligible"]
    table = pilot_table(rows)
    by_size = {s: [r for r in rows if r["pilot_search"] == "C-36@%d" % s] for s in P.SIZE_C_CANDIDATES}
    rule = pilot_rule(by_size, bool(eligible))
    lines = table_lines(table)
    body = dict(author="Chimdi Walter Ndubuisi", label="development only: the pilot for the size limit s of C; never a result",
                what="C-36 at each candidate size, and L4-36, L5-36 and LC4-36, on every eligible development name (36 fit examples; "
                     "no final panel is opened); the protocol's numeric rule for s",
                names=names, eligible=eligible, setup=setups, policy=pol, memory_ceiling=ceiling, searches=rows, table=table, table_text=lines,
                rule=rule, s_by_the_rule=rule["s"], presets_SIZE_C_is_not_set_by_the_pilot=P.SIZE_C,
                ended_early=None if stop is None else str(stop), started=started, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                cpu_s=round(time.process_time() - t0, 1), pools_setup_cpu_s=pools_cpu_s, wall_s=round(time.time() - w0, 1),
                resident_peak_kb=G.resident_peak_kb(), address_space_peak_kb=G.address_space_peak_kb(), python=platform.python_version())
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    print("\n".join(lines))
    print("rule: %s" % json.dumps(rule["by_size"], sort_keys=True))
    print("s by the rule: %d (presets SIZE_C is not changed by the pilot)" % rule["s"])
    if stop is not None:
        return end_near_ceiling(stop, "the pilot; what was done is in %s" % path)
    return 0


# ---------------------------------------------------------------- command line
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--roster", choices=("dev", "all"))
    ap.add_argument("--targets")
    ap.add_argument("--freeze")
    ap.add_argument("--setup-record")
    ap.add_argument("--dev-size-c", type=int, help="development runs only: the size limit of C while presets SIZE_C is not set")
    ap.add_argument("--make-freeze")
    ap.add_argument("--setup-only")
    ap.add_argument("--pilot-s")
    ap.add_argument("--summarize")
    a = ap.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    ceiling = set_memory_ceiling()
    try:
        P.combination_budget()                                   # None (off) or a positive whole number: checked before anything runs
    except RuntimeError as e:
        raise SystemExit("refusing: %s" % e)
    if a.make_freeze:
        make_freeze(a.make_freeze, a.setup_record)
        return 0
    if a.summarize:
        import summarize_bl as SM
        if not os.path.isdir(a.summarize):
            raise SystemExit("refusing: %s is not an output folder" % a.summarize)
        s = SM.write_summary(a.summarize, a.setup_record)
        print("summary written:", os.path.join(a.summarize, "SUMMARY.json"), "| primary:", s["PRIMARY"]["status"])
        return 0
    if a.setup_only:
        if not a.roster:
            sys.exit("--setup-only needs --roster dev|all")
        return do_setup_only(a.setup_only, a.roster, ceiling)
    if a.pilot_s:
        if a.roster == "all":
            raise SystemExit("refusing: the pilot uses development names only")
        return do_pilot(a.pilot_s, a.targets.split(",") if a.targets else None, ceiling)
    if not a.outdir or not a.roster:
        sys.exit("need <outdir> and --roster dev|all")
    freeze_sha = setup_sha = None
    if a.roster == "all":
        if not a.freeze:
            raise SystemExit("refusing: --roster all needs --freeze <FREEZE.json>")
        if not a.setup_record:
            raise SystemExit("refusing: --roster all needs --setup-record <the committed setup record>")
        if a.dev_size_c is not None or a.targets:
            raise SystemExit("refusing: --dev-size-c and --targets are for the development roster only")
        if P.SIZE_C not in P.SIZE_C_CANDIDATES:
            raise SystemExit("refusing: presets SIZE_C is not set; the all-roster run needs the size limit of C fixed in the frozen presets")
        freeze_sha = check_freeze(a.freeze, a.setup_record)
        setup_sha = sha256_file(a.setup_record)
        refuse_if_launched(HERE)                               # first, so that a later launch is told why it is refused
        if os.path.lexists(a.outdir) and (not os.path.isdir(a.outdir) or os.listdir(a.outdir)):
            raise SystemExit("refusing: the output folder of the all-roster run must be new or empty")
        ensure_receipt(HERE, a.outdir, freeze_sha, setup_sha)
    else:
        if a.setup_record and not os.path.exists(a.setup_record):
            raise SystemExit("refusing: setup record does not exist")
        if a.dev_size_c is not None:
            if a.dev_size_c not in P.SIZE_C_CANDIDATES:
                raise SystemExit("refusing: --dev-size-c must be one of %s" % (P.SIZE_C_CANDIDATES,))
            if P.SIZE_C is not None and P.SIZE_C != a.dev_size_c:
                raise SystemExit("refusing: presets SIZE_C is set to %s; --dev-size-c cannot change it" % P.SIZE_C)
            P.SIZE_C = a.dev_size_c                            # in this process only: a development run
        if P.SIZE_C not in P.SIZE_C_CANDIDATES:
            raise SystemExit("refusing: presets SIZE_C is not set; a development run needs --dev-size-c N")
    import episode_bl as E
    import summarize_bl as SM
    roster = roster_of(a.roster)
    targets = roster
    if a.targets:
        targets = a.targets.split(",")
        bad = [t for t in targets if t not in roster]
        if bad:
            raise SystemExit("refusing: targets outside the %s roster: %s" % (a.roster, bad))
    os.makedirs(a.outdir, exist_ok=True)
    mp = os.path.join(a.outdir, "MANIFEST.json")
    if not os.path.exists(mp):
        with open(mp, "w") as f:
            json.dump(dict(label=LABEL, roster=a.roster, targets=targets, development_only=a.roster == "dev", freeze_sha256=freeze_sha,
                           size_c=P.SIZE_C, size_c_from="--dev-size-c (development only)" if a.dev_size_c is not None else "presets",
                           setup_record=a.setup_record, setup_record_sha256=sha256_file(a.setup_record) if a.setup_record else None,
                           hashes=file_hashes(), policy=policy(), memory_ceiling=ceiling, python=platform.python_version(),
                           pythonhashseed=os.environ["PYTHONHASHSEED"], started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                      f, indent=1, sort_keys=True)
    w0, c0 = time.time(), time.process_time()
    pools_cpu_s = set_up_pools()                               # its own line of the costs, outside every target
    for i, X in enumerate(targets):
        t = time.process_time()
        try:
            r = E.run_target(X, a.outdir)
        except G.NearCeiling as e:
            return end_near_ceiling(e, "target %s; its record says so; no summary is written by this process" % X)
        print("[%d/%d] %s %s %s cpu=%.1f" % (i + 1, len(targets), X, r.get("status"), (r.get("reason") or "")[:70], time.process_time() - t), flush=True)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    with open(os.path.join(a.outdir, "RUN_COSTS.json"), "w") as f:
        json.dump(dict(label=LABEL, what="costs of the whole job as this process measured them (an outer record of /usr/bin/time is the "
                                         "reference; nested subtotals are never added to these)",
                       cpu_user_s=round(usage.ru_utime, 1), cpu_system_s=round(usage.ru_stime, 1), cpu_process_s=round(time.process_time() - c0, 1),
                       pools_setup_cpu_s=pools_cpu_s,
                       wall_s=round(time.time() - w0, 1), resident_peak_kb=G.resident_peak_kb(), address_space_peak_kb=G.address_space_peak_kb(),
                       memory_ceiling=ceiling, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), f, indent=1, sort_keys=True)
    s = SM.write_summary(a.outdir, a.setup_record)
    print("summary: %s" % json.dumps(s["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
