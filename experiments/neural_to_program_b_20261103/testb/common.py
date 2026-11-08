"""Shared rules for Test B (PROTOCOL.md, revision 3). Standard library only.

Exact conventions fixed here and tested in tests/test_adversarial.py:
- sha256 of text: the UTF-8 bytes, hex digest.
- Hashed orders ("donor:", "taskB:"): ascending by the hex digest of sha256(prefix + task id); ties cannot occur
  for distinct ids (the id itself is a second key only to make the sort total).
- PRNG seed: seed_of(text) = int.from_bytes(sha256(text).digest(), "big"), which equals int(hexdigest, 16), and the
  generator is random.Random(seed_of(text)). For the random target, text = "random:" + task id + ":" + str(output
  index). A string or bytes seed would give a different stream; the integer is the only form used.
- Records are written atomically: a temporary file in the same folder, fsync, rename, then fsync of the folder.
- Claims (RUN_CLAIM, SCORE_CLAIM) are created with O_CREAT | O_EXCL and fsynced before anything else happens.
- GO files: exactly one line per key, '<key> <64 lowercase hex>', and nothing else (one final newline allowed).
"""
import hashlib
import json
import os
import random
import re
import sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))        # experiments/neural_to_program_b_20261103
REPO = os.path.dirname(os.path.dirname(EXP))
PY_WORKER = "python3"
ANSWER_NAME = re.compile(r"solutions", re.I)
HEX64 = re.compile(r"[0-9a-f]{64}")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def canon(obj):
    """Canonical JSON text, used for every content digest of a record."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def seed_of(text):
    """The exact hash-to-seed conversion: the full 32-byte digest, read as one big-endian integer."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")


def rng_for(text):
    return random.Random(seed_of(text))


def hashed_order(prefix, ids):
    return sorted(ids, key=lambda t: (sha_text(prefix + t), t))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fsync_dir(d):
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_atomic(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fsync_dir(d)


def exclusive_claim(path, obj):
    """Create path only if it does not exist (O_CREAT | O_EXCL), write obj, fsync file and folder. Raises
    FileExistsError if the claim already exists: a claim is never reused or overwritten."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        os.write(fd, (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(d)


_GUARD = {"installed": False, "blocked": set(), "inodes": set(), "allowed": set()}
_EXEC_EVENTS = {"os.exec", "os.posix_spawn", "os.spawn", "os.system", "subprocess.Popen", "pty.spawn"}


def _strings(x):
    if isinstance(x, (str, bytes, os.PathLike)):
        yield os.fsdecode(x)
    elif isinstance(x, (list, tuple)):
        for y in x:
            yield from _strings(y)


def _refused(p):
    rp = os.path.realpath(p)
    if rp in _GUARD["allowed"]:
        return False
    if ANSWER_NAME.search(os.path.basename(p)) or ANSWER_NAME.search(os.path.basename(rp)) or rp in _GUARD["blocked"]:
        return True
    try:
        st = os.stat(p)
    except OSError:
        return False
    return (st.st_dev, st.st_ino) in _GUARD["inodes"]


def _hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        if _refused(p):
            raise PermissionError(f"answer files are unreadable in this process: {p}")
    elif event in _EXEC_EVENTS:
        for s in _strings(args[:3]):
            for part in s.split():
                if ANSWER_NAME.search(part) or os.path.realpath(part) in _GUARD["blocked"]:
                    raise PermissionError(f"answer files are unreadable in this process: {event} {part}")


def install_answer_guard(blocked_paths=()):
    """Make answer files unreadable by this process. An audit hook (which cannot be removed) refuses any open() or
    os.open() of a path whose file name contains "solutions", that resolves to one of blocked_paths, or that is a
    hard link to one of them, and any exec or subprocess whose arguments name such a file. Only a path added to
    allow_after_claim() later (the scorer, after its exclusive claim) is exempt."""
    for p in blocked_paths:
        if not p:
            continue
        rp = os.path.realpath(p)
        _GUARD["blocked"].add(rp)
        try:
            st = os.stat(rp)
            _GUARD["inodes"].add((st.st_dev, st.st_ino))
        except OSError:
            pass
    if not _GUARD["installed"]:
        sys.addaudithook(_hook)
        _GUARD["installed"] = True


_SPAWN_EVENTS = {"os.fork", "os.forkpty", "os.posix_spawn", "os.spawn", "os.exec", "os.system", "subprocess.Popen",
                 "pty.spawn", "_thread.start_new_thread"}


def _deny_hook(event, args):
    if event in _SPAWN_EVENTS:
        raise PermissionError(f"process and thread creation is denied in a Test B arm worker: {event}")


def deny_process_creation():
    """Worker only: refuse every audited process- or thread-creation event with a clear error. The binding control
    is RLIMIT_NPROC = 0 (set before this, and by the guard before exec), which the kernel enforces for routes that
    raise no audit event (multiprocessing's spawn start method, ctypes calls into libc)."""
    sys.addaudithook(_deny_hook)


def allow_after_claim(path):
    """Scorer only: exempt this one answers path, after the exclusive score claim exists."""
    _GUARD["allowed"].add(os.path.realpath(path))


def read_go(path, keys):
    """The exact GO lines: line i is '<keys[i]> <64 lowercase hex>', there are exactly len(keys) lines, and nothing
    else is in the file except one optional final newline."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise SystemExit(f"{os.path.basename(path)}: not plain ASCII")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) != len(keys):
        raise SystemExit(f"{os.path.basename(path)}: {len(lines)} lines, expected exactly {len(keys)}")
    out = {}
    for i, k in enumerate(keys):
        m = re.fullmatch(rf"{re.escape(k)} ([0-9a-f]{{64}})", lines[i])
        if not m:
            raise SystemExit(f"{os.path.basename(path)}: line {i + 1} is not exactly '{k} <sha256>'")
        out[k] = m.group(1)
    return out


def grid_ok(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and 1 <= len(g[0]) <= 30 and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


def shape(g):
    return (len(g), len(g[0]))


def rel(path, repo=REPO):
    """Repository-relative form of a path inside the repository, else the absolute path."""
    ap = os.path.abspath(path)
    return os.path.relpath(ap, repo) if ap.startswith(repo + os.sep) else ap


def absp(path, repo=REPO):
    return path if os.path.isabs(path) else os.path.join(repo, path)
