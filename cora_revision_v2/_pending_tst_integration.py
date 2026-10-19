"""Integrate the two-stage typed scene transformation family ("tst") into scene_reasoner and the runner
(apply only after the selection engineering run has finished)."""
ROOT = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026/"


def sub(s, old, new):
    assert s.count(old) == 1, old[:70]
    return s.replace(old, new)


p = ROOT + "cora_revision_v2/scene_reasoner.py"
s = open(p).read()
s = sub(s, '''    if h.get("family") == "select":
        from cora_revision_v2 import selection as SEL
        return SEL.predict(h, test_input)
    A = np.asarray(test_input)''', '''    if h.get("family") == "select":
        from cora_revision_v2 import selection as SEL
        return SEL.predict(h, test_input)
    if h.get("family") == "tst":
        from cora_revision_v2 import tst as T
        return T.predict(h, test_input)
    A = np.asarray(test_input)''')
s = sub(s, '''    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    if not h["policy"].startswith("TABLE:"):
        return set()''', '''    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    if not h.get("policy", "").startswith("TABLE:"):
        return set()''')
s = sub(s, '''    if not h["policy"].startswith("TABLE:"):
        return {}''', '''    if not h.get("policy", "").startswith("TABLE:"):
        return {}''')
s = sub(s, '''        m = _required_keys(h, held[0]) - set(h["table"] or {})''', '''        m = _required_keys(h, held[0]) - set(h.get("table") or {})''')
s = sub(s, '''    if "select" in families:
        from cora_revision_v2 import selection as SEL
        sh, nsel, complete = SEL.version_space(pairs, deadline=time.process_time() + select_cpu)
        hyps = hyps + sh
        if sel is not None:
            sel["n_selective"] = sel.get("n_selective", 0) + nsel
            sel["complete"] = sel.get("complete", True) and complete
    return hyps, npos''', '''    if "select" in families:
        from cora_revision_v2 import selection as SEL
        sh, nsel, complete = SEL.version_space(pairs, deadline=time.process_time() + select_cpu)
        hyps = hyps + sh
        if sel is not None:
            sel["n_selective"] = sel.get("n_selective", 0) + nsel
            sel["complete"] = sel.get("complete", True) and complete
    if "tst" in families:
        from cora_revision_v2 import tst as T
        th, info = T.version_space(pairs, families=tuple(f for f in families if f != "tst"), select_cpu=select_cpu)
        hyps = hyps + th
        if sel is not None:
            sel["n_tst"] = sel.get("n_tst", 0) + len(th)
            sel["tst_stage1_rules"] = info.get("stage1_rules", 0)
    return hyps, npos''')
s = sub(s, '''    if "select" in families:
        rec["n_selective"], rec["select_complete"] = sel.get("n_selective", 0), sel.get("complete", True)''',
        '''    if "select" in families:
        rec["n_selective"], rec["select_complete"] = sel.get("n_selective", 0), sel.get("complete", True)
    if "tst" in families:
        rec["n_tst"], rec["tst_stage1_rules"] = sel.get("n_tst", 0), sel.get("tst_stage1_rules", 0)''')
s = sub(s, '''                  if k in ("view", "expr", "policy", "guard", "family")}''',
        '''                  if k in ("view", "expr", "policy", "guard", "family")}
    if rec["top"].get("family") == "tst":
        t = sorted(hyps, key=lambda h: h["complexity"])[0]
        rec["top"]["stage1"] = {k: t["rule"].get(k) for k in ("view", "feature", "rules", "default")}
        rec["top"]["stage2"] = GG.pretty(t["stage2"]["expr"]) if t["stage2"] else None''')
open(p, "w").write(s)

p = ROOT + "cora_revision_v2/tst.py"
s = open(p).read()
s = sub(s, '''            hyps.append({"family": "tst", "rule": r, "stage2": None, "complexity": (4, _rank(r))})''',
        '''            hyps.append({"family": "tst", "view": r["view"], "rule": r, "stage2": None, "complexity": (4, _rank(r))})''')
s = sub(s, '''            hyps.append({"family": "tst", "rule": r, "stage2": h2,''', '''            hyps.append({"family": "tst", "view": r["view"], "rule": r, "stage2": h2,''')
open(p, "w").write(s)

p = ROOT + "cora_revision_v2/run_v2.py"
s = open(p).read()
s = sub(s, '''           "n_selective": rec.get("n_selective"), "select_complete": rec.get("select_complete"),''',
        '''           "n_selective": rec.get("n_selective"), "select_complete": rec.get("select_complete"),
           "n_tst": rec.get("n_tst"), "tst_stage1_rules": rec.get("tst_stage1_rules"),''')
s = sub(s, '''    ap.add_argument("--families", default="grow", help="comma-separated: grow[,select]")''',
        '''    ap.add_argument("--families", default="grow", help="comma-separated: grow[,select][,tst]")''')
open(p, "w").write(s)
print("patched tst integration")
