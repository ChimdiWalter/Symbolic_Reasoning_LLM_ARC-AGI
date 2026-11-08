"""Real combinational benchmark functions: the two-level PLA files of the Espresso example suite (MCNC benchmarks).

Read straight from the downloaded archive (never extracted). Espresso's default file type fd is used: output '1' puts
the cube in the on-set, '-' or '2' in the don't-care set, '0' and '~' mean nothing. Eligible items: files with 6 to 12
inputs (so the full truth table is the exact check); outputs that are completely specified (empty don't-care set) and
not constant. Identical files and identical output functions are kept once, the first in sorted order.
"""
import hashlib
import tarfile

from .core import essential, masks


class PlaError(ValueError):
    pass


def read_archive(path, subdir="examples"):
    """Yield (name, bytes) for the files directly inside <top>/<subdir>/ of the archive."""
    with tarfile.open(path, "r:gz") as tf:
        for m in sorted(tf.getmembers(), key=lambda m: m.name):
            parts = m.name.split("/")
            if m.isfile() and len(parts) == 3 and parts[1] == subdir:
                yield parts[2], tf.extractfile(m).read()


def parse(text):
    """Return (n_in, n_out, cubes, output_labels); cubes are (input string, output string)."""
    n = m = None
    cubes, labels, buf = [], None, ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("."):
            f = line.split()
            if f[0] == ".i":
                n = int(f[1])
            elif f[0] == ".o":
                m = int(f[1])
            elif f[0] == ".ob":
                labels = f[1:]
            elif f[0] in (".e", ".end"):
                break
            elif f[0] in (".type", ".mv", ".kiss", ".phase", ".pair", ".symbolic", ".label"):
                raise PlaError("unsupported directive " + f[0])
            continue
        if n is None or m is None:
            raise PlaError("cube before .i/.o")
        buf += "".join(ch for ch in line if not ch.isspace() and ch != "|")
        while len(buf) >= n + m:
            cubes.append((buf[:n], buf[n:n + m]))
            buf = buf[n + m:]
    if n is None or m is None:
        raise PlaError("missing .i/.o")
    if buf:
        raise PlaError("cube width")
    return n, m, cubes, labels


def tables(n, m, cubes):
    """On-set and don't-care set of every output, as truth-table integers."""
    full, V, NV, _ = masks(n)
    on, dc = [0] * m, [0] * m
    for ins, outs in cubes:
        c = full
        for v, ch in enumerate(ins):
            if ch == "1":
                c &= V[v]
            elif ch == "0":
                c &= NV[v]
            elif ch not in "-2":
                raise PlaError("input character " + ch)
        for j, ch in enumerate(outs):
            if ch in "14":
                on[j] |= c
            elif ch in "-2":
                dc[j] |= c
            elif ch not in "0~3":
                raise PlaError("output character " + ch)
    return on, dc


def items(path, n_min=6, n_max=12):
    """All eligible circuit items and an account of every exclusion."""
    out, account, seen_files, seen_funcs = [], [], {}, {}
    for name, data in read_archive(path):
        h = hashlib.sha256(data).hexdigest()
        if h in seen_files:
            account.append({"file": name, "excluded": "identical file to " + seen_files[h]})
            continue
        seen_files[h] = name
        try:
            n, m, cubes, labels = parse(data.decode("latin-1"))
        except PlaError as e:
            account.append({"file": name, "excluded": "parse: " + str(e)})
            continue
        if not n_min <= n <= n_max:
            account.append({"file": name, "excluded": f"{n} inputs outside {n_min}..{n_max}"})
            continue
        try:
            on, dc = tables(n, m, cubes)
        except PlaError as e:
            account.append({"file": name, "excluded": "parse: " + str(e)})
            continue
        full = masks(n)[0]
        kept = 0
        for j in range(m):
            iid = f"pla/{name}/{j}"
            if dc[j]:
                account.append({"item": iid, "excluded": "don't-care set not empty"})
            elif on[j] in (0, full):
                account.append({"item": iid, "excluded": "constant"})
            elif (n, on[j]) in seen_funcs:
                account.append({"item": iid, "excluded": "same function as " + seen_funcs[(n, on[j])]})
            else:
                seen_funcs[(n, on[j])] = iid
                out.append({"id": iid, "domain": "circuit", "cluster": "pla/" + name, "n": n, "T": on[j],
                            "support": len(essential(on[j], n)), "ones": on[j].bit_count(),
                            "label": labels[j] if labels and j < len(labels) else None})
                kept += 1
        account.append({"file": name, "inputs": n, "outputs": m, "kept": kept})
    return out, account
