"""Build cora_reach2/measure2.py from cora_reach/measure.py (reach v2).

  python scripts/build_measure2.py           write cora_reach2/measure2.py
  python scripts/build_measure2.py --check   exit 1 unless the file equals the build

The successor's object_run, loo_fold, run_control and run_task are v1's
source with the EDITS below (each new line marked `# V2`); nothing else.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(HERE, "cora_reach2", "measure2.py")
FUNCS = ("object_run", "loo_fold", "run_control", "run_task")
HEADER = '"""Reach v2 measurement: the reach v1 policy (cora_reach.measure, frozen at\nc8d8e3a) with the one licensed repair, variant-carrying installation\n(cora_reach2.variant): wherever the policy installs an extension that carries\na construction variant (the failure-conditioned proposal, every leave-one-out\nfold\'s proposal, the shuffled-failure donor\'s proposal), the variant is\nsearched first while the extension is installed. The demonstration-only\ncontrol has no variant and is installed as in v1.\n\nGENERATED from cora_reach/measure.py by targeted edits, each marked `# V2`\n(scripts/build_measure2.py records them); every other line of object_run,\nloo_fold, run_control and run_task is v1\'s, and every helper is imported\nfrom v1 unchanged. tests/test_reach2.py checks that removing the V2 edits\ngives back v1\'s source exactly.\n"""\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport os\nimport time\n\nimport numpy as np\n\nfrom cora_reach import bridge as BR\nfrom cora_reach import construct as CN\nfrom cora_reach import growth_ext as GE\nfrom cora_reach import instances as INST\nfrom cora_reach import relations as REL\nfrom cora_reach.measure import (BUDGET_S, CAP_SLACK_S, CONTROL_ARMS, EXTRACT_CAP_S, FRAMES_ALLOWANCE_S,  # noqa: F401\n                                GATES, MATCHED_MAX_S, MATCHED_MIN_S, PATH_CLASSES, PROGRESSION, _close, _grid,\n                                _hard_timeout, _load, _proposal_summary, arrays, as_task, clear_engine_caches,\n                                demo_only_propose, engine_dirs, grow_observer, hard_cap, inspect_program, pool_predictions,\n                                psha, read_instances, separation, substituted)\nfrom cora_reach2 import variant as VA\n\nVERSION = "reach-v2-measure"\n\n\n'
EDITS = {
    "object_run": [
        ("def object_run(task_id, train, tests, engine_dir, ext=None, budget_s=BUDGET_S, inspect=False):",
         "def object_run(task_id, train, tests, engine_dir, ext=None, budget_s=BUDGET_S, inspect=False, variant=None):  # V2"),
        ("                stack.enter_context(BR.installed(ext))\n",
         "                stack.enter_context(BR.installed(ext))\n"
         "                if variant is not None:  # V2\n"
         "                    out[\"variant_first\"] = stack.enter_context(VA.variant_first(variant))  # V2\n"),
    ],
    "loo_fold": [
        ("    e = prop[\"proposals\"][0][\"ext\"]\n",
         "    e = prop[\"proposals\"][0][\"ext\"]\n"
         "    f[\"selected_variant\"] = prop[\"proposals\"][0][\"variant\"]  # V2\n"),
        ("    run, _prog = object_run(f\"{key}_loo{i}\", rest, [a], dirs[\"loo\"], ext=e, budget_s=budget_s)",
         "    run, _prog = object_run(f\"{key}_loo{i}\", rest, [a], dirs[\"loo\"], ext=e, budget_s=budget_s,  # V2\n"
         "                            variant=f[\"selected_variant\"])  # V2"),
    ],
    "run_control": [
        ("                            dirs[\"demo_only\" if arm == \"DEMO_ONLY\" else \"shuffled\"], ext=e, budget_s=budget_s)",
         "                            dirs[\"demo_only\" if arm == \"DEMO_ONLY\" else \"shuffled\"], ext=e, budget_s=budget_s,  # V2\n"
         "                            variant=prop[\"proposals\"][0].get(\"variant\"))  # V2"),
    ],
    "run_task": [
        ("    w1, prog1 = object_run(key, train, tests, dirs[\"fc\"], ext=e, budget_s=budget, inspect=True)\n"
         "    w2, _ = object_run(key, train, tests, dirs[\"fc\"], ext=e, budget_s=budget)\n",
         "    v = fc[\"proposals\"][0][\"variant\"]  # V2\n"
         "    w1, prog1 = object_run(key, train, tests, dirs[\"fc\"], ext=e, budget_s=budget, inspect=True, variant=v)  # V2\n"
         "    w2, _ = object_run(key, train, tests, dirs[\"fc\"], ext=e, budget_s=budget, variant=v)  # V2\n"),
    ],
}


def v1_functions() -> dict:
    src = open(os.path.join(HERE, "cora_reach", "measure.py")).read()
    lines = src.splitlines(keepends=True)
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCS:
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            out[node.name] = "".join(lines[start:node.end_lineno])
    return out


def build() -> str:
    funcs = v1_functions()
    parts = []
    for name in FUNCS:
        s = funcs[name]
        for old, new in EDITS[name]:
            if s.count(old) != 1:
                raise SystemExit(f"{name}: edit anchor not found exactly once: {old[:60]!r}")
            s = s.replace(old, new)
        parts.append(s)
    return HEADER + "\n\n".join(parts)


def main(argv):
    text = build()
    if argv[:1] == ["--check"]:
        same = open(TARGET).read() == text
        print("measure2.py equals the build" if same else "measure2.py DIFFERS from the build")
        sys.exit(0 if same else 1)
    with open(TARGET, "w") as handle:
        handle.write(text)
    print("written", TARGET)


if __name__ == "__main__":
    main(sys.argv[1:])
