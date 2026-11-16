"""Fast tests of stage A on invented cases. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python -s -B -m pytest -q -p no:cacheprovider experiments/visible_failure_20261113/tests
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import pytest

import frozen
import dslx
import gen
import search as S
import presets_vf1 as V
import vsearch as VS
import consumers as C
import gate as G
import library as LIB
import episode as E
import summarize as SM
import run_stage_a as R
import core

L = dslx.load()
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = [sys.executable, "-s", "-B"]
ENV = dict(os.environ, PYTHONHASHSEED="0")


def make_episode(X, cands, hide="self", outdir=None, B=1.0):
    """An episode set up with a fixed ordered candidate list (a test hook: the seeded rule is tested separately).
    The three roles take the first three candidates that pass the gate on the setup examples."""
    old = C.candidate_posts
    C.candidate_posts = lambda X_, outs, closure=None: dict(cands=list(cands), n_raw=len(cands))
    try:
        ep = E.Episode(X, outdir or tempfile.mkdtemp(), B, None, hide)
        assert ep.setup() is None, ep.res
    finally:
        C.candidate_posts = old
    return ep


ROT = ("tophalf", "hfrontier", "vfrontier")


# ---------------------------------------------------------------- start-up guards
def test_frozen_hashes_checked_and_tamper_refused(tmp_path):
    got = frozen.verify()
    assert set(got) >= set(frozen.REQUIRED)
    shutil.copy(os.path.join(frozen.CORE_DIR, "FREEZE.json"), tmp_path / "FREEZE.json")
    for n in frozen.REQUIRED + frozen.ALSO:
        shutil.copy(os.path.join(frozen.CORE_DIR, n), tmp_path / n)
    assert frozen.verify(str(tmp_path))
    with open(tmp_path / "gen.py", "a") as f:
        f.write("\n# changed\n")
    with pytest.raises(SystemExit):
        frozen.verify(str(tmp_path))


def test_dev_roster_by_rule_and_flags():
    ok = [o for o in L["lib_order"] if gen.gen_examples(o)["status"] == "ok"]
    assert V.derive_dev_extra(ok, dslx.held_out_names()) == V.DEV_EXTRA_OPS
    assert len(V.DEV_ROSTER) == 20 and len(set(V.DEV_ROSTER)) == 20
    assert not (set(V.DEV_EXTRA_OPS) & set(dslx.held_out_names()))
    assert len(ok) == 145


# ---------------------------------------------------------------- vsearch
@pytest.mark.parametrize("X,hidden,size", [("rot180", ["rot180"], 3), ("lefthalf", ["lefthalf"], 3),
                                           ("righthalf", ["righthalf"], 3), ("other", ["other"], 4)])
def test_vsearch_with_plain_equality_agrees_with_frozen_search(X, hidden, size):
    g = gen.gen_examples(X)["examples"][:6]
    ns = dslx.library_namespace(hidden)
    ops, leaves, Y = core.build(X, set(hidden), g, ns)
    a = S.search(ops, leaves, Y, 40, size, 300, 250000)
    b = VS.search(ops, leaves, VS.plain_accept(Y), len(Y), 40, size, 300, 250000)
    assert a["found"] is not None and b["found"] is not None
    assert a["found"][0] == b["found"][0] and a["found"][1] == b["found"][1]
    assert a["bank"] == b["bank"] and a["stop"] == b["stop"] == "found"
    c = VS.search(ops, leaves, VS.plain_accept(Y), len(Y), 40, size, 300, 250000, collect=5)
    assert c["hits"][0][0] == a["found"][0] and len(c["hits"]) >= 1


def test_vsearch_negative_agreement_and_collect_cap():
    g = gen.gen_examples("hmirror")["examples"][:3]
    fam = L["fam_of"]["hmirror"]
    ns = dslx.library_namespace(fam)
    ops, leaves, Y = core.build("hmirror", set(fam), g, ns)
    a = S.search(ops, leaves, Y, 20, 2, 300, 250000)
    b = VS.search(ops, leaves, VS.plain_accept(Y), len(Y), 20, 2, 300, 250000)
    assert a["found"] == b["found"] and a["stop"] == b["stop"] and a["bank"] == b["bank"]
    # an acceptance that takes everything of size >= 1 collects exactly k hits
    r = VS.search(ops, leaves, lambda v: True, 3, 20, 3, 300, 250000, collect=7)
    assert len(r["hits"]) == 7 and r["stop"] == "collected"


# ---------------------------------------------------------------- generator, consumers, record sets
def test_generator_66_keeps_the_first_36_examples():
    a = gen.gen_examples("rot180")["examples"]
    b = gen.gen_examples("rot180", n_total=V.N_GEN)
    assert b["status"] == "ok" and len(b["examples"]) == 66
    assert repr(b["examples"][:36]) == repr(a)


def test_target_that_cannot_give_66_examples_is_excluded(monkeypatch):
    monkeypatch.setattr(E.gen, "gen_examples", lambda X, n_total=36: dict(status="excluded", reason="only 40 of 66 valid examples in 4000 draws", examples=[]))
    r = E.Episode("rot180", tempfile.mkdtemp(), 1.0).setup()
    assert r["status"] == "excluded" and r["reason"].startswith("generator:") and "66" in r["reason"]


def test_candidate_posts_seeded_outside_closure_and_distinct():
    g = gen.gen_examples("rot180", n_total=66)["examples"]
    outs = [o for _, o in g[V.SETUP_FROM:V.SETUP_TO]]
    a, b = C.candidate_posts("rot180", outs), C.candidate_posts("rot180", outs)
    assert a == b and len(a["cands"]) >= 3 and len(set(a["cands"])) == len(a["cands"])
    assert not (set(a["cands"]) & C.closure_of("rot180")) and "identity" not in a["cands"]
    full = dslx.full_ns()
    for p in a["cands"][:5]:
        assert len({dslx.canon(full[p](o)) for o in outs}) >= 2 and len(L["sigs"][p]) == 1


ROT = ("tophalf", "hfrontier", "vfrontier")


def test_post_that_hides_x_is_skipped_and_next_taken():
    # numcolors never changes under rot180: a trivial repair passes on the setup examples, so it is skipped
    ep = make_episode("rot180", ("numcolors",) + ROT)
    c = ep.res["consumers"]
    assert c["post"] == dict(acq="tophalf", adm="hfrontier", reuse="vfrontier")
    assert c["n_skipped"] >= 1 and c["skipped"][0]["post"] == "numcolors" and "trivial" in c["skipped"][0]["reason"]
    assert all(c["roles"][k]["distinct_final_outputs_on_setup_examples"] >= 2 for k in ("acq", "adm", "reuse"))
    assert ep.F is None                                   # nothing of the final panel exists yet


@pytest.mark.parametrize("cands", [("tophalf", "hfrontier"), ("numcolors", "tophalf", "hfrontier"), ()])
def test_fewer_than_three_eligible_posts_excludes_the_target_never_pads(cands):
    old = C.candidate_posts
    C.candidate_posts = lambda X, outs, closure=None: dict(cands=list(cands), n_raw=len(cands))
    try:
        r = E.Episode("rot180", tempfile.mkdtemp(), 1.0, None, "self").setup()
    finally:
        C.candidate_posts = old
    assert r["status"] == "excluded" and r["reason"].startswith("fewer than three consumers")


def test_pooled_tuples_unique_disjoint_from_generator_tuples_and_between_slices():
    for X in ("rot180", "width", "color"):
        ep = make_episode(X, C.candidate_posts(X, [o for _, o in gen.gen_examples(X, n_total=66)["examples"][18:36]], dslx.reverse_closure(L["fam_of"][X]))["cands"], "family")
        gk = C.gen_keys(ep.g)
        keys = [dslx.canon(a) for a in ep.seq]
        assert len(keys) == len(set(keys)) and not (set(keys) & gk)
        sl = [{dslx.canon(a) for a in x} for x in (ep.slice_R, ep.slice_A, ep.slice_UA, ep.slice_B, ep.slice_UB)]
        for i in range(5):
            for j in range(i + 1, 5):
                assert not (sl[i] & sl[j])
        assert sum(len(x) for x in sl) <= len(keys) and len(sl[1]) == len(sl[2]) and len(sl[3]) == len(sl[4])   # UA is as large as A, UB as B


def test_record_sets_are_disjoint_and_the_grid_is_nested():
    assert (V.N_ACQ, V.GRID_FROM, V.N_GRID, V.SUPPORT_FROM, V.SETUP_FROM, V.SETUP_TO, V.FINAL_FROM, V.N_FINAL_GEN) == (3, 3, 12, 15, 18, 36, 36, 30)
    assert V.GRID_FROM + V.N_GRID == V.SUPPORT_FROM and V.SUPPORT_FROM + V.N_SUPPORT == V.SETUP_FROM and V.FINAL_FROM + V.N_FINAL_GEN == V.N_GEN
    assert V.GRID_NS == (3, 6, 12) and V.RULE_N == 6
    ep = make_episode("rot180", ROT)
    ep.open_admission()
    key = lambda xs: {dslx.canon(x) for x in xs}
    gsets = [key([a for a, _ in ep.g[i:j]]) for i, j in ((0, 3), (3, 15), (15, 18), (18, 36), (36, 66))]
    for i in range(5):
        for j in range(i + 1, 5):
            assert not (gsets[i] & gsets[j])
    assert key(ep.acq_args) == gsets[0] and key(ep.adm["gen_args"]) == gsets[1] and len(ep.adm["pool_args"]) == 12
    assert not (key(ep.adm["pool_args"]) & key(ep.slice_B)) and not (key(ep.adm["pool_args"]) & key(ep.slice_R))
    for tree in (("L", "rot90", ("L", "rot90", ("P", "grid"))), ("P", "grid"), ("L", "hmirror", ("P", "grid"))):
        a = ep.admission(ep.cand_fn(tree), tree)
        for st in ("same_kind", "adm_generator", "adm_pooled"):
            v = [a[st][n] for n in ("3", "6", "12")]
            assert v == sorted(v, reverse=True)                  # nested: passing at 12 implies passing at 6 and 3
        assert a["rule"] == (a["adm_both"]["6"] and a["bank_ok"]) and a["rule_standard"].startswith("adm_both@6")
        assert all(a["adm_both"][n] == (a["adm_generator"][n] and a["adm_pooled"][n]) for n in ("3", "6", "12"))
    a = ep.admission(ep.cand_fn(("L", "rot90", ("L", "rot90", ("P", "grid")))), ("P", "grid"))
    assert a["rule"] and a["adm_pooled"] == {"3": True, "6": True, "12": True} and a["adm_both"] == {"3": True, "6": True, "12": True}


def test_rule_needs_both_kinds_of_evidence(monkeypatch):
    ep = make_episode("rot180", ROT)
    ep.open_admission()
    tree = ("L", "rot90", ("L", "rot90", ("P", "grid")))
    fn = ep.cand_fn(tree)

    def fake(pool_ok, gen_ok):
        def ml(f, args, xo, role, whole=False):
            ok = pool_ok if args is ep.adm["pool_args"] else gen_ok
            return [ok] * len(args), None, 0
        return ml
    for pool_ok, gen_ok, want in ((True, False, False), (False, True, False), (True, True, True), (False, False, False)):
        monkeypatch.setattr(ep, "match_list", fake(pool_ok, gen_ok))
        a = ep.admission(fn, tree)
        assert a["adm_pooled"]["6"] is pool_ok and a["adm_generator"]["6"] is gen_ok
        assert a["adm_both"]["6"] is want and a["rule"] is want                  # passing one kind only is not admitted


def test_setup_excludes_target_with_too_few_usable_pooled_inputs(monkeypatch):
    real = C.stream_usable

    def cut_adm(k_adm, k_final):
        def f(X, argsets, post_fns=(), cpu=20):
            out = real(X, argsets, post_fns, cpu)
            return out[:k_adm] if len(post_fns) == 1 else out[:k_final]
        return f
    old = C.candidate_posts
    C.candidate_posts = lambda X, outs, closure=None: dict(cands=list(ROT), n_raw=3)
    try:
        for k_adm, k_fin, ok in ((11, 99, False), (12, 29, False), (12, 30, True)):
            monkeypatch.setattr(C, "stream_usable", cut_adm(k_adm, k_fin))
            r = E.Episode("rot180", tempfile.mkdtemp(), 1.0, None, "self").setup()
            if ok:
                assert r is None
            else:
                assert r["status"] == "excluded" and r["reason"].startswith("too few usable pooled inputs") and "draws" in r["reason"]
    finally:
        C.candidate_posts = old


def test_late_shortage_of_stream_a_is_flagged_never_excludes():
    ep = make_episode("rot180", ROT)
    ep.slice_A = []
    ep.open_admission()
    assert ep.res["admission_evidence"]["pooled_short"] is True and ep.res.get("status") != "excluded"


# ---------------------------------------------------------------- gate
def _envs(fam):
    ns = dslx.library_namespace(fam)
    return C.make_env(ns), C.make_env(dslx.full_ns()), ns


def test_gate_accepts_normal_and_rejects_unexercising_target():
    X = "rot180"
    g = [a for a, _ in gen.gen_examples(X)["examples"]]
    el, ef, ns = _envs(L["fam_of"][X])
    ok = G.check(X, "tophalf", g[:3], el, ef, ns["tophalf"])
    assert ok["ok"] and ok["trivial_passing"] == []
    bad = G.check(X, "numcolors", g[:3], el, ef, ns["numcolors"])          # rot180 never changes the number of colours
    assert not bad["ok"] and "arg:grid" in bad["trivial_passing"]
    same3 = G.check(X, "tophalf", [g[0]] * 3, el, ef, ns["tophalf"])      # examples that never vary: a constant repair passes
    assert not same3["ok"] and any(t.startswith("const") for t in same3["trivial_passing"])


def test_gate_lesion_must_fail():
    X = "rot180"
    g = [a for a, _ in gen.gen_examples(X)["examples"]][:3]
    _, ef, _ = _envs([])
    r = G.check(X, "tophalf", g, ef, ef, dslx.full_ns()["tophalf"])      # nothing hidden: the "lesioned" consumer does not fail
    assert not r["ok"] and any("lesioned consumer does not fail" in f for f in r["failed"])


# ---------------------------------------------------------------- known acquisition, admission, library, final
def _first_fit(ep, budget=30, size=3, collect=0):
    ex = list(zip(ep.acq_args, ep.acq_final))
    ops, leaves, Y = ep.build(ex, ep.hidden, ep.ns_les)
    acc = E.post_accept(ep.post_les["acq"], Y)
    return VS.search(ops, leaves, acc, len(Y), budget, size, V.MAX_FN, V.MAX_BANK, collect=collect)


def test_known_acquisition_end_to_end_and_family_hidden_not_acquired():
    out = tempfile.mkdtemp()
    ep = make_episode("rot180", ROT, "self", out)
    r = _first_fit(ep)
    assert r["found"] and r["found"][0] == "rot90(rot90(grid))"
    ep.open_admission()
    rec = ep.admit("V", r["found"][2])
    assert rec["admitted"] and rec["library"]["mode"] == "0o444"
    ep.open_final()
    ep.final_eval_candidate(rec, r["found"][2])
    assert rec["correct"] and rec["reused"] and rec["task_acq_exact"]
    lib = rec["library"]
    path = os.path.join(out, lib["path"])
    assert lib["hash_ok_before"] and lib["hash_ok_after"] and not (os.stat(path).st_mode & stat.S_IWUSR)
    # the whole family hidden: rot90 is gone, so the two-turn rebuild is impossible and nothing is acquired
    epf = make_episode("rot180", ROT, "family", tempfile.mkdtemp())
    rf = _first_fit(epf, budget=15, size=3)
    assert not (rf["found"] and rf["found"][0] == "rot90(rot90(grid))")
    obs = G.run_lesioned("rot180", "tophalf", ep.acq_args[0], ep.env_les)
    assert obs["failed"] and obs["error_type"] == "NameError" and obs["missing_name"] == "rot180"


def test_admission_rule_rejects_wrong_repair_that_fits_the_acquisition_examples():
    out = tempfile.mkdtemp()
    ep = make_episode("rot180", ROT, "self", out)
    grids = [tuple(tuple([c] * 5) for _ in range(5)) for c in (1, 2, 3)]      # uniform grids: every flip looks alike
    ep.acq_args = [(g,) for g in grids]
    ep.acq_final = [C.apply_post(ep.post_full["acq"], ep.full["rot180"](*a)) for a in ep.acq_args]
    r = _first_fit(ep, size=2)
    assert r["found"] and r["found"][0] == "grid"                         # fits the three examples, but is wrong
    ep.open_admission()
    rec = ep.admit("V", r["found"][2])
    assert rec["admission"]["none"] and not rec["admitted"] and rec["admission"]["adm_both"]["6"] is False and "library" not in rec
    assert not os.path.exists(os.path.join(out, "library"))
    ep.open_final()
    ep.final_eval_candidate(rec, r["found"][2])
    assert not rec["correct"] and not rec["reused"]


class _FakeSearch:
    """Stands in for the searches of one episode so that the candidate order is controlled."""
    def __init__(self, hits):
        self.hits = hits

    def v(self, examples, budget, collect, post_role):
        return dict(found=self.hits[0][:3] if self.hits else None, hits=list(self.hits), stop="collected", level=3, bank=10,
                    function_cap_reached=False, cpu_s=0.2)

    @staticmethod
    def none(*a, **k):
        return dict(found=None, stop="size_exhausted", level=2, bank=1, function_cap_reached=False, cpu_s=0.01)


def _patched_run(monkeypatch, hits, B=0.5, hook=None):
    fake = _FakeSearch(hits)
    monkeypatch.setattr(E.Episode, "search_v", lambda self, ex, b, col, role: fake.v(ex, b, col, role))
    monkeypatch.setattr(E.Episode, "search_s", lambda self, *a, **k: fake.none())
    monkeypatch.setattr(E.Episode, "search_t", lambda self, *a, **k: fake.none())
    monkeypatch.setattr(C, "candidate_posts", lambda X, outs, closure=None: dict(cands=list(ROT), n_raw=3))
    if hook:
        monkeypatch.setattr(E.Episode, "open_final", hook(E.Episode.open_final))
    out = tempfile.mkdtemp()
    return out, E.run_target("rot180", out, B, "self")


WRONG = ("wrong", 2, ("L", "hmirror", ("P", "grid")), 0.01, 5)
RIGHT = ("rot90(rot90(grid))", 3, ("L", "rot90", ("L", "rot90", ("P", "grid"))), 0.05, 9)


def test_admission_ends_the_candidate_no_second_candidate_from_admission_results(monkeypatch):
    out, r = _patched_run(monkeypatch, [WRONG, RIGHT])
    v = r["arms"]["V"]
    assert v["expr"] == "hmirror(grid)" and v["admitted"] is False and "library" not in v     # the first fit is frozen
    assert not os.path.exists(os.path.join(out, "library", "rot180__V.json"))
    assert r["arms"]["V"]["n_hits"] == 2 and r["selection"]["fits"][1]["admitted"] is True    # measured, never selected
    assert r["selection"]["first_fit"]["admitted"] is False and v["task_acq_exact"] is False and r["primary"]["acquisition_task"]["V"] is False


def test_final_inputs_are_not_read_before_the_library_is_sealed(monkeypatch):
    seen = {}

    def hook(orig):
        def wrapper(self):
            seen["F_before"] = self.F
            seen["library_files"] = sorted(os.listdir(os.path.join(self.outdir, "library"))) if os.path.isdir(os.path.join(self.outdir, "library")) else []
            seen["events"] = [json.loads(x) for x in open(self.j.path)]
            with pytest.raises(RuntimeError):
                self.exact(self.cand_fn(("P", "grid")), None)          # any read of the final panel before opening fails
            return orig(self)
        return wrapper
    out, r = _patched_run(monkeypatch, [RIGHT], hook=hook)
    assert seen["F_before"] is None and seen["library_files"] == ["rot180__V.json"]
    names = [e["name"] for e in seen["events"] if e["event"] == "seal"]
    for n in ("setup_set", "acquisition_set", "candidates", "admission_set", "library_V", "reuse_support_set"):
        assert n in names
    assert names.index("candidates") < names.index("admission_set") < names.index("library_V") < names.index("reuse_support_set")
    assert "final_set" not in names and not any(e["event"].startswith("outcome_") for e in seen["events"])
    assert r["arms"]["V"]["admitted"] and r["arms"]["V"]["correct"] and r["arms"]["V"]["reused"] and r["primary"]["acquisition_task"]["V"]
    names = [json.loads(x) for x in open(os.path.join(out, "journal", "rot180.jsonl"))]
    assert [e["name"] for e in names if e["event"] == "seal"][-1] == "final_set"


def test_failure_at_final_evaluation_never_changes_the_record_set_or_candidate(monkeypatch):
    out, r = _patched_run(monkeypatch, [RIGHT])
    assert r["arms"]["V"]["expr"] == "rot90(rot90(grid))" and r["status"] == "done"
    assert r["gate"]["attempts"][0]["source"] == "generator"             # no redraw after the fact


# ---------------------------------------------------------------- library and preservation bank
def test_library_file_read_only_and_hash_checked(tmp_path):
    tree = ("L", "rot90", ("L", "rot90", ("P", "grid")))
    p = str(tmp_path / "a.json")
    name, sha = LIB.write_library_file(p, "t", "rot180", tree, {"a": 1}, {"b": 2})
    assert name.startswith("vf_") and "rot180" not in open(p).read().replace('"signature"', "")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o444 and LIB.verify_library_file(p, sha)
    body = json.load(open(p))
    assert body["version"] == 1 and body["expression"] == "rot90(rot90(grid))" and body["uses"] == ["rot90"]
    assert len(body["acquisition_record_sha256"]) == 64
    fn = LIB.load_operation(p, sha, dslx.library_namespace(["rot180"]))[1]
    g = gen.gen_examples("rot180")["examples"][0]
    assert fn(*g[0]) == g[1]
    os.chmod(p, 0o644)
    assert not LIB.verify_library_file(p, sha)
    with pytest.raises(ValueError):
        LIB.load_operation(p, sha, dslx.library_namespace(["rot180"]))
    os.chmod(p, 0o444)
    with pytest.raises(ValueError):
        LIB.load_operation(p, "0" * 64, dslx.library_namespace(["rot180"]))


def test_preservation_bank_counts_only_successful_entries_and_needs_one():
    ns = dslx.library_namespace(L["fam_of"]["rot180"])
    base = C.bank_baseline(ns)
    assert len(base) > 0 and C.bank_check(ns, "vf_new", lambda g: g, base)
    assert not C.bank_check(ns, "tophalf", lambda g: g, base)                  # a name clash
    ns2 = dict(ns)
    ns2["height"] = lambda g: (_ for _ in ()).throw(ValueError("raises"))      # an entry that raises is not preserved behaviour
    base2 = C.bank_baseline(ns2)
    assert all(o != "height" for o, _, _ in base2) and 0 < len(base2) < len(base)
    assert C.bank_check(ns2, "vf_new", lambda g: g, base2)
    assert C.bank_baseline({}) == [] and not C.bank_check({}, "vf_new", lambda g: g, [])   # no successful entry: not valid
    broken = dict(ns)
    broken["width"] = lambda g: 0                                              # changes behaviour of a baseline entry
    assert not C.bank_check(broken, "vf_new", lambda g: g, base)


def test_target_with_an_empty_preservation_bank_is_excluded(monkeypatch):
    monkeypatch.setattr(E.C, "bank_baseline", lambda ns: [])
    r = E.Episode("rot180", tempfile.mkdtemp(), 1.0).setup()
    assert r["status"] == "excluded" and "preservation bank" in r["reason"]


# ---------------------------------------------------------------- receipts and refusals
def test_second_all_roster_receipt_refused(tmp_path):
    p1 = R.ensure_receipt(str(tmp_path), "/tmp/out_a", "f" * 64)
    assert os.path.exists(p1)
    assert R.ensure_receipt(str(tmp_path), "/tmp/out_a", "f" * 64) == p1      # same folder: resume
    with pytest.raises(SystemExit):
        R.ensure_receipt(str(tmp_path), "/tmp/out_b", "f" * 64)


def _copy_exp(tmp_path, protocol=True):
    """A private copy of the stage A folder (so freezes and receipts never touch the real folder)."""
    d = tmp_path / "expcopy"
    shutil.copytree(HERE, d, ignore=shutil.ignore_patterns("dev_out*", "__pycache__", "RECEIPT*", "PROTOCOL.md"))
    if protocol:
        (d / "PROTOCOL.md").write_text("test protocol\n")
    return d


def _run(args, env=None, base=None, **kw):
    return subprocess.run(PY + [os.path.join(str(base or HERE), "run_stage_a.py")] + args, env=env or ENV, capture_output=True,
                          text=True, cwd=tempfile.gettempdir(), timeout=300, **kw)


def test_refusal_paths_in_a_fresh_process(tmp_path):
    exp = _copy_exp(tmp_path, protocol=False)
    out = str(tmp_path / "out")
    r = _run([out, "--roster", "all"], base=exp)
    assert r.returncode != 0 and "freeze" in (r.stderr + r.stdout) and not os.path.exists(out)
    fz = tmp_path / "ok.json"
    r = _run(["--make-freeze", str(fz)], base=exp)                      # no PROTOCOL.md: refused
    assert r.returncode != 0 and "PROTOCOL.md" in (r.stderr + r.stdout) and not fz.exists()
    (exp / "PROTOCOL.md").write_text("test protocol\n")
    assert _run(["--make-freeze", str(fz)], base=exp).returncode == 0
    body = json.load(open(fz))
    rels = [k.split("/")[-1] for k in body["files"]]
    for need in ("PROTOCOL.md", "README.md", "test_stage_a.py", "conftest.py", "episode.py"):
        assert need in rels
    bad = tmp_path / "bad.json"
    k = sorted(body["files"])[0]
    body["files"][k] = "0" * 64
    json.dump(body, open(bad, "w"))
    r = _run([out, "--roster", "all", "--freeze", str(bad)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in (r.stderr + r.stdout) and not os.path.exists(out)
    for tail in ("README.md", "PROTOCOL.md", "test_stage_a.py"):
        body = json.load(open(fz))
        body["files"].pop([k for k in body["files"] if k.endswith(tail)][0])
        json.dump(body, open(bad, "w"))
        r = _run([out, "--roster", "all", "--freeze", str(bad)], base=exp)
        assert r.returncode != 0 and "does not cover" in (r.stderr + r.stdout)
    (exp / "README.md").write_text("changed after the freeze\n")
    r = _run([out, "--roster", "all", "--freeze", str(fz)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in (r.stderr + r.stdout)
    (exp / "README.md").write_text(open(os.path.join(HERE, "README.md")).read())
    assert _run(["--make-freeze", str(tmp_path / "ok2.json")], base=exp).returncode == 0
    fz = tmp_path / "ok2.json"
    # a valid freeze, but an earlier receipt for another output folder exists: refused before any target
    folder = tmp_path / "ovr"
    folder.mkdir()
    R.ensure_receipt(str(folder), str(folder / "other_out"), "a" * 64)
    env = dict(ENV, VF1_EXPERIMENT_DIR=str(folder))
    out_in = str(folder / "out")
    r = _run([out_in, "--roster", "all", "--freeze", str(fz)], env=env, base=exp)
    assert r.returncode != 0 and "receipt" in (r.stderr + r.stdout) and not os.path.exists(out_in)
    # the override cannot hide a second run: the output folder must lie inside it
    r = _run([out, "--roster", "all", "--freeze", str(fz)], env=env, base=exp)
    assert r.returncode != 0 and "outside it" in (r.stderr + r.stdout) and not os.path.exists(out)
    # and the receipts of the real experiment folder are still consulted when the override is set
    R2 = tmp_path / "ovr2"
    R2.mkdir()
    (exp / "RECEIPT_ALL_ROSTER.json").write_text(json.dumps(dict(outdir=str(tmp_path / "first_out"))))
    r = _run([str(R2 / "out"), "--roster", "all", "--freeze", str(fz)], env=dict(ENV, VF1_EXPERIMENT_DIR=str(R2)), base=exp)
    assert r.returncode != 0 and "receipt" in (r.stderr + r.stdout) and not (R2 / "out").exists()
    # no hash seed, targets outside the roster, --B or --targets with the full roster
    r = _run([out, "--roster", "dev"], env={k: v for k, v in ENV.items() if k != "PYTHONHASHSEED"}, base=exp)
    assert r.returncode != 0
    r = _run([out, "--roster", "dev", "--targets", "hline"], base=exp)
    assert r.returncode != 0 and "outside" in (r.stderr + r.stdout) and not os.path.exists(os.path.join(out, "targets"))
    r = _run([out_in, "--roster", "all", "--freeze", str(fz), "--B", "1"], env=env, base=exp)
    assert r.returncode != 0


def test_override_recorded_in_manifest_and_receipt(tmp_path):
    p = R.ensure_receipt(str(tmp_path), str(tmp_path / "o"), "b" * 64, str(tmp_path))
    assert json.load(open(p))["experiment_dir_override"] == str(tmp_path)
    ovr = tmp_path / "ovr"
    ovr.mkdir()
    r = _run([str(ovr / "dev"), "--roster", "dev", "--targets", "rot180", "--B", "0.2"], env=dict(ENV, VF1_EXPERIMENT_DIR=str(ovr)))
    assert r.returncode == 0, r.stderr
    assert json.load(open(ovr / "dev" / "MANIFEST.json"))["experiment_dir_override"] == str(ovr)


# ---------------------------------------------------------------- summary
def _rec(name, dev, v_acq, s_acq, **kw):
    """A hand-made target record: v_acq and s_acq are the PRIMARY endpoint (acquisition task exact) of V and S."""
    g = {"3": True, "6": True, "12": True}
    va = dict(fit=True, admitted=True, correct=v_acq, reused=v_acq, task_acq_exact=v_acq, stop="found", stop_class="fit", cpu_s=1.0,
              cpu_s_physical=1.0, cpu_to_first_fit=0.4, cpu_admission_s=0.1, reuse_cpu_s=0.02,
              admission=dict(none=True, same_kind=g, adm_generator=g, adm_pooled=g, adm_both=g, rule=True, cpu_preservation_s=0.05),
              library=dict(cpu_write_s=0.01, cpu_load_s=0.01, cpu_deployment_s=0.02))
    sa = dict(fit=True, stop="found", stop_class="fit", cpu_s=2.0, cpu_s_physical=2.0, task_acq_exact=s_acq, standin=dict(contains_standin=s_acq))
    other = dict(fit=False, admitted=False, correct=False, reused=False, task_acq_exact=False, stop="size_exhausted", stop_class="complete_negative", cpu_s=0.1)
    sel = dict(n_fits=2, fits=[], distinct_behaviours=2, first_fit=dict(admitted=True, correct=v_acq),
               random_seeds=[dict(seed=i, index=0, admitted=True, correct=v_acq) for i in range(V.N_SEEDS)])
    rcs = {k: dict(order=["V", "S"], reached=True, cpu_s=1.0) for k in ("rule", "v_then_s", "s_then_v")}
    rcs["random"] = [dict(seed=i, order=["V", "S"], reached=True, cpu_s=1.0) for i in range(V.N_SEEDS)]
    ctl = dict(no_retention=dict(cost_cpu_s=4.0, fit=True, exact_on_final=True, cpu_s=4.0),
               fixed_library_B=dict(cpu_s=10.0, fit=False, exact_on_final=False),
               conditional_comparison_fixed_library_10B=dict(cpu_s=30.0, exact_on_final=True) if v_acq else None,
               costs=dict(retained_parts=dict(acquisition_to_first_fit_cpu_s=0.4, admission_cpu_s=0.1, preservation_cpu_s=0.05,
                                              library_write_cpu_s=0.01, library_load_cpu_s=0.01, deployment_at_reuse_cpu_s=0.02)))
    prim = dict(acquisition_task=dict(V=v_acq, S=s_acq, V_cpu_counterfactual_s=0.4, V_cpu_physical_s=1.0, S_cpu_physical_s=2.0),
                reuse_task_secondary=dict(retained_V=v_acq, S_fresh=False, no_retention=True, V_admitted=True))
    d = dict(target=name, status="done", dev=dev, held_out_family=False, arms=dict(V=va, S=sa, H=dict(other), T=dict(other)), selection=sel,
             repair_choice=rcs, reuse_controls=ctl, cpu_s_total=5.0, consumers=dict(flags=[]), primary=prim, final_panel=dict(pooled_short=False))
    d.update(kw)
    return d


def test_sign_test_exact():
    assert SM.sign_test_two_sided(0, 0) == 1.0
    assert SM.sign_test_two_sided(5, 0) == pytest.approx(0.0625)
    assert SM.sign_test_two_sided(6, 0) == pytest.approx(0.03125)
    assert SM.sign_test_two_sided(3, 1) == pytest.approx(0.625)
    assert SM.sign_test_two_sided(1, 1) == 1.0 and SM.sign_test_two_sided(0, 8) == pytest.approx(2 / 256)


def test_summary_counts_add_up(tmp_path):
    out = tmp_path
    (out / "targets").mkdir()
    recs = []
    for i in range(6):                                        # 6 wins of V over S outside the development roster
        recs.append(_rec("w%d" % i, False, True, False))
    recs.append(_rec("l0", False, False, True))               # 1 loss
    recs.append(_rec("t0", False, True, True))                # tie, both
    recs.append(_rec("t1", False, False, False))              # tie, neither
    recs.append(_rec("d0", True, True, False))                # development target
    recs.append(dict(target="x0", status="excluded", reason="fewer than three consumers (1 eligible of 3 candidates)", dev=False, held_out_family=False))
    recs.append(dict(target="i0", status="incomplete", reason="boom", dev=False, held_out_family=False))
    for r in recs:
        json.dump(r, open(out / "targets" / (r["target"] + ".json"), "w"))
    json.dump(dict(roster="dev", targets=[r["target"] for r in recs] + ["pending"], B=1.0), open(out / "MANIFEST.json", "w"))
    s = SM.write_summary(str(out))
    assert "development study" in s["label"] and "budget mixture" in s["label"]
    assert s["n_listed"] == 13 and s["n_done"] == 10 and s["n_excluded_by_gate"] == 1 and s["n_incomplete_infrastructure"] == 1
    assert s["n_not_yet_run"] == 1 and s["n_done"] + s["n_excluded_by_gate"] + s["n_incomplete_infrastructure"] + s["n_not_yet_run"] == s["n_listed"]
    o = s["outside_development_roster"]
    assert o["n_targets"] == 9 and s["development_roster_development_only"]["n_targets"] == 1
    c = o["PRIMARY_acquisition_task_V_against_S"]
    assert (c["wins"], c["losses"], c["ties"]) == (6, 1, 2) and c["wins"] + c["losses"] + c["ties"] == o["n_targets"]
    assert (c["V_exact"], c["S_exact"]) == (7, 2) and c["p_two_sided_sign_test"] == pytest.approx(2 * 8 / 128) and c["decision_rule_met"] is False
    assert c["cpu_s"]["V_physical"] == 9.0 and c["cpu_s"]["V_counterfactual_to_first_fit"] == pytest.approx(3.6) and c["cpu_s"]["S_physical"] == 18.0
    v = o["arms"]["V"]
    assert (v["fit"], v["admitted"], v["correct"], v["reused"], v["task_acq_exact"]) == (9, 9, 7, 7, 7) and v["false_admissions"] == 2
    assert o["arms"]["S"]["contains_standin"] == 2 and "admitted" not in o["arms"]["S"]
    tab = o["admission_table_first_fit_of_V"]
    assert tab["rule"]["false_admissions"] == 2 and tab["adm_both@6"]["admitted"] == 9 and set(tab) >= {"none", "same_kind@3", "adm_generator@12", "adm_pooled@6", "adm_both@12"}
    assert "adm_both at n = 6" in s["0_the_rule"] or "adm_both" in s["0_the_rule"]
    assert o["selection_controls"]["first_fit_rule"]["admitted_and_correct"] == 7
    rs = o["secondary_reuse_task_declared"]
    assert rs["retained_V_exact"] == 7 and rs["no_retention_exact"] == 9 and rs["conditional_comparison_fixed_library_10B"]["n"] == 7
    be = o["reuse_costs_targets_where_V_admitted"]["w0"]
    assert be["retained_fixed_cost_cpu_s"] == pytest.approx(0.52) and be["break_even_reuses"] == 1      # ceil(0.52 / (4 - 0.02))
    assert "preservation_cpu_s" in be["retained_parts"] and s["development_only"] is True and "i0" in s["incomplete_infrastructure"]


# ---------------------------------------------------------------- one tiny episode, journal, resume
def test_tiny_episode_journal_and_resume(tmp_path):
    r = E.run_target("rot180", str(tmp_path), B=0.4)
    assert r["status"] == "done" and set(r["arms"]) == {"V", "S", "H", "T"} and "development study" in r["label"]
    assert r["failure"]["error_type"] == "NameError" and r["failure"]["missing_name"] == "rot180"
    assert r["failure"]["all_examples_fail"] and len(r["failure"]["required_outputs"]) == 3
    for k in ("selection", "repair_choice", "reuse_controls", "diagnosis", "decision", "consumers", "gate", "primary", "final_panel", "late_gate_flags"):
        assert k in r
    ev = [json.loads(x) for x in open(tmp_path / "journal" / "rot180.jsonl")]
    names = [e["event"] for e in ev]
    for e in ("start", "consumers", "gate", "observed_failure", "arm_V", "arm_S", "arm_T", "outcome_V", "diagnosis", "final_opened", "done"):
        assert e in names
    seals = [e["name"] for e in ev if e["event"] == "seal"]
    assert seals[:2] == ["setup_set", "acquisition_set"] and seals[-1] == "final_set" and all(len(e["sha256"]) == 64 for e in ev if e["event"] == "seal")
    assert names.index("final_opened") > names.index("arm_T") and r["arms"]["S"]["note"].startswith("S is scored at task level")
    assert r["arms"]["V"]["stop_class"] in ("allowance_used_up", "complete_negative", "fit", "size_limit_with_function_cap")
    again = E.run_target("rot180", str(tmp_path), B=0.4)
    assert again["cpu_s_total"] == r["cpu_s_total"]          # finished targets are skipped
