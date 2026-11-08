"""Phase 2, step 4: check one world kernel's downloaded output and place it (standard library only; run with -I).

    python3 -I phase2/place_outputs.py W1            (check only)
    python3 -I phase2/place_outputs.py W1 --place    (check, then copy WORLD/runs to runs/generated/W1/runs)

Reads runs/kaggle/download/<W>/ (the kernel's output, untrusted until checked) and extracts its archive into
runs/kaggle/extract/<W>/ (must not exist yet). Custody checks, which must pass before anything is placed (a failure is a download or placement matter):
- the archive <W>_outputs.tar.gz has the sha256 that the notebook printed in its log;
- every archive member is a regular file or folder under <W>/runs/ (no link, no absolute or parent path);
- neither the extraction folder nor runs/generated/<W>/runs exists yet.
Output checks, recorded and never blocking (the frozen analysis judges the outputs): <W>/runs/OUTPUT_MANIFEST.json
covers every file under runs/ exactly and every digest equals the file; runs/STAGES.json names world <W>, status
"complete" and the package digest of runs/kaggle/PACKAGE_MANIFEST.json.
Writes runs/kaggle/PLACEMENT_<W>.json with the digests and the results. Never changes the outputs.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(world, place):
    dl = os.path.join(STUDY, "runs", "kaggle", "download", world)
    ex = os.path.join(STUDY, "runs", "kaggle", "extract", world)
    dest = os.path.join(STUDY, "runs", "generated", world, "runs")
    rec = {"world": world, "problems": [], "output_problems": []}
    bad, obs = rec["problems"], rec["output_problems"]
    arc = os.path.join(dl, f"{world}_outputs.tar.gz")
    if not os.path.isfile(arc):
        bad.append(f"no {world}_outputs.tar.gz in the download")
        return finish(rec, world)
    rec["archive_sha256"] = sha(arc)
    printed = set()
    for name in sorted(os.listdir(dl)):
        if name.endswith(".log"):
            with open(os.path.join(dl, name), encoding="utf-8", errors="replace") as f:
                printed |= set(re.findall(re.escape(world) + r"_outputs\.tar\.gz ([0-9a-f]{64})", f.read()))
    rec["printed_sha256"] = sorted(printed)
    if printed != {rec["archive_sha256"]}:
        bad.append("the archive's digest differs from the digest the notebook printed (or none was printed)")
    if os.path.exists(ex) or os.path.exists(dest):
        bad.append("the extraction folder or the destination exists already")
        return finish(rec, world)
    os.makedirs(ex)
    with tarfile.open(arc, "r:gz") as tf:
        members = tf.getmembers()
        for m in members:
            parts = m.name.split("/")
            if m.name.startswith("/") or ".." in parts or parts[:2] != [world, "runs"] or not (m.isfile() or m.isdir()):
                bad.append(f"archive member not allowed: {m.name!r}")
        if bad:
            return finish(rec, world)
        tf.extractall(ex, filter="data")
    runs = os.path.join(ex, world, "runs")
    om_path = os.path.join(runs, "OUTPUT_MANIFEST.json")
    try:
        with open(om_path, encoding="utf-8") as f:
            om = json.load(f)
    except (OSError, ValueError):
        om = None
    present = set()
    for d, _, files in os.walk(runs):
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), os.path.join(ex, world))
            if not rel.endswith(".tmp") and rel != "runs/OUTPUT_MANIFEST.json":
                present.add(rel)
    if not isinstance(om, dict) or not om:
        obs.append("OUTPUT_MANIFEST.json missing or empty")
    else:
        if set(om) != present:
            obs.append(f"the output manifest does not cover runs/ exactly (missing {sorted(present - set(om))[:5]}, "
                       f"extra {sorted(set(om) - present)[:5]})")
        wrong = [rel for rel, h in om.items() if not os.path.isfile(os.path.join(ex, world, rel)) or
                 sha(os.path.join(ex, world, rel)) != h]
        if wrong:
            obs.append(f"{len(wrong)} outputs differ from the manifest ({wrong[:5]})")
        rec["output_manifest_sha256"] = sha(om_path)
        rec["manifest_entries"] = len(om)
    try:
        with open(os.path.join(runs, "STAGES.json"), encoding="utf-8") as f:
            st = json.load(f)
        with open(os.path.join(STUDY, "runs", "kaggle", "PACKAGE_MANIFEST.json"), encoding="utf-8") as f:
            pm = json.load(f)
    except (OSError, ValueError):
        st, pm = {}, {}
        obs.append("STAGES.json or PACKAGE_MANIFEST.json unreadable")
    rec["kernel_status"] = st.get("status")
    rec["stages"] = {k: v.get("status") for k, v in (st.get("stages") or {}).items()}
    rec["cpu_scale"] = st.get("cpu_scale")
    if st.get("world") != world:
        obs.append(f"STAGES.json names world {st.get('world')!r}")
    if st.get("status") != "complete":
        obs.append(f"kernel status {st.get('status')!r}")
    if st.get("archive_sha256") != pm.get("archive_sha256"):
        obs.append("the kernel ran from another package than PACKAGE_MANIFEST.json")
    if place and not bad:
        shutil.copytree(runs, dest)
        rec["placed"] = os.path.relpath(dest, STUDY)
    return finish(rec, world)


def finish(rec, world):
    rec["custody_ok"] = not rec["problems"]
    rec["outputs_verified"] = rec["custody_ok"] and not rec.get("output_problems") and "manifest_entries" in rec
    out = os.path.join(STUDY, "runs", "kaggle", f"PLACEMENT_{world}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({k: rec.get(k) for k in ("world", "custody_ok", "outputs_verified", "archive_sha256",
                                               "printed_sha256", "kernel_status", "manifest_entries", "placed",
                                               "problems", "output_problems")}))
    return rec


if __name__ == "__main__":
    main(sys.argv[1], "--place" in sys.argv[2:])
