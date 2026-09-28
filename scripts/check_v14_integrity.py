"""Item-2 v1.4 erratum 2 integrity gate, run before resuming and before the
sealed audit.

    pre    the resume preconditions: freeze, the preserved first run, the
           slot-order inclusion state (41 included, one excluded duplicate),
           the original first start and a live cap, no writer alive
    post   the pre-audit checks: everything above, exactly 42 included
           groups, no new duplicate admitted, and for every admitted group
           the grammar re-derivation, twin law, one-token difference,
           run-order law, seed law, group integrity and leakage

Reads slot records and recomputes targets from the frozen grammar. It
computes no distance, neighbour or stage statistic and never opens an audit
report. Exit status 0 means PASS.
"""
from __future__ import annotations

import fcntl
import glob
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402

G, CD, CV = L.G, L.CD, L.CV
COR_DIR = os.path.join(HERE, "outputs", "tti", "v14_twin_corpus")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "mechanistic_frontier_v14_manifest.json")
FULL_RECORD = re.compile(r"^full(\d{5})\.json$")
FAMILIES = ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze(man):
    p = []
    if sha(os.path.join(HERE, man["protocol_doc"])) != man["protocol_doc_sha256"]:
        p.append("protocol")
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha(MANIFEST):
            p.append("manifest")
    for rel, digest in man["implementation_sha256"].items():
        if sha(os.path.join(HERE, rel)) != digest:
            p.append(rel)
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            p.append(f"dependency:{name}")
    for path, digest in man["external_file_sha256"].items():
        if sha(path) != digest:
            p.append(path)
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    return p


def preservation(man):
    e2 = man["erratum_2"]
    p = L.preserved_problems(
        os.path.join(HERE, e2["preserved_hash_list"]["path"]),
        e2["preserved_hash_list"]["sha256"], COR_DIR,
        archived=[(os.path.join(HERE, e2["archived_run_end"]),
                   "full_run_end.json")])
    for rel in e2["blocked_audit_paths"]:
        path = os.path.join(HERE, rel)
        if not os.path.exists(path) or sha(path) != e2["blocked_audit_sha256"]:
            p.append(f"blocked_audit:{rel}")
    return p


def load_records():
    names = sorted(n for n in os.listdir(COR_DIR) if FULL_RECORD.match(n))
    records = []
    for n in names:
        with open(os.path.join(COR_DIR, n)) as handle:
            records.append(json.load(handle))
    return records


def writer_alive():
    """True if another process holds the generator's writer lock."""
    with open(os.path.join(COR_DIR, ".writer.lock"), "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
    return False


def check_group(r, problems):
    """Grammar re-derivation, twin law, one-token difference, seed law,
    run-order law, group integrity and leakage for one admitted record."""
    g, slot = r["group"], r["slot"]
    fam_text = FAMILIES[slot % 5]
    if g["anchor_family"] != fam_text or r["anchor_family"] != fam_text:
        problems.append(f"slot{slot}:family_cycle")
    off = g["pair_seed"] - L.SEED_BASE - slot * L.SLOT_STRIDE
    attempt, rem = divmod(off, L.ATTEMPT_STRIDE)
    if rem or not 0 <= attempt < L.ATTEMPTS_PER_SLOT \
            or attempt != r["pair_attempts"] - 1:
        problems.append(f"slot{slot}:pair_seed")
        return
    anchor = CD.sample_target(g["pair_seed"], G.parse_family(fam_text))
    contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
    if [CV.digest(anchor), CV.digest(contrast)] != g["target_digests"]:
        problems.append(f"slot{slot}:derivation")
    if G.group_digest(*g["target_digests"]) != g["group_digest"]:
        problems.append(f"slot{slot}:group_digest")
    if not L.twin_law(anchor, contrast)[0]:
        problems.append(f"slot{slot}:twin_law")
    by = {(e["target_index"], e["replicate_index"]): e for e in g["episodes"]}
    for rr in range(L.REPLICATES):
        ta, tb = by[(0, rr)]["target_tokens"], by[(1, rr)]["target_tokens"]
        if len(ta) != len(tb) or sum(1 for x, y in zip(ta, tb) if x != y) != 1:
            problems.append(f"slot{slot}:r{rr}:token_difference")
    seeds = [by[(0, rr)]["seed"] for rr in range(L.REPLICATES)]
    if len(set(seeds)) != L.REPLICATES or any(
            not 0 <= s - g["pair_seed"] < L.SEEDS_PER_PAIR for s in seeds) or any(
            by[(1, rr)]["seed"] != seeds[rr] for rr in range(L.REPLICATES)):
        problems.append(f"slot{slot}:seed_law")
    for rr in range(L.REPLICATES):
        a = by[(0, rr)]
        rerun = a.get("self_rerun")
        expect = ["A" if w == 0 else "B" if w == 1 else "rerun"
                  for w in L.run_order(a["seed"])]
        if rerun is None or rerun.get("order") != expect:
            problems.append(f"slot{slot}:r{rr}:run_order")
        if "self_rerun" in by[(1, rr)]:
            problems.append(f"slot{slot}:r{rr}:rerun_on_target_1")
    for x in L.integrity_problems(g):
        problems.append(f"slot{slot}:integrity:{x}")
    for e in g["episodes"]:
        for x in L.view_leaks(e, g):
            problems.append(f"slot{slot}:leak:{x}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("pre", "post"):
        raise SystemExit("usage: check_v14_integrity.py pre|post")
    with open(MANIFEST) as handle:
        man = json.load(handle)
    e2 = man["erratum_2"]
    problems = []

    fz = freeze(man)
    problems += [f"freeze:{x}" for x in fz]
    pv = preservation(man)
    problems += pv
    print("freeze now:", "OK" if not fz else fz)
    print("preserved first run (136 records, run state, run end, archive, "
          "3 blocked reports):", "OK" if not pv else pv)

    tmp = glob.glob(os.path.join(COR_DIR, "*.tmp"))
    records = load_records()
    slots = [r["slot"] for r in records]
    contiguous = slots == list(range(len(records)))
    if tmp or not contiguous:
        problems.append("slot_files")
    print(f"slot records {len(records)} readable, contiguous {contiguous}, "
          f"partial files {len(tmp)}")

    with open(os.path.join(COR_DIR, "full_run_state.json")) as handle:
        first = json.load(handle)["first_started_epoch"]
    if first != e2["first_started_epoch"]:
        problems.append("first_start_changed")
    print(f"first start epoch {first} (unchanged {first == e2['first_started_epoch']})")

    included, excluded = L.first_admissions(records)
    expected_excluded = e2["excluded_at_resume"]
    admitted = [r for r in records if r["admitted"]]
    print(f"admissions {len(admitted)}, included {len(included)}, excluded "
          f"{[(x['group_digest'][:12], x['first_slot'], x['excluded_slot']) for x in excluded]}")
    if excluded != expected_excluded:
        problems.append("excluded_duplicates")

    env_bad = [r["slot"] for r in records
               if r["environment"] != man["environment"]["required_snapshot"]]
    ver_bad = [r["slot"] for r in records
               if r["runtime_versions"] != man["runtime_versions"]]
    frz_bad = [r["slot"] for r in records if r["freeze_ok"] is not True]
    eng_bad = [r["slot"] for r in records if r["engine_state_problems"]]
    problems += [f"slot{s}:environment" for s in env_bad] + \
        [f"slot{s}:versions" for s in ver_bad] + \
        [f"slot{s}:freeze_ok" for s in frz_bad] + \
        [f"slot{s}:engine_state" for s in eng_bad]
    print(f"every slot: environment frozen {not env_bad}, versions frozen "
          f"{not ver_bad}, freeze_ok {not frz_bad}, engine state clean {not eng_bad}")

    now = time.time()
    if mode == "pre":
        if len(records) != e2["resume_slot"]:
            problems.append("resume_slot")
        if len(included) != e2["included_at_resume"]:
            problems.append("included_at_resume")
        live = now < e2["launch_deadline_epoch"] and now - first <= man["caps"]["wall_clock_s"]
        if not live:
            problems.append("ERRATUM2_ORIGINAL_CAP_EXPIRED")
        alive = writer_alive()
        if alive:
            problems.append("writer_alive")
        print(f"resume slot {len(records)} (expected {e2['resume_slot']}), "
              f"included {len(included)} (expected {e2['included_at_resume']}), "
              f"cap live {live} ({e2['launch_deadline_utc']} deadline, "
              f"{(e2['launch_deadline_epoch'] - now) / 3600:.2f} h left), "
              f"writer alive {alive}")
    else:
        new = [r for r in records if r["slot"] >= e2["resume_slot"]]
        man_sha = sha(MANIFEST)
        for r in new:
            if r.get("manifest_sha256") != man_sha:
                problems.append(f"slot{r['slot']}:manifest")
            if r.get("started_since_first_start_s") is None or \
                    r["started_since_first_start_s"] > man["caps"]["wall_clock_s"]:
                problems.append(f"slot{r['slot']}:cap")
        if len(included) != man["caps"]["target_groups"]:
            problems.append("included_count")
        end_path = os.path.join(COR_DIR, "full_run_end_erratum2.json")
        end = json.load(open(end_path)) if os.path.exists(end_path) else {}
        if end.get("stop_reason") != "target_groups" or \
                end.get("admitted_groups") != man["caps"]["target_groups"]:
            problems.append("run_end")
        for r in admitted:
            check_group(r, problems)
        skips = [s for r in new for s in r.get("duplicate_skips", [])]
        new_adm = [r for r in new if r["admitted"]]
        print(f"continuation slots {len(new)} ({new[0]['slot'] if new else '-'} to "
              f"{new[-1]['slot'] if new else '-'}), new admissions {len(new_adm)}, "
              f"duplicate pairs skipped before any engine run {len(skips)}")
        for r in new_adm:
            g = r["group"]
            print(f"new included group: slot {r['slot']}, digest {g['group_digest']}, "
                  f"family {g['anchor_family']}, pair seed {g['pair_seed']}, "
                  f"attempt {r['pair_attempts'] - 1}, started "
                  f"{r['started_since_first_start_s']} s after first start")
        print(f"run end: {end}")
        print(f"every admitted group ({len(admitted)}): grammar re-derivation, twin law, "
              f"one-token difference, seed law, run-order law, group integrity, "
              f"leakage checked")
        rej = Counter()
        for r in records:
            rej.update(r["rejections"])
        print("rejections by frozen reason:", dict(rej.most_common()))
        runs = [(e["observation_s"], e["cpu_s"]) for r in included
                for e in r["group"]["episodes"]]
        runs += [(e["self_rerun"]["observation_s"], e["self_rerun"]["cpu_s"])
                 for r in included for e in r["group"]["episodes"]
                 if "self_rerun" in e]
        obs = sorted(o for o, _ in runs)
        cpu = sorted(c for _, c in runs)
        ratio = sorted(c / o for o, c in runs if o)
        mid = lambda xs: xs[len(xs) // 2]
        print(f"engine runs in included groups {len(runs)}: wall s median {mid(obs)} "
              f"(min {obs[0]}, max {obs[-1]}); cpu s median {mid(cpu)} "
              f"(min {cpu[0]}, max {cpu[-1]}); cpu/wall median {mid(ratio):.3f}")
    print("INTEGRITY", mode, "PASS" if not problems else f"FAIL {problems[:30]}")
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
