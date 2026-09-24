"""Generate the frozen v1.3 contrastive corpus.

Phases, in the required order:
  phaseA   200 calibration episodes, no groups, no contrast, no selection
  calib    compute and hash the frozen normalization constants
  pilot    exactly 40 group slots, to measure the group admission rate q
  full     ceil(84/q) group slots, capped at 1200

Protocol sha256 66aa1c561ac4fd2a619459f15919282776a5898ab3ae6f36ae6944a5389d8f1e
Manifest sha256 9492f392d13e95b033b3f6a77d6dd75d27cbb11b6d0ac7dad104901fab56de14

No group or episode is ever filtered on any property of its failure frontier.
Resumable and single writer: a slot whose record exists is skipped.
"""
import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v13_gen as G                             # noqa: E402
from cora_tti import constructive_dataset as CD                   # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402

CAL_DIR = os.path.join(HERE, "outputs", "tti", "v13_calibration")
COR_DIR = os.path.join(HERE, "outputs", "tti", "v13_contrastive_corpus")
CAL_FILE = os.path.join(CAL_DIR, "calibration.json")
PILOT_FILE = os.path.join(COR_DIR, "pilot_result.json")

CONTRAST_TYPES = ("PARTITION", "FEATURE", "SELECT")


def eligible_anchors(contrast_type, train_families):
    out = []
    for fam in train_families:
        probe = CD.sample_target(999983, fam)
        if G.contrast_target(probe, contrast_type) is not None:
            out.append(fam)
    return out


# --------------------------------------------------------------------------
# phase A
# --------------------------------------------------------------------------

def phase_a(man, target=200, slot_cap=12000):
    os.makedirs(CAL_DIR, exist_ok=True)
    budgets = man["budgets"]
    gate = man["gates"]
    gate_rule = {"require": "frontier_term_count >= 2"}
    families = [G.parse_family(f) for f in
                ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]]
    base = man["seeds"]["phase_A_from"]
    admitted = len([n for n in os.listdir(CAL_DIR) if n.startswith("ep")])
    started = time.monotonic()
    for slot in range(slot_cap):
        if admitted >= target:
            break
        path = os.path.join(CAL_DIR, f"slot{slot:04d}.done")
        if os.path.exists(path):
            continue
        fam = families[slot % len(families)]
        schema = CD.sample_target(base + slot, fam)
        code, ep = G.make_episode(schema, base + slot, budgets, gate_rule,
                                  f"v13A-{slot:04d}")
        with open(path, "w") as handle:
            handle.write(code)
        if code == "ADMITTED":
            with open(os.path.join(CAL_DIR, f"ep{admitted:04d}.json"), "w") as h:
                json.dump(ep, h, default=str)
            admitted += 1
            if admitted % 20 == 0:
                print(f"  phase A {admitted}/{target} admitted, slot {slot}, "
                      f"{round(time.monotonic()-started)}s", flush=True)
    print(f"phase A complete: {admitted} admitted episodes", flush=True)
    return admitted


def build_calibration(man):
    eps = []
    for name in sorted(os.listdir(CAL_DIR)):
        if name.startswith("ep") and name.endswith(".json"):
            with open(os.path.join(CAL_DIR, name)) as handle:
                eps.append(json.load(handle))
    assert eps, "phase A produced nothing"

    def stats(vectors, names):
        """Mean and effective divisor, per erratum 1.

        A field constant across calibration gets a divisor of 1.0, not a
        near-zero floor. A near-zero floor would turn any Phase-B movement on
        that field into a standardized difference of about a billion and make
        the distance a lookup on whichever constant field happened to move.
        """
        n = len(vectors)
        width = len(vectors[0])
        mean = [sum(v[i] for v in vectors) / n for i in range(width)]
        raw, eff, floored = [], [], []
        for i in range(width):
            var = sum((v[i] - mean[i]) ** 2 for v in vectors) / n
            sd = math.sqrt(var)
            raw.append(sd)
            if sd < 1e-6:
                eff.append(1.0)
                floored.append(names[i])
            else:
                eff.append(sd)
        return mean, eff, raw, floored

    demo_vecs = [[float(e["model_view"]["features"].get(k, 0) or 0)
                  if not isinstance(e["model_view"]["features"].get(k), bool)
                  else float(e["model_view"]["features"][k])
                  for k in G.DEMO_FEATURES] for e in eps]
    desc_vecs = [[float(e["descriptor"].get(k, 0) or 0)
                  for k in G.DESCRIPTOR_ORDER] for e in eps]
    dm, ds, ds_raw, d_floored = stats(demo_vecs, list(G.DEMO_FEATURES))
    fm, fs, fs_raw, f_floored = stats(desc_vecs, list(G.DESCRIPTOR_ORDER))
    art = {
        "parent_protocol_sha256": man["protocol_doc_sha256"],
        "parent_manifest_sha256": hashlib.sha256(
            open(G.MANIFEST, "rb").read()).hexdigest(),
        "phase_a_episodes": len(eps),
        "phase_a_target_digests": sorted({e["target_digest"] for e in eps}),
        "demo_features": list(G.DEMO_FEATURES),
        "demo_mean": dm, "demo_std": ds, "demo_std_raw": ds_raw,
        "demo_floored_fields": d_floored,
        "descriptor_order": list(G.DESCRIPTOR_ORDER),
        "descriptor_mean": fm, "descriptor_std": fs,
        "descriptor_std_raw": fs_raw, "descriptor_floored_fields": f_floored,
        "erratum": "erratum 1: fields with calibration std below 1e-6 use a "
                   "divisor of 1.0, not a near-zero floor",
        "note": "calibration only; these episodes never enter any gate or split",
    }
    blob = json.dumps(art, indent=1, sort_keys=True)
    with open(CAL_FILE, "w") as handle:
        handle.write(blob + "\n")
    sha = hashlib.sha256((blob + "\n").encode()).hexdigest()
    with open(CAL_FILE + ".sha256", "w") as handle:
        handle.write(f"{sha}  calibration.json\n")
    print(f"calibration written, sha256 {sha}")
    return art, sha


def load_calibration():
    with open(CAL_FILE) as handle:
        return json.load(handle)


# --------------------------------------------------------------------------
# group generation
# --------------------------------------------------------------------------

def demo_vector(episodes, cal):
    width = len(cal["demo_features"])
    acc = [0.0] * width
    for ep in episodes:
        f = ep["model_view"]["features"]
        for i, name in enumerate(cal["demo_features"]):
            value = f.get(name, 0)
            acc[i] += 1.0 if value is True else 0.0 if value is False else float(value)
    return [(acc[i] / len(episodes) - cal["demo_mean"][i]) / cal["demo_std"][i]
            for i in range(width)]


def generate_groups(man, cal, slots, tag):
    os.makedirs(COR_DIR, exist_ok=True)
    budgets = man["budgets"]
    gate_rule = {"require": "frontier_term_count >= 2"}
    replicates = man["group_law"]["replicates_per_target"]
    eps_demo = man["d_demo"]["epsilon_demo"]
    cap = man["budgets"]["attempts_per_episode_slot"]
    families = [G.parse_family(f) for f in
                ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]]
    eligible = {c: eligible_anchors(c, families) for c in CONTRAST_TYPES}
    base = man["seeds"]["groups_from"]
    started = time.monotonic()
    for slot in range(slots):
        path = os.path.join(COR_DIR, f"{tag}{slot:05d}.json")
        if os.path.exists(path):
            continue
        ctype = CONTRAST_TYPES[slot % len(CONTRAST_TYPES)]
        anchors = eligible[ctype]
        fam = anchors[(slot // len(CONTRAST_TYPES)) % len(anchors)]
        record = {"slot": slot, "tag": tag, "contrast_type": ctype,
                  "anchor_family": CV.family_text(fam), "admitted": False,
                  "group": None, "attempts": 0, "rejections": {}}
        slot_started = time.monotonic()
        for attempt in range(cap):
            record["attempts"] = attempt + 1
            seed = base + slot * 10000 + attempt * 100
            anchor = CD.sample_target(seed, fam)
            contrast = G.contrast_target(anchor, ctype, rotation=attempt)
            if contrast is None:
                record["rejections"][G.R_CONTRAST_ILLEGAL] = \
                    record["rejections"].get(G.R_CONTRAST_ILLEGAL, 0) + 1
                continue
            episodes, failed = {0: [], 1: []}, None
            for t, schema in ((0, anchor), (1, contrast)):
                for r in range(replicates):
                    code, ep = G.make_episode(
                        schema, seed + t * 10 + r, budgets, gate_rule,
                        f"v13-{tag}{slot:05d}-{attempt}-{t}-{r}")
                    if code != "ADMITTED":
                        record["rejections"][code] = \
                            record["rejections"].get(code, 0) + 1
                        failed = code
                        break
                    ep["target_index"] = t
                    ep["replicate_index"] = r
                    episodes[t].append(ep)
                if failed:
                    break
            if failed:
                continue
            va = demo_vector(episodes[0], cal)
            vb = demo_vector(episodes[1], cal)
            d_demo = math.sqrt(sum((a - b) ** 2 for a, b in zip(va, vb)))
            if d_demo > eps_demo:
                record["rejections"][G.R_DEMO] = \
                    record["rejections"].get(G.R_DEMO, 0) + 1
                record["last_d_demo"] = round(d_demo, 5)
                continue
            da = episodes[0][0]["target_digest"]
            db = episodes[1][0]["target_digest"]
            record["group"] = {
                "group_digest": G.group_digest(da, db),
                "contrast_type": ctype,
                "anchor_family": CV.family_text(fam),
                "target_digests": [da, db],
                "d_demo": round(d_demo, 5),
                "episodes": episodes[0] + episodes[1],
            }
            record["admitted"] = True
            break
        record["elapsed_s"] = round(time.monotonic() - slot_started, 2)
        tmp = path + ".tmp"
        with open(tmp, "w") as handle:
            json.dump(record, handle, default=str)
        os.replace(tmp, path)
        print(f"  {tag}{slot:05d} {ctype:9s} {CV.family_text(fam):8s} "
              f"admitted={record['admitted']} attempts={record['attempts']} "
              f"{record['elapsed_s']}s total={round(time.monotonic()-started)}s",
              flush=True)


def count_groups(tag):
    admitted = total = 0
    for name in sorted(os.listdir(COR_DIR)):
        if name.startswith(tag) and name.endswith(".json"):
            with open(os.path.join(COR_DIR, name)) as handle:
                d = json.load(handle)
            total += 1
            admitted += bool(d["admitted"])
    return admitted, total


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "phaseA"
    man = G.manifest()
    if phase == "phaseA":
        phase_a(man, target=man["calibration_phase_A"]["episodes"])
        build_calibration(man)
    elif phase == "pilot":
        cal = load_calibration()
        generate_groups(man, cal, man["sizing_rule"]["pilot_group_slots"], "pilot")
        admitted, total = count_groups("pilot")
        q = admitted / total if total else 0.0
        art = {"requested_group_slots": total, "admitted_groups": admitted,
               "q": q,
               "full_request": (min(math.ceil(84 / q),
                                    man["sizing_rule"]["cap"]) if q > 0 else None),
               "cap": man["sizing_rule"]["cap"],
               "cap_applied": (q > 0 and math.ceil(84 / q) > man["sizing_rule"]["cap"]),
               "zero_admission": q == 0}
        blob = json.dumps(art, indent=1, sort_keys=True)
        with open(PILOT_FILE, "w") as handle:
            handle.write(blob + "\n")
        with open(PILOT_FILE + ".sha256", "w") as handle:
            handle.write(hashlib.sha256((blob + "\n").encode()).hexdigest()
                         + "  pilot_result.json\n")
        print(json.dumps(art, indent=1))
    elif phase == "full":
        cal = load_calibration()
        with open(PILOT_FILE) as handle:
            pilot = json.load(handle)
        if pilot["zero_admission"]:
            print("ZERO_GROUP_ADMISSION_PILOT: the frozen formula is undefined")
            return
        generate_groups(man, cal, pilot["full_request"], "full")
    else:
        raise SystemExit(f"unknown phase {phase}")


if __name__ == "__main__":
    main()
