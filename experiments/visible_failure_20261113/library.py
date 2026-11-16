"""Read-only library files for admitted operations.
Author: Chimdi Walter Ndubuisi

One JSON file (mode 0444) per admitted (target, arm): a new neutral name, the expression text and tree, the
signature, the library names it uses, the sha256 of the acquisition and admission records, a version number. The
file's own sha256 is kept by the caller; it is verified before and after reuse. The library is arc-dsl by Michael
Hodel (MIT); expressions only call its operations.
"""
import hashlib
import json
import os
import stat

import frozen  # noqa: F401
import dslx
import search as S

L = dslx.load()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_json(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def tree_to_json(t):
    return [t[0], t[1]] + [tree_to_json(c) for c in t[2:]]


def tree_from_json(j):
    return (j[0], j[1]) + tuple(tree_from_json(c) for c in j[2:])


def consts_used(t, out=None):
    out = set() if out is None else out
    if t[0] == "C":
        out.add(t[1])
    for c in t[2:] if t[0] == "L" else ():
        consts_used(c, out)
    return out


def neutral_name(tag, expr):
    return "vf_" + hashlib.sha256((tag + ":" + expr).encode()).hexdigest()[:8]


def write_library_file(path, tag, X, tree, acq_record, adm_record, version=1):
    """Write the library file read-only. Returns (name, sha256 of the file bytes)."""
    expr = S.render(tree)
    name = neutral_name(tag, expr)
    body = dict(name=name, version=version, expression=expr, tree=tree_to_json(tree),
                signature=[[p, a] for p, a in L["sigs"][X]], uses=sorted(S.names_used(tree)),
                constants=sorted(consts_used(tree)), acquisition_record_sha256=sha256_json(acq_record),
                admission_record_sha256=sha256_json(adm_record))
    data = (json.dumps(body, indent=1, sort_keys=True) + "\n").encode()
    if os.path.exists(path):
        os.chmod(path, 0o644)
        os.remove(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(path, 0o444)
    return name, sha256_bytes(data)


def verify_library_file(path, sha):
    """True when the file exists, is read-only (no write bit), and its bytes hash to `sha`."""
    if not os.path.exists(path):
        return False
    if os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        return False
    with open(path, "rb") as f:
        return sha256_bytes(f.read()) == sha


def load_operation(path, sha, ns):
    """(name, function, body) from a verified library file; raises ValueError when the check fails. The function
    evaluates the stored expression in namespace `ns` (the lesioned library) on argument values."""
    if not verify_library_file(path, sha):
        raise ValueError("library file failed its read-only or hash check: " + path)
    with open(path) as f:
        body = json.load(f)
    tree = tree_from_json(body["tree"])
    params = [p for p, _ in body["signature"]]
    bad = [n for n in body["uses"] if n not in ns]
    if bad:
        raise ValueError("library file uses names that are not in the library: %s" % bad)

    def fn(*args):
        return S.eval_tree(tree, ns, L["consts"], dict(zip(params, args)))
    return body["name"], fn, body
