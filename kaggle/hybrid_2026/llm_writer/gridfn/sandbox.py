"""The parent side of the isolated execution: one persistent worker process (worker.py) per Python process.

`run(src, grid, limits=None, cpu_s=None)` sends one program and one grid to the worker and returns its reply
(ok, out, kind, message, line, steps, cpu). The worker is started on first use with
    <python> -S -B -P -m <package>.worker '<config>'
(no site packages, no bytecode written, no unsafe path entry), stdin/stdout pipes only, stderr discarded, cwd `/`,
a new session, and an environment holding only PYTHONPATH (this package's root), a fixed hash seed and locale
settings. The worker sets its own rlimits (worker.py). The parent enforces a wall-clock backstop per grid
(wall_base + wall_factor * cpu_s): on expiry the worker is killed (by its pid only) and the grid gets Timeout; a
dead or killed worker is replaced on the next call. The worker is also replaced once its total CPU time passes
`recycle_cpu_s`, so its RLIMIT_CPU is never reached in normal use. If the caller is interrupted while waiting (for
example by its own alarm signal), the worker is killed before the exception propagates, so replies never get out
of step. A forked child never uses its parent's worker. Calls are serialized by a lock.
"""
import atexit
import json
import os
import select
import subprocess
import sys
import threading
import time

from . import interp as I

PKG = __name__.rsplit(".", 1)[0]                               # e.g. llm_writer.gridfn
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[".."] * PKG.count(".") + [".."]))
MAX_REPLY = 1 << 22


class Sandbox:
    def __init__(self, as_mb=512, cpu_total_s=120, recycle_cpu_s=60.0, cpu_s=5.0, wall_base=10.0, wall_factor=3.0,
                 limits=None, python=None):
        self.cfg = {"as_mb": as_mb, "cpu_total_s": cpu_total_s, "recursion": 100000}
        self.recycle_cpu_s, self.cpu_s = recycle_cpu_s, cpu_s
        self.wall_base, self.wall_factor = wall_base, wall_factor
        self.limits = limits or I.Limits()
        self.python = python or sys.executable
        self.proc, self.pid_owner, self.buf, self.n = None, None, b"", 0
        self.lock = threading.Lock()
        self.stats = {"spawns": 0, "kills": 0, "requests": 0, "wall_timeouts": 0, "crashes": 0}

    # ---------- process management
    def _argv(self):
        flags = ["-S", "-B"] + (["-P"] if sys.version_info >= (3, 11) else [])
        return [self.python] + flags + ["-m", PKG + ".worker", json.dumps(self.cfg)]

    def _env(self):
        # the worker runs with -S (no site processing); gridfn-2 needs numpy, so only numpy's own installation
        # directory is added to the path (programs cannot import anything: the checker lowers or refuses imports)
        import numpy
        np_dir = os.path.dirname(os.path.dirname(os.path.abspath(numpy.__file__)))
        return {"PYTHONPATH": ROOT + os.pathsep + np_dir, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
                "PYTHONIOENCODING": "utf-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin",
                # numpy (gridfn-2) must not start BLAS thread pools inside the address-space and process limits
                "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1"}

    def _spawn(self):
        self.proc = subprocess.Popen(self._argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, cwd="/", env=self._env(), close_fds=True,
                                     start_new_session=True, bufsize=0)
        self.pid_owner, self.buf = os.getpid(), b""
        self.stats["spawns"] += 1
        ready = self._readline(self.wall_base + 20.0)
        if json.loads(ready).get("ready") is not True:
            raise OSError("worker did not start")

    def _alive(self):
        if self.proc is not None and self.pid_owner != os.getpid():   # inherited through fork: not ours
            for f in (self.proc.stdin, self.proc.stdout):
                try:
                    f.close()
                except OSError:
                    pass
            self.proc = None
        return self.proc is not None and self.proc.poll() is None

    def kill(self):
        p, self.proc, self.buf = self.proc, None, b""
        if p is None:
            return
        if p.poll() is None:
            self.stats["kills"] += 1
            try:
                p.kill()
            except OSError:
                pass
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        for f in (p.stdin, p.stdout):
            try:
                f.close()
            except OSError:
                pass

    def close(self):
        p = self.proc
        if p is None or self.pid_owner != os.getpid():
            return
        try:
            p.stdin.close()
            p.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.kill()

    def _readline(self, timeout):
        fd = self.proc.stdout.fileno()
        deadline = time.monotonic() + timeout
        while b"\n" not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError()
            r, _, _ = select.select([fd], [], [], left)
            if not r:
                continue
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                raise EOFError()
            self.buf += chunk
            if len(self.buf) > MAX_REPLY:
                raise EOFError()
        line, _, self.buf = self.buf.partition(b"\n")
        return line

    # ---------- one grid
    def run(self, src, grid, limits=None, cpu_s=None):
        limits = limits or self.limits
        cpu_s = self.cpu_s if cpu_s is None else cpu_s
        with self.lock:
            return self._run(src, grid, limits, cpu_s)

    def _fail(self, kind, message):
        return {"ok": False, "out": None, "kind": kind, "message": message, "line": None, "steps": 0, "cpu": 0.0}

    def _run(self, src, grid, limits, cpu_s):
        self.stats["requests"] += 1
        try:
            if not self._alive():
                self.kill()
                self._spawn()
        except (OSError, ValueError, TimeoutError, EOFError) as e:
            self.kill()
            return self._fail("RuntimeFault", f"sandbox unavailable: {type(e).__name__}")
        self.n += 1
        req = json.dumps({"id": self.n, "src": src, "grid": grid, "limits": limits.as_dict(), "cpu_s": cpu_s},
                         separators=(",", ":")).encode() + b"\n"
        try:
            self.proc.stdin.write(req)
            self.proc.stdin.flush()
            line = self._readline(self.wall_base + self.wall_factor * cpu_s)
            rep = json.loads(line)
            if rep.get("id") != self.n:
                raise EOFError()
        except TimeoutError:
            self.stats["wall_timeouts"] += 1
            self.kill()
            return self._fail("Timeout", "the program ran too long (wall clock); it was stopped")
        except (EOFError, OSError, ValueError):
            code = self.proc.poll() if self.proc is not None else None
            self.stats["crashes"] += 1
            self.kill()
            if code is not None and code in (-24, -9):           # SIGXCPU, or killed for CPU or memory
                return self._fail("Timeout", "the program used too much CPU time; it was stopped")
            return self._fail("RuntimeFault", "the program crashed the execution worker (too much memory or "
                              "too deep data?)")
        except BaseException:
            self.kill()                                          # keep replies in step, then let it propagate
            raise
        if rep.get("cpu_total", 0.0) > self.recycle_cpu_s:
            self.close()
        return {k: rep.get(k) for k in ("ok", "out", "kind", "message", "line", "steps", "cpu")}


_DEFAULT = None
_DEFAULT_LOCK = threading.Lock()


def default():
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = Sandbox()
            atexit.register(_DEFAULT.close)
        return _DEFAULT


def configure(**kw):
    """Replace the default sandbox (for example with other limits); closes the old worker."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is not None:
            _DEFAULT.close()
        _DEFAULT = Sandbox(**kw)
        atexit.register(_DEFAULT.close)
        return _DEFAULT
