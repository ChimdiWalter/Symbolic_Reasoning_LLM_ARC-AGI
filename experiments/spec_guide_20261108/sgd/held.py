"""The held run (after the GO only; PROTOCOL.md). On Athe, detached, in one process:
    sh scripts/run_detached.sh sg_held --slot env PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= \
        python3 -s -B experiments/spec_guide_20261108/run.py held all

    python -s -B run.py held gen PER_EDIT MAX_S I/K    held families on held-pool grids, seeded by the GO's sha256;
                                                       writes runs/held/tasks.<I>.jsonl (demonstrations and test
                                                       input) and runs/held/solutions.<I>.jsonl (sealed: never read
                                                       by `run`); at most PER_EDIT admitted tasks per edit type
    python -s -B run.py held run  I/K                  every arm at every budget on the held tasks (direct
                                                       execution of the frozen step); writes
                                                       runs/held/predictions.<I>.jsonl
    python -s -B run.py held seal                      the predictions' digest -> runs/SEALED_PREDICTIONS
Admission of a generated held task: the frozen step in the hand-set order at 20,000 operations is not capped and
answers the test input correctly (pass at 2 from its multi-pair candidates); this uses the generated test output,
inside the generator, before any arm runs, and is the same for every arm (at 20,000 with no cap all orders give the
same candidates).
"""
import hashlib
import json
import os
import random
import sys
import time

import numpy as np
import torch

from sgd import env as E, gate as GT, gen as GN, net as NT, train as TR, data as DA
from gcon import engine as EN, features as FT, model as MD, policy as PO

HELD = os.path.join(E.STUDY, "runs", "rehearsal_held" if GT.REHEARSAL else "held")
CONFIG = os.path.join(E.STUDY, "config", "CONFIG.json")


def gen(per_edit, max_s, shard="0/1"):
    """Worker I of K: held families on held-pool grids, from the seed (GO sha256 prefix) x 1000 + I; at most
    ceil(PER_EDIT / K) admitted tasks per edit type in this worker (edit-type balancing, PROTOCOL.md); stops at
    MAX_S seconds of wall time."""
    i, kk = (int(x) for x in shard.split("/"))
    seed = GT.held_seed() * 1000 + i
    rng = random.Random(seed)
    if GT.REHEARSAL:
        pool, part = GN.pools("dev"), "val"
    else:
        rng.held_ok = True
        pool, part = GN.pools("held", allow_held=True), "held"
    cap = -(-int(per_edit) // kk)
    os.makedirs(HELD, exist_ok=True)
    tpath, spath = os.path.join(HELD, f"tasks.{i}.jsonl"), os.path.join(HELD, f"solutions.{i}.jsonl")
    # nothing held may exist before this worker writes: its own files, any predictions, any seal (the kernel starts
    # from a freshly unpacked package; the workers start together, so other workers' task files are not a refusal)
    if os.path.exists(tpath) or os.path.exists(spath) or any(fn.startswith("predictions.") for fn in os.listdir(HELD)) \
            or os.path.exists(os.path.join(E.STUDY, "runs", "SEALED_PREDICTIONS")):
        raise GT.GateRefused("held tasks exist already: they are generated once")
    counts = {}
    k = tried = skipped = 0
    w0 = time.time()
    with E.open_write(tpath) as ft, E.open_write(spath) as fs:
        while time.time() - w0 < float(max_s):
            t = GN.make_task(rng, pool, part)
            if t is None:
                continue
            if counts.get(t["edit"], 0) >= cap:
                skipped += 1
                if all(counts.get(e, 0) >= cap for e in GN.EDIT_TYPES + ("crop",)):
                    break
                continue
            tried += 1
            tr = GN.trace_task(t)
            if tr["capped"] or not tr["correct_20000"]:
                continue
            tid = f"h{i}_{k:04d}"
            ft.write(json.dumps({"task": tid, "train": t["train"], "test_input": t["test_input"]},
                                separators=(",", ":")) + "\n")
            fs.write(json.dumps({"task": tid, "test_output": t["test_output"], "family": t["family"],
                                 "edit": t["edit"], "view": t["view"], "pred_kind": t["pred_kind"], "op": t["op"],
                                 "src": t["src"]}, separators=(",", ":")) + "\n")
            ft.flush()
            fs.flush()
            counts[t["edit"]] = counts.get(t["edit"], 0) + 1
            k += 1
    rec = {"worker": i, "seed": seed, "admitted": k, "traced": tried, "skipped_at_cap": skipped,
           "per_edit": counts, "cap_per_edit": cap, "wall_s": round(time.time() - w0, 1)}
    E.dump(os.path.join(HELD, f"GEN_RECORD.{i}.json"), rec, indent=1)
    print(json.dumps(rec))


def load_models():
    c = E.load(CONFIG)
    md = os.path.join(E.STUDY, "models")
    blk = E.load(os.path.join(md, "block_models.json"))
    M = {"frequency": MD.Frequency.from_json(blk["frequency"]), "linear": MD.Model.from_json(blk["linear"]),
         "small_guide": MD.Model.from_json(blk["small_guide"])}
    ck = torch.load(os.path.join(md, "spec_guide.pt"), map_location="cpu", weights_only=False)
    cc = ck["cfg"]
    net = NT.SpecNet(d=cc.get("d", 128), layers=cc.get("layers", 4), heads=cc.get("heads", 4), ff=cc.get("ff", 256),
                     dropout=0.0)
    net.load_state_dict(ck["state"])
    net.eval()
    torch.manual_seed(int(c.get("probe_random_init_seed", 1)))
    rnd = NT.SpecNet(d=cc.get("d", 128), layers=cc.get("layers", 4), heads=cc.get("heads", 4), ff=cc.get("ff", 256),
                     dropout=0.0)
    rnd.eval()
    M.update(net=net, ck=ck, rnd=rnd, cfg=c)
    return M


def spec_block_scores(M, pairs, hs, fe):
    """The specification-reading guide's p x exp(-c) per block of hs, reading the specification `pairs`."""
    ck, net = M["ck"], M["net"]
    with torch.no_grad():
        t, m = TR.pad([TR.tok_array(pairs)], "cpu")
        o = net(t, m)
        z = o["z"]
        bl = hs.blocks
        feats = torch.tensor([fe[b] for b in bl], dtype=torch.float32)
        keys = torch.tensor([NT.KEY_INDEX.get(tuple(hs.block_key(b)), 0) for b in bl])
        owner = torch.zeros(len(bl), dtype=torch.long)
        f_mu = torch.tensor(ck["f_mu"], dtype=torch.float32)
        f_sd = torch.tensor(ck["f_sd"], dtype=torch.float32)
        lg, cp = net.blocks(z, owner, (feats - f_mu) / f_sd, keys)
        p = torch.sigmoid(lg).numpy()
        c = cp.numpy() * ck["c_sd"] + ck["c_mu"]
    return [float(a) * float(np.exp(-b)) for a, b in zip(p, c)], o


def attempts(top):
    """The first two distinct test predictions of the multi-pair candidates, in the frozen order."""
    out = []
    for c in top:
        if not c["loo"] or not c["pred_key"] or any(v is None for v in c["pred_key"]):
            continue
        g = c["pred_key"][0]
        if g not in out:
            out.append(g)
        if len(out) == 2:
            break
    return out


def run(shard="0/1"):
    i, k = (int(x) for x in shard.split("/"))
    go = GT.require_go()
    fr = E.sha_file(GT.FREEZE)
    M = load_models()
    budgets = M["cfg"]["budgets"]
    tasks = []
    for fn in sorted(f for f in os.listdir(HELD) if f.startswith("tasks.") and f.endswith(".jsonl")):
        with open(os.path.join(HELD, fn), encoding="utf-8") as f:
            tasks += [json.loads(x) for x in f if x.strip()]
    tasks.sort(key=lambda t: t["task"])
    n = len(tasks)
    pairs_all = [[(GN.grid(a), GN.grid(b)) for a, b in t["train"]] for t in tasks]
    out_path = os.path.join(HELD, f"predictions.{i}.jsonl")
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(x)["task"] for x in f if x.strip()}
    with E.open_write(out_path, "a") as fo:
        for idx, t in enumerate(tasks):
            if idx % k != i or t["task"] in done:
                continue
            t0 = time.process_time()
            pairs = pairs_all[idx]
            hs = EN.HoleState(pairs, [GN.grid(t["test_input"])], meta={"rank": 0})
            fe = {b: [round(v, 5) for v in x] for b, x in FT.hole_features(hs).items()}
            setup_cpu = time.process_time() - t0
            blocks = hs.blocks
            keys = [list(hs.block_key(b)) for b in blocks]
            X = [fe[b] for b in blocks]
            s_spec, o = spec_block_scores(M, pairs, hs, fe)
            s_shuf, _ = spec_block_scores(M, pairs_all[(idx + n // 2) % n], hs, fe)
            seqs = {"hand": PO.hand(blocks),
                    "frequency": PO.by_scores(blocks, M["frequency"].scores_keys(keys)),
                    "linear": PO.by_scores(blocks, M["linear"].scores(X)),
                    "small_guide": PO.by_scores(blocks, M["small_guide"].scores(X)),
                    "spec_guide": PO.by_scores(blocks, s_spec),
                    "shuffled_spec": PO.by_scores(blocks, s_shuf)}
            row = {"task": t["task"], "go_sha256": go, "freeze_sha256": fr, "setup_cpu_s": round(setup_cpu, 3),
                   "arms": {}}
            for arm, seq in seqs.items():
                for B in budgets:
                    c0 = time.process_time()
                    top, rec = EN.run_hole(hs, seq, B)
                    row["arms"][f"{arm}@{B}"] = {"attempts": attempts(top), "ops": rec["counts"]["op"],
                                                 "edit": rec["counts"]["edit"], "capped": rec["capped"],
                                                 "cpu_s": round(time.process_time() - c0, 3)}
            with torch.no_grad():
                tk, mk = TR.pad([TR.tok_array(pairs)], "cpu")
                row["z_trained"] = [round(float(v), 5) for v in o["z"][0]]
                row["z_random"] = [round(float(v), 5) for v in M["rnd"](tk, mk)["z"][0]]
                row["edit_probs"] = [round(float(v), 5) for v in torch.softmax(o["edit"][0], -1)]
            row["cpu_s"] = round(time.process_time() - t0, 3)
            fo.write(json.dumps(row, separators=(",", ":"), default=list) + "\n")
            fo.flush()


def seal():
    GT.require_go()
    files = sorted(fn for fn in os.listdir(HELD) if fn.startswith("predictions.") and fn.endswith(".jsonl"))
    digs = {fn: E.sha_file(os.path.join(HELD, fn)) for fn in files}
    joint = hashlib.sha256("".join(f"{p} {h}\n" for p, h in sorted(digs.items())).encode()).hexdigest()
    path = os.path.join(E.STUDY, "runs", "REHEARSAL_SEALED" if GT.REHEARSAL else "SEALED_PREDICTIONS")
    if os.path.exists(path):
        raise GT.GateRefused("predictions are sealed already")
    with E.open_write(path) as f:
        f.write(json.dumps({"files": digs, "joint_sha256": joint, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                                      time.gmtime())}, indent=1))
    print(json.dumps({"joint_sha256": joint, "files": len(digs)}))


def status(msg):
    os.makedirs(HELD, exist_ok=True)
    with E.open_write(os.path.join(HELD, "run.status"), "a") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")


def run_all():
    """The held run on Athe, in one detached process (PROTOCOL.md section 5): the custody checks (the GO committed
    alone and unchanged since its first commit; its freeze commit the last commit that changed FREEZE.json; every
    frozen hash; nothing held exists), then generation, the arms and the seal."""
    c = E.load(CONFIG)
    if GT.REHEARSAL:
        salt, fc = GT.require_go(), None
    else:
        salt, fc = GT.git_checks()
    GT.check_freeze()
    if os.path.isdir(HELD) and any(fn.startswith(("tasks.", "solutions.", "predictions.")) for fn in os.listdir(HELD)):
        raise GT.GateRefused("held tasks exist already: one held run only")
    per_edit, limit = c["per_edit"], c["gen_limit_s"]
    if GT.REHEARSAL and os.environ.get("SG_REHEARSAL_LIMITS"):          # smoke tests only: smaller limits
        per_edit, limit = (int(x) for x in os.environ["SG_REHEARSAL_LIMITS"].split(","))
    status(f"STARTED salt {salt} freeze_commit {fc}")
    gen(per_edit, limit, "0/1")
    status("GENERATED")
    run("0/1")
    status("ARMS_DONE")
    seal()
    status("SEALED")


def main(cmd, *args):
    return {"gen": gen, "run": run, "seal": seal, "all": run_all}[cmd](*args)
