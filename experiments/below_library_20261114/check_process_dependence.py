"""Do the values of the setup step and of a development episode depend on the process? A check on development
names. Never a result.

Protocol section 9 (process dependence): the setup pass and a development episode are compared across fresh
processes with changed memory layouts and with address randomization on and off, values and not only counts.

This script starts two fresh processes of itself:
  A   as launched (address randomization as the machine has it, Python's own allocator);
  B   address randomization off (setarch -R), the system allocator in place of Python's own (PYTHONMALLOC=malloc)
      and a block of allocations made before anything of the experiment is imported: another memory layout.
Each process computes, through this experiment's own path (episode_bl):
  for every development name   the sha256 of the setup view (decisions and counts), of the 66 generator examples
                               (inputs by key, outputs by canonical text), of the usability slice and of the
                               final slice of the pooled sequence (inputs by key; the true operation is not run on
                               the final slice here), and of what the true operation gives on the usability slice;
  for the targets named        a whole episode (run_target into a temporary folder): the five seals, the setup
                               view, every search (expression, size, ending, the check of its first fit; level,
                               bank, function-valued entries, refusals and the record of function-making when the
                               search ended on its own or by the combination budget, not by processor time), the selections, the final
                               panel, every final check with its counterexample, and the witness state.
The two processes must agree on every one of these values; every difference is listed. Processor times and memory
peaks are not compared, and neither is the bank of a search that ended by processor time (it depends on timing).

    env PYTHONHASHSEED=0 python -s -B check_process_dependence.py <out.json> [--targets a,b,c] [--dev-size-c N]

Development names only. Run it inside a CPU slot (it takes several minutes).   Author: Chimdi Walter Ndubuisi
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PAD = "BL1_PROCESS_CHECK_PAD"
ON_ITS_OWN = ("found", "size_limit_completed", "size_limit_completed_function_cap", "combination_budget_used_up")   # the budget in combinations: no timing
DEFAULT_TARGETS = "color,rot180,mfilter"


def sha(texts):
    return hashlib.sha256("\x1f".join(texts).encode()).hexdigest()


def child(folder, targets, dev_size_c):
    """One process: the values, written to <folder>/values.json."""
    junk = [bytearray(1000 * (i % 97 + 1)) for i in range(5000)] if os.environ.get(PAD) else []
    sys.path.insert(0, HERE)
    import bl_frozen  # noqa: F401
    import dslx
    import presets_bl as P
    import run_bl
    ceiling = run_bl.set_memory_ceiling()
    import episode_bl as E
    import gen_bl
    if P.SIZE_C is None:
        if dev_size_c not in P.SIZE_C_CANDIDATES:
            raise SystemExit("refusing: presets SIZE_C is not set; give --dev-size-c N")
        P.SIZE_C = dev_size_c                                    # in this process only: a development check
    elif dev_size_c is not None and dev_size_c != P.SIZE_C:
        raise SystemExit("refusing: presets SIZE_C is set to %s; --dev-size-c cannot change it" % P.SIZE_C)
    bad = [t for t in targets if t not in P.DEV_ROSTER]
    if bad:
        raise SystemExit("refusing: development names only (%s)" % bad)
    run_bl.set_up_pools()
    setup = {}
    for X in P.DEV_ROSTER:
        ep = E.Episode(X)
        excluded = ep.setup()
        view = ep.setup_view()
        g = E.G.call_checked(gen_bl.gen_examples, X, n_total=P.N_GEN)
        row = dict(view=E.sha256_json(view), status=view["decision"]["status"],
                   generator_examples=sha([E.input_key(tuple(a)) + "=>" + E.input_key(y) for a, y in g["examples"]]))
        if excluded is None:
            usable, info = E.stream_usable(ep.x_true, ep.slice_usability, P.STREAM_GUARD_S)
            row.update(usability_slice_inputs=sha([E.input_key(t) for t in ep.slice_usability]),
                       final_slice_inputs=sha([E.input_key(t) for t in ep.slice_final]),
                       usability_slice_outputs=sha([dslx.canon(y) for _, y in usable]), usable=info["usable"],
                       usability_guard_timeout=info["guard_timeout"])
        setup[X] = row
    episodes = {}
    out = os.path.join(folder, "out")
    for X in targets:
        r = E.run_target(X, out)
        searches = {}
        for name, a in (r.get("searches") or {}).items():
            s = {k: a.get(k) for k in ("expr", "size", "stop_class", "first_fit", "fit_recheck", "incomplete", "error")}
            final = dict(a.get("final") or {})
            final.pop("cpu_s", None)
            s["final"] = final or None
            if a.get("stop_class") in ON_ITS_OWN:
                s.update({k: a.get(k) for k in ("level_completed", "bank", "function_valued_entries", "refused_by_the_wrappers",
                                                "function_making", "refused_by_the_wrappers_in_later_evaluations")})
            searches[name] = s
        witness = dict(r.get("witness") or {})
        episodes[X] = dict(status=r.get("status"), seals=r.get("seals"), setup_view=r.get("setup_view"), searches=searches,
                           selection=r.get("selection"), final_panel=r.get("final_panel"), witness=witness,
                           opened_roles=r.get("opened_roles"))
    try:
        with open("/proc/self/personality") as f:
            personality = f.read().strip()
    except OSError:
        personality = None
    body = dict(setup=setup, episodes=episodes, memory_ceiling=ceiling,
                process=dict(personality=personality, address_randomization_off=None if personality is None else bool(int(personality, 16) & 0x0040000),
                             pythonmalloc=os.environ.get("PYTHONMALLOC"), allocations_before_the_imports=len(junk),
                             address_of_a_function=id(E.pools), address_of_a_library_operation=id(dslx.full_ns()["size"]),
                             python=platform.python_version(), pythonhashseed=os.environ.get("PYTHONHASHSEED")),
                cpu_s=round(time.process_time(), 1))
    with open(os.path.join(folder, "values.json"), "w") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
    return 0


def differences(a, b, path=""):
    """Every path at which two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(dict(path=path + "/" + str(k), A=a.get(k, "<absent>"), B=b.get(k, "<absent>")))
            else:
                out += differences(a[k], b[k], path + "/" + str(k))
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += differences(x, y, "%s[%d]" % (path, i))
        return out
    return [] if a == b else [dict(path=path, A=a, B=b)]


def main(argv):
    if "--child" in argv:
        folder = argv[argv.index("--child") + 1]
        targets = [t for t in argv[argv.index("--targets") + 1].split(",") if t]
        size = int(argv[argv.index("--dev-size-c") + 1]) if "--dev-size-c" in argv else None
        return child(folder, targets, size)
    out_path = argv[0]
    if os.path.exists(out_path):
        raise SystemExit("refusing: %s exists" % out_path)
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("run with PYTHONHASHSEED=0")
    targets = argv[argv.index("--targets") + 1] if "--targets" in argv else DEFAULT_TARGETS
    extra = ["--dev-size-c", argv[argv.index("--dev-size-c") + 1]] if "--dev-size-c" in argv else []
    setarch = shutil.which("setarch")
    runs = (("A", [], {}),
            ("B", ([setarch, platform.machine(), "-R"] if setarch else []), {"PYTHONMALLOC": "malloc", PAD: "x" * 4096}))
    values, wall = {}, {}
    tmp = tempfile.mkdtemp(prefix="bl1_process_check_")
    try:
        for label, prefix, more in runs:
            folder = os.path.join(tmp, label)
            os.makedirs(folder)
            env = dict(os.environ, PYTHONHASHSEED="0")
            env.pop(PAD, None)
            env.pop("PYTHONMALLOC", None)
            env.update(more)
            t = time.time()
            r = subprocess.run(prefix + [sys.executable, "-s", "-B", os.path.abspath(__file__), "--child", folder, "--targets", targets] + extra,
                               env=env, capture_output=True, text=True, cwd=tempfile.gettempdir())
            wall[label] = round(time.time() - t, 1)
            if r.returncode != 0:
                raise SystemExit("process %s ended with status %d: %s" % (label, r.returncode, (r.stderr or r.stdout)[-800:]))
            with open(os.path.join(folder, "values.json")) as f:
                values[label] = json.load(f)
            print("process %s done: %.0f s wall, %s" % (label, wall[label], json.dumps(values[label]["process"], sort_keys=True)), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    diff_setup = differences(values["A"]["setup"], values["B"]["setup"])
    diff_episodes = differences(values["A"]["episodes"], values["B"]["episodes"])
    pa, pb = values["A"]["process"], values["B"]["process"]
    body = dict(author="Chimdi Walter Ndubuisi", label="development only: a check of process dependence; never a result",
                what="the values of the setup step of every development name and of whole episodes of the targets named, in two fresh "
                     "processes: A as launched; B with address randomization off, the system allocator and other allocations first",
                targets=targets.split(","), processes=dict(A=pa, B=pb),
                the_two_layouts_differ=bool(pa["address_of_a_function"] != pb["address_of_a_function"]
                                            or pa["address_of_a_library_operation"] != pb["address_of_a_library_operation"]),
                address_randomization=dict(A_off=pa["address_randomization_off"], B_off=pb["address_randomization_off"]),
                setup=dict(names=len(values["A"]["setup"]), same=not diff_setup, differences=diff_setup),
                episodes=dict(names=sorted(values["A"]["episodes"]), same=not diff_episodes, differences=diff_episodes,
                              not_compared="processor times, memory peaks, and the level, bank and function-making of a search that "
                                           "ended by processor time (they depend on timing)"),
                all_the_same=not diff_setup and not diff_episodes, values=values, wall_s=wall,
                cpu_s=dict(A=values["A"]["cpu_s"], B=values["B"]["cpu_s"]))
    with open(out_path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    print("setup of %d development names: %s; episodes of %s: %s; the two layouts differ: %s; address randomization off in A: %s, in B: %s" % (
        body["setup"]["names"], "the same" if not diff_setup else "%d DIFFERENCES" % len(diff_setup), body["episodes"]["names"],
        "the same" if not diff_episodes else "%d DIFFERENCES" % len(diff_episodes), body["the_two_layouts_differ"],
        pa["address_randomization_off"], pb["address_randomization_off"]))
    return 0 if body["all_the_same"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
