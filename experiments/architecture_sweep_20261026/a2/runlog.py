"""Run bookkeeping for A2/A3 detached stages: START/EXIT status files, pid, CPU/wall time, and append-only records
in the shared RUN_LEDGER.jsonl (failed and interrupted runs stay in the ledger). Resumable stages skip finished
units by key; a relaunch of the same command resumes.
"""
import atexit
import fcntl
import hashlib
import json
import os
import resource
import signal
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
if EXP not in sys.path:
    sys.path.insert(0, EXP)
from harness import paths as P        # noqa: E402


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_files(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def code_hash(family_dir):
    return sha_files([os.path.join(family_dir, f) for f in os.listdir(family_dir) if f.endswith(".py")])


KIND = {"traces": "prep", "pools": "prep", "labels": "prep", "libraries": "prep", "data": "prep",
        "ranker": "train", "train": "train", "eval_canary": "canary"}


def ledger_append(rec):
    """Helper 1's ledger (harness.ledger.append, shared schema); tests write a local ledger instead."""
    from harness import ledger as LG
    return LG.append(rec, os.environ.get("A2_TEST_LEDGER") or None)


class Run:
    """One detached stage: <status_dir>/<run_id>.START/.EXIT files and START/EXIT rows in the shared ledger
    (fields: ts, run_id, family, kind, status, config_sha, data_sha, code_sha, wall_h, cpu_h, gpu_wall_h,
    gpu_active_h, max_rss_mb, pid, log, cmd, artifact, note)."""

    def __init__(self, family, stage, status_dir, config, resume_cmd, gpu=False, data_sha=None, artifact=None):
        self.family, self.stage, self.status_dir, self.config = family.upper(), stage, status_dir, config
        self.cfg_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
        self.run_id = f"{family}-{stage}-{self.cfg_hash}"
        self.resume_cmd, self.gpu = resume_cmd, gpu
        self.data_sha, self.artifact = data_sha or _splits_sha(), artifact
        self.t0 = time.time()
        self.extra, self.done = {}, False
        dirs = [os.path.join(EXP, "a2")] + ([os.path.join(EXP, "a3")] if family.lower() == "a3" else [])
        self.code_sha = sha_files([os.path.join(d, f) for d in dirs for f in os.listdir(d) if f.endswith((".py", ".sh"))])
        os.makedirs(status_dir, exist_ok=True)

    def _base(self, status):
        ru = resource.getrusage(resource.RUSAGE_SELF)
        ch = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall_h = (time.time() - self.t0) / 3600
        log = self.resume_cmd.split("> ")[-1].split(" ")[0] if "> " in self.resume_cmd else None
        return {"run_id": self.run_id, "family": self.family, "kind": KIND.get(self.stage, "screen"),
                "status": status, "config_sha": self.cfg_hash, "data_sha": self.data_sha, "code_sha": self.code_sha,
                "wall_h": round(wall_h, 4), "cpu_h": round((ru.ru_utime + ru.ru_stime + ch.ru_utime + ch.ru_stime)
                                                          / 3600, 4),
                "gpu_wall_h": round(wall_h, 4) if self.gpu else 0, "gpu_active_h": None,
                "max_rss_mb": round(ru.ru_maxrss / 1024, 1), "pid": os.getpid(), "log": log,
                "cmd": self.resume_cmd, "artifact": self.artifact, "stage": self.stage}

    def start(self):
        rec = dict(self._base("START"), note=json.dumps(self.config, sort_keys=True)[:400])
        with open(os.path.join(self.status_dir, self.run_id + ".START"), "w") as f:
            json.dump(dict(rec, utc=now(), host=socket.gethostname()), f)
        ledger_append(rec)
        atexit.register(self._exit_unclean)
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, self._on_signal)
        return self

    def _on_signal(self, signum, frame):          # noqa: ARG002
        self.finish("TERMINATED", signal=signum)
        os._exit(128 + signum)

    def _exit_unclean(self):
        if not self.done:
            self.finish("EXIT_FAIL", note="exited without finishing (exception or kill)")

    def finish(self, status, **kw):
        if self.done:
            return
        self.done = True
        status = {"OK": "EXIT_OK"}.get(status, status)
        note = kw.pop("note", None) or json.dumps(self.extra, sort_keys=True, default=str)[:1500]
        rec = dict(self._base(status), note=note, **{k: v for k, v in kw.items() if k != "note"})
        with open(os.path.join(self.status_dir, self.run_id + ".EXIT"), "w") as f:
            json.dump(dict(rec, utc=now(), extra=self.extra), f, default=str)
        ledger_append(rec)


def _splits_sha():
    try:
        with open(os.path.join(EXP, "splits", "SPLITS_MANIFEST.json"), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return None


def append_jsonl(path, rec):
    with P.open_allowed(path, mode="a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with P.open_allowed(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:            # a torn last line after a kill: skipped, recomputed
                    pass
    return out
