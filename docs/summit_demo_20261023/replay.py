"""OFFLINE REPLAY of a recorded CORA-FHR development run (no Athe, no native engine, no network).

  python replay.py            # text, step by step
  python replay.py --png      # also writes step images to ./frames/ (needs matplotlib)

Everything shown comes from the bundled records in ./data/ (hash-checked against MANIFEST.json):
- the task's demonstrations and test input;
- frozen CORA's failure;
- the authentic failure evidence (native's memorized growth);
- the constructed operator;
- the adaptive-LOO fold records;
- the committed prediction;
- the evaluator's verdict;
- the ablation and the controls.

The operator is re-executed here with ggrow_standalone.py, a copy of cora_fhr/ggrow.py, to show what it does on
the real grids. The native reasoner is NOT re-run offline. Its recorded outputs are replayed, and labelled as
such. This replays a logged experiment; it is not a live execution.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ggrow_standalone as GG                                          # noqa: E402

GLYPH = ".123456789"


def show(grid, title):
    print(f"  {title}")
    for row in grid:
        print("    " + " ".join(GLYPH[v] for v in row))


def main():
    man = json.load(open(os.path.join(HERE, "MANIFEST.json")))
    for f, sha in man["files"].items():
        got = hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
        if got != sha:
            sys.exit(f"{f}: sha256 mismatch ({got[:12]} != {sha[:12]}); not replaying an unrecorded file")
    w = json.load(open(os.path.join(HERE, "data", "witness.json")))
    t = json.load(open(os.path.join(HERE, "data", "task.json")))
    png = "--png" in sys.argv
    print(f"CORA-FHR offline replay | task {w['key']} | {w['tier']} | recorded run, provenance {w['provenance']['git_head'][:10]}")
    print("\n1. THE TASK: three demonstrations and one test input")
    for i, (a, b) in enumerate(t["train"]):
        show(a, f"demonstration {i} input");  show(b, f"demonstration {i} output")
    show(t["test"][0][0], "test input")
    print("\n2. THE FAILURE (frozen CORA, recorded): native fits the demonstrations by memorizing constant growth;")
    print(f"   its own leave-one-out rejects it, so frozen CORA certifies nothing. {w['logged']['A']}")
    print("\n3. THE DIAGNOSIS (recorded): native's own failure trace, the objects it could only memorize")
    print(f"   (detect_grow fell back to the constant 'pattern'): {w['failure_evidence']}")
    print("\n4. THE CONSTRUCTION (recorded): the canonical-first G-grow expression explaining every memorized instance")
    op = w["operator"]
    print(f"   operator {op['pretty']}  canonical {op['expr']}  name {op['name']}")
    print(f"   novelty: {op['novelty']} | on {w['perturbation_novelty']['objects']} perturbed geometries, native explains "
          f"{w['perturbation_novelty']['native_explains']}, best cora_reach setting matches {w['perturbation_novelty']['best_reach_setting']['matches']}")
    expr = GG.from_str(op["expr"])
    print("\n5. THE OPERATOR, re-executed here on the test input's objects (ggrow_standalone)")
    for o in w["test_objects"]:
        cc = {tuple(c): v for c, v in o}
        added = sorted(GG.evaluate(expr, GG.Ctx(cc, t["test"][0][0])))
        print(f"   object {sorted(cc)} -> adds {added}")
    print("\n6. THE CHECK (recorded): adaptive leave-one-out; each fold rebuilt the operator from its own two demonstrations")
    for f in w["folds"]:
        print(f"   fold {f['fold']}: {f['class']} | rebuilt {f['selected']} | same as full {f['same_as_full']} | "
              f"native accepted {f['accepted']} | uses it {f['uses']} | held-out exact {f['heldout_exact']}")
    print(f"   demonstration replay inside the installed overlay: {w['replay']['replays_every_demonstration']}; "
          f"engine state restored: {w['replay']['restored']}")
    print("\n7. THE RESULT (recorded): CORA commits its prediction, then the independent evaluator scores it")
    show(w["committed"][0], "committed prediction")
    print(f"   evaluator: correct = {w['evaluator']['E']}")
    print("\n8. THE ABLATION AND CONTROLS (recorded)")
    print(f"   without the extension (frozen CORA): certified = {w['ablation']['without_extension_certified']}")
    print(f"   failure-blind construction C: {w['controls']['C']} | correspondence-matched C': {w['controls'].get('C2')}")
    print("   HONEST NOTE: the failure-blind control reached the same certified answer, so this witness shows")
    print("   capability construction, not yet that the failure record is what made it possible.")
    if png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B",
                               "#7FDBFF", "#870C25"])
        os.makedirs(os.path.join(HERE, "frames"), exist_ok=True)
        panels = [(a, f"demo {i} in") for i, (a, _b) in enumerate(t["train"])] + [(b, f"demo {i} out") for i, (_a, b) in enumerate(t["train"])]
        panels += [(t["test"][0][0], "test input"), (w["committed"][0], "CORA's committed prediction")]
        for k, (g, name) in enumerate(panels):
            fig, ax = plt.subplots(figsize=(3, 3), dpi=120)
            ax.imshow(g, cmap=cmap, vmin=0, vmax=9)
            ax.set_title(name, fontsize=10)
            ax.set_xticks([]); ax.set_yticks([])
            fig.savefig(os.path.join(HERE, "frames", f"{k:02d}.png"), bbox_inches="tight")
            plt.close(fig)
        print("\n   frames written to ./frames/")


if __name__ == "__main__":
    main()
