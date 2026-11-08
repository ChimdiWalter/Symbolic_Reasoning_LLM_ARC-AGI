"""Item pools and the development / held split.

Circuits: a PLA file is a development file when int(sha256("T1-dev|" + file name), 16) % 4 == 0; its eligible
outputs are the development circuit items. Every other file is a held-candidate file. Held circuit items are chosen
in the scored run: inside each held-candidate file, eligible outputs are ranked by sha256(salt + "|" + item id) and
the first cap are taken, where salt is the sha256 (64 hex characters) of the committed GO file (PROTOCOL.md
section 2, Amendment 1).
Policies: development policies come from the stream "development"; held policies from the stream
"held|" + salt (generated only in the scored run), skipping any function equal to a development policy.
"""
import hashlib
import json
import os
import tarfile

from . import pla, policy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path=None):
    with open(path or os.path.join(HERE, "config.json")) as f:
        return json.load(f)


def is_dev_file(cluster):
    name = cluster.split("/", 1)[1]
    return int(hashlib.sha256(("T1-dev|" + name).encode()).hexdigest(), 16) % 4 == 0


def circuits(cfg):
    c = cfg["circuit"]
    return pla.items(os.path.join(HERE, c["archive"]), c["n_min"], c["n_max"])


def seed_texts(cfg):
    out = {}
    with tarfile.open(os.path.join(HERE, cfg["policy"]["archive"]), "r:gz") as tf:
        for m in sorted(tf.getmembers(), key=lambda m: m.name):
            parts = m.name.split("/")
            if m.isfile() and len(parts) == 2 and parts[0] == "parameter_files" and parts[1].endswith("_seed"):
                out[parts[1]] = tf.extractfile(m).read().decode("latin-1")
    return out


def dev_items(cfg):
    circ, _ = circuits(cfg)
    dev_c = [i for i in circ if is_dev_file(i["cluster"])]
    p = cfg["policy"]
    dev_p, _ = policy.items(seed_texts(cfg), "development", p["dev_per_seed"], p["m_min"], p["m_max"])
    return dev_c, dev_p


def held_items(cfg, salt):
    """Only for the scored run, after GO."""
    if len(salt) != 64 or any(ch not in "0123456789abcdef" for ch in salt):
        raise ValueError("salt must be the 64-character sha256 of the committed GO file")
    circ, _ = circuits(cfg)
    cap = cfg["circuit"]["held_cap_per_file"]
    by_file = {}
    for i in circ:
        if not is_dev_file(i["cluster"]):
            by_file.setdefault(i["cluster"], []).append(i)
    held_c = []
    for f in sorted(by_file):
        ranked = sorted(by_file[f], key=lambda i: hashlib.sha256((salt + "|" + i["id"]).encode()).hexdigest())
        held_c += ranked[:cap]
    p = cfg["policy"]
    texts = seed_texts(cfg)
    dev_p, _ = policy.items(texts, "development", p["dev_per_seed"], p["m_min"], p["m_max"])
    held_p, _ = policy.items(texts, "held|" + salt, p["held_per_seed"], p["m_min"], p["m_max"],
                             exclude=frozenset(i["T"] for i in dev_p))
    return held_c, held_p
